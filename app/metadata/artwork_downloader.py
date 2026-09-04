"""Artwork download helper for the TMDB metadata pipeline.

Provides idempotent downloading of poster and backdrop images from TMDB
into the project's local artwork cache.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_ARTWORK_ROOT = Path(__file__).resolve().parents[2] / "assets" / "artwork"


def _ensure_dir(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def download_artwork(
    *,
    url: str | None,
    local_dir: Path,
    entity_id: int,
    artwork_type: str,
    session: requests.Session | None = None,
) -> str | None:
    """Download artwork from *url* into *local_dir*/<entity_id>.<ext>.

    Returns the absolute local path when the file exists, otherwise
    ``None``.  The operation is idempotent: if the target file already
    exists it is not re-downloaded.
    """
    if not url:
        return None

    local_dir = _ensure_dir(local_dir)
    ext = _guess_ext(url)
    target = local_dir / f"{entity_id}{ext}"

    if target.exists() and target.stat().st_size > 0:
        return str(target)

    try:
        sess = session or requests.Session()
        resp = sess.get(url, timeout=15.0, stream=True)
        resp.raise_for_status()
        data = resp.content
        if not data:
            return None
        target.write_bytes(data)
        if target.stat().st_size == 0:
            target.unlink(missing_ok=True)
            return None
        return str(target)
    except requests.RequestException:
        logger.warning("Artwork download failed: %s", url, exc_info=True)
        return None
    except OSError:
        logger.warning("Artwork write failed: %s", target, exc_info=True)
        return None


def _guess_ext(url: str) -> str:
    """Heuristic extension guess from URL."""
    ext = Path(url.split("?")[0]).suffix.lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"):
        return ext
    # Default to .jpg for unknown image URLs
    return ".jpg"
