from __future__ import annotations

import sqlite3

from app.domain.media import Album, Artist, MediaFile, MusicTrack


class MusicRepository:
    """CRUD/query operations for artists, albums and music tracks.

    All resolve_* methods are get-or-create and therefore idempotent for the
    same identifying attributes.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    # -- resolve (get-or-create) -------------------------------------------

    def resolve_artist(self, name: str) -> tuple[int, bool]:
        name = name.strip()
        if not name:
            raise ValueError("artist name must not be empty")
        row = self._conn.execute(
            "SELECT id FROM artists WHERE name = ?", (name,)
        ).fetchone()
        if row is not None:
            return int(row["id"]), False
        cursor = self._conn.execute(
            "INSERT INTO artists(name) VALUES (?)", (name,)
        )
        self._conn.commit()
        return int(cursor.lastrowid), True

    def resolve_album(
        self, artist_id: int, title: str, year: int | None = None
    ) -> tuple[int, bool]:
        title = title.strip()
        if not title:
            raise ValueError("album title must not be empty")
        row = self._conn.execute(
            "SELECT id FROM albums WHERE artist_id = ? AND title = ?",
            (artist_id, title),
        ).fetchone()
        if row is not None:
            if year is not None:
                self._conn.execute(
                    "UPDATE albums SET year = COALESCE(year, ?), "
                    "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (year, row["id"]),
                )
                self._conn.commit()
            return int(row["id"]), False
        cursor = self._conn.execute(
            "INSERT INTO albums(artist_id, title, year) VALUES (?, ?, ?)",
            (artist_id, title, year),
        )
        self._conn.commit()
        return int(cursor.lastrowid), True

    def resolve_track(
        self,
        album_id: int,
        title: str,
        *,
        track_number: int | None = None,
        duration_seconds: float | None = None,
        year: int | None = None,
    ) -> tuple[int, bool]:
        title = title.strip()
        if not title:
            raise ValueError("track title must not be empty")
        row = self._conn.execute(
            "SELECT id FROM music_tracks WHERE album_id = ? AND title = ?",
            (album_id, title),
        ).fetchone()
        if row is not None:
            if track_number is not None or duration_seconds is not None or year is not None:
                self._conn.execute(
                    "UPDATE music_tracks SET "
                    "track_number = COALESCE(track_number, ?), "
                    "duration_seconds = COALESCE(duration_seconds, ?), "
                    "year = COALESCE(year, ?), "
                    "updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?",
                    (track_number, duration_seconds, year, row["id"]),
                )
                self._conn.commit()
            return int(row["id"]), False
        cursor = self._conn.execute(
            "INSERT INTO music_tracks "
            "(album_id, title, track_number, duration_seconds, year) "
            "VALUES (?, ?, ?, ?, ?)",
            (album_id, title, track_number, duration_seconds, year),
        )
        self._conn.commit()
        return int(cursor.lastrowid), True

    # -- reads ---------------------------------------------------------------

    def get_artist(self, artist_id: int) -> Artist | None:
        row = self._conn.execute(
            "SELECT id, name, biography FROM artists WHERE id = ?", (artist_id,)
        ).fetchone()
        if row is None:
            return None
        return Artist(id=row["id"], name=row["name"], biography=row["biography"])

    def get_album(self, album_id: int) -> Album | None:
        row = self._conn.execute(
            "SELECT id, artist_id, title, year FROM albums WHERE id = ?",
            (album_id,),
        ).fetchone()
        if row is None:
            return None
        return Album(
            id=row["id"],
            artist_id=row["artist_id"],
            title=row["title"],
            year=row["year"],
            artist=self.get_artist(row["artist_id"]),
        )

    def get_track(self, track_id: int) -> MusicTrack | None:
        row = self._conn.execute(
            """
            SELECT t.id, t.album_id, t.title, t.track_number,
                   t.duration_seconds, t.year
            FROM music_tracks AS t
            WHERE t.id = ?
            """,
            (track_id,),
        ).fetchone()
        if row is None:
            return None
        album = self.get_album(row["album_id"])
        artist = album.artist if album is not None else None
        return MusicTrack(
            id=row["id"],
            album_id=row["album_id"],
            title=row["title"],
            track_number=row["track_number"],
            duration_seconds=row["duration_seconds"],
            year=row["year"],
            album=album,
            artist=artist,
        )

    # -- file relationships ----------------------------------------------------

    def link_track_file(self, track_id: int, media_file_id: int) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO track_files(track_id, media_file_id) VALUES (?, ?)",
            (track_id, media_file_id),
        )
        self._conn.commit()

    def list_files_for_track(self, track_id: int) -> list[MediaFile]:
        rows = self._conn.execute(
            """
            SELECT mf.* FROM media_files AS mf
            JOIN track_files AS tf ON tf.media_file_id = mf.id
            WHERE tf.track_id = ?
            ORDER BY mf.path
            """,
            (track_id,),
        ).fetchall()
        return [
            MediaFile(
                path=row["path"],
                filename=row["filename"],
                extension=row["extension"],
                size_bytes=row["size_bytes"],
                duration_seconds=row["duration_seconds"],
                mime_type=row["mime_type"],
                id=row["id"],
            )
            for row in rows
        ]

    def find_track_id_by_media_file(self, media_file_id: int) -> int | None:
        row = self._conn.execute(
            "SELECT track_id FROM track_files WHERE media_file_id = ?",
            (media_file_id,),
        ).fetchone()
        return int(row["track_id"]) if row is not None else None

    # -- search ----------------------------------------------------------------

    @staticmethod
    def _like(query: str) -> str:
        return f"%{query}%"

    def search_artists(self, query: str, *, limit: int = 50) -> list[Artist]:
        like = self._like(query)
        rows = self._conn.execute(
            "SELECT id, name, biography FROM artists "
            "WHERE name LIKE ? "
            "ORDER BY CASE WHEN name = ? THEN 0 WHEN name LIKE ? THEN 1 ELSE 2 END, name "
            "LIMIT ?",
            (like, query, like, limit),
        ).fetchall()
        return [
            Artist(id=row["id"], name=row["name"], biography=row["biography"])
            for row in rows
        ]

    def search_albums(self, query: str, *, limit: int = 50) -> list[Album]:
        like = self._like(query)
        rows = self._conn.execute(
            """
            SELECT a.id, a.artist_id, a.title, a.year
            FROM albums AS a
            JOIN artists AS ar ON ar.id = a.artist_id
            WHERE a.title LIKE ?
            ORDER BY CASE WHEN a.title = ? THEN 0 WHEN a.title LIKE ? THEN 1 ELSE 2 END, a.title
            LIMIT ?
            """,
            (like, query, like, limit),
        ).fetchall()
        return [
            Album(
                id=row["id"],
                artist_id=row["artist_id"],
                title=row["title"],
                year=row["year"],
                artist=self.get_artist(row["artist_id"]),
            )
            for row in rows
        ]

    def search_tracks(self, query: str, *, limit: int = 50) -> list[MusicTrack]:
        like = self._like(query)
        rows = self._conn.execute(
            """
            SELECT t.id, t.album_id, t.title, t.track_number,
                   t.duration_seconds, t.year
            FROM music_tracks AS t
            JOIN albums AS a ON a.id = t.album_id
            JOIN artists AS ar ON ar.id = a.artist_id
            WHERE t.title LIKE ?
            ORDER BY CASE WHEN t.title = ? THEN 0 WHEN t.title LIKE ? THEN 1 ELSE 2 END, t.title
            LIMIT ?
            """,
            (like, query, like, limit),
        ).fetchall()
        results: list[MusicTrack] = []
        for row in rows:
            album = self.get_album(row["album_id"])
            results.append(
                MusicTrack(
                    id=row["id"],
                    album_id=row["album_id"],
                    title=row["title"],
                    track_number=row["track_number"],
                    duration_seconds=row["duration_seconds"],
                    year=row["year"],
                    album=album,
                    artist=album.artist if album is not None else None,
                )
            )
        return results

    # -- counts ----------------------------------------------------------------

    def count_artists(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM artists").fetchone()[0])

    def count_albums(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM albums").fetchone()[0])

    def count_tracks(self) -> int:
        return int(
            self._conn.execute("SELECT COUNT(*) FROM music_tracks").fetchone()[0]
        )
