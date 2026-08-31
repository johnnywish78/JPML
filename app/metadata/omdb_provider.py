from __future__ import annotations

import os
from typing import Any

import requests

from .provider import MetadataProvider, ProviderMetadata


class OMDbMetadataProvider(MetadataProvider):
    """Metadata provider backed by the OMDb API using IMDb IDs."""

    name = "omdb"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://www.omdbapi.com/",
        timeout: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = (
            api_key
            if api_key is not None
            else os.environ.get("OMDB_API_KEY", "")
        ).strip()

        self.base_url = base_url
        self.timeout = timeout
        self.session = session or requests.Session()

    def fetch_metadata(
        self,
        *,
        entity_type: str,
        external_id: str,
    ) -> ProviderMetadata | None:
        if entity_type != "movie":
            return None

        if not self.api_key:
            raise ValueError(
                "OMDB_API_KEY is required for OMDb metadata lookup"
            )

        imdb_id = external_id.strip()
        if not imdb_id.startswith("tt"):
            raise ValueError(
                f"OMDb provider requires an IMDb ID, got: {external_id!r}"
            )

        response = self.session.get(
            self.base_url,
            params={
                "apikey": self.api_key,
                "i": imdb_id,
                "plot": "full",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()

        payload: dict[str, Any] = response.json()

        if str(payload.get("Response", "")).lower() != "true":
            return None

        title = str(payload.get("Title") or "").strip()
        if not title:
            return None

        year = self._parse_year(payload.get("Year"))

        genres = tuple(
            genre.strip()
            for genre in str(payload.get("Genre") or "").split(",")
            if genre.strip()
        )

        overview = str(payload.get("Plot") or "").strip() or None

        return ProviderMetadata(
            title=title,
            year=year,
            overview=overview,
            genres=genres,
            external_id=imdb_id,
            metadata_version="omdb-v1",
        )

    @staticmethod
    def _parse_year(value: Any) -> int | None:
        if value is None:
            return None

        text = str(value).strip()

        # OMDb may return ranges such as "2008–2013".
        first = text[:4]

        if first.isdigit() and len(first) == 4:
            return int(first)

        return None
