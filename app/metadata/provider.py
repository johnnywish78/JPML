from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
    # TMDB-specific fields
    tmdb_id: int | None = None
    imdb_id: str | None = None
    poster_path: str | None = None
    backdrop_path: str | None = None
    # Credits / people (list of dicts with 'name', 'character', 'role', 'order')
    credits: list[dict[str, str]] = field(default_factory=list)
    # TV-show specific
    first_air_date: str | None = None
    number_of_seasons: int | None = None
    number_of_episodes: int | None = None


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

    def search(
        self,
        *,
        entity_type: str,
        query: str,
        year: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search for entities matching *query*. Returns a list of dicts
        with at minimum ``id``, ``title`` (or ``name``), ``year`` (or
        ``first_air_date``), and ``media_type`` keys. The default
        implementation returns an empty list (provider does not support
        discovery)."""
        return []

    def normalize_metadata(
        self,
        metadata: dict[str, Any],
    ) -> ProviderMetadata:
        title = str(metadata.get("title") or metadata.get("name") or "").strip()
        if not title:
            raise ValueError("metadata title must not be empty")

        raw_genres = metadata.get("genres") or ()
        genres = tuple(
            str(genre).strip()
            for genre in raw_genres
            if str(genre).strip()
        )

        year = metadata.get("year")
        if year is None:
            year = metadata.get("release_date", "")[:4]
            if year and year.isdigit():
                year = int(year)
            else:
                # Try first_air_date for TV shows
                year = metadata.get("first_air_date", "")[:4]
                if year and year.isdigit():
                    year = int(year)
                else:
                    year = None
        else:
            year_text = str(year)[:4]
            if year_text.isdigit():
                year = int(year_text)
            else:
                year = None

        external_id = metadata.get("external_id")
        if external_id is not None:
            external_id = str(external_id)

        tmdb_id = metadata.get("tmdb_id")
        if tmdb_id is None:
            tmdb_id = metadata.get("id")
        if tmdb_id is not None:
            tmdb_id = int(tmdb_id)

        imdb_id = metadata.get("imdb_id")
        if imdb_id is not None:
            imdb_id = str(imdb_id)

        poster_path = metadata.get("poster_path")
        if poster_path is not None:
            poster_path = str(poster_path)

        backdrop_path = metadata.get("backdrop_path")
        if backdrop_path is not None:
            backdrop_path = str(backdrop_path)

        credits_raw = metadata.get("credits") or []
        credits: list[dict[str, str]] = []
        if isinstance(credits_raw, dict):
            for person in credits_raw.get("cast", []) + credits_raw.get("crew", []):
                person_id = person.get("id")
                credits.append({
                    "name": str(person.get("name", "")),
                    "tmdb_id": str(person_id) if person_id is not None else "",
                    "character": str(person.get("character", "")),
                    "role": str(person.get("job", person.get("department", ""))),
                    "order": str(person.get("order", "")),
                })
        elif isinstance(credits_raw, list):
            for person in credits_raw:
                if isinstance(person, dict):
                    person_id = person.get("id")
                    credits.append({
                        "name": str(person.get("name", "")),
                        "tmdb_id": str(person_id) if person_id is not None else "",
                        "character": str(person.get("character", "")),
                        "role": str(person.get("job", person.get("department", ""))),
                        "order": str(person.get("order", "")),
                    })

        metadata_version = metadata.get("metadata_version")
        if metadata_version is not None:
            metadata_version = str(metadata_version)

        overview = metadata.get("overview")
        if overview is not None:
            overview = str(overview)

        first_air_date = metadata.get("first_air_date")
        if first_air_date is not None:
            first_air_date = str(first_air_date)

        number_of_seasons = metadata.get("number_of_seasons")
        if number_of_seasons is not None:
            number_of_seasons = int(number_of_seasons)

        number_of_episodes = metadata.get("number_of_episodes")
        if number_of_episodes is not None:
            number_of_episodes = int(number_of_episodes)

        return ProviderMetadata(
            title=title,
            year=year,
            overview=overview,
            genres=genres,
            external_id=external_id,
            metadata_version=metadata_version,
            tmdb_id=tmdb_id,
            imdb_id=imdb_id,
            poster_path=poster_path,
            backdrop_path=backdrop_path,
            credits=credits,
            first_air_date=first_air_date,
            number_of_seasons=number_of_seasons,
            number_of_episodes=number_of_episodes,
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
