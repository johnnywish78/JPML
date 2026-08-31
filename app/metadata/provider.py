from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProviderMetadata:
    """Normalized metadata returned by an external metadata provider."""

    title: str
    year: int | None = None
    overview: str | None = None
    genres: tuple[str, ...] = ()
    external_id: str | None = None
    metadata_version: str | None = None


class MetadataProvider(ABC):
    """Provider interface used by MetadataService."""

    name: str

    @abstractmethod
    def fetch_metadata(
        self,
        *,
        entity_type: str,
        external_id: str,
    ) -> ProviderMetadata | None:
        """Fetch normalized metadata for an entity."""

    def normalize_metadata(
        self,
        metadata: dict[str, Any],
    ) -> ProviderMetadata:
        title = str(metadata.get("title") or "").strip()
        if not title:
            raise ValueError("metadata title must not be empty")

        raw_genres = metadata.get("genres") or ()
        genres = tuple(
            str(genre).strip()
            for genre in raw_genres
            if str(genre).strip()
        )

        year = metadata.get("year")
        if year is not None:
            year = int(year)

        external_id = metadata.get("external_id")
        if external_id is not None:
            external_id = str(external_id)

        metadata_version = metadata.get("metadata_version")
        if metadata_version is not None:
            metadata_version = str(metadata_version)

        overview = metadata.get("overview")
        if overview is not None:
            overview = str(overview)

        return ProviderMetadata(
            title=title,
            year=year,
            overview=overview,
            genres=genres,
            external_id=external_id,
            metadata_version=metadata_version,
        )


class StaticMetadataProvider(MetadataProvider):
    """Small deterministic provider useful for tests and local integration."""

    name = "static"

    def __init__(self, records: dict[str, dict[str, Any]]) -> None:
        self.records = records

    def fetch_metadata(
        self,
        *,
        entity_type: str,
        external_id: str,
    ) -> ProviderMetadata | None:
        record = self.records.get(f"{entity_type}:{external_id}")
        if record is None:
            return None

        return self.normalize_metadata(record)
