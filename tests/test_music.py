from __future__ import annotations

import sqlite3

import pytest

from app.database.schema import initialize
from app.domain.media import Album, Artist, MediaFile, MusicTrack
from app.library.music_repository import MusicRepository
from app.metadata.identifier import IdentificationResult
from app.domain.media import MediaType
from app.services.music import MusicService, MusicResolution


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize(connection)
    return connection


class TestMusicDomain:
    def test_models(self) -> None:
        artist = Artist(id=1, name="Daft Punk")
        album = Album(
            id=2, artist_id=1, title="RAM", artist=artist
        )
        track = MusicTrack(
            id=3,
            album_id=2,
            title="Get Lucky",
            track_number=6,
            album=album,
            artist=artist,
        )
        assert track.artist is artist
        assert track.album is album
        file = MediaFile(path="/m.mp3", filename="m.mp3")
        track.files.append(file)
        assert track.files[0] is file


class TestMusicRepository:
    def test_resolve_chain_idempotent(self) -> None:
        conn = _connection()
        repo = MusicRepository(conn)

        a1, created_a1 = repo.resolve_artist("Daft Punk")
        assert created_a1 is True
        a2, created_a2 = repo.resolve_artist("Daft Punk")
        assert a1 == a2
        assert created_a2 is False

        al1, created_al = repo.resolve_album(a1, "RAM", year=2013)
        assert created_al is True
        al2, _ = repo.resolve_album(a1, "RAM")
        assert al1 == al2

        t1, created_t = repo.resolve_track(al1, "Get Lucky", track_number=6)
        assert created_t is True
        t2, _ = repo.resolve_track(al1, "Get Lucky")
        assert t1 == t2

    def test_resolve_reuses_different_album_same_artist(self) -> None:
        conn = _connection()
        repo = MusicRepository(conn)
        artist_id, _ = repo.resolve_artist("X")
        a1, _ = repo.resolve_album(artist_id, "One")
        a2, _ = repo.resolve_album(artist_id, "Two")
        assert a1 != a2
        assert repo.count_albums() == 2

    def test_get_track_with_joins(self) -> None:
        conn = _connection()
        repo = MusicRepository(conn)
        artist_id, _ = repo.resolve_artist("Artist")
        album_id, _ = repo.resolve_album(artist_id, "Album", year=2020)
        track_id, _ = repo.resolve_track(
            album_id, "Song", track_number=1, duration_seconds=210.5, year=2020
        )

        track = repo.get_track(track_id)
        assert track is not None
        assert track.title == "Song"
        assert track.track_number == 1
        assert track.duration_seconds == 210.5
        assert track.album is not None
        assert track.album.title == "Album"
        assert track.album.artist is not None
        assert track.album.artist.name == "Artist"
        assert track.artist.name == "Artist"

        album = repo.get_album(album_id)
        assert album is not None
        assert album.year == 2020
        assert album.artist is not None

    def test_link_track_file_and_lookup(self) -> None:
        conn = _connection()
        repo = MusicRepository(conn)
        artist_id, _ = repo.resolve_artist("A")
        album_id, _ = repo.resolve_album(artist_id, "B")
        track_id, _ = repo.resolve_track(album_id, "T")
        conn.execute(
            "INSERT INTO media_files(id, path, filename) VALUES (1, '/t.mp3', 't.mp3')"
        )
        conn.commit()

        repo.link_track_file(track_id, 1)
        repo.link_track_file(track_id, 1)  # duplicate-safe
        count = conn.execute(
            "SELECT COUNT(*) FROM track_files WHERE track_id = ?", (track_id,)
        ).fetchone()[0]
        assert count == 1

        assert repo.find_track_id_by_media_file(1) == track_id
        assert repo.find_track_id_by_media_file(99) is None

        files = repo.list_files_for_track(track_id)
        assert len(files) == 1
        assert files[0].path == "/t.mp3"

    def test_cascade_delete(self) -> None:
        conn = _connection()
        repo = MusicRepository(conn)
        artist_id, _ = repo.resolve_artist("A")
        album_id, _ = repo.resolve_album(artist_id, "B")
        track_id, _ = repo.resolve_track(album_id, "T")
        conn.execute(
            "INSERT INTO media_files(id, path, filename) VALUES (1, '/t.mp3', 't.mp3')"
        )
        conn.commit()
        repo.link_track_file(track_id, 1)

        conn.execute("DELETE FROM artists WHERE id = ?", (artist_id,))
        conn.commit()

        assert repo.count_albums() == 0
        assert repo.count_tracks() == 0
        link_count = conn.execute(
            "SELECT COUNT(*) FROM track_files"
        ).fetchone()[0]
        assert link_count == 0
        # media file itself survives
        assert conn.execute("SELECT COUNT(*) FROM media_files").fetchone()[0] == 1

    def test_search(self) -> None:
        conn = _connection()
        repo = MusicRepository(conn)
        a1, _ = repo.resolve_artist("Daft Punk")
        a2, _ = repo.resolve_artist("Dua Lipa")
        al1, _ = repo.resolve_album(a1, "Random Access Memories")
        al2, _ = repo.resolve_album(a2, "Future Nostalgia")
        repo.resolve_track(al1, "Get Lucky")
        repo.resolve_track(al2, "Don't Start Now")

        artists = repo.search_artists("daft")
        assert [a.name for a in artists] == ["Daft Punk"]

        albums = repo.search_albums("future")
        assert [a.title for a in albums] == ["Future Nostalgia"]
        assert albums[0].artist is not None

        tracks = repo.search_tracks("lucky")
        assert [t.title for t in tracks] == ["Get Lucky"]
        assert tracks[0].album is not None

    def test_empty_names_raise(self) -> None:
        conn = _connection()
        repo = MusicRepository(conn)
        with pytest.raises(ValueError):
            repo.resolve_artist("   ")
        with pytest.raises(ValueError):
            repo.resolve_album(1, "  ")
        with pytest.raises(ValueError):
            repo.resolve_track(1, " ")


class TestMusicService:
    def test_resolve_identification_full(self) -> None:
        conn = _connection()
        repo = MusicRepository(conn)
        svc = MusicService(repo)

        result = IdentificationResult(
            media_type=MediaType.MUSIC,
            title="Get Lucky",
            artist="Daft Punk",
            album="Random Access Memories",
            track_number=6,
            confidence=0.75,
        )
        resolution = svc.resolve_identification(result)
        assert isinstance(resolution, MusicResolution)
        assert resolution.created is True

        track = svc.get_track(resolution.track_id)
        assert track is not None
        assert track.title == "Get Lucky"
        assert track.track_number == 6
        assert track.artist.name == "Daft Punk"
        assert track.album.title == "Random Access Memories"

    def test_resolve_identification_idempotent(self) -> None:
        conn = _connection()
        svc = MusicService(MusicRepository(conn))
        result = IdentificationResult(
            media_type=MediaType.MUSIC,
            title="Song",
            artist="Artist",
            album="Album",
        )
        r1 = svc.resolve_identification(result)
        r2 = svc.resolve_identification(result)
        assert r1.track_id == r2.track_id
        assert r2.created is False
        assert svc.repository.count_tracks() == 1

    def test_resolve_identification_defaults(self) -> None:
        conn = _connection()
        svc = MusicService(MusicRepository(conn))
        result = IdentificationResult(
            media_type=MediaType.MUSIC,
            title="  ",
        )
        resolution = svc.resolve_identification(result)
        track = svc.get_track(resolution.track_id)
        assert track is not None
        assert track.artist.name == "Unknown Artist"
        assert track.album.title == "Unknown Artist"
        assert track.title == "Unknown Track"

    def test_metadata_handler_year_used(self) -> None:
        conn = _connection()
        svc = MusicService(
            MusicRepository(conn),
            metadata_handler=lambda kind, name, artist: {"year": 1999},
        )
        resolution = svc.resolve_identification(
            IdentificationResult(
                media_type=MediaType.MUSIC,
                title="Old Song",
                artist="Vintage",
                album="Classic",
            )
        )
        track = svc.get_track(resolution.track_id)
        assert track.year == 1999
        assert track.album.year == 1999

    def test_metadata_handler_failure_ignored(self) -> None:
        conn = _connection()

        def broken(kind: str, name: str, artist: str) -> dict:
            raise RuntimeError("provider down")

        svc = MusicService(MusicRepository(conn), metadata_handler=broken)
        resolution = svc.resolve_identification(
            IdentificationResult(
                media_type=MediaType.MUSIC,
                title="Song",
                artist="A",
                album="B",
            )
        )
        track = svc.get_track(resolution.track_id)
        assert track.year is None

    def test_search_delegation(self) -> None:
        conn = _connection()
        repo = MusicRepository(conn)
        svc = MusicService(repo)
        a, _ = repo.resolve_artist("Neon")
        al, _ = repo.resolve_album(a, "Neon Dreams")
        repo.resolve_track(al, "Neon Nights")

        assert len(svc.search_artists("neon")) == 1
        assert len(svc.search_albums("neon")) == 1
        assert len(svc.search_tracks("neon")) == 1
