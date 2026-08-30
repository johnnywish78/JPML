from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.domain.media import MediaType
from app.library.scanner import VIDEO_EXTENSIONS, AUDIO_EXTENSIONS, ScanResult


@dataclass(slots=True)
class IdentificationResult:
    media_type: MediaType
    title: str
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    episode_end: int | None = None
    artist: str | None = None
    album: str | None = None
    track_number: int | None = None
    confidence: float = 0.0
    path: str = ""
    raw_title: str = ""


_YEAR_RANGE = range(1900, 2031)

_TECHNICAL_TOKENS: frozenset[str] = frozenset({
    "480p", "576p", "720p", "1080p", "1440p", "2160p", "4k", "8k", "uhd",
    "web", "web-dl", "webrip", "webdl", "bluray", "bdrip", "brrip",
    "hdtv", "dvdrip", "remux", "proper", "repack", "limited",
    "extended", "uncut", "directors", "director", "cut",
    "x264", "x265", "h264", "h265", "hevc", "av1", "mpeg4",
    "hdr", "hdr10", "hdr10+", "dv", "dolby", "vision",
    "aac", "ac3", "eac3", "dts", "dts-hd", "truehd", "atmos", "flac",
    "internal", "loquent", "synced", "dubbed", "subbed",
    "cam", "ts", "tc", "scr", "screener", "hdrip",
    ".multi", "multi", "dual", "audio",
    "10bit", "10-bit", "8bit", "sdr",
    "nf", "amzn", "dsnp", "atvp", "hmax", "pmtp", "IÊN",
})

_TV_EP_PATTERN_STANDARD = re.compile(
    r"[\.\s\-]?[Ss](\d{1,2})[Ee](\d{1,3})(?:[\.\s\-]?[Ee](\d{1,3}))?",
)
_TV_EP_PATTERN_X = re.compile(
    r"[\.\s\-]?(\d{1,2})[xX](\d{1,3})",
)
_TV_EP_PATTERN_WORDY = re.compile(
    r"[Ss]eason\s+(\d{1,2})\s+[Ee]pisode\s+(\d{1,3})",
    re.IGNORECASE,
)
_TV_EP_PATTERN_EP_TITLE = re.compile(
    r"[\.\s\-]?[Ss](\d{1,2})[Ee](\d{1,3})[\.\s\-]+(.+?)(?:\.[\w]{2,5})?$",
)

_YEAR_PAREN = re.compile(r"\((\d{4})\)")
_YEAR_BARE = re.compile(r"[\.\s\-]((?:19|20)\d{2})[\.\s\-]")


def _normalize_spaces(s: str) -> str:
    return re.sub(r"[\s._]+", " ", s).strip()


def normalize_title(title: str) -> str:
    title = _normalize_spaces(title)
    title = re.sub(r"\s*-\s*", " - ", title)
    title = re.sub(r"\s{2,}", " ", title)
    return title.strip()


def _extract_year_from_stem(stem: str) -> tuple[int | None, str]:
    m = _YEAR_PAREN.search(stem)
    if m:
        year = int(m.group(1))
        if year in _YEAR_RANGE:
            cleaned = stem[: m.start()] + stem[m.end() :]
            return year, cleaned

    parts = re.split(r"[\.\s\-]", stem)
    candidates: list[tuple[int, int]] = []
    for i, part in enumerate(parts):
        clean_part = part.strip("()")
        if clean_part.isdigit() and len(clean_part) == 4:
            year = int(clean_part)
            if year in _YEAR_RANGE:
                candidates.append((year, i))

    if len(candidates) == 1:
        year, idx = candidates[0]
        remaining = [p for j, p in enumerate(parts) if j != idx]
        return year, ".".join(remaining)

    if len(candidates) >= 2:
        year, idx = candidates[-1]
        remaining = [p for j, p in enumerate(parts) if j != idx]
        return year, ".".join(remaining)

    return None, stem


def _looks_like_episode_number(s: str) -> bool:
    return bool(re.match(r"^\d{1,3}$", s))


def _strip_release_group(stem: str) -> str:
    if "-" in stem:
        last_dash_idx = stem.rfind("-")
        candidate = stem[last_dash_idx + 1 :].strip()
        candidate_lower = candidate.lower()
        if (
            len(candidate) < 30
            and any(tok in candidate_lower for tok in _TECHNICAL_TOKENS)
        ):
            return stem[:last_dash_idx].strip()
        if len(candidate) < 20 and not any(c.isdigit() for c in candidate):
            has_known = any(tok in candidate_lower for tok in _TECHNICAL_TOKENS)
            if not has_known:
                return stem[:last_dash_idx].strip()
    return stem


def _detect_tv_episode(stem: str) -> tuple[int, int, int | None, str] | None:
    m = _TV_EP_PATTERN_STANDARD.search(stem)
    if m:
        season = int(m.group(1))
        episode = int(m.group(2))
        episode_end = int(m.group(3)) if m.lastindex and m.lastindex >= 3 and m.group(3) else None
        cleaned = stem[: m.start()] + stem[m.end() :]
        return season, episode, episode_end, cleaned

    m = _TV_EP_PATTERN_X.search(stem)
    if m:
        season = int(m.group(1))
        episode = int(m.group(2))
        cleaned = stem[: m.start()] + stem[m.end() :]
        return season, episode, None, cleaned

    m = _TV_EP_PATTERN_WORDY.search(stem)
    if m:
        season = int(m.group(1))
        episode = int(m.group(2))
        cleaned = stem[: m.start()] + stem[m.end() :]
        return season, episode, None, cleaned

    return None


def _detect_episode_title(stem: str) -> str | None:
    m = _TV_EP_PATTERN_EP_TITLE.search(stem)
    if m:
        title_part = m.group(3).strip(".- _")
        if title_part and len(title_part) > 1:
            return normalize_title(title_part)
    return None


def _detect_music(filename: str, parent_parts: list[str]) -> IdentificationResult | None:
    stem = Path(filename).stem

    def _music_artist_album(parents: list[str]) -> tuple[str | None, str | None]:
        if len(parents) >= 2:
            return parents[-2], parents[-1]
        if len(parents) == 1:
            return None, parents[0]
        return None, None

    m = re.match(r"^(\d{1,3})\s*[\.\-\s]\s*(.+)$", stem)
    if m:
        track_num = int(m.group(1))
        track_title = normalize_title(m.group(2))
        artist, album = _music_artist_album(parent_parts)
        return IdentificationResult(
            media_type=MediaType.MUSIC,
            title=track_title,
            artist=artist,
            album=album,
            track_number=track_num,
            confidence=0.70,
            path=filename,
            raw_title=stem,
        )

    m = re.match(r"^(.+?)\s*-\s*(.+)$", stem)
    if m:
        possible_artist = m.group(1).strip()
        rest = m.group(2).strip()
        if "-" in rest:
            parts = rest.split("-", 1)
            album_or_track = parts[0].strip()
            track_title = normalize_title(parts[1].strip()) if len(parts) > 1 else normalize_title(album_or_track)
            artist = possible_artist
            album = album_or_track
        else:
            artist = possible_artist
            track_title = normalize_title(rest)
            _, album = _music_artist_album(parent_parts)
        return IdentificationResult(
            media_type=MediaType.MUSIC,
            title=track_title,
            artist=artist,
            album=album,
            confidence=0.75,
            path=filename,
            raw_title=stem,
        )

    return None


def _identify_video(filename: str, parent_parts: list[str]) -> IdentificationResult:
    stem = Path(filename).stem
    cleaned_stem = _strip_release_group(stem)
    cleaned_stem = _normalize_spaces(cleaned_stem)

    tv = _detect_tv_episode(cleaned_stem)
    if tv is not None:
        season, episode, episode_end, after_tv = tv
        year, _ = _extract_year_from_stem(after_tv)
        title_text = normalize_title(after_tv)
        title_text = re.sub(r"\s*\(\d{4}\)\s*", "", title_text).strip()
        title_text = re.sub(r"\b(?:19|20)\d{2}\b", "", title_text).strip(".- _")
        title_text = normalize_title(title_text)
        ep_title = _detect_episode_title(stem)

        if season_dir_parts := [p for p in parent_parts if re.match(
            r"(?i)^season\s*\d+|^s\d{1,2}$", p
        )]:
            confidence = 0.92
        else:
            confidence = 0.85

        final_title = title_text if title_text else ep_title if ep_title else "Unknown"
        return IdentificationResult(
            media_type=MediaType.EPISODE,
            title=final_title,
            year=year,
            season=season,
            episode=episode,
            episode_end=episode_end,
            confidence=confidence,
            path=filename,
            raw_title=stem,
        )

    year, cleaned_for_title = _extract_year_from_stem(cleaned_stem)
    title_text = normalize_title(cleaned_for_title)
    title_text = re.sub(r"\s*\(\d{4}\)\s*", "", title_text).strip()
    title_text = normalize_title(title_text)

    if year is not None:
        confidence = 0.80
    elif parent_parts and any(
        re.match(r"(?i)^(movies?|films?)$", p) for p in parent_parts
    ):
        confidence = 0.65
    else:
        confidence = 0.55

    return IdentificationResult(
        media_type=MediaType.MOVIE,
        title=title_text if title_text else "Unknown",
        year=year,
        confidence=confidence,
        path=filename,
        raw_title=stem,
    )


def identify(
    scan_result: ScanResult,
    parent_parts: list[str] | None = None,
) -> IdentificationResult:
    if parent_parts is None:
        parent_parts = []

    filename = scan_result.filename
    ext = scan_result.extension.lower()

    if ext in AUDIO_EXTENSIONS:
        music = _detect_music(filename, parent_parts)
        if music is not None:
            music.path = str(scan_result.path)
            return music

        return IdentificationResult(
            media_type=MediaType.MUSIC,
            title=normalize_title(Path(filename).stem),
            confidence=0.40,
            path=str(scan_result.path),
            raw_title=Path(filename).stem,
        )

    if ext in VIDEO_EXTENSIONS:
        return _identify_video(filename, parent_parts)

    return IdentificationResult(
        media_type=MediaType.MOVIE,
        title=normalize_title(Path(filename).stem),
        confidence=0.20,
        path=str(scan_result.path),
        raw_title=Path(filename).stem,
    )
