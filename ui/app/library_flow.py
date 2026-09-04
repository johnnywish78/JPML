"""Library management flow on top of the frozen backend.

The UI never opens backend write paths on its own; everything here goes
through the existing public API:

- app.database.connection.connect / app.database.schema.initialize
  (fresh thread-bound connection, the pattern the UI already uses)
- app.library.library_repository.LibraryRepository
  (add / list / remove library locations)
- app.library.coordinator.sync_location
  (scan a location and upsert its media files — idempotent)
- app.metadata… via app.bootstrap.create_metadata_integration
  + app.library.coordinator.process_library_metadata
  (filenames → movies / TV shows / music entities, real pipeline)

Scan work runs on a QThread so the UI stays responsive; the thread
builds its own connection (frozen backend keeps connections
thread-bound) and closes everything before finishing.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal


class LibrarySyncWorker(QThread):
    """Adds (optionally) a location, syncs all locations, then runs the
    metadata pipeline. Emits real phase/count updates only — never
    invented progress."""

    progress = pyqtSignal(str, str)  # phase, message
    done = pyqtSignal(object)  # summary dict
    failed = pyqtSignal(object)  # Exception

    def __init__(self, *, add_path: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self._add_path = str(add_path) if add_path else None

    # ------------------------------------------------------------------ #

    def run(self) -> None:
        from app.bootstrap import create_metadata_integration
        from app.database.connection import connect
        from app.database.schema import initialize
        from app.library.coordinator import (
            process_library_metadata,
            sync_location,
        )
        from app.library.library_repository import LibraryRepository

        conn = connect()
        initialize(conn)
        integration = None
        try:
            repo = LibraryRepository(conn)
            if self._add_path:
                candidate = Path(self._add_path)
                if not candidate.is_dir():
                    raise RuntimeError(
                        f"Folder is not available: {candidate}"
                    )
                repo.add_location(candidate, label=candidate.name or None)
                self.progress.emit("location", f"Added {candidate}")

            locations = repo.list_locations()
            if not locations:
                raise RuntimeError("No library locations to scan.")
            paths = [Path(str(row["path"])) for row in locations]

            self.progress.emit(
                "scanning", f"Scanning {len(paths)} location(s)…"
            )
            files_found = 0
            files_added = 0
            errors: list[str] = []
            for index, location in enumerate(paths, start=1):
                result = sync_location(conn, location)
                files_found += result.scan_stats.media_files_found
                files_added += result.files_added
                errors.extend(result.scan_stats.errors)
                self.progress.emit(
                    "scanning",
                    f"Location {index}/{len(paths)} — "
                    f"{files_found} media file(s) found",
                )

            self.progress.emit(
                "metadata", "Matching titles, shows and artists…"
            )
            integration = create_metadata_integration()
            processed = process_library_metadata(
                conn, integration=integration
            )
            errors.extend(processed.errors)

            self.done.emit(
                {
                    "locations": len(paths),
                    "media_files_found": files_found,
                    "media_files_added": files_added,
                    "files_processed": processed.files_processed,
                    "entities_created": processed.entities_created,
                    "entities_reused": processed.entities_reused,
                    "errors": errors,
                }
            )
        except Exception as exc:  # noqa: BLE001 — surfaced as UI error state
            try:
                self.failed.emit(exc)
            except RuntimeError:
                pass  # C++ object destroyed (app shutting down)
        finally:
            self._close_connections(conn, integration)

    # ------------------------------------------------------------------ #

    @staticmethod
    def _close_connections(conn, integration) -> None:
        def _close(connection) -> None:
            if connection is not None:
                try:
                    connection.close()
                except Exception:  # noqa: BLE001 — best effort teardown
                    pass

        _close(conn)
        if integration is not None:
            repository = getattr(
                getattr(integration, "metadata_service", None),
                "repository",
                None,
            )
            _close(getattr(repository, "_conn", None))


# --------------------------------------------------------------------------- #
# App-level helpers (the running scan is shared UI state)                     #
# --------------------------------------------------------------------------- #


def app_state(app) -> object | None:
    return getattr(app, "jpml_state", None) if app is not None else None


def current_scan_worker(app) -> LibrarySyncWorker | None:
    state = app_state(app)
    worker = getattr(state, "scan_worker", None) if state is not None else None
    if worker is None:
        return None
    return worker if worker.isRunning() else None


def scan_in_progress(app) -> bool:
    return current_scan_worker(app) is not None


def register_scan_worker(app, worker: LibrarySyncWorker | None) -> None:
    state = app_state(app)
    if state is not None:
        state.scan_worker = worker
