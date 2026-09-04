"""Centralized artwork loading and caching.

The UI never calls providers or the network directly. Artwork paths
come from the backend's artwork table (local_path) or from the local
assets directory. Loading happens on one background worker so the UI
thread remains responsive; every request yields a fixed-size pixmap so
card geometry never jumps.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from PyQt6.QtCore import QObject, QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap

_ARTWORK_ROOT_CANDIDATES = (
    Path(__file__).resolve().parents[2] / "assets" / "artwork",
)


# ---------------------------------------------------------------------------
# Worker (background thread)
# ---------------------------------------------------------------------------


class _WorkerHost(QThread):
    """Loads pixmaps off the UI thread; emits ``loaded(key, pixmap)`` on
    the UI thread (queued automatically across threads)."""

    loaded = pyqtSignal(str, object)

    def __init__(self) -> None:
        super().__init__()
        import queue as _queue
        import threading as _threading

        self._queue: "_queue.Queue" = _queue.Queue()
        self._stop = _threading.Event()
        self.start()

    def request(self, key: str, source: str | None, size: QSize) -> None:
        self._queue.put((key, source, size))

    def run(self) -> None:  # noqa: D102
        while not self._stop.is_set():
            try:
                key, source, size = self._queue.get(timeout=0.5)
            except Exception:
                if self._stop.is_set():
                    break
                continue
            pixmap = _load_pixmap(source, size)
            self.loaded.emit(key, pixmap)

    def stop(self) -> None:
        self._stop.set()
        self.wait(2000)


_worker_host: _WorkerHost | None = None


# ---------------------------------------------------------------------------
# Main-thread state
# ---------------------------------------------------------------------------

_cache: dict[str, QPixmap] = {}
_placeholders: dict[tuple, QPixmap] = {}
_inflight: set[str] = set()
_callbacks: dict[object, object] = {}


def _main_emit(key: str, pixmap: QPixmap | None) -> None:
    """Runs on the UI thread (queued signal from the worker)."""
    _inflight.discard(key)
    if pixmap is not None:
        _cache[key] = pixmap
    for callback in list(_callbacks.values()):
        try:
            callback(key)
        except Exception:
            pass


def _ensure_worker() -> _WorkerHost:
    global _worker_host
    if _worker_host is None or not _worker_host.isRunning():
        _worker_host = _WorkerHost()
        _worker_host.loaded.connect(_main_emit)
    return _worker_host


def _key(source: str | None, size: QSize) -> str:
    basis = source or "placeholder"
    digest = hashlib.md5(basis.encode("utf-8")).hexdigest()[:10]
    return f"{size.width()}x{size.height()}-{digest}"


def _load_pixmap(source: str | None, size: QSize) -> QPixmap | None:
    if not source:
        return None
    path = Path(source)
    if not path.is_file():
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    scaled = pixmap.scaled(
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    cropped = scaled.copy(
        (scaled.width() - size.width()) // 2,
        (scaled.height() - size.height()) // 2,
        size.width(),
        size.height(),
    )
    return cropped


def _assets_root() -> Path | None:
    for candidate in _ARTWORK_ROOT_CANDIDATES:
        if candidate.is_dir():
            return candidate
    return None


def _placeholder_pixmap(width: int, height: int, tokens=None) -> QPixmap:
    dark = tokens is None or getattr(tokens, "name", "dark") == "dark"
    cache_key = (width, height, dark)
    if cache_key in _placeholders:
        return _placeholders[cache_key]
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor("#1A1D26" if dark else "#E8E9ED"))
    painter = QPainter(pixmap)
    font = QFont("Sans Serif")
    font.setPixelSize(max(10, width // 12))
    painter.setFont(font)
    painter.setPen(QColor("#39404E" if dark else "#AEB2BC"))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "JPML")
    painter.end()
    _placeholders[cache_key] = pixmap
    return pixmap


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_pixmap(source: str | None, size: QSize, callback, tokens=None) -> QPixmap:
    """Return the best pixmap available *right now* and guarantee that
    *callback(key)* fires once the requested size is known (possibly
    immediately). A placeholder keeps layout stable while loading."""
    key = _key(source, size)
    if key in _cache:
        return _cache[key]
    if callback is not None:
        _callbacks[id(callback)] = callback
    host = _ensure_worker()
    if key not in _inflight:
        _inflight.add(key)
        host.request(key, source, size)
    return _placeholder_pixmap(size.width(), size.height(), tokens)


def _local_asset_path(artwork: dict | None, kind: str) -> str | None:
    root = _assets_root()
    if root is None or not artwork:
        return None
    entity_id = artwork.get("entity_id")
    if entity_id is None:
        return None
    folder = {
        "poster": "posters",
        "backdrop": "backdrops",
        "album": "posters",
        "artist": "people",
        "person": "people",
    }.get(kind, "posters")
    directory = root / folder
    if not directory.is_dir():
        return None
    for candidate in sorted(directory.iterdir()):
        if str(candidate.stem) == str(entity_id):
            return str(candidate)
    return None


def pixmap_for_artwork(
    artwork: dict | None,
    kind: str,
    size: QSize,
    callback,
    tokens=None,
) -> QPixmap:
    """Resolve an artwork record (MetadataRepository.list_artwork row) to
    a fixed-size pixmap, falling back to local asset files, then to a
    JPML placeholder."""
    local_path: str | None = None
    if artwork:
        raw = artwork.get("local_path")
        if raw and Path(str(raw)).is_file():
            local_path = str(raw)
    if not local_path:
        local_path = _local_asset_path(artwork, kind)
    return get_pixmap(local_path, size, callback, tokens)


def clear_cache() -> None:
    _cache.clear()
    _placeholders.clear()


def shutdown() -> None:
    """Stop the loader thread (called on application teardown)."""
    global _worker_host
    if _worker_host is not None:
        _worker_host.stop()
        _worker_host = None
    _inflight.clear()


def cached(key: str) -> QPixmap | None:
    """Read the cache with a public key (used by Artwork on load events)."""
    return _cache.get(key)


def key_for(source: str | None, size: QSize) -> str:
    return _key(source, size)


def resolve_artwork_source(artwork: dict | None, kind: str) -> str | None:
    """Pick the best local file for an artwork record: the stored
    local_path if it still exists, otherwise a conventional local asset
    (assets/artwork/<folder>/<entity_id>.*), otherwise nothing (the
    caller shows the JPML placeholder)."""
    if artwork:
        raw = artwork.get("local_path")
        if raw and Path(str(raw)).is_file():
            return str(raw)
    return _local_asset_path(artwork, kind)
