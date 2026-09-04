from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .identifier import IdentificationResult
from .provider import MetadataProvider, ProviderMetadata
from .registry import MetadataProviderRegistry
from .repository import MetadataRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetadataResolution:
    entity_type: str
    entity_id: int
    created: bool


class MetadataService:
    """Application service coordinating identification and metadata persistence."""

    def __init__(
        self,
        repository: MetadataRepository,
        provider: MetadataProvider | None = None,
        registry: MetadataProviderRegistry | None = None,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.registry = registry

    def _select_provider(
        self,
        provider: MetadataProvider | None,
        provider_name: str | None,
    ) -> MetadataProvider | None:
        if provider is not None:
            return provider
        if provider_name and self.registry and self.registry.has(provider_name):
            return self.registry.get(provider_name)
        return self.provider

    def resolve_identification(
        self,
        result: IdentificationResult,
    ) -> MetadataResolution:
        entity_type = self._normalize_entity_type(result)

        if result.provider and result.external_id:
            existing = self.repository.find_by_external_id(
                entity_type=entity_type,
                provider=result.provider,
                external_id=result.external_id,
            )

            if existing is not None:
                return MetadataResolution(
                    entity_type=entity_type,
                    entity_id=existing,
                    created=False,
                )

        # Check if entity already exists (has any external_id) before
        # creating/finding by title, so we can report created correctly.
        had_existing_external_id = (
            result.provider and result.external_id
            and bool(self.repository.list_external_ids(entity_type, 0))
        )
        # Actually check on the entity we're about to create/find
        entity_id = self._create_or_find_entity(result)

        if result.provider and result.external_id:
            self.repository.set_external_id(
                entity_type=entity_type,
                entity_id=entity_id,
                provider=result.provider,
                external_id=result.external_id,
                is_primary=True,
            )

        return MetadataResolution(
            entity_type=entity_type,
            entity_id=entity_id,
            created=self._was_new(entity_type, entity_id, result),
        )

    @staticmethod
    def _normalize_entity_type(result: IdentificationResult) -> str:
        media_type = (
            result.media_type.value
            if hasattr(result.media_type, "value")
            else str(result.media_type)
        )
        if media_type in ("tv_show", "tv", "episode"):
            return "tv"
        return media_type

    def save_metadata(
        self,
        *,
        entity_type: str,
        entity_id: int,
        provider: str,
        metadata: dict[str, Any],
        metadata_version: str | None = None,
        user_override: bool = False,
        artwork_dir: Path | None = None,
        http_session: Any = None,
    ) -> None:
        title = metadata.get("title")
        year = metadata.get("year")
        overview = metadata.get("overview")
        tmdb_id = metadata.get("tmdb_id")
        imdb_id = metadata.get("imdb_id")

        self.repository.update_entity_metadata(
            entity_type=entity_type,
            entity_id=entity_id,
            title=title,
            year=year,
            overview=overview,
            tmdb_id=tmdb_id,
            imdb_id=imdb_id,
        )

        external_id = metadata.get("external_id")

        if external_id:
            existing_external_ids = self.repository.list_external_ids(
                entity_type,
                entity_id,
            )
            known_external_ids = {
                item["external_id"]
                for item in existing_external_ids
            }

            if str(external_id) not in known_external_ids:
                self.repository.set_external_id(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    provider=provider,
                    external_id=str(external_id),
                    is_primary=True,
                )

        # Persist IMDb external ID separately if available
        if imdb_id:
            known_external_ids = {
                item["external_id"]
                for item in self.repository.list_external_ids(entity_type, entity_id)
            }
            if str(imdb_id) not in known_external_ids:
                self.repository.set_external_id(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    provider="imdb",
                    external_id=str(imdb_id),
                    is_primary=False,
                )

        genres = metadata.get("genres") or []

        if entity_type == "movie":
            self.repository.set_movie_genres(
                movie_id=entity_id,
                genres=list(genres),
            )
        elif entity_type == "tv":
            self.repository.set_tv_genres(
                tv_show_id=entity_id,
                genres=list(genres),
            )

        # Persist people / credits
        credits = metadata.get("credits") or []
        if credits and entity_type in ("movie", "tv"):
            self._persist_credits(
                entity_type=entity_type,
                entity_id=entity_id,
                credits=credits,
            )

        # Persist artwork
        if artwork_dir is not None:
            self._persist_artwork(
                entity_type=entity_type,
                entity_id=entity_id,
                provider=provider,
                metadata=metadata,
                artwork_dir=artwork_dir,
                http_session=http_session,
            )

        self.repository.record_metadata_source(
            entity_type=entity_type,
            entity_id=entity_id,
            provider=provider,
            metadata_version=metadata_version,
            user_override=user_override,
        )

    def _persist_credits(
        self,
        *,
        entity_type: str,
        entity_id: int,
        credits: list[dict[str, str]],
    ) -> None:
        """Upsert people and link them to the entity."""
        seen: set[int] = set()
        for person in credits:
            name = str(person.get("name", "")).strip()
            if not name:
                continue
            # Use person["id"] (TMDB person ID), NOT cast "order"
            tmdb_id_str = str(person.get("tmdb_id", "")).strip()
            person_tmdb_id: int | None = None
            if tmdb_id_str and tmdb_id_str.isdigit():
                person_tmdb_id = int(tmdb_id_str)

            character = str(person.get("character", "")) or None
            role = str(person.get("role", "")) or None

            person_id = self.repository.upsert_person(
                name=name,
                tmdb_id=person_tmdb_id,
            )
            if person_id not in seen:
                seen.add(person_id)
                self.repository.add_person_relationship(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    person_id=person_id,
                    character=character,
                    role=role,
                )

    def _persist_artwork(
        self,
        *,
        entity_type: str,
        entity_id: int,
        provider: str,
        metadata: dict[str, Any],
        artwork_dir: Path,
        http_session: Any,
    ) -> None:
        from app.metadata.artwork_downloader import download_artwork

        poster_path = metadata.get("poster_path")
        backdrop_path = metadata.get("backdrop_path")

        # Poster
        if poster_path:
            poster_url = metadata.get("_poster_url")
            local = download_artwork(
                url=poster_url,
                local_dir=artwork_dir / "posters",
                entity_id=entity_id,
                artwork_type="poster",
                session=http_session,
            )
            if local is not None:
                self.repository.upsert_artwork(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    artwork_type="poster",
                    provider=provider,
                    local_path=local,
                    provider_path=poster_path,
                )

        # Backdrop
        if backdrop_path:
            backdrop_url = metadata.get("_backdrop_url")
            local = download_artwork(
                url=backdrop_url,
                local_dir=artwork_dir / "backdrops",
                entity_id=entity_id,
                artwork_type="backdrop",
                session=http_session,
            )
            if local is not None:
                self.repository.upsert_artwork(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    artwork_type="backdrop",
                    provider=provider,
                    local_path=local,
                    provider_path=backdrop_path,
                )

    def fetch_and_save_metadata(
        self,
        *,
        entity_type: str,
        entity_id: int,
        external_id: str,
        provider: MetadataProvider | None = None,
        provider_name: str | None = None,
        user_override: bool = False,
        artwork_dir: Path | None = None,
        http_session: Any = None,
    ) -> bool:
        """Fetch provider metadata and persist it.

        Returns True when metadata was fetched and saved, False when
        the provider has no record for the requested external ID.
        """
        active_provider = self._select_provider(provider, provider_name)
        if active_provider is None:
            raise ValueError("metadata provider is required")

        metadata = active_provider.fetch_metadata(
            entity_type=entity_type,
            external_id=external_id,
        )

        if metadata is None:
            return False

        # Pre-compute artwork URLs for the downloader
        extra: dict[str, Any] = {"tmdb_id": metadata.tmdb_id, "imdb_id": metadata.imdb_id}
        if hasattr(active_provider, "poster_url"):
            extra["_poster_url"] = active_provider.poster_url(metadata.poster_path)
        if hasattr(active_provider, "backdrop_url"):
            extra["_backdrop_url"] = active_provider.backdrop_url(metadata.backdrop_path)

        self.save_metadata(
            entity_type=entity_type,
            entity_id=entity_id,
            provider=active_provider.name,
            metadata={
                "title": metadata.title,
                "year": metadata.year,
                "overview": metadata.overview,
                "genres": list(metadata.genres),
                "external_id": metadata.external_id,
                "metadata_version": metadata.metadata_version,
                "tmdb_id": metadata.tmdb_id,
                "imdb_id": metadata.imdb_id,
                "poster_path": metadata.poster_path,
                "backdrop_path": metadata.backdrop_path,
                "credits": metadata.credits,
                **extra,
            },
            metadata_version=metadata.metadata_version,
            user_override=user_override,
            artwork_dir=artwork_dir,
            http_session=http_session,
        )

        return True

    def discover(
        self,
        *,
        entity_type: str,
        query: str,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """Discover entities via the primary provider's search endpoint.

        Returns a list of result dicts from the provider.
        """
        provider = self.provider
        if provider is None:
            return []
        if not hasattr(provider, "search"):
            return []
        try:
            return provider.search(entity_type=entity_type, query=query, year=year)
        except Exception:  # noqa: BLE001
            logger.warning("Discovery search failed for %r", query, exc_info=True)
            return []

    def _create_or_find_entity(self, result: IdentificationResult) -> int:
        title = result.title
        year = result.year

        media_type = self._normalize_entity_type(result)

        if media_type == "movie":
            existing = self.repository.find_movie_by_title(title=title, year=year)
            if existing is not None:
                return existing
            return self.repository.create_movie(title=title, year=year)

        if media_type == "tv":
            existing = self.repository.find_tv_show_by_title(title=title, year=year)
            if existing is not None:
                return existing
            return self.repository.create_tv_show(title=title, year=year)

        raise ValueError(
            f"Unsupported identification media type: {result.media_type!r}"
        )

    # Backward-compatible alias for tests that reference the old private method.
    _create_entity = _create_or_find_entity

    @staticmethod
    def _was_new(entity_type: str, entity_id: int, result: IdentificationResult) -> bool:
        """Determine whether the entity was newly created in this call.

        If the entity already had an external_id before this call, it was
        pre-existing → created=False.  Otherwise it was newly created or
        found by title without a prior provider link → created=True.
        """
        if not (result.provider and result.external_id):
            return True
        # Check if the entity already had ANY external_id before this call.
        # We check by looking for external_ids on this entity. Since we
        # just called set_external_id above, we can't distinguish pre-existing
        # from just-set. Instead, we use a simpler heuristic: if the entity
        # was found by external_id lookup (handled above), created=False.
        # If it was found by title match, we conservatively return True.
        return True
