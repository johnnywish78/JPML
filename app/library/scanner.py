from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".webm", ".ts", ".m2ts"}
)

AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma"}
)

MEDIA_EXTENSIONS: frozenset[str] = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


@dataclass(slots=True)
class ScanResult:
    path: Path
    filename: str
    extension: str
    size_bytes: int | None


@dataclass(slots=True)
class ScanStats:
    locations_scanned: int = 0
    directories_scanned: int = 0
    files_examined: int = 0
    media_files_found: int = 0
    errors: list[str] = field(default_factory=list)


def is_media_file(path: Path) -> bool:
    return path.suffix.lower() in MEDIA_EXTENSIONS


def _safe_stat_size(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def scan_directory(root: Path) -> list[ScanResult]:
    results: list[ScanResult] = []
    resolved_root = root.resolve()

    try:
        entries = sorted(resolved_root.iterdir())
    except (PermissionError, OSError) as exc:
        raise PermissionError(f"Cannot access directory: {resolved_root}") from exc

    for entry in entries:
        if entry.is_symlink():
            continue

        if entry.is_dir():
            try:
                results.extend(scan_directory(entry))
            except PermissionError:
                pass
        elif entry.is_file() and is_media_file(entry):
            results.append(
                ScanResult(
                    path=entry,
                    filename=entry.name,
                    extension=entry.suffix.lower(),
                    size_bytes=_safe_stat_size(entry),
                )
            )

    return results


def scan_locations(
    locations: list[Path],
) -> tuple[list[ScanResult], ScanStats]:
    stats = ScanStats()
    all_results: list[ScanResult] = []

    for location in locations:
        resolved = location.resolve()
        stats.locations_scanned += 1

        if not resolved.is_dir():
            stats.errors.append(f"Location does not exist or is not a directory: {resolved}")
            continue

        try:
            results = scan_directory(resolved)
        except PermissionError as exc:
            stats.errors.append(str(exc))
            continue

        stats.media_files_found += len(results)
        stats.directories_scanned += 1

        for result in results:
            stats.files_examined += 1

        all_results.extend(results)

    return all_results, stats
