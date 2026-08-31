from __future__ import annotations

import sqlite3

import pytest

from app.database.schema import initialize
from app.metadata.omdb_provider import OMDbMetadataProvider
from app.metadata.provider import ProviderMetadata
from app.metadata.repository import MetadataRepository
from app.metadata.service import MetadataService


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def get(self, url, *, params, timeout):
        self.calls.append(
            {
                "url": url,
                "params": params,
                "timeout": timeout,
            }
        )
        return FakeResponse(self.payload)


def test_omdb_provider_normalizes_realistic_imdb_movie_response() -> None:
    session = FakeSession(
        {
            "Response": "True",
            "Title": "Inception",
            "Year": "2010",
            "Plot": "A thief who steals corporate secrets through dream-sharing technology.",
            "Genre": "Action, Sci-Fi, Thriller",
            "imdbID": "tt1375666",
            "Poster": "https://example.test/inception.jpg",
        }
    )

    provider = OMDbMetadataProvider(
        api_key="test-key",
        session=session,
    )

    metadata = provider.fetch_metadata(
        entity_type="movie",
        external_id="tt1375666",
    )

    assert metadata == ProviderMetadata(
        title="Inception",
        year=2010,
        overview=(
            "A thief who steals corporate secrets through "
            "dream-sharing technology."
        ),
        genres=("Action", "Sci-Fi", "Thriller"),
        external_id="tt1375666",
        metadata_version="omdb-v1",
    )

    assert len(session.calls) == 1
    assert session.calls[0]["params"]["apikey"] == "test-key"
    assert session.calls[0]["params"]["i"] == "tt1375666"
    assert session.calls[0]["params"]["plot"] == "full"


def test_omdb_provider_returns_none_for_api_not_found() -> None:
    session = FakeSession(
        {
            "Response": "False",
            "Error": "Movie not found!",
        }
    )

    provider = OMDbMetadataProvider(
        api_key="test-key",
        session=session,
    )

    assert (
        provider.fetch_metadata(
            entity_type="movie",
            external_id="tt0000000",
        )
        is None
    )


def test_omdb_provider_requires_api_key() -> None:
    provider = OMDbMetadataProvider(
        api_key="",
        session=FakeSession({}),
    )

    with pytest.raises(ValueError, match="OMDB_API_KEY"):
        provider.fetch_metadata(
            entity_type="movie",
            external_id="tt1375666",
        )


def test_omdb_provider_requires_imdb_id() -> None:
    provider = OMDbMetadataProvider(
        api_key="test-key",
        session=FakeSession({}),
    )

    with pytest.raises(ValueError, match="IMDb ID"):
        provider.fetch_metadata(
            entity_type="movie",
            external_id="12345",
        )


def test_omdb_provider_rejects_non_movie_entity() -> None:
    provider = OMDbMetadataProvider(
        api_key="test-key",
        session=FakeSession({}),
    )

    assert (
        provider.fetch_metadata(
            entity_type="tv",
            external_id="tt0903747",
        )
        is None
    )


def test_omdb_provider_integrates_with_metadata_service() -> None:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    initialize(db)

    repository = MetadataRepository(db)

    session = FakeSession(
        {
            "Response": "True",
            "Title": "Dune",
            "Year": "2021",
            "Plot": "A noble family becomes involved in a galactic struggle.",
            "Genre": "Adventure, Drama, Sci-Fi",
            "imdbID": "tt1160419",
        }
    )

    provider = OMDbMetadataProvider(
        api_key="test-key",
        session=session,
    )

    service = MetadataService(repository, provider)

    movie_id = repository.create_movie(
        title="Dune",
        year=2021,
    )

    assert service.fetch_and_save_metadata(
        entity_type="movie",
        entity_id=movie_id,
        external_id="tt1160419",
    )

    movie = db.execute(
        """
        SELECT title, year, overview
        FROM movies
        WHERE id = ?
        """,
        (movie_id,),
    ).fetchone()

    assert movie is not None
    assert movie["title"] == "Dune"
    assert movie["year"] == 2021
    assert "galactic struggle" in movie["overview"]

    genres = db.execute(
        """
        SELECT g.name
        FROM genres g
        JOIN movie_genres mg
          ON mg.genre_id = g.id
        WHERE mg.movie_id = ?
        ORDER BY g.name
        """,
        (movie_id,),
    ).fetchall()

    assert [row["name"] for row in genres] == [
        "Adventure",
        "Drama",
        "Sci-Fi",
    ]

    source = repository.get_metadata_source(
        "movie",
        movie_id,
        "omdb",
    )

    assert source is not None
    assert source["metadata_version"] == "omdb-v1"
