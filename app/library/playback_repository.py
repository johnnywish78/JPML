from __future__ import annotations

import sqlite3


class PlaybackRepository:
    """Persistence for playback state in the JPML v5 playback_history table."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def _get_row(
        self,
        media_type: str,
        media_id: int,
    ) -> sqlite3.Row | None:
        return self._conn.execute(
            """
            SELECT *
            FROM playback_history
            WHERE media_type = ? AND media_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (media_type, media_id),
        ).fetchone()

    def start_playback(
        self,
        media_type: str,
        media_id: int,
        file_path: str,
        *,
        duration: float = 0.0,
        backend_used: str = "",
    ) -> int:
        row = self._get_row(media_type, media_id)

        if row is None:
            cursor = self._conn.execute(
                """
                INSERT INTO playback_history (
                    media_type,
                    media_id,
                    file_path,
                    started_at,
                    stopped_at,
                    last_position,
                    duration,
                    completed,
                    backend_used
                )
                VALUES (
                    ?, ?, ?, CURRENT_TIMESTAMP, NULL,
                    0.0, ?, 0, ?
                )
                """,
                (
                    media_type,
                    media_id,
                    file_path,
                    max(0.0, float(duration)),
                    backend_used,
                ),
            )
            self._conn.commit()
            return int(cursor.lastrowid)

        self._conn.execute(
            """
            UPDATE playback_history
            SET file_path = ?,
                started_at = CURRENT_TIMESTAMP,
                stopped_at = NULL,
                last_position = 0.0,
                duration = ?,
                completed = 0,
                backend_used = ?
            WHERE id = ?
            """,
            (
                file_path,
                max(0.0, float(duration)),
                backend_used,
                row["id"],
            ),
        )
        self._conn.commit()
        return int(row["id"])

    def update_position(
        self,
        media_type: str,
        media_id: int,
        position_seconds: float,
    ) -> None:
        position = max(0.0, float(position_seconds))
        row = self._get_row(media_type, media_id)

        if row is None:
            self._conn.execute(
                """
                INSERT INTO playback_history (
                    media_type,
                    media_id,
                    file_path,
                    started_at,
                    last_position,
                    duration,
                    completed
                )
                VALUES (?, ?, '', CURRENT_TIMESTAMP, ?, 0.0, 0)
                """,
                (media_type, media_id, position),
            )
        else:
            self._conn.execute(
                """
                UPDATE playback_history
                SET last_position = ?,
                    stopped_at = CURRENT_TIMESTAMP,
                    completed = 0
                WHERE id = ?
                """,
                (position, row["id"]),
            )

        self._conn.commit()

    def get_position(
        self,
        media_type: str,
        media_id: int,
    ) -> float:
        row = self._get_row(media_type, media_id)

        if row is None:
            return 0.0

        return float(row["last_position"] or 0.0)

    def get_last_position(
        self,
        media_type: str,
        media_id: int,
    ) -> float:
        row = self._get_row(media_type, media_id)

        if row is None or bool(row["completed"]):
            return 0.0

        return float(row["last_position"] or 0.0)

    def mark_completed(
        self,
        media_type: str,
        media_id: int,
    ) -> None:
        row = self._get_row(media_type, media_id)

        if row is None:
            self._conn.execute(
                """
                INSERT INTO playback_history (
                    media_type,
                    media_id,
                    file_path,
                    started_at,
                    stopped_at,
                    last_position,
                    duration,
                    completed
                )
                VALUES (?, ?, '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0.0, 0.0, 1)
                """,
                (media_type, media_id),
            )
        else:
            self._conn.execute(
                """
                UPDATE playback_history
                SET completed = 1,
                    stopped_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (row["id"],),
            )

        self._conn.commit()

    def is_completed(
        self,
        media_type: str,
        media_id: int,
    ) -> bool:
        row = self._get_row(media_type, media_id)
        return bool(row and row["completed"])

    def clear(
        self,
        media_type: str,
        media_id: int,
    ) -> None:
        self._conn.execute(
            """
            DELETE FROM playback_history
            WHERE media_type = ? AND media_id = ?
            """,
            (media_type, media_id),
        )
        self._conn.commit()

    def clear_all(self) -> None:
        self._conn.execute("DELETE FROM playback_history")
        self._conn.commit()

    def get_resume_candidates(
        self,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        limit = max(0, int(limit))

        rows = self._conn.execute(
            """
            SELECT
                ph.id,
                ph.media_type,
                ph.media_id,
                ph.file_path,
                ph.started_at,
                ph.stopped_at,
                ph.last_position,
                ph.duration,
                ph.completed,
                ph.backend_used
            FROM playback_history AS ph
            WHERE ph.completed = 0
              AND ph.last_position > 0
              AND (
                    NOT EXISTS (
                        SELECT 1
                        FROM media_files AS mf
                        WHERE mf.path = ph.file_path
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM media_files AS mf
                        WHERE mf.path = ph.file_path
                          AND mf.is_missing = 0
                    )
                  )
            ORDER BY
                COALESCE(ph.stopped_at, ph.started_at) DESC,
                ph.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [
            {
                "id": row["id"],
                "media_type": row["media_type"],
                "media_id": row["media_id"],
                "file_path": row["file_path"],
                "started_at": row["started_at"],
                "stopped_at": row["stopped_at"],
                "last_position": float(row["last_position"] or 0.0),
                "duration": float(row["duration"] or 0.0),
                "completed": bool(row["completed"]),
                "backend_used": row["backend_used"],
            }
            for row in rows
        ]

