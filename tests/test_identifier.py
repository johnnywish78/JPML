from __future__ import annotations

from pathlib import Path

from app.domain.media import MediaType
from app.library.scanner import ScanResult
from app.metadata.identifier import IdentificationResult, identify, normalize_title


def _sr(filename: str, ext: str | None = None, path: str | None = None) -> ScanResult:
    if ext is None:
        ext = Path(filename).suffix.lower()
    return ScanResult(
        path=Path(path or f"/tmp/{filename}"),
        filename=filename,
        extension=ext,
        size_bytes=1000,
    )


# ─── 1. Movie with year in parentheses ───────────────────────────────────────

def test_movie_with_year_in_parentheses() -> None:
    result = identify(_sr("Inception (2010).mkv"))
    assert result.media_type == MediaType.MOVIE
    assert result.title == "Inception"
    assert result.year == 2010
    assert result.confidence >= 0.70


# ─── 2. Movie with year as bare token ─────────────────────────────────────────

def test_movie_with_year_bare_token() -> None:
    result = identify(_sr("The.Dark.Knight.2008.1080p.BluRay.x264.mkv"))
    assert result.media_type == MediaType.MOVIE
    assert "Dark Knight" in result.title
    assert result.year == 2008


# ─── 3. Movie without year ───────────────────────────────────────────────────

def test_movie_without_year() -> None:
    result = identify(_sr("Dune.Part.Two.2160p.UHD.BluRay.mkv"))
    assert result.media_type == MediaType.MOVIE
    assert "Dune" in result.title
    assert result.year is None


# ─── 4. Movie with spaces in filename ────────────────────────────────────────

def test_movie_with_spaces() -> None:
    result = identify(_sr("The Lord of the Rings - The Fellowship of the Ring (2001).mkv"))
    assert result.media_type == MediaType.MOVIE
    assert "Lord of the Rings" in result.title
    assert result.year == 2001


# ─── 5. Movie with dots ──────────────────────────────────────────────────────

def test_movie_with_dots() -> None:
    result = identify(_sr("Oppenheimer.2023.1080p.WEB-DL.mkv"))
    assert result.media_type == MediaType.MOVIE
    assert "Oppenheimer" in result.title
    assert result.year == 2023


# ─── 6. Movie with hyphens ───────────────────────────────────────────────────

def test_movie_with_hyphens() -> None:
    result = identify(_sr("Spider-Man-No-Way-Home-2021.mkv"))
    assert result.media_type == MediaType.MOVIE
    assert "Spider" in result.title
    assert result.year == 2021


# ─── 7. Movie with technical release tags ────────────────────────────────────

def test_movie_with_technical_tags() -> None:
    result = identify(_sr("Interstellar.2014.2160p.UHD.BluRay.REMUX.DV.HDR.HEVC.TrueHD- GROUP.mkv"))
    assert result.media_type == MediaType.MOVIE
    assert "Interstellar" in result.title
    assert result.year == 2014


# ─── 8. TV S01E01 standard pattern ───────────────────────────────────────────

def test_tv_s01e01() -> None:
    result = identify(_sr("Breaking.Bad.S01E01.720p.mkv"))
    assert result.media_type == MediaType.EPISODE
    assert "Breaking Bad" in result.title
    assert result.season == 1
    assert result.episode == 1
    assert result.confidence >= 0.80


# ─── 9. TV 1x01 pattern ──────────────────────────────────────────────────────

def test_tv_1x01() -> None:
    result = identify(_sr("Breaking.Bad.1x01.720p.mkv"))
    assert result.media_type == MediaType.EPISODE
    assert "Breaking Bad" in result.title
    assert result.season == 1
    assert result.episode == 1


# ─── 10. TV with episode title ───────────────────────────────────────────────

def test_tv_with_episode_title() -> None:
    result = identify(_sr("Breaking.Bad.S01E01.720p.Pilot.mkv"))
    assert result.media_type == MediaType.EPISODE
    assert result.season == 1
    assert result.episode == 1


# ─── 11. TV multi-episode ────────────────────────────────────────────────────

def test_tv_multi_episode() -> None:
    result = identify(_sr("Breaking.Bad.S01E01E02.mkv"))
    assert result.media_type == MediaType.EPISODE
    assert result.season == 1
    assert result.episode == 1
    assert result.episode_end == 2


# ─── 12. TV multi-episode with hyphen ────────────────────────────────────────

def test_tv_multi_episode_hyphen() -> None:
    result = identify(_sr("Breaking.Bad.S01E01-E03.mkv"))
    assert result.media_type == MediaType.EPISODE
    assert result.season == 1
    assert result.episode == 1
    assert result.episode_end == 3


# ─── 13. TV with year ────────────────────────────────────────────────────────

def test_tv_with_year() -> None:
    result = identify(_sr("The.Office.2005.S02E03.mkv"))
    assert result.media_type == MediaType.EPISODE
    assert "Office" in result.title
    assert result.year == 2005
    assert result.season == 2
    assert result.episode == 3


# ─── 14. TV with season directory hint ────────────────────────────────────────

def test_tv_with_season_directory() -> None:
    result = identify(
        _sr("Breaking.Bad.S01E01.mkv"),
        parent_parts=["TV Shows", "Breaking Bad", "Season 01"],
    )
    assert result.media_type == MediaType.EPISODE
    assert result.confidence >= 0.90


# ─── 15. Season directory S02E03 with title ──────────────────────────────────

def test_tv_show_with_episode_title_and_season_dir() -> None:
    result = identify(
        _sr("S02E03 - The Negotiation.mkv"),
        parent_parts=["The Office", "Season 2"],
    )
    assert result.media_type == MediaType.EPISODE
    assert result.season == 2
    assert result.episode == 3
    assert result.confidence >= 0.90


# ─── 16. Music Artist - Track ────────────────────────────────────────────────

def test_music_artist_track() -> None:
    result = identify(_sr("Pink Floyd - Comfortably Numb.mp3"))
    assert result.media_type == MediaType.MUSIC
    assert result.artist == "Pink Floyd"
    assert result.title == "Comfortably Numb"
    assert result.confidence >= 0.60


# ─── 17. Music with track number ─────────────────────────────────────────────

def test_music_with_track_number() -> None:
    result = identify(_sr("01 - Speak to Me.flac"))
    assert result.media_type == MediaType.MUSIC
    assert result.track_number == 1
    assert result.title == "Speak to Me"


# ─── 18. Music with track number dot ─────────────────────────────────────────

def test_music_with_track_number_dot() -> None:
    result = identify(_sr("02. Song Title.m4a"))
    assert result.media_type == MediaType.MUSIC
    assert result.track_number == 2
    assert result.title == "Song Title"


# ─── 19. Music directory hierarchy ───────────────────────────────────────────

def test_music_directory_hierarchy() -> None:
    result = identify(
        _sr("01 - Speak to Me.flac"),
        parent_parts=["Pink Floyd", "The Dark Side of the Moon"],
    )
    assert result.media_type == MediaType.MUSIC
    assert result.artist == "Pink Floyd"
    assert result.album == "The Dark Side of the Moon"
    assert result.track_number == 1


# ─── 20. Mixed-case extensions ───────────────────────────────────────────────

def test_mixed_case_extensions() -> None:
    result = identify(_sr("Movie.2020.MKV", ext=".mkv"))
    assert result.media_type == MediaType.MOVIE
    assert result.year == 2020


# ─── 21. Unicode title ───────────────────────────────────────────────────────

def test_unicode_title() -> None:
    result = identify(_sr("Amélie (2001).mkv"))
    assert result.media_type == MediaType.MOVIE
    assert "Amélie" in result.title
    assert result.year == 2001


# ─── 22. Filenames with spaces (video) ───────────────────────────────────────

def test_video_filename_with_spaces() -> None:
    result = identify(_sr("My Movie 2022.mkv"))
    assert result.media_type == MediaType.MOVIE
    assert result.year == 2022
    assert "My Movie" in result.title


# ─── 23. Filenames with brackets ─────────────────────────────────────────────

def test_filename_with_brackets() -> None:
    result = identify(_sr("Movie [2022] 1080p.mkv"))
    assert result.media_type == MediaType.MOVIE


# ─── 24. Filenames containing ordinary numbers ───────────────────────────────

def test_filenames_with_ordinary_numbers() -> None:
    result = identify(_sr("2001.A.Space.Odyssey.1968.mkv"))
    assert result.media_type == MediaType.MOVIE
    assert "Space Odyssey" in result.title
    assert result.year == 1968


# ─── 25. Movie titles containing numbers ─────────────────────────────────────

def test_movie_titles_containing_numbers() -> None:
    result = identify(_sr("District.9.2009.1080p.BluRay.mkv"))
    assert result.media_type == MediaType.MOVIE
    assert "District" in result.title
    assert result.year == 2009


# ─── 26. Show titles containing numbers ──────────────────────────────────────

def test_show_titles_containing_numbers() -> None:
    result = identify(_sr("Babylon.5.S01E01.720p.mkv"))
    assert result.media_type == MediaType.EPISODE
    assert "Babylon" in result.title
    assert result.season == 1
    assert result.episode == 1


# ─── 27. Release group at end ────────────────────────────────────────────────

def test_release_group_at_end() -> None:
    result = identify(_sr("Movie.2022.1080p.WEB-DL-GRP.mkv"))
    assert result.media_type == MediaType.MOVIE
    assert "GRP" not in result.title.lower() or "movie" in result.title.lower()


# ─── 28. Multiple technical tokens ───────────────────────────────────────────

def test_multiple_technical_tokens() -> None:
    result = identify(_sr("Film.2023.2160p.UHD.BluRay.REMUX.DV.HDR.HEVC.TrueHD-Team.mkv"))
    assert result.media_type == MediaType.MOVIE
    assert "Film" in result.title
    assert result.year == 2023


# ─── 29. TV wordy pattern ────────────────────────────────────────────────────

def test_tv_wordy_pattern() -> None:
    result = identify(_sr("Show Name Season 2 Episode 4.mkv"))
    assert result.media_type == MediaType.EPISODE
    assert result.season == 2
    assert result.episode == 4


# ─── 30. Normalize title function ────────────────────────────────────────────

def test_normalize_title() -> None:
    assert normalize_title("The.Dark.Knight") == "The Dark Knight"
    assert normalize_title("  spaces  ") == "spaces"
    assert normalize_title("a___b") == "a b"


# ─── 31. Unknown extension falls back to movie ───────────────────────────────

def test_unknown_extension_fallback() -> None:
    result = identify(_sr("Some.File.xyz", ext=".xyz"))
    assert result.media_type == MediaType.MOVIE
    assert result.confidence == 0.20


# ─── 32. Music fallback for audio without pattern ────────────────────────────

def test_music_fallback_no_pattern() -> None:
    result = identify(_sr("recording.mp3"))
    assert result.media_type == MediaType.MUSIC
    assert result.confidence < 0.50


# ─── 33. Music Artist - Album - Track ────────────────────────────────────────

def test_music_artist_album_track() -> None:
    result = identify(_sr("Pink Floyd - The Wall - Comfortably Numb.flac"))
    assert result.media_type == MediaType.MUSIC
    assert result.artist == "Pink Floyd"
    assert result.title == "Comfortably Numb"
    assert result.album == "The Wall"


# ─── 34. TV episode with Season wordy in directory ───────────────────────────

def test_tv_season_wordy_in_parent() -> None:
    result = identify(
        _sr("S01E01.mkv"),
        parent_parts=["Breaking Bad", "Season 01"],
    )
    assert result.media_type == MediaType.EPISODE
    assert result.confidence >= 0.90


# ─── 35. Edge case - no false SxxExx from regular words ──────────────────────

def test_no_false_episode_from_regular_words() -> None:
    result = identify(_sr("Small.Ordinal.Number.2020.mkv"))
    assert result.media_type == MediaType.MOVIE
    assert result.year == 2020
