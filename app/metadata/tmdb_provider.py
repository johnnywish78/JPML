"""TMDB metadata provider with discovery, metadata, artwork, and people support.

Uses the official TMDB v3 API.  The provider supports:

- Search/discovery by title (movie and TV)
- Metadata retrieval by TMDB ID
- External ID resolution (IMDb ID from TMDB)
- Artwork path extraction (poster, backdrop)
- Credits / people extraction

The provider is configured via the ``TmdbConfig`` dataclass (or the
``TMDB_API_KEY`` environment variable).  When no API key is available
the provider raises ``ValueError`` on discovery / fetch operations so
the caller can handle the absence gracefully.
"""
from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urljoin

import requests

from app.config import TmdbConfig

from .provider import MetadataProvider, ProviderMetadata

logger = logging.getLogger(__name__)

TMDB_API_BASE = "https://api.themoviedb.org/3/"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
TMDB_IMAGE_BACKDROP = "https://image.tmdb.org/t/p/w1280"


class TmdbMetadataProvider(MetadataProvider):
    """Metadata provider backed by The Movie Database (TMDB) API."""

    name = "tmdb"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = TMDB_API_BASE,
        image_base: str = TMDB_IMAGE_BASE,
        backdrop_image_base: str = TMDB_IMAGE_BACKDROP,
        timeout: float = 10.0,
        session: requests.Session | None = None,
        config: TmdbConfig | None = None,
    ) -> None:
        if config is not None:
            self.api_key = config.api_key.strip()
            self.base_url = config.base_url
            self.image_base = config.image_base
            self.backdrop_image_base = config.backdrop_image_base
            self.timeout = config.timeout
        else:
            self.api_key = (
                api_key
                if api_key is not None
                else os.environ.get("TMDB_API_KEY", "")
            ).strip()
            self.base_url = base_url
            self.image_base = image_base
            self.backdrop_image_base = backdrop_image_base
            self.timeout = timeout

        self.session = session or requests.Session()

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #

    def search(
        self,
        *,
        entity_type: str,
        query: str,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search TMDB for entities matching *query*.

        Returns a list of result dicts each containing at minimum::

            {
                "id": <tmdb_id>,
                "title": <display_title>,
                "media_type": "movie" | "tv",
                "year": <int|None>,
                "poster_path": <str|None>,
                "backdrop_path": <str|None>,
            }

        Results are ranked by relevance / vote average.  When *year* is
        provided, results whose year matches exactly are promoted to the
        front of the list.
        """
        if entity_type not in ("movie", "tv"):
            return []

        if not self.api_key:
            raise ValueError("TMDB_API_KEY is required for TMDB discovery")

        params: dict[str, Any] = {
            "api_key": self.api_key,
            "query": query,
            "include_adult": "false",
        }
        if year is not None:
            param_name = "primary_release_year" if entity_type == "movie" else "first_air_date_year"
            params[param_name] = str(year)

        try:
            resp = self.session.get(
                urljoin(self.base_url, f"search/{entity_type}"),
                params=params,
                timeout=self.timeout,
            )
            resp.raise_for_status()
        except requests.RequestException:
            logger.warning("TMDB search failed for %r", query, exc_info=True)
            return []

        try:
            payload: dict[str, Any] = resp.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            logger.warning("TMDB returned malformed JSON for %r", query)
            return []

        if not isinstance(payload, dict):
            return []

        results = payload.get("results") or []
        if not isinstance(results, list):
            return []

        hits: list[dict[str, Any]] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            tmdb_id = item.get("id")
            if tmdb_id is None:
                continue

            title = str(item.get("title") or item.get("name") or "").strip()
            if not title:
                continue

            # Determine year
            year_val: int | None = None
            date_str = (
                item.get("release_date")
                or item.get("first_air_date")
                or ""
            )
            if isinstance(date_str, str) and len(date_str) >= 4:
                candidate = date_str[:4]
                if candidate.isdigit():
                    year_val = int(candidate)

            # Media type from search results is sometimes explicit
            media_type = str(item.get("media_type", entity_type)).lower()
            if media_type not in ("movie", "tv"):
                media_type = entity_type

            hits.append({
                "id": int(tmdb_id),
                "title": title,
                "media_type": media_type,
                "year": year_val,
                "poster_path": item.get("poster_path"),
                "backdrop_path": item.get("backdrop_path"),
                "vote_average": float(item.get("vote_average") or 0.0),
                "overview": item.get("overview"),
            })

        # Promote exact-year matches to the front
        if year is not None:
            matched: list[dict[str, Any]] = []
            unmatched: list[dict[str, Any]] = []
            for hit in hits:
                if hit["year"] == year:
                    matched.append(hit)
                else:
                    unmatched.append(hit)
            # Sort matched by vote_average descending, then unmatched too
            matched.sort(key=lambda h: -h["vote_average"])
            unmatched.sort(key=lambda h: -h["vote_average"])
            hits = matched + unmatched
        else:
            hits.sort(key=lambda h: -h["vote_average"])

        return hits

    # ------------------------------------------------------------------ #
    # Metadata fetching
    # ------------------------------------------------------------------ #

    def fetch_metadata(
        self,
        *,
        entity_type: str,
        external_id: str,
    ) -> ProviderMetadata | None:
        if entity_type not in ("movie", "tv"):
            return None

        if not self.api_key:
            raise ValueError("TMDB_API_KEY is required for TMDB metadata lookup")

        try:
            details_resp = self.session.get(
                urljoin(self.base_url, f"{entity_type}/{external_id}"),
                params={"api_key": self.api_key},
                timeout=self.timeout,
            )
            details_resp.raise_for_status()
        except requests.RequestException:
            logger.warning("TMDB details request failed for %s/%s", entity_type, external_id, exc_info=True)
            raise

        try:
            details: dict[str, Any] = details_resp.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            logger.warning("TMDB returned malformed JSON for %s/%s", entity_type, external_id)
            return None

        if not isinstance(details, dict):
            return None

        # Build normalized metadata dict
        metadata: dict[str, Any] = {
            "title": details.get("title") or details.get("name"),
            "year": details.get("release_date") or details.get("first_air_date"),
            "overview": details.get("overview"),
            "genres": [g["name"] for g in (details.get("genres") or []) if isinstance(g, dict)],
            "tmdb_id": details.get("id"),
            "poster_path": details.get("poster_path"),
            "backdrop_path": details.get("backdrop_path"),
            "first_air_date": details.get("first_air_date"),
            "number_of_seasons": details.get("number_of_seasons"),
            "number_of_episodes": details.get("number_of_episodes"),
            "metadata_version": "tmdb-v3",
        }

        # External IDs (IMDb)
        try:
            ext_resp = self.session.get(
                urljoin(self.base_url, f"{entity_type}/{external_id}/external_ids"),
                params={"api_key": self.api_key},
                timeout=self.timeout,
            )
            ext_resp.raise_for_status()
            ext_data: dict[str, Any] = ext_resp.json()
            imdb_id = ext_data.get("imdb_id")
            if imdb_id:
                metadata["imdb_id"] = str(imdb_id)
            # Also store tmdb_id as external_id for dedup
            metadata["external_id"] = str(external_id)
        except requests.RequestException:
            logger.warning("TMDB external_ids request failed for %s/%s", entity_type, external_id, exc_info=True)
            metadata["external_id"] = str(external_id)

        # Credits
        try:
            credits_resp = self.session.get(
                urljoin(self.base_url, f"{entity_type}/{external_id}/credits"),
                params={"api_key": self.api_key},
                timeout=self.timeout,
            )
            credits_resp.raise_for_status()
            credits_data: dict[str, Any] = credits_resp.json()
            metadata["credits"] = credits_data
        except requests.RequestException:
            logger.warning("TMDB credits request failed for %s/%s", entity_type, external_id, exc_info=True)
            metadata["credits"] = {}

        return self.normalize_metadata(metadata)

    # ------------------------------------------------------------------ #
    # Artwork URL helpers
    # ------------------------------------------------------------------ #

    def poster_url(self, poster_path: str | None) -> str | None:
        if not poster_path:
            return None
        return f"{self.image_base}{poster_path}"

    def backdrop_url(self, backdrop_path: str | None) -> str | None:
        if not backdrop_path:
            return None
        return f"{self.backdrop_image_base}{backdrop_path}"
