from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class MediaType(StrEnum):
    MOVIE = "movie"
    TV_SHOW = "tv_show"
    EPISODE = "episode"
    MUSIC = "music"


class PersonRole(StrEnum):
    ACTOR = "actor"
    DIRECTOR = "director"
    WRITER = "writer"
    PRODUCER = "producer"


@dataclass(slots=True)
class MediaFile:
    path: str
    filename: str
    extension: str | None = None
    size_bytes: int | None = None
    duration_seconds: float | None = None
    mime_type: str | None = None
    id: int | None = None


@dataclass(slots=True)
class Person:
    name: str
    biography: str | None = None
    imdb_id: str | None = None
    tmdb_id: int | None = None
    id: int | None = None


@dataclass(slots=True)
class Movie:
    title: str
    original_title: str | None = None
    year: int | None = None
    overview: str | None = None
    runtime_minutes: int | None = None
    imdb_id: str | None = None
    tmdb_id: int | None = None
    id: int | None = None
    files: list[MediaFile] = field(default_factory=list)
    people: list[Person] = field(default_factory=list)


@dataclass(slots=True)
class Episode:
    title: str
    episode_number: int
    season_number: int
    overview: str | None = None
    air_date: str | None = None
    imdb_id: str | None = None
    tmdb_id: int | None = None
    id: int | None = None
    files: list[MediaFile] = field(default_factory=list)


@dataclass(slots=True)
class Season:
    season_number: int
    tv_show_id: int | None = None
    title: str | None = None
    overview: str | None = None
    id: int | None = None
    episodes: list[Episode] = field(default_factory=list)


@dataclass(slots=True)
class TVShow:
    title: str
    original_title: str | None = None
    year: int | None = None
    overview: str | None = None
    imdb_id: str | None = None
    tmdb_id: int | None = None
    id: int | None = None
    seasons: list[Season] = field(default_factory=list)
    people: list[Person] = field(default_factory=list)
