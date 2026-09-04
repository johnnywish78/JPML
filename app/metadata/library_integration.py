from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.domain.media import MediaType

from .identifier import IdentificationResult
from .service import MetadataResolution, MetadataService

if TYPE_CHECKING:
    from app.services.music import MusicService

logger = logging.getLogger(__name__)


def _normalize_entity_type_for_provider(media_type) -> str:
    media_type_str = (
        media_type.value
        if hasattr(media_type, "value")
        else str(media_type)
    )
    if media_type_str in ("tv_show", "tv", "episode"):
        return "tv"
    return media_type_str


@dataclass(frozen=True)
class LibraryMetadataResult:
    resolution: MetadataResolution
    metadata_fetched: bool
    discovery_provider: str | None = None
    discovery_external_id: str | None = None


class LibraryMetadataIntegration:
    """Bridge between library identification and metadata persistence.

    The integration performs discovery via the metadata service's primary
    provider (typically TMDB) when the identification result does not
    already carry a provider / external_id.  This allows local filename
    identification to be enriched with remote metadata automatically.
    """

    def __init__(
        self,
        metadata_service: MetadataService,
        music_service: "MusicService | None" = None,
        artwork_dir: Path | None = None,
        http_session: object | None = None,
    ) -> None:
        self.metadata_service = metadata_service
        self.music_service = music_service
        self._artwork_dir = artwork_dir
        self._http_session = http_session

    def process_identification(
        self,
        result: IdentificationResult,
    ) -> LibraryMetadataResult:
        if result.media_type == MediaType.MUSIC:
            return self._process_music(result)

        entity_type = _normalize_entity_type_for_provider(result.media_type)

        # If no provider/external_id yet, attempt discovery
        if not result.provider or not result.external_id:
            discovered = self._discover(result, entity_type)
            if discovered is not None:
                result.provider = discovered["provider"]
                result.external_id = discovered["external_id"]

        resolution = self.metadata_service.resolve_identification(result)

        fetched = False

        if result.external_id:
            try:
                fetched = self.metadata_service.fetch_and_save_metadata(
                    entity_type=entity_type,
                    entity_id=resolution.entity_id,
                    external_id=result.external_id,
                    provider_name=result.provider,
                    artwork_dir=self._artwork_dir,
                    http_session=self._http_session,
                )
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Metadata fetch failed for %s %r: continuing with local entity",
                    entity_type,
                    result.external_id,
                    exc_info=True,
                )

        return LibraryMetadataResult(
            resolution=resolution,
            metadata_fetched=fetched,
            discovery_provider=result.provider,
            discovery_external_id=result.external_id,
        )

    def _discover(
        self,
        result: IdentificationResult,
        entity_type: str,
    ) -> dict[str, str] | None:
        """Attempt provider discovery to enrich the identification result.

        Returns a dict with ``provider`` and ``external_id`` keys when
        discovery succeeds, otherwise ``None``.
        """
        # Try primary provider first, then fall back to registry
        provider = self.metadata_service.provider
        if provider is None and self.metadata_service.registry:
            names = self.metadata_service.registry.names()
            if names:
                provider = self.metadata_service.registry.get(names[0])

        if provider is None:
            return None
        if not hasattr(provider, "search"):
            return None

        try:
            hits = provider.search(
                entity_type=entity_type,
                query=result.title,
                year=result.year,
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Discovery search failed for %r", result.title, exc_info=True
            )
            return None

        if not hits:
            return None

        # Pick the best match: prefer exact year match, then highest vote
        if result.year is not None:
            year_matches = [h for h in hits if h.get("year") == result.year]
            if year_matches:
                best = max(year_matches, key=lambda h: float(h.get("vote_average") or 0))
            else:
                best = max(hits, key=lambda h: float(h.get("vote_average") or 0))
        else:
            best = max(hits, key=lambda h: float(h.get("vote_average") or 0))
        if best is None:
            return None

        return {
            "provider": provider.name,
            "external_id": str(best["id"]),
        }

    def _process_music(self, result: IdentificationResult) -> LibraryMetadataResult:
        if self.music_service is None:
            raise RuntimeError(
                "MusicService is required to process music identifications"
            )
        resolution = self.music_service.resolve_identification(result)
        return LibraryMetadataResult(
            resolution=MetadataResolution(
                entity_type="track",
                entity_id=resolution.track_id,
                created=resolution.created,
            ),
            metadata_fetched=False,
        )
