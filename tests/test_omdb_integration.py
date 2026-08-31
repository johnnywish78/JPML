from __future__ import annotations

import os
import sqlite3

import pytest

from app.database.schema import initialize
from app.metadata.omdb_provider import OMDbMetadataProvider
from app.metadata.repository import MetadataRepository
from app.metadata.service import MetadataService


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def get(self, url, *, params=None, timeout=None):
        self.calls.append(
            {
                "url": url,
                "params": params,
                "timeout": timeout,
            }
        )
        return FakeResponse(self.payload)


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    initialize(connection)
    return connection


def test_omdb_provider_uses_imdb_id() -> None:
    session = FakeSession(
        {
            "Response": "True",
            "Title": "Inception",
            "Year": "2010",
            "Plot": "A thief enters dreams.",
            "Genre": "Action, Sci-Fi, Thriller",
            "imdbID": "tt1375666",
            "Type": "movie",
        }
    )

    provider = OMDbMetadataProvider(
        api_key="test-key",
        session=session,
    )

    result = provider.fetch_metadata(
        entity_type="movie",
        external_id="tt1375666",
    )

    assert result.title == "Inception"
    assert result.year == 2010
    assert result.external_id == "tt1375666"
    assert result.genres == ("Action", "Sci-Fi", "Thriller")

    assert len(session.calls) == 1
    assert session.calls[0]["params"]["i"] == "tt1375666"
    assert session.calls[0]["params"]["apikey"] == "test-key"


def test_omdb_provider_returns_none_for_not_found() -> None:
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

    assert provider.fetch_metadata(
            entity_type="movie",
            external_id="tt0000000",
        ) is None


def test_omdb_provider_requires_api_key() -> None:
    provider = OMDbMetadataProvider(api_key="")

    with pytest.raises(ValueError):
        provider.fetch_metadata(
            entity_type="movie",
            external_id="tt1375666",
        )


def test_omdb_metadata_flows_into_service_and_database() -> None:
    connection = db()
    repository = MetadataRepository(connection)

    session = FakeSession(
        {
            "Response": "True",
            "Title": "Dune",
            "Year": "2021",
            "Plot": "A noble family becomes involved in a galactic struggle.",
            "Genre": "Adventure, Drama, Sci-Fi",
            "imdbID": "tt1160419",
            "Type": "movie",
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

    result = service.fetch_and_save_metadata(
        entity_type="movie",
        entity_id=movie_id,
        external_id="tt1160419",
    )

    assert result is True

    movie = connection.execute(
        """
        SELECT title, year, overview
        FROM movies
        WHERE id = ?
        """,
        (movie_id,),
    ).fetchone()

    assert movie["title"] == "Dune"
    assert movie["year"] == 2021
    assert movie["overview"].startswith("A noble family")

    genres = connection.execute(
        """
        SELECT g.name
        FROM genres g
        JOIN movie_genres mg ON mg.genre_id = g.id
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


@pytest.mark.skipif(
    not os.environ.get("OMDB_API_KEY"),
    reason="OMDB_API_KEY is not configured",
)
def test_live_omdb_inception() -> None:
    provider = OMDbMetadataProvider(
        api_key=os.environ["OMDB_API_KEY"],
    )

    result = provider.fetch_metadata(
        entity_type="movie",
        external_id="tt1375666",
    )

    assert result is not None
    assert result.external_id == "tt1375666"
    assert result.title == "Inception"
    assert result.year == 2010
