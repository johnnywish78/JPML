from __future__ import annotations

MOVIE = "movie"
TV = "tv"
EPISODE = "episode"
PERSON = "person"
ARTIST = "artist"
ALBUM = "album"
TRACK = "track"

VALID_ENTITY_TYPES: frozenset[str] = frozenset(
    {MOVIE, TV, EPISODE, PERSON, ARTIST, ALBUM, TRACK}
)

# Entity type -> backing table, used for existence checks and prune().
ENTITY_TABLES: dict[str, str] = {
    MOVIE: "movies",
    TV: "tv_shows",
    EPISODE: "episodes",
    PERSON: "people",
    ARTIST: "artists",
    ALBUM: "albums",
    TRACK: "music_tracks",
}


def validate_entity(entity_type: str, entity_id: int) -> None:
    if entity_type not in VALID_ENTITY_TYPES:
        raise ValueError(f"Unknown entity_type: {entity_type!r}")
    if isinstance(entity_id, bool) or not isinstance(entity_id, int) or entity_id <= 0:
        raise ValueError(f"entity_id must be a positive integer, got {entity_id!r}")
