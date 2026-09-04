"""Read-side data layer: maps the frozen backend to screen data.

Every function returns plain EntityRef display models or small dataclasses.
No SQL is executed here — only frozen backend service/repository contracts
(wired by composition.py) are used.

Documented adaptations to the frozen backend:
  * Listing all movies/shows/people uses ``search(query="")`` — the frozen
    SearchService API; an empty query returns the full set ordered by title.
  * "Most Watched" / "Recently Played" are produced client-side by
    joining StatisticsService.most_watched()/recent_playback().
  * "Rating" sorting is intentionally NOT offered (no rating column exists
    in the frozen schema).
  * Artwork comes from MetadataRepository.list_artwork (the only frozen
    artwork read contract) plus the local asset cache; never a provider.
"""
from __future__ import annotations

import logging
import os
from types import SimpleNamespace
from typing import Any

from ui.models import EntityRef
from ui.utils.formatting import join_meta

log = logging.getLogger("jpml.ui.data")


# ---------------------------------------------------------------------------
# Resilience — one failing lookup must not kill a whole screen
# ---------------------------------------------------------------------------


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:  # noqa: BLE001 — UI must survive any single lookup
        log.warning("data lookup failed", exc_info=True)
        return default


def _artwork_for(metadata_repo, entity_type: str, entity_id: int, kind: str):
    rows = _safe(lambda: metadata_repo.list_artwork(entity_type, entity_id), [])
    if not rows:
        return None
    want = kind if kind in ("poster", "backdrop") else "poster"
    for row in rows:
        if row.get("artwork_type") == want:
            return row
    return rows[0]


def _enrich(ref: EntityRef, metadata_repo, kind: str) -> EntityRef:
    art_kind = "backdrop" if kind == "backdrop" else "poster"
    ref.artwork = _artwork_for(metadata_repo, ref.kind, ref.entity_id, art_kind)
    return ref


# ---------------------------------------------------------------------------
# id-maps (cached per call) — the frozen listing API
# ---------------------------------------------------------------------------


def movies_by_id(services) -> dict[int, Any]:
    rows = _safe(lambda: services.search.search_movies("", limit=100000), [])
    return {r.entity_id: r for r in rows}


def shows_by_id(services) -> dict[int, Any]:
    rows = _safe(lambda: services.search.search_tv_shows("", limit=100000), [])
    return {r.entity_id: r for r in rows}


# ---------------------------------------------------------------------------
# Search (query-driven) — same mapping as listings, filtered
# ---------------------------------------------------------------------------


def search_movies(services, query: str, limit: int = 100000) -> list[EntityRef]:
    rows = _safe(lambda: services.search.search_movies(query, limit=limit), [])
    refs = [
        EntityRef(
            kind="movie",
            entity_id=r.entity_id,
            title=r.title,
            year=r.year,
            overview=r.overview,
            meta=join_meta(str(r.year) if r.year else None),
            artwork_kind="poster",
        )
        for r in rows
    ]
    refs = [_enrich(r, services.metadata_repository, "poster") for r in refs]
    return refs


def search_tv_shows(services, query: str, limit: int = 100000) -> list[EntityRef]:
    rows = _safe(lambda: services.search.search_tv_shows(query, limit=limit), [])
    refs = [
        EntityRef(
            kind="tv",
            entity_id=r.entity_id,
            title=r.title,
            year=r.year,
            overview=r.overview,
            meta=join_meta(str(r.year) if r.year else None),
            artwork_kind="poster",
        )
        for r in rows
    ]
    refs = [_enrich(r, services.metadata_repository, "poster") for r in refs]
    return refs


def search_people(services, query: str, limit: int = 100000) -> list[EntityRef]:
    rows = _safe(lambda: services.search.search_people(query, limit=limit), [])
    return [
        EntityRef(
            kind="person",
            entity_id=r.entity_id,
            title=r.title,
            overview=r.overview,
            meta="",
            artwork_kind="person",
        )
        for r in rows
    ]


def search_albums(services, query: str, limit: int = 100000) -> list[EntityRef]:
    rows = _safe(lambda: services.music.search_albums(query, limit=limit), [])
    refs = [
        EntityRef(
            kind="album",
            entity_id=a.id,
            title=a.title,
            year=a.year,
            meta=(a.artist.name if a.artist is not None else ""),
            artwork_kind="album",
        )
        for a in rows
    ]
    for ref in refs:
        ref.artwork = _artwork_for(services.metadata_repository, "album", ref.entity_id, "poster")
    return refs


def search_tracks(services, query: str, limit: int = 100000):
    return _safe(lambda: services.music.search_tracks(query, limit=limit), [])


def search_music(services, query: str):
    rows = _safe(lambda: services.search.search_music(query, limit=50), [])
    return rows


# ---------------------------------------------------------------------------
# Library listings
# ---------------------------------------------------------------------------


def fetch_movies(services, *, sort: str = "title") -> list[EntityRef]:
    rows = _safe(lambda: services.search.search_movies("", limit=100000), [])
    refs = [
        EntityRef(
            kind="movie",
            entity_id=r.entity_id,
            title=r.title,
            year=r.year,
            overview=r.overview,
            meta=join_meta(str(r.year) if r.year else None),
            artwork_kind="poster",
        )
        for r in rows
    ]
    refs = [_enrich(r, services.metadata_repository, "poster") for r in refs]
    refs = decorate_progress(services, refs)
    refs = _sort_refs(services, refs, sort)
    return refs


def fetch_tv_shows(services) -> list[EntityRef]:
    rows = _safe(lambda: services.search.search_tv_shows("", limit=100000), [])
    refs = [
        EntityRef(
            kind="tv",
            entity_id=r.entity_id,
            title=r.title,
            year=r.year,
            overview=r.overview,
            meta=join_meta(str(r.year) if r.year else None),
            artwork_kind="poster",
        )
        for r in rows
    ]
    refs = [_enrich(r, services.metadata_repository, "poster") for r in refs]
    return decorate_progress(services, refs)


def fetch_people(services) -> list[EntityRef]:
    rows = _safe(lambda: services.search.search_people("", limit=100000), [])
    return [
        EntityRef(
            kind="person",
            entity_id=r.entity_id,
            title=r.title,
            overview=r.overview,
            meta="",
            artwork_kind="person",
        )
        for r in rows
    ]


def _sort_refs(services, refs: list[EntityRef], sort: str) -> list[EntityRef]:
    if sort == "year":
        refs.sort(key=lambda e: (e.year is None, -(e.year or 0), e.title))
    elif sort == "most_watched":
        counts = _play_counts(services)
        refs.sort(key=lambda e: (-counts.get(e.key(), 0), e.title))
    elif sort == "recently_played":
        order = _recent_order(services)
        refs.sort(key=lambda e: (1 << 30 if e.key() not in order else order[e.key()], e.title))
    # "title" is the natural backend order
    return refs


def _play_counts(services) -> dict[tuple[str, int], int]:
    rows = _safe(lambda: services.statistics.most_watched(1000), [])
    return {(str(r["media_type"]), int(r["media_id"])): int(r["plays"]) for r in rows}


def _recent_order(services) -> dict[tuple[str, int], int]:
    rows = _safe(lambda: services.statistics.recent_playback(1000), [])
    order: dict[tuple[str, int], int] = {}
    for i, row in enumerate(rows):
        order[(str(row["media_type"]), int(row["media_id"]))] = i
    return order


# ---------------------------------------------------------------------------
# Music
# ---------------------------------------------------------------------------


def fetch_artists(services) -> list[EntityRef]:
    artists = _safe(lambda: services.music.search_artists("", limit=100000), [])
    refs = [
        EntityRef(
            kind="artist",
            entity_id=a.id,
            title=a.name,
            overview=a.biography,
            meta="",
            artwork_kind="artist",
        )
        for a in artists
    ]
    for ref in refs:
        ref.artwork = _artwork_for(services.metadata_repository, "artist", ref.entity_id, "poster")
    refs.sort(key=lambda r: r.title.lower())
    return refs


def fetch_albums(services) -> list[EntityRef]:
    albums = _safe(lambda: services.music.search_albums("", limit=100000), [])
    refs = [
        EntityRef(
            kind="album",
            entity_id=a.id,
            title=a.title,
            year=a.year,
            meta=(a.artist.name if a.artist is not None else ""),
            artwork_kind="album",
            extra={"artist_id": a.artist_id} if a.artist_id else {},
        )
        for a in albums
    ]
    for ref in refs:
        ref.artwork = _artwork_for(services.metadata_repository, "album", ref.entity_id, "poster")
    refs.sort(key=lambda r: (r.meta.lower(), r.title.lower()))
    return refs


def fetch_tracks(services) -> list[EntityRef]:
    tracks = _safe(lambda: services.music.search_tracks("", limit=100000), [])
    refs = []
    for t in tracks:
        refs.append(
            EntityRef(
                kind="track",
                entity_id=t.id,
                title=t.title,
                year=t.year,
                meta=(t.artist.name if t.artist is not None else ""),
                artwork_kind="album",
                extra={
                    "album_name": t.album.title if t.album is not None else "",
                    "track_number": t.track_number,
                    "duration_seconds": t.duration_seconds,
                },
            )
        )
    refs.sort(key=lambda r: (r.extra.get("album_name", ""), r.title.lower()))
    return refs


def fetch_recently_played_music(services) -> list[EntityRef]:
    rows = _safe(lambda: services.statistics.recent_playback(50), [])
    refs: list[EntityRef] = []
    seen: set[int] = set()
    for row in rows:
        if row["media_type"] != "track":
            continue
        track_id = int(row["media_id"])
        if track_id in seen:
            continue
        seen.add(track_id)
        track = _safe(lambda: services.music.get_track(track_id))
        if track is None:
            continue
        refs.append(
            EntityRef(
                kind="track",
                entity_id=track_id,
                title=track.title,
                meta=(track.artist.name if track.artist else ""),
                artwork_kind="album",
                extra={"album_name": track.album.title if track.album else ""},
            )
        )
    return refs


# ---------------------------------------------------------------------------
# Playback / discovery rows
# ---------------------------------------------------------------------------


def fetch_continue_watching(services) -> list[EntityRef]:
    candidates = _safe(lambda: services.playback_repository.get_resume_candidates(40), [])
    if not candidates:
        return []
    movies = movies_by_id(services)
    shows = shows_by_id(services)
    refs: list[EntityRef] = []
    for cand in candidates:
        ref = _ref_from_candidate(services, cand, movies, shows)
        if ref is not None:
            refs.append(ref)
    return refs


def _ref_from_candidate(services, cand, movies, shows):
    from ui.utils.formatting import format_seconds

    mtype = str(cand["media_type"])
    mid = int(cand["media_id"])
    position = float(cand.get("last_position") or 0.0)
    duration = float(cand.get("duration") or 0.0)
    ref: EntityRef | None
    if mtype == "movie" and mid in movies:
        s = movies[mid]
        ref = EntityRef(kind="movie", entity_id=mid, title=s.title, year=s.year,
                        artwork_kind="poster")
    elif mtype == "tv" and mid in shows:
        s = shows[mid]
        ref = EntityRef(kind="tv", entity_id=mid, title=s.title, year=s.year,
                        artwork_kind="poster")
    elif mtype == "track":
        track = _safe(lambda: services.music.get_track(mid))
        if track is None:
            return None
        ref = EntityRef(
            kind="track", entity_id=mid, title=track.title,
            meta=(track.artist.name if track.artist else ""), artwork_kind="album",
            extra={"album_name": track.album.title if track.album else ""},
        )
    else:
        return None
    ref.file_path = cand.get("file_path")
    ref.progress = (position / duration) if duration > 0 else None
    ref.progress_label = (
        f"{format_seconds(duration - position)} left"
        if duration > 0
        else f"{format_seconds(position)} in"
    )
    _enrich(ref, services.metadata_repository, "poster")
    return ref


def fetch_recently_added(services) -> list[EntityRef]:
    items = _safe(lambda: services.discovery_repository.get_newest_added(30), [])
    movies = movies_by_id(services)
    shows = shows_by_id(services)
    refs = []
    for item in items:
        if item.entity_type == "movie" and item.entity_id in movies:
            s = movies[item.entity_id]
            ref = EntityRef(kind="movie", entity_id=item.entity_id, title=s.title,
                            year=s.year, artwork_kind="poster")
        elif item.entity_type == "tv" and item.entity_id in shows:
            s = shows[item.entity_id]
            ref = EntityRef(kind="tv", entity_id=item.entity_id, title=s.title,
                            year=s.year, artwork_kind="poster")
        else:
            continue
        _enrich(ref, services.metadata_repository, "poster")
        refs.append(ref)
    return refs


def fetch_trending(services) -> list[EntityRef]:
    items = _safe(lambda: services.discovery.trending(24), [])
    refs: list[EntityRef] = []
    movies = movies_by_id(services)
    shows = shows_by_id(services)
    for item in items:
        if item.entity_type == "movie" and item.entity_id in movies:
            s = movies[item.entity_id]
            ref = EntityRef(kind="movie", entity_id=item.entity_id, title=s.title,
                            year=s.year, artwork_kind="poster")
        elif item.entity_type == "tv" and item.entity_id in shows:
            s = shows[item.entity_id]
            ref = EntityRef(kind="tv", entity_id=item.entity_id, title=s.title,
                            year=s.year, artwork_kind="poster")
        elif item.entity_type == "track":
            track = _safe(lambda: services.music.get_track(item.entity_id))
            if track is None:
                continue
            ref = EntityRef(
                kind="track", entity_id=item.entity_id, title=track.title,
                meta=(track.artist.name if track.artist else ""), artwork_kind="album",
            )
        else:
            continue
        ref.extra["reason"] = item.reason
        _enrich(ref, services.metadata_repository, "poster")
        refs.append(ref)
    return refs


def fetch_recommendations(services, reference: EntityRef | None = None) -> list[EntityRef]:
    recs: list[Any] = []
    if reference is not None and reference.kind in ("movie", "tv"):
        recs = _safe(lambda: services.discovery.recommendations(
            reference.kind, reference.entity_id, 24), [])
    movies = movies_by_id(services)
    shows = shows_by_id(services)
    refs: list[EntityRef] = []
    seen = set()
    for rec in recs:
        table = movies if rec.entity_type == "movie" else shows
        src = table.get(rec.entity_id)
        if src is None or (rec.entity_type, rec.entity_id) in seen:
            continue
        seen.add((rec.entity_type, rec.entity_id))
        ref = _enrich(
            EntityRef(kind=rec.entity_type, entity_id=rec.entity_id, title=src.title,
                      year=src.year, artwork_kind="poster"),
            services.metadata_repository, "poster",
        )
        ref.extra["reason"] = rec.reason
        refs.append(ref)
        if len(refs) >= 24:
            break
    return refs


def fetch_similar(services, reference: EntityRef) -> list[EntityRef]:
    if reference.kind not in ("movie", "tv"):
        return []
    return fetch_recommendations(services, reference=reference)


# ---------------------------------------------------------------------------
# Personal lists
# ---------------------------------------------------------------------------


def _ref_for_entry(services, entry) -> EntityRef | None:
    kind = entry.entity_type
    eid = entry.entity_id
    if kind in ("movie", "tv"):
        table = movies_by_id(services) if kind == "movie" else shows_by_id(services)
        s = table.get(eid)
        if s is None:
            return None
        ref = EntityRef(kind=kind, entity_id=eid, title=s.title, year=s.year,
                        artwork_kind="poster")
        _enrich(ref, services.metadata_repository, "poster")
        return ref
    if kind == "artist":
        obj = _safe(lambda: services.music.get_artist(eid))
        if obj is None:
            return None
        ref = EntityRef(kind=kind, entity_id=eid, title=obj.name, overview=obj.biography,
                        artwork_kind="artist")
    elif kind == "album":
        obj = _safe(lambda: services.music.get_album(eid))
        if obj is None:
            return None
        ref = EntityRef(kind=kind, entity_id=eid, title=obj.title, year=obj.year,
                        meta=(obj.artist.name if obj.artist else ""), artwork_kind="album")
    elif kind == "track":
        obj = _safe(lambda: services.music.get_track(eid))
        if obj is None:
            return None
        ref = EntityRef(kind=kind, entity_id=eid, title=obj.title,
                        meta=(obj.artist.name if obj.artist else ""), artwork_kind="album",
                        extra={"album_name": obj.album.title if obj.album else ""})
    else:
        return None
    ref.artwork = _artwork_for(services.metadata_repository, kind, eid, "poster")
    return ref


def fetch_favorites(services) -> list[EntityRef]:
    entries = _safe(lambda: services.favorites.list(), [])
    refs = []
    for entry in entries:
        ref = _ref_for_entry(services, entry)
        if ref is not None:
            ref.is_favorite = True
            refs.append(ref)
    return refs


def fetch_watchlist(services) -> list[EntityRef]:
    entries = _safe(lambda: services.watchlist.list(), [])
    refs = []
    for entry in entries:
        ref = _ref_for_entry(services, entry)
        if ref is not None:
            ref.in_watchlist = True
            refs.append(ref)
    return refs


def fetch_collections(services) -> list[Any]:
    return _safe(lambda: services.collections.list(), [])


def fetch_collection_items(services, collection_id: int) -> list[EntityRef]:
    items = _safe(lambda: services.collections.list_items(collection_id), [])
    refs = []
    for item in items:
        entry = SimpleNamespace(entity_type=item.entity_type, entity_id=item.entity_id)
        ref = _ref_for_entry(services, entry)
        if ref is not None:
            refs.append(ref)
    return refs


# ---------------------------------------------------------------------------
# Progress / state decoration
# ---------------------------------------------------------------------------


def decorate_progress(services, refs: list[EntityRef]) -> list[EntityRef]:
    from ui.utils.formatting import format_seconds

    history = _safe(lambda: services.playback_repository.get_resume_candidates(1000), [])
    progress: dict[tuple[str, int], tuple[float, float]] = {}
    for row in history:
        duration = float(row.get("duration") or 0.0)
        position = float(row.get("last_position") or 0.0)
        progress[(str(row["media_type"]), int(row["media_id"]))] = (position, duration)
    for ref in refs:
        pd = progress.get((ref.kind, ref.entity_id))
        if pd is not None:
            position, duration = pd
            if duration > 0:
                ref.progress = min(1.0, position / duration)
            ref.progress_label = (
                f"{format_seconds(duration - position)} left"
                if duration > 0
                else f"{format_seconds(position)} in"
            )
        ref.completed = _safe(
            lambda r=ref: services.playback_repository.is_completed(r.kind, r.entity_id),
            False,
        )
    _flag_favorites(services, refs)
    return refs


def _flag_favorites(services, refs: list[EntityRef]) -> None:
    try:
        fav = {(e.entity_type, e.entity_id) for e in services.favorites.list()}
        wl = {(e.entity_type, e.entity_id) for e in services.watchlist.list()}
    except Exception:  # noqa: BLE001
        return
    for ref in refs:
        ref.is_favorite = ref.key() in fav
        ref.in_watchlist = ref.key() in wl


# ---------------------------------------------------------------------------
# Details + playback file resolution
# ---------------------------------------------------------------------------


def entity_ref_for_details(services, kind: str, entity_id: int) -> EntityRef | None:
    if kind in ("movie", "tv"):
        table = movies_by_id(services) if kind == "movie" else shows_by_id(services)
        s = table.get(entity_id)
        if s is None:
            return None
        ref = _enrich(
            EntityRef(kind=kind, entity_id=entity_id, title=s.title, year=s.year,
                      overview=s.overview, artwork_kind="poster"),
            services.metadata_repository, "poster",
        )
        rows = _safe(lambda: services.metadata_repository.list_artwork(kind, entity_id), [])
        backdrop = next((r for r in rows if r.get("artwork_type") == "backdrop"), None)
        if backdrop:
            ref.extra["backdrop"] = backdrop
        return decorate_progress(services, [ref])[0]
    if kind == "track":
        track = _safe(lambda: services.music.get_track(entity_id))
        if track is None:
            return None
        ref = EntityRef(kind=kind, entity_id=entity_id, title=track.title, year=track.year,
                        meta=(track.artist.name if track.artist else ""),
                        artwork_kind="album",
                        extra={"album_name": track.album.title if track.album else ""})
        ref.artwork = _artwork_for(services.metadata_repository, "album",
                                   track.album_id or 0, "poster")
        return decorate_progress(services, [ref])[0]
    if kind == "album":
        album = _safe(lambda: services.music.get_album(entity_id))
        if album is None:
            return None
        ref = EntityRef(kind=kind, entity_id=entity_id, title=album.title, year=album.year,
                        meta=(album.artist.name if album.artist else ""), artwork_kind="album")
        ref.artwork = _artwork_for(services.metadata_repository, "album", entity_id, "poster")
        return decorate_progress(services, [ref])[0]
    if kind == "artist":
        artist = _safe(lambda: services.music.get_artist(entity_id))
        if artist is None:
            return None
        ref = EntityRef(kind=kind, entity_id=entity_id, title=artist.name,
                        overview=artist.biography, artwork_kind="artist")
        ref.artwork = _artwork_for(services.metadata_repository, "artist", entity_id, "poster")
        return ref
    if kind == "person":
        rows = _safe(lambda: services.search.search_people("", limit=100000), [])
        for row in rows:
            if row.entity_id == entity_id:
                return EntityRef(kind="person", entity_id=entity_id, title=row.title,
                                 overview=row.overview, artwork_kind="person")
    return None


def fetch_movie_genres(services, movie_id: int) -> list[str]:
    return _safe(lambda: services.metadata_repository.get_movie_genres(movie_id), [])


def fetch_tv_genres(services, tv_id: int) -> list[str]:
    return _safe(lambda: services.metadata_repository.get_tv_genres(tv_id), [])


def resolve_play_file(services, ref: EntityRef) -> str | None:
    """Resolve a real, existing playable file for an entity.

    Uses only frozen read contracts. Returns None when no usable file can
    be found (the UI then shows the unavailable-file state instead of
    pretending playback succeeded).

    Resolution order:
      1. A known file_path on the ref (from Continue Watching / playback
         history) that still exists on disk.
      2. For music: MusicRepository.list_files_for_track().
      3. A file in playback history for the same entity that still exists.
      4. A deterministic filename match across the library (the identifier
         derives titles from filenames, so the library's own naming is the
         signal). Shortest matching filename wins.
    """
    if ref.file_path and os.path.isfile(ref.file_path):
        return ref.file_path

    if ref.kind == "track":
        files = _safe(lambda: services.music_repository.list_files_for_track(ref.entity_id), [])
        for f in files:
            if f and os.path.isfile(f.path):
                return f.path
        return None

    if ref.kind in ("movie", "tv", "episode"):
        for cand in _safe(lambda: services.playback_repository.get_resume_candidates(500), []):
            if (
                str(cand.get("media_type")) == ref.kind
                and int(cand.get("media_id")) == ref.entity_id
                and cand.get("file_path")
                and os.path.isfile(str(cand["file_path"]))
            ):
                return str(cand["file_path"])
        title = (ref.title or "").strip().lower()
        if title:
            files = _safe(lambda: services.media_repository.list_all(), [])
            candidates = [
                f
                for f in files
                if f.path and title in (f.filename or "").lower()
            ]
            if candidates:
                candidates.sort(key=lambda f: (len(f.filename or ""), f.path))
                best = candidates[0]
                if os.path.isfile(best.path):
                    return best.path
    return None


def library_is_empty(services) -> bool:
    stats = _safe(lambda: services.statistics.library())
    if stats is None:
        return True
    return (
        stats.total_movies == 0
        and stats.total_tv_shows == 0
        and stats.total_tracks == 0
    )
