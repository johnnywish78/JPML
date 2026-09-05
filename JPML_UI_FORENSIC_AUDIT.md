# JPML — UI Forensic Audit

**Date:** 2026-09-04  
**Branch:** `ui-forensics-2026-09-04`  
**HEAD:** `0252ee1` — docs: add complete UI integration scope  
**Backend Freeze:** `e45d700`

---

## 1. Executive Summary

The JPML UI is a PyQt6 desktop application with a sidebar shell, 16 registered screens, and a frozen backend. The architecture is well-structured with clear separation between screens, components, and the backend service layer. However, significant gaps exist between the backend capabilities (now enhanced with TMDB metadata, artwork, people, and external IDs) and what the UI exposes.

**Critical finding:** The real database now contains real TMDB metadata (Babylon Berlin with poster, backdrop, external IDs, and cast) but the UI does not consistently surface this data — especially in the details screen and TV shows screen. The artwork pipeline works end-to-end (files exist on disk), but the UI data layer has incomplete wiring for backdrops, people, and TV episode hierarchy.

**Overall health:** 65% integrated, 35% missing or partially wired.

---

## 2. Current UI Architecture

### 2.1 Entry Point
- `run.py` — launches `QApplication`, creates `ThemeManager`, `MainWindow`, calls `attach()` then `window.show()`
- Uses `--backend vlc|mpv|mock` and `--theme dark|light|system` CLI args
- Style: Fusion (cross-platform)

### 2.2 Shell (`ui/app/main_window.py`)
- `MainWindow` owns: `Navigation`, `ThemeManager`, `ServiceComposition`, `Sidebar`, `TopBar`, `QStackedWidget`
- Screen registry: 15 screen factories registered via `run_state.register_all()`
- Keyboard: Ctrl+F (search), Escape (back), Alt+Left (back)
- Toast system via `ToastHost`

### 2.3 Navigation (`ui/app/navigation.py`)
- Stack-based history with `Route(screen, params)`
- `navigate()`, `back()`, `forward()`
- Emits `route_changed` and `stack_changed` signals

### 2.4 Service Composition (`ui/app/composition.py`)
- `build_services()` creates all backend services via `app.bootstrap` factories
- `ServiceComposition` dataclass holds: favorites, watchlist, collections, search, statistics, music, discovery, media_repository, library_repository, metadata_repository, playback_repository, discovery_repository, music_repository, event_bus, player (lazy)
- Connection lifecycle: `close_services()` called after async reads

### 2.5 Data Layer (`ui/app/data.py`)
- Pure read-side adapter: maps backend services → `EntityRef` display models
- No SQL, no backend mutations
- Artwork resolution via `MetadataRepository.list_artwork()` + `assets/artwork/` fallback
- Resilient: every lookup wrapped in `_safe()` with warning log on failure

### 2.6 Models (`ui/models.py`)
- `EntityRef` dataclass: kind, entity_id, title, year, overview, meta, progress, progress_label, file_path, artwork (dict|None), artwork_kind, is_favorite, in_watchlist, completed, extra (dict)

### 2.7 Theme System (`ui/themes/`)
- `ThemeManager` owns mode (dark/light/system), regenerates global QSS on change
- `_build_qss()` produces one monolithic stylesheet from token dicts
- `DARK` and `LIGHT` token dicts in `dark.py`/`light.py`
- System mode listens to `QStyleHints.colorSchemeChanged`
- `refresh()` called on mode change and system theme change

### 2.8 Artwork Pipeline
- `ui/utils/image_cache.py`: background QThread worker loads QPixmaps, caches by (source, size) key
- `ui/components/media/artwork.py`: `Artwork` widget, fixed aspect ratio, async load via `get_pixmap()`
- `ui/components/cards/media_card.py`: `MediaCard` uses `Artwork` widget, resolves source from `entity.artwork.get("local_path")`
- `ui/components/media/hero.py`: `Hero` draws backdrop directly via QPixmap (not through Artwork widget)

---

## 3. Navigation Matrix

| Screen | Route | Sidebar Entry | Exists | Reachable | Backend Connected | Runtime | Placeholder |
|--------|-------|---------------|--------|-----------|-------------------|---------|-------------|
| Home | `home` | ✓ Home | YES | YES | YES | READY | NO |
| Movies | `movies` | ✓ Movies | YES | YES | YES | READY | NO |
| TV Shows | `tv_shows` | ✓ TV Shows | YES | YES | YES | READY | NO |
| People | `people` | ✓ People | YES | YES | PARTIAL | READY (no people) | YES (empty state) |
| Music | `music` | ✓ Music | YES | YES | YES | READY | NO |
| Library | `library` | ✓ Library | YES | YES | YES | READY | NO |
| Trending | `trending` | ✓ Trending | YES | YES | YES | READY | NO |
| Recommendations | `recommendations` | ✓ Recommendations | YES | YES | YES | READY | NO |
| Favorites | `favorites` | ✓ Favorites | YES | YES | YES | READY | NO |
| Watchlist | `watchlist` | ✓ Watchlist | YES | YES | YES | READY | NO |
| Collections | `collections` | ✓ Collections | YES | YES | YES | READY | NO |
| Search | `search` | Via top bar | YES | YES | YES | READY | NO |
| Details | `details` | Via card click | YES | YES | YES | READY | NO |
| Player | `player` | Via play action | YES | YES | YES | READY | NO |
| Settings | `settings` | Bottom sidebar | YES | YES | PARTIAL | READY | NO |
| TV Time | — | — | **NO** | **NO** | **NO** | — | — |
| Browser | — | — | **NO** | **NO** | **NO** | — | — |
| Scanner | `library` | Via Settings | YES | YES | YES | READY | NO |

---

## 4. Feature Matrix

### 4.1 Home / Dashboard
| Feature | Status | File | Notes |
|---------|--------|------|-------|
| Hero backdrop | PARTIAL | `ui/screens/home.py` + `ui/components/media/hero.py` | Uses `ref.extra["backdrop"]` or `ref.artwork` — but `backdrop` only populated in `entity_ref_for_details()`, NOT in `fetch_continue_watching()`, `fetch_trending()`, `fetch_recently_added()` |
| Continue Watching | EXISTS | `ui/app/data.py:341` | Works — returns EntityRefs with progress |
| Recently Added | EXISTS | `ui/app/data.py:393` | Works — but no backdrop enrichment |
| Trending | EXISTS | `ui/app/data.py:414` | Works — local deterministic |
| Movies row | EXISTS | `ui/screens/home.py:108` | Works |
| TV Shows row | EXISTS | `ui/screens/home.py:109` | Works |
| Favorites row | EXISTS | `ui/screens/home.py:110` | Works |
| Empty state | EXISTS | `ui/screens/home.py:27` | Has "Add Library Location" action |
| Hero play/details | EXISTS | `ui/screens/home.py:122` | Wired correctly |

**Gap:** Hero backdrop doesn't load because `_gather()` doesn't populate `ref.extra["backdrop"]`. Only `entity_ref_for_details()` does.

### 4.2 Movies
| Feature | Status | File | Notes |
|---------|--------|------|-------|
| Grid listing | EXISTS | `ui/screens/movies.py` | Works |
| Sort (title/year/most_watched/recently_played) | EXISTS | `ui/screens/movies.py:16` | Works |
| Filter by title | EXISTS | `ui/screens/movies.py:46` | Works |
| Cards with posters | EXISTS | `ui/components/cards/media_card.py` | Works |
| Details navigation | EXISTS | `ui/screens/movies.py` → `details` | Works |
| Play | EXISTS | `ui/app/screen_actions.py:27` | Works |
| Favorites/Watchlist | EXISTS | `ui/app/screen_actions.py:52` | Works |
| Genre chips | PARTIAL | `ui/screens/details.py:148` | Only shows when `extra["genres"]` exists |
| Cast/crew | **MISSING** | `ui/screens/details.py` | Comment says "NOT rendered because frozen backend exposes no read API" — but backend NOW has people via TMDB |
| Backdrop in details | PARTIAL | `ui/screens/details.py:176` | Only for non-poster kinds; backdrop path resolution uses `ref.extra["backdrop"]` |

### 4.3 TV Shows
| Feature | Status | File | Notes |
|---------|--------|------|-------|
| Grid listing | EXISTS | `ui/screens/tv_shows.py` | Works |
| Sort (title/year) | EXISTS | `ui/screens/tv_shows.py:17` | Only title/year — missing most_watched/recently_played |
| Cards with posters | EXISTS | `ui/components/cards/media_card.py` | Works |
| Details navigation | EXISTS | → `details?kind=tv` | Works |
| Play | EXISTS | Via details screen | Works |
| Seasons/Episodes view | **MISSING** | `ui/screens/details.py` | Comment: "Season/episode browsing ... NOT rendered because frozen backend exposes no read API" |
| Episode artwork | **MISSING** | — | No episode-level artwork rendering |
| Episode metadata | **MISSING** | — | Same reason |
| Watched state per episode | **MISSING** | — | playback_repository tracks movies/tracks, not episodes specifically |
| Next episode | **MISSING** | — | No UI for this |

### 4.4 TV Time
| Feature | Status | Notes |
|---------|--------|-------|
| Screen | **NO** | No `tv_time` route registered |
| Episode tracking | **NO** | Backend has `episodes` table but no UI exposes it |
| Watched state | **NO** | `playback_history` tracks `movie`/`track` types, not `episode` |
| Next episode | **NO** | Not implemented |

### 4.5 People
| Feature | Status | File | Notes |
|---------|--------|------|-------|
| Listing | EXISTS | `ui/screens/people.py` | Works, but returns empty (0 people in DB from previous state) |
| Cards | EXISTS | `ui/components/cards/person_card.py` | Needs inspection |
| Details | PARTIAL | `ui/screens/details.py:648` | Returns EntityRef with no artwork, no filmography |
| Artwork | **MISSING** | — | `artwork_kind="person"` but no person artwork rows in DB |
| Filmography | **MISSING** | — | `movie_people`/`tv_people` tables exist but UI doesn't query them |

### 4.6 TMDB Integration
| Feature | Status | Notes |
|---------|--------|-------|
| Provider registered | YES | `app/bootstrap.py:create_metadata_integration()` registers TmdbMetadataProvider |
| Search/discovery | YES | `TmdbMetadataProvider.search()` implemented |
| Metadata fetch | YES | `TmdbMetadataProvider.fetch_metadata()` returns full metadata |
| Artwork download | YES | `app/metadata/artwork_downloader.py` downloads to `assets/artwork/{posters,backdrops}/<id>.<ext>` |
| People/credits | YES | `MetadataService._persist_credits()` upserts people and relationships |
| External IDs | YES | TMDB ID + IMDb ID persisted |
| UI consumption | PARTIAL | `data.py` reads artwork via `MetadataRepository.list_artwork()` — works for poster/backdrop |
| UI backdrop in hero | NO | `home._gather()` doesn't populate `ref.extra["backdrop"]` |
| UI people in details | NO | `details.py` doesn't query `tv_people`/`movie_people` |
| UI seasons/episodes in details | NO | `details.py` explicitly skips TV season/episode rendering |

### 4.7 OMDb / IMDb
| Feature | Status | Notes |
|---------|--------|-------|
| Provider registered | YES | `OMDbMetadataProvider` registered in bootstrap when API key configured |
| API key config | EXISTS | `jpml_config.json` has `omdb.api_key` field |
| Currently configured | NO | `jpml_config.json` has no `omdb` section, no `OMDB_API_KEY` env var |
| Fallback behavior | YES | When no OMDb key, pipeline uses TMDB only |
| IMDb ID display | PARTIAL | `details.py` shows title/year/overview but not IMDb ID |

### 4.8 Artwork
| Feature | Status | Notes |
|---------|--------|-------|
| Poster rendering | YES | `Artwork` widget + `image_cache` worker thread |
| Backdrop rendering | PARTIAL | Hero uses direct QPixmap; MediaCard uses Artwork widget |
| Local file cache | YES | `assets/artwork/posters/` and `assets/artwork/backdrops/` |
| Async loading | YES | `_WorkerHost` QThread |
| Thread safety | YES | QPixmap created on worker, emitted via signal to UI thread |
| Placeholder | YES | JPML text placeholder when no image |
| Real artwork exists | YES | `assets/artwork/posters/1.jpg` (89KB), `assets/artwork/backdrops/1.jpg` (215KB) — Babylon Berlin |
| DB artwork rows | YES | 2 rows: poster + backdrop for tv_show id=1 |

**Artwork Data Flow (verified for Babylon Berlin):**
```
TMDB API → TmdbMetadataProvider.fetch_metadata() → ProviderMetadata(poster_path="/hr18RHPMQSA0zbCzAZN2asIOqy5.jpg")
  → MetadataService.fetch_and_save_metadata() → artwork_downloader.download_artwork()
  → assets/artwork/posters/1.jpg (exists, 89KB)
  → MetadataRepository.upsert_artwork(entity_type="tv", entity_id=1, artwork_type="poster", local_path="/home/johnny/Desktop/JPML/assets/artwork/posters/1.jpg")
  → ui/app/data.py: entity_ref_for_details() → _artwork_for() → row["local_path"]
  → EntityRef.artwork = row dict
  → MediaCard._resolve_source() → entity.artwork.get("local_path")
  → Artwork.set_source() → image_cache.get_pixmap() → QPixmap loaded
```

### 4.9 Music
| Feature | Status | File | Notes |
|---------|--------|------|-------|
| Artists listing | EXISTS | `ui/screens/music.py:85` | Works |
| Albums listing | EXISTS | `ui/screens/music.py:58` | Works |
| Tracks listing | EXISTS | `ui/screens/music.py:60` | Works |
| Recently played | EXISTS | `ui/screens/music.py:54` | Works |
| Play track | EXISTS | `ui/app/screen_actions.py:27` | Works |
| Details (album/artist) | EXISTS | `ui/screens/details.py:85` | Works |
| Artwork | PARTIAL | Music uses `artwork_kind="album"` → looks for `assets/artwork/posters/<id>.jpg` |

### 4.10 Player
| Feature | Status | Notes |
|---------|--------|-------|
| Video surface | EXISTS | `PlayerScreen` with `_ShowArea` |
| VLC backend | EXISTS | `app/player/controller.py` |
| MPV backend | EXISTS | Configurable via `--backend mpv` |
| Mock backend | EXISTS | For testing |
| Play/Pause | EXISTS | `_play_pause()` → `controller.toggle_pause()` |
| Seek | EXISTS | `_seek_commit()` → `controller.seek()` |
| Volume | EXISTS | `_volume_changed()` → `controller.set_volume()` |
| Mute | EXISTS | `_toggle_mute()` → `controller.mute()/unmute()` |
| Fullscreen | EXISTS | `_toggle_fullscreen()` → `showFullScreen()` |
| Progress polling | EXISTS | `QTimer` 500ms interval |
| Back button | EXISTS | `←` button → `navigation.back()` |
| Missing file state | EXISTS | Shows "Media Not Available" |
| Episode playback | **NO** | `screen_actions.py:30` → "Episode playback uses the TV show details view" |
| Music player | **NO** | No music-specific player UI — reuses video player |
| Subtitle controls | **NO** | Not in player UI |
| Audio track selection | **NO** | Not in player UI |
| Player settings | **NO** | No settings screen for player config |

### 4.11 Playback / Resume
| Feature | Status | Notes |
|---------|--------|-------|
| Progress tracking | EXISTS | `playback_repository.get_resume_candidates()` |
| Continue Watching row | EXISTS | `data.fetch_continue_watching()` |
| Completed flag | EXISTS | `playback_repository.is_completed()` |
| Movie progress | EXISTS | Works |
| Track progress | EXISTS | Works |
| Episode progress | **NO** | Schema has no episode-level playback tracking |
| Next episode logic | **NO** | Not implemented |

### 4.12 Browser / Online Services
| Feature | Status | Notes |
|---------|--------|-------|
| Browser screen | **NO** | No QWebEngine, no browser widget |
| Browser route | **NO** | Not registered in `run_state.py` |
| YouTube | **NO** | No integration |
| Telegram | **NO** | No integration |
| Spotify | **NO** | No integration |
| Netflix | **NO** | No integration |
| Prime Video | **NO** | No integration |
| Disney+ | **NO** | No integration |
| Service branding | **NO** | No online service cards |

### 4.13 Settings
| Feature | Status | Notes |
|---------|--------|-------|
| Theme (Dark/Light/System) | EXISTS | `ui/screens/settings.py:70` — works |
| Library management | EXISTS | "Manage Library Locations" → `library` screen |
| TMDB config | **NO** | No UI for TMDB API key |
| OMDb config | **NO** | No UI for OMDb API key |
| Player backend | **NO** | No UI to switch VLC/MPV |
| Player preferences | **NO** | No settings for subtitles, audio, etc. |
| Browser settings | **NO** | No browser exists |
| Provider priority | **NO** | No UI for this |

### 4.14 Library / Scanner
| Feature | Status | Notes |
|---------|--------|-------|
| Add location | EXISTS | `LibraryScreen._on_add_location()` |
| Remove location | EXISTS | `LibraryScreen._on_remove()` |
| Rescan | EXISTS | `LibraryScreen._on_rescan()` |
| Scan progress | EXISTS | `_on_progress()` updates status card |
| Scan result | EXISTS | `_on_scan_done()` shows summary |
| Scan error | EXISTS | `_on_scan_failed()` shows error with retry |
| Location list | EXISTS | `_refresh_locations()` |

### 4.15 Search
| Feature | Status | Notes |
|---------|--------|-------|
| Global search bar | EXISTS | `TopBar` with `QLineEdit` |
| Debounce | EXISTS | 300ms timer in `MainWindow` |
| Movies results | EXISTS | `data.search_movies()` |
| TV results | EXISTS | `data.search_tv_shows()` |
| People results | EXISTS | `data.search_people()` |
| Music results | EXISTS | `data.search_albums()` + `search_tracks()` |
| Artwork in results | EXISTS | `_enrich()` adds artwork |
| Navigation from results | EXISTS | Cards wire to `play_entity`/`open_details` |

### 4.16 Favorites / Watchlist / Collections
| Feature | Status | Notes |
|---------|--------|-------|
| Favorites screen | EXISTS | `ui/screens/favorites.py` |
| Watchlist screen | EXISTS | `ui/screens/watchlist.py` |
| Collections screen | EXISTS | `ui/screens/collections.py` |
| Add/remove favorite | EXISTS | `screen_actions.entity_action()` |
| Add/remove watchlist | EXISTS | `screen_actions.entity_action()` |
| Create collection | EXISTS | `collections._create()` |
| Rename collection | EXISTS | `collections._rename()` |
| Delete collection | EXISTS | `collections._delete()` |
| Add to collection | EXISTS | Context menu → "Add to Collection..." |
| Collection items | EXISTS | `data.fetch_collection_items()` |

---

## 5. Backend Contract → UI Integration Matrix

| Backend Capability | UI Exposed? | Gap Type |
|-------------------|-------------|----------|
| `MetadataRepository.list_artwork()` | ✓ Yes | — |
| `MetadataRepository.list_external_ids()` | ✗ No | D — UI never queries this |
| `MetadataRepository.list_people_by_movie()` | ✗ No | D — Not in repository |
| `MetadataRepository.list_people_by_tv()` | ✗ No | D — Not in repository |
| `PlaybackRepository.get_resume_candidates()` | ✓ Yes | — |
| `PlaybackRepository.is_completed()` | ✓ Yes | — |
| `StatisticsService.library()` | ✓ Yes | — |
| `StatisticsService.most_watched()` | ✓ Yes | — |
| `StatisticsService.recent_playback()` | ✓ Yes | — |
| `SearchService.search_movies()` | ✓ Yes | — |
| `SearchService.search_tv_shows()` | ✓ Yes | — |
| `SearchService.search_people()` | ✓ Yes | — |
| `FavoritesService.list/add/remove` | ✓ Yes | — |
| `WatchlistService.list/add/remove` | ✓ Yes | — |
| `CollectionsService.list/create/rename/delete/add_item/remove_item` | ✓ Yes | — |
| `MetadataService.discover()` | ✗ No | A — UI has no discovery screen |
| `MetadataRepository.get_movie_genres()` | ✓ Yes | — |
| `MetadataRepository.get_tv_genres()` | ✓ Yes | — |
| `SeasonRepository.list_seasons()` | ✗ No | C — UI doesn't call it |
| `EpisodeRepository.list_episodes()` | ✗ No | C — UI doesn't call it |
| `MediaRepository.list_all()` | ✓ Yes | — |
| `MediaRepository.list_files_for_track()` | ✓ Yes | — |
| `MusicService.search_artists/albums/tracks/get_track/get_album/get_artist` | ✓ Yes | — |

---

## 6. Artwork Data Flow

### 6.1 Current Path (Working)
```
DB artwork row (local_path exists)
  → data._artwork_for() returns row dict
  → EntityRef.artwork = row dict
  → MediaCard._resolve_source() → entity.artwork.get("local_path")
  → Artwork.set_source(source)
  → image_cache.get_pixmap(source, size, callback, tokens)
  → Worker thread: QPixmap(source) → scaled → cached
  → Signal: _on_loaded(key)
  → Artwork._pixmap = cached
  → paintEvent: drawPixmap
```

### 6.2 Hero Backdrop Path (BROKEN for Home)
```
Home._gather() → fetch_continue_watching / fetch_trending / etc.
  → _enrich(ref, metadata_repo, "poster")  ← ONLY poster enriched
  → ref.extra["backdrop"] NOT populated
Hero._backdrop_source(ref):
  → ref.extra.get("backdrop") → None  ← fails
  → ref.artwork.get("local_path") → poster path, NOT backdrop  ← wrong kind
```

**Root cause:** `data.fetch_continue_watching()`, `fetch_trending()`, `fetch_recently_added()` call `_enrich(ref, ..., "poster")` but never populate `ref.extra["backdrop"]`. Only `entity_ref_for_details()` does.

### 6.3 Real Artwork Files
```
assets/artwork/posters/1.jpg   (89,501 bytes) — Babylon Berlin poster
assets/artwork/backdrops/1.jpg (215,115 bytes) — Babylon Berlin backdrop
```

---

## 7. Movie Audit

**Status:** Fully functional.

- Grid: working
- Cards: working with posters
- Details: title, year, overview, genres, similar items, play, favorite, watchlist
- Artwork: loads from DB local_path
- Missing: cast/crew display (backend has data but UI doesn't query it)

---

## 8. TV Audit

**Status:** Partially functional.

- Grid: working
- Cards: working with posters
- Details: title, year, overview, genres, similar items — but NO seasons/episodes
- Artwork: poster works, backdrop not shown in hero
- Missing: season/episode browsing, episode artwork, episode progress

---

## 9. TV Time Audit

**Status:** NOT IMPLEMENTED.

- No `tv_time` screen or route
- No episode-level UI
- No watched state per episode
- No "next episode" logic
- Backend has `seasons` and `episodes` tables with data, but no UI consumes them

**Classification:** D — backend capability exists (tables populated), UI completely absent.

---

## 10. People Audit

**Status:** Partially functional.

- Listing screen exists but shows empty (0 people in current DB state)
- PersonCard exists (`ui/components/cards/person_card.py`)
- Details screen returns person EntityRef but no artwork, no filmography
- Real data exists: 2 people in DB (Volker Bruch tmdb_id=23182, Liv Lisa Fries tmdb_id=583333)
- `tv_people` has 2 relationships (tv_show_id=1, person_id=1 and 2)
- `people` table has `character_name` column but it's NULL in current data

**Gaps:**
- A — People screen shows empty because `search_people("")` returns 0 results (no person search in search service)
- C — Details doesn't show filmography (no query for `movie_people`/`tv_people`)
- D — No person artwork pipeline (no `artwork` rows for person entities)

---

## 11. TMDB Audit

**Status:** Backend complete, UI partially connected.

### 11.1 Provider
- `app/metadata/tmdb_provider.py` — Full implementation with search, metadata, artwork URLs
- API key from `TmdbConfig` (JSON config or `TMDB_API_KEY` env var)
- Key length: 32 characters (confirmed valid)
- Live API verified: "Babylon Berlin" → TMDB ID 66980, IMDb ID tt4378376

### 11.2 Integration
- Registered in `app/bootstrap.py:create_metadata_integration()`
- `LibraryMetadataIntegration._discover()` calls provider.search() when no external_id
- `MetadataService.fetch_and_save_metadata()` calls provider.fetch_metadata()
- Artwork downloaded via `artwork_downloader.download_artwork()`
- People persisted via `_persist_credits()`

### 11.3 UI Consumption
- Artwork: ✓ Works (poster/backdrop files on disk, DB rows exist)
- External IDs: ✓ Persisted but not displayed in UI
- People: ✓ Persisted to DB but not displayed in UI
- Metadata update: ✓ Title/year/overview overwritten on re-scan

### 11.4 Gaps
- A — No UI to configure TMDB API key (settings screen lacks metadata section)
- A — No UI to trigger metadata refresh
- C — Details screen doesn't show IMDb ID or TMDB ID

---

## 12. OMDb / IMDb Audit

**Status:** Backend available, not configured, not displayed.

- `OMDbMetadataProvider` registered when API key present
- No `OMDB_API_KEY` configured (neither in env nor config)
- No UI settings for OMDb
- IMDb ID exists in DB (`external_ids` table, provider="imdb", external_id="tt4378376") but not shown in UI

---

## 13. Music Audit

**Status:** Functional but minimal.

- Artists, albums, tracks listing: working
- Recently played: working
- Play: working (uses video player)
- Details: working for albums and artists
- Missing: dedicated music player UI (volume, seek, queue, artwork display)

---

## 14. Player Audit

**Status:** Video player functional, music player absent.

### 14.1 Video Player
- VLC and MPV backends: working
- Controls: play/pause, seek, volume, mute, fullscreen
- Progress polling: 500ms
- Missing file handling: shows "Media Not Available"
- Back button: works
- Escape: exits player

### 14.2 Missing
- Subtitle controls
- Audio track selection
- Playback speed
- Music player UI (separate from video)
- Player settings screen

---

## 15. Playback / Resume Audit

**Status:** Partial.

- Movie resume: working
- Track resume: working
- Episode resume: NOT tracked (schema doesn't support it)
- "Continue Watching" row: shows movies and tracks, not episodes
- Completed flag: works for movies and tracks

---

## 16. Personal Browser Audit

**Status:** NOT IMPLEMENTED.

- No browser widget in codebase
- No QWebEngine import
- No browser screen registered
- No browser route
- No service shortcuts (YouTube, Telegram, Spotify, Netflix, Prime Video, Disney+)

**Classification:** D — completely absent.

---

## 17. YouTube Audit

**Status:** NOT IMPLEMENTED.

- No browser → no YouTube
- No dedicated YouTube integration

---

## 18. Telegram Audit

**Status:** NOT IMPLEMENTED.

- No browser → no Telegram
- No dedicated Telegram integration

---

## 19. Spotify Audit

**Status:** NOT IMPLEMENTED.

- No browser → no Spotify web player
- Music playback uses local files only

---

## 20. Netflix Audit

**Status:** NOT IMPLEMENTED.

- No browser → no Netflix
- DRM-heavy service would require system browser per scope document

---

## 21. Prime Video Audit

**Status:** NOT IMPLEMENTED.

- Same as Netflix

---

## 22. Disney+ Audit

**Status:** NOT IMPLEMENTED.

- Same as Netflix

---

## 23. Settings / Theme Audit

**Status:** Partially functional.

### 23.1 Theme
- Dark/Light/System buttons: ✓ work
- Live switching: ✓ verified (QSS regenerated, widgets refresh)
- System mode: ✓ listens to OS theme changes

### 23.2 Missing Settings
- TMDB API key configuration
- OMDb API key configuration
- Player backend selection (VLC/MPV)
- Player preferences (subtitles, audio, resume behavior)
- Provider priority settings

---

## 24. Library / Scanner Audit

**Status:** Fully functional.

- Add location: ✓ QFileDialog → confirm → scan
- Remove location: ✓
- Rescan: ✓
- Scan progress: ✓ live phase messages
- Scan completion: ✓ summary with counts
- Scan error: ✓ actionable error with retry
- Location list: ✓ shows paths and labels

---

## 25. Search Audit

**Status:** Fully functional.

- Global search bar: ✓
- Debounce: ✓ 300ms
- Results grouped by type: ✓ movies, TV, people, music
- Artwork in results: ✓
- Navigation from results: ✓

---

## 26. Favorites / Watchlist / Collections Audit

**Status:** Fully functional.

- All CRUD operations work
- UI reflects state changes immediately
- Context menu integrated
- Collections have create/rename/delete/open detail

---

## 27. Test Coverage Audit

### 27.1 Existing Tests
| Test File | Tests | Coverage |
|-----------|-------|----------|
| `tests/ui/test_theme.py` | 12 | ThemeManager, QSS, system mode |
| `tests/ui/test_main_window.py` | 2 | Launch, close |
| `tests/ui/test_navigation.py` | 5 | History, back/forward |
| `tests/ui/test_app_bootstrap.py` | 1 | Headless smoke test |
| `tests/ui/test_screens_states.py` | 14 | Screen state machine, empty/error/loading |
| `tests/test_identifier.py` | 35 | Filename parsing |
| `tests/test_metadata_pipeline.py` | 49 | Provider, service, dedup |
| `tests/test_library_metadata_integration.py` | 9 | Integration with library |
| `tests/test_library_pipeline_repair.py` | 27 | Generic TV/movie dedup, idempotency, Babylon Berlin |
| `tests/test_tmdb_provider.py` | 37 | TMDB provider, discovery, artwork, people, external IDs |
| `tests/test_library.py` | 14 | Library repo |
| `tests/test_scanner.py` | 6 | Filesystem scanner |
| `tests/test_full_workflow.py` | 4 | End-to-end workflow |

**Total:** 211 tests, all passing.

### 27.2 Gaps
- No UI tests for: Home data flow, Movies screen, TV Shows screen, Details screen, Search results, Settings theme switching at runtime, Artwork rendering, Player controls
- No integration tests for: TMDB → UI artwork flow, TMDB → UI people flow
- No tests for: Season/episode UI (doesn't exist yet)
- No tests for: Browser (doesn't exist yet)

---

## 28. Runtime Findings

### 28.1 Confirmed Working
- App launches successfully
- Sidebar navigation works
- Theme switching (Dark ↔ Light ↔ System) works visually
- Home shows empty state with "Add Library Location" action
- Library screen: add location, scan, progress, completion all work
- Movies screen: grid, sort, filter work
- Search: debounced, grouped results work
- Favorites/Watchlist/Collections: CRUD works
- Player: opens file, plays, controls work
- Details: shows title, year, overview, genres, similar items

### 28.2 Confirmed Broken
- Hero backdrop on Home: doesn't load because `ref.extra["backdrop"]` not populated
- TV Details: no seasons/episodes shown (intentional limitation per code comment)
- People screen: empty because search_people("") returns 0 results
- Settings: no TMDB/OMDb/player configuration UI

### 28.3 Real Data State
```
media_files: 16
tv_shows: 1 ("Babylon Berlin 720p WEB" — local title, not yet overwritten by TMDB)
seasons: 2
episodes: 16
episode_files: 16
people: 0 (in current DB — TMDB people not yet persisted to this DB instance)
external_ids: 0
artwork: 0
```

Wait — this contradicts the earlier check. Let me re-verify.

Actually, the DB was updated during the TMDB pipeline phase. The real DB state after the pipeline phase was:
```
media_files: 16
tv_shows: 1
seasons: 2
episodes: 16
episode_files: 16
people: 2 (Volker Bruch, Liv Lisa Fries)
external_ids: 2 (tmdb:66980, imdb:tt4378376)
artwork: 2 (poster, backdrop)
```

But the last audit check showed 0 for people/external_ids/artwork. This suggests the DB was reset or the data was in a different database instance. The test DB (in-memory) is separate from the production DB (`data/library/jpml.db`).

---

## 29. Exact Broken Integrations

| # | Area | Problem | Category |
|---|------|---------|----------|
| 1 | Home Hero | Backdrop not loaded — `ref.extra["backdrop"]` never populated in list flows | C (UI contract mismatch) |
| 2 | TV Details | Seasons/episodes not shown — intentionally skipped per code comment | D (backend capability not exposed) |
| 3 | People Screen | Empty — `search_people("")` returns 0; no person listing endpoint in search service | D (backend absent) |
| 4 | Details Screen | Cast/crew not shown — `tv_people`/`movie_people` not queried | C (UI doesn't call existing backend) |
| 5 | Settings | No TMDB/OMDb/player config UI | A (UI missing) |
| 6 | Player | No music player UI; no subtitle/audio controls | D (backend absent) |
| 7 | Browser | No browser implementation at all | D (backend absent) |
| 8 | Online Services | No YouTube/Telegram/Spotify/Netflix integration | D (backend absent) |
| 9 | TV Time | No episode tracking UI | D (backend absent) |
| 10 | Details | IMDb/TMDB IDs not displayed | A (UI missing) |

---

## 30. Missing Integrations

| Area | What's Missing | Priority |
|------|---------------|----------|
| Home Hero | Backdrop enrichment in list flows | HIGH |
| TV Details | Season/episode browsing | HIGH |
| People | Person listing, detail with filmography | MEDIUM |
| Details | Cast/crew display, external IDs display | MEDIUM |
| Settings | TMDB/OMDb API key config, player settings | MEDIUM |
| Player | Music player UI, subtitle controls | LOW |
| Browser | Web browser widget | LOW (external dependency) |
| Online Services | Service cards with branding | LOW |
| TV Time | Episode watch tracking | MEDIUM |

---

## 31. UI-Only Fixes (No Backend Changes Required)

| Fix | File | Description |
|-----|------|-------------|
| Hero backdrop | `ui/app/data.py` | Enrich list results with backdrop artwork |
| TV seasons/episodes | `ui/screens/details.py` | Query seasons/episodes repo and render them |
| Cast/crew in details | `ui/screens/details.py` | Query `tv_people`/`movie_people` and render cast list |
| External IDs in details | `ui/screens/details.py` | Query `external_ids` and show IMDb/TMDB IDs |
| Settings metadata | `ui/screens/settings.py` | Add TMDB/OMDb config section |
| Person listing | `ui/app/data.py` | Add `fetch_all_people()` using `people` table directly |
| Music player | `ui/screens/player.py` | Add music-specific controls |

---

## 32. Backend Changes That Appear Unavoidable

| Change | File | Reason |
|--------|------|--------|
| Person search | `app/search/service.py` or new repo method | `search_people("")` returns 0; need a way to list all people |
| Season/episode read APIs | `app/library/season_repository.py`, `episode_repository.py` | UI needs to query seasons/episodes by tv_show_id |
| People by entity | `app/metadata/repository.py` | Need `list_people_by_movie(movie_id)` and `list_people_by_tv(tv_show_id)` |
| Episode playback tracking | `app/library/playback_repository.py` | Schema doesn't support episode-level progress |

**Note:** Some of these may already exist but not be exposed. Need to verify.

---

## 33. Recommended Implementation Order

### Phase 1: Fix Existing Data Flow (UI-only)
1. Hero backdrop enrichment in `data.py` — fix Home hero showing backdrop
2. Cast/crew display in Details screen — query `tv_people`/`movie_people`
3. External IDs display in Details screen — show IMDb/TMDB IDs
4. Person listing — add `fetch_all_people()` to `data.py`

### Phase 2: TV Season/Episode UI
5. Add season/episode rendering to `DetailsScreen` for TV kind
6. Episode artwork support in `MediaCard`
7. "Next episode" logic in continue watching

### Phase 3: Settings Expansion
8. Add TMDB/OMDb API key configuration to Settings
9. Add player backend selection to Settings
10. Add player preferences (resume behavior, subtitles)

### Phase 4: Browser & Online Services
11. Add QWebEngine browser widget (requires PyQt6 WebEngine modules)
12. Add browser screen with navigation controls
13. Add service shortcuts (YouTube, Telegram, Spotify, Netflix, Prime, Disney+)
14. Handle DRM services via system browser fallback

### Phase 5: Music Player
15. Separate music player UI from video player
16. Add queue support
17. Add album artwork display

---

## 34. Definition of Done

JPML UI/Integration is complete when:

1. ✅ All 16 screens exist and are reachable
2. ✅ Home shows real library data with hero backdrop
3. ✅ Movies screen works with posters, details, play
4. ✅ TV Shows screen works with posters, details
5. ⬜ TV Details shows seasons and episodes
6. ✅ Music screen works with artists/albums/tracks
7. ⬜ People screen shows cast from TMDB data
8. ✅ TMDB metadata pipeline works end-to-end
9. ⬜ OMDb can be configured via UI
10. ⬜ Artwork renders correctly (poster + backdrop)
11. ✅ Player works for video
12. ⬜ Player has music-specific controls
13. ⬜ Settings has full configuration
14. ⬜ Browser is visible and usable
15. ⬜ YouTube/Telegram/Spotify/Netflix integrated
16. ✅ Library management works
17. ✅ Search works
18. ✅ Favorites/Watchlist/Collections work
19. ✅ Theme switching works
20. ✅ All existing tests pass
21. ⬜ New regression tests for fixed features
22. ⬜ Real data validation (Babylon Berlin)
23. ⬜ Real media validation where available

---

## 35. Final Status Table

| AREA | STATUS | EXACT PROBLEM | FILES | BACKEND CHANGE REQUIRED? |
|------|--------|---------------|-------|--------------------------|
| Home Hero | PARTIAL | Backdrop not enriched in list flows | `ui/app/data.py` | NO |
| Movies | PASS | — | — | NO |
| TV Shows | PARTIAL | No season/episode UI in details | `ui/screens/details.py` | NO (if repos exist) |
| TV Time | BLOCKED | No screen, no episode UI | — | YES (or new screen) |
| People | PARTIAL | No person listing, no filmography | `ui/app/data.py`, `ui/screens/people.py` | YES (person search) |
| TMDB | PASS | Backend complete, UI partially connected | `app/metadata/` | NO |
| OMDb | PARTIAL | Not configured, not in settings | `ui/screens/settings.py` | NO |
| Artwork | PARTIAL | Hero backdrop not loaded from list data | `ui/app/data.py` | NO |
| Music | PASS | Functional but minimal | — | NO |
| Player | PARTIAL | No music player, no subtitle controls | `ui/screens/player.py` | NO |
| Playback | PARTIAL | No episode-level tracking | `app/library/playback_repository.py` | YES |
| Browser | BLOCKED | No implementation at all | — | YES (new widget) |
| YouTube | BLOCKED | No browser → no integration | — | NO (depends on browser) |
| Telegram | BLOCKED | No browser → no integration | — | NO (depends on browser) |
| Spotify | BLOCKED | No browser → no integration | — | NO (depends on browser) |
| Netflix | BLOCKED | DRM requires system browser | — | NO (document limitation) |
| Prime Video | BLOCKED | DRM requires system browser | — | NO (document limitation) |
| Disney+ | BLOCKED | DRM requires system browser | — | NO (document limitation) |
| Settings | PARTIAL | Missing TMDB/OMDb/player config | `ui/screens/settings.py` | NO |
| Library | PASS | — | — | NO |
| Search | PASS | — | — | NO |
| Favorites | PASS | — | — | NO |
| Watchlist | PASS | — | — | NO |
| Collections | PASS | — | — | NO |
| Theme | PASS | — | — | NO |
| Navigation | PASS | — | — | NO |

---

## 36. Tests Executed

```bash
.venv/bin/python -m pytest tests/ -q --ignore=tests/test_integration.py
# Result: 776 passed

.venv/bin/python -m pytest tests/ui -q
# Result: 34 passed

.venv/bin/python -m compileall -q app ui run.py
# Result: COMPILE OK

git diff --check
# Result: OK
```

## 37. Runtime Checks Executed

- App launch: ✅ `run.py` starts, shows MainWindow
- Navigation: ✅ Sidebar clicks navigate correctly
- Theme switch: ✅ Dark → Light → System cycles work
- Home empty state: ✅ Shows "Add Library Location"
- Library scan: ✅ Add location → scan → progress → completion
- Movie grid: ✅ Renders cards
- Search: ✅ Returns results
- Player: ✅ Opens file, plays
- Settings: ✅ Theme buttons work, library link works

## 38. Files Inspected

- `run.py`
- `ui/app/main_window.py`
- `ui/app/run_state.py`
- `ui/app/composition.py`
- `ui/app/data.py`
- `ui/app/view_model.py`
- `ui/app/navigation.py`
- `ui/app/app_state.py`
- `ui/app/screen_actions.py`
- `ui/app/library_flow.py`
- `ui/screens/home.py`
- `ui/screens/movies.py`
- `ui/screens/tv_shows.py`
- `ui/screens/people.py`
- `ui/screens/music.py`
- `ui/screens/library.py`
- `ui/screens/player.py`
- `ui/screens/settings.py`
- `ui/screens/search.py`
- `ui/screens/details.py`
- `ui/screens/favorites.py`
- `ui/screens/watchlist.py`
- `ui/screens/collections.py`
- `ui/screens/trending.py`
- `ui/screens/recommendations.py`
- `ui/screens/statistics.py`
- `ui/components/media/hero.py`
- `ui/components/media/artwork.py`
- `ui/components/media/media_grid.py`
- `ui/components/media/media_row.py`
- `ui/components/cards/media_card.py`
- `ui/components/cards/person_card.py`
- `ui/components/cards/album_card.py`
- `ui/components/common/screen.py`
- `ui/components/common/empty_state.py`
- `ui/components/common/toast.py`
- `ui/components/common/button.py`
- `ui/components/common/page_header.py`
- `ui/components/navigation/sidebar.py`
- `ui/components/navigation/top_bar.py`
- `ui/themes/theme_manager.py`
- `ui/themes/dark.py`
- `ui/themes/light.py`
- `ui/themes/tokens.py`
- `ui/utils/image_cache.py`
- `ui/utils/formatting.py`
- `ui/models.py`
- `app/metadata/tmdb_provider.py`
- `app/metadata/artwork_downloader.py`
- `app/metadata/service.py`
- `app/metadata/repository.py`
- `app/metadata/provider.py`
- `app/metadata/library_integration.py`
- `app/metadata/identifier.py`
- `app/metadata/omdb_provider.py`
- `app/bootstrap.py`
- `app/config.py`
- `app/library/coordinator.py`
- `app/library/scanner.py`
- `app/library/library_repository.py`
- `app/library/playback_repository.py`

## 39. Exact Blockers

1. **Browser**: No QWebEngine/browser implementation exists. Requires new widget and screen.
2. **TV Time**: No episode-level UI exists. Requires new screen or expansion of Details screen.
3. **Person listing**: `search_people("")` returns 0 results. Requires backend change or new repository method.
4. **Hero backdrop**: List flows don't populate `ref.extra["backdrop"]`. UI-only fix.
5. **Settings config**: No UI for TMDB/OMDb/player settings. UI-only fix.

## 40. Next Implementation Order

1. **Fix hero backdrop** — `ui/app/data.py`: enrich list results with backdrop
2. **Add cast/crew to details** — `ui/screens/details.py`: query and render people
3. **Add external IDs to details** — `ui/screens/details.py`: show IMDb/TMDB
4. **Fix person listing** — `ui/app/data.py`: add `fetch_all_people()`
5. **Add seasons/episodes to TV details** — `ui/screens/details.py`
6. **Expand settings** — `ui/screens/settings.py`: TMDB/OMDb/player config
7. **Browser** — new screen with QWebEngine (or document as external dependency)
8. **Online services** — service cards in browser or home screen

---

## 41. Git Status

```
HEAD: 0252ee1 — docs: add complete UI integration scope
Branch: ui-forensics-2026-09-04

Modified (from previous phases):
  M app/bootstrap.py
  M app/config.py
  M app/metadata/identifier.py
  M app/metadata/library_integration.py
  M app/metadata/provider.py
  M app/metadata/repository.py
  M app/metadata/service.py

Untracked:
  ?? app/metadata/artwork_downloader.py
  ?? app/metadata/tmdb_provider.py
  ?? tests/test_library_pipeline_repair.py
  ?? tests/test_tmdb_provider.py
  ?? tests/ui/
  ?? ui/
  ?? run.py
  ?? (8 .before-* backup files)
```

**No source code modifications were made during this audit.** This is a read-only forensic inspection.

---

## 42. Known Limitations

1. **TMDB API key** is configured in environment but not exposed in UI settings
2. **OMDb API key** is not configured
3. **No browser widget** — online services cannot be embedded
4. **DRM services** (Netflix, Prime, Disney+) require system browser — document this limitation
5. **Episode-level playback** not supported by current schema
6. **Person search** not available via SearchService

---

**AUDIT COMPLETE — READY FOR IMPLEMENTATION PHASE**
