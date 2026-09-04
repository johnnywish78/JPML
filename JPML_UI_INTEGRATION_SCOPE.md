# JPML — UI & Integration Completion Scope

**Date:** 2026-09-04  
**Project:** Johnny Personal Media Library (JPML)  
**Status:** ACTIVE — FINAL UI/INTEGRATION SCOPE

---

## 1. PURPOSE

This document is the authoritative checklist for completing the JPML UI and integration layer.

The existing backend/product architecture is considered frozen.

The objective is:

> COMPLETE THE EXISTING JPML PRODUCT — DO NOT REBUILD IT.

All existing backend capabilities must be exposed through a coherent, usable and tested UI.

---

# 2. BACKEND FREEZE RULE

The existing backend implementation and contracts are the source of truth.

Before modifying backend code:

1. Inspect the existing implementation.
2. Inspect its public contract/API.
3. Inspect the current UI integration.
4. Identify the exact integration gap.
5. Prove that the problem cannot be solved in the UI.
6. Make the smallest possible backend change only if absolutely necessary.

### DO NOT

- Restart completed backend phases.
- Rewrite repositories without evidence.
- Create duplicate services.
- Create duplicate database models.
- Create a second playback architecture.
- Rebuild metadata architecture.
- Rebuild scanner architecture.
- Rebuild library architecture.
- Change database schema without forensic proof.
- Replace working backend functionality merely because the UI is incomplete.

---

# 3. REQUIRED PRODUCT AREAS

Every area below MUST be audited.

A file/class existing in the repository does NOT mean the feature is complete.

A feature is complete only when it is:

- reachable from the UI
- visually usable
- connected to the existing backend contract
- functional at runtime
- tested where practical
- free of placeholder behavior

---

# 4. HOME / DASHBOARD

Audit and complete:

- Hero
- Backdrop
- Featured media
- Continue Watching
- Recently Added
- Favorites
- Movies
- TV Shows
- Music
- Trending
- Recommendations
- Search
- Media cards
- Posters
- Backdrops
- Progress indicators
- Click navigation
- Details navigation
- Play
- Resume

Home must display valid existing library data.

---

# 5. MOVIES

Audit:

- Movie library
- Movie cards
- Posters
- Backdrops
- Details
- Overview
- Genres
- Year
- Runtime
- Rating
- Cast
- Crew
- TMDB metadata
- IMDb / OMDb metadata
- IMDb ID
- Artwork
- Play
- Resume
- Favorites
- Watchlist
- Collections
- Search
- Navigation

---

# 6. TV SHOWS

Audit:

- TV library
- Show cards
- Posters
- Backdrops
- Details
- Overview
- Genres
- Rating
- Cast
- Crew
- Seasons
- Episodes
- Episode artwork
- Episode metadata
- Watched state
- Unwatched state
- Episode progress
- Resume
- Next episode
- Favorites
- Watchlist
- Search

---

# 7. TV TIME

TV Time is a required product area.

Audit existing TV Time/watch functionality.

Where supported by existing architecture:

- TV discovery
- TV watch tracking
- Episode tracking
- Watched state
- Next episode
- TV recommendations
- TV discovery
- TV metadata
- TV details
- TV artwork
- Episode progress
- TV navigation

Do NOT invent a fake TV Time subsystem.

Use existing backend contracts.

If backend functionality exists but UI does not expose it, integrate it.

If a capability genuinely does not exist, document the gap instead of inventing incompatible architecture.

---

# 8. PEOPLE

Audit:

- People search
- Actor details
- Director details
- Crew details
- Person artwork
- Filmography
- Movie links
- TV links
- Metadata enrichment
- Navigation

People should not remain text-only when artwork/data exists.

---

# 9. TMDB

Audit the complete TMDB pipeline:

- Configuration
- API key
- Provider initialization
- Search
- Movie metadata
- TV metadata
- People
- Posters
- Backdrops
- Artwork
- Discovery
- Trending
- Recommendations
- Error handling
- Fallback behavior
- UI integration
- Settings integration
- Runtime behavior
- Cache behavior

TMDB must be visibly and correctly connected to the UI.

---

# 10. IMDb / OMDb

Audit the complete IMDb/OMDb pipeline:

- OMDb configuration
- OMDb API key
- IMDb ID
- Movie metadata
- TV metadata
- People metadata
- Ratings
- IMDb-specific information
- Provider fallback
- Provider priority
- Settings
- Runtime integration
- Error handling

Do not confuse OMDb/IMDb with TMDB artwork.

If TMDB artwork already exists locally, do not unnecessarily replace the artwork provider.

---

# 11. ARTWORK

Audit the complete pipeline:

Provider

→ Metadata

→ Artwork Repository

→ Local Cache

→ UI Data

→ Artwork Component

→ Image Cache

→ Qt Rendering

Required:

- Movie posters
- TV posters
- Backdrops
- Episode artwork
- People artwork
- Music artwork
- Local artwork
- Provider artwork
- Cache
- Fallback
- Resize
- Crop
- Loading state
- Missing-artwork state
- Thread safety

### CRITICAL

Inspect:

`ui/utils/image_cache.py`

Do not create GUI-only Qt objects such as `QPixmap` from worker threads unless the implementation is proven safe.

If asynchronous artwork loading is responsible for missing posters:

- move GUI object creation to the GUI thread
- preserve asynchronous loading where possible
- preserve cache behavior
- test real cached artwork

### Required regression case

Use:

**Babylon Berlin**

Verify:

- TV show appears
- Poster loads
- Backdrop loads
- Details opens
- Metadata appears
- People/cast behavior
- Seasons
- Episodes
- Watch state
- Play/resume where applicable

---

# 12. MUSIC

Music is a first-class JPML product area.

Audit:

- Music Library
- Artists
- Albums
- Tracks
- Artist artwork
- Album artwork
- Track artwork
- Metadata
- Search
- Favorites
- Playback
- Resume
- Progress
- Previous
- Next
- Queue where supported
- Music Player
- Music Player settings
- Home integration
- Search integration
- Library management

Do not leave Music as backend-only functionality.

---

# 13. PLAYER

The player must be treated as a complete product component.

## VIDEO PLAYER

Audit:

- Play
- Pause
- Stop
- Seek
- Timeline
- Volume
- Mute
- Fullscreen
- Windowed mode
- Resume
- Progress
- Previous/next where applicable
- Subtitles
- Audio tracks
- Playback speed where supported
- Loading state
- Error state

## MUSIC PLAYER

Audit:

- Play
- Pause
- Seek
- Timeline
- Volume
- Previous
- Next
- Track information
- Artwork
- Queue where supported
- Resume
- Progress
- Error state

## PLAYER SETTINGS

Player settings MUST NOT be omitted.

Audit all existing player configuration and expose it through Settings/UI where supported:

- Player backend
- mpv
- VLC
- Playback preferences
- Subtitle preferences
- Audio preferences
- Volume behavior
- Fullscreen behavior
- Resume behavior
- Keyboard shortcuts
- Other existing player configuration

Do not declare Player complete merely because media can be launched.

---

# 14. PLAYBACK / WATCH ENGINE

Audit the complete lifecycle:

Play

→ Progress

→ Pause / Exit

→ Persist

→ Resume

→ Complete

→ Continue Watching update

For TV:

Show

→ Season

→ Episode

→ Progress

→ Watched

→ Next Episode

Do NOT create a second playback database architecture.

The existing backend/database contract is authoritative.

---

# 15. PERSONAL BROWSER

JPML Personal Browser is a core product component.

Audit:

- Browser screen
- Browser visibility
- Browser initialization
- Address/search bar
- Back
- Forward
- Reload
- Page loading
- Error handling
- Service shortcuts
- Online navigation
- Runtime integration
- Browser engine behavior

The UI must NOT merely display:

`Chrome Ready`

while no usable browser is visible.

---

# 16. YOUTUBE

Audit:

- YouTube entry
- Correct branding
- Navigation
- Browser integration
- Search/navigation where supported
- Page loading
- Error handling
- UI visibility

Do not create a fake YouTube player if the architecture expects browser playback.

---

# 17. TELEGRAM

Audit:

- Telegram entry
- Correct branding
- Browser integration
- Navigation
- UI visibility
- Error handling

---

# 18. SPOTIFY

Audit:

- Spotify entry
- Correct branding
- Browser integration
- Navigation
- UI visibility
- Error handling

---

# 19. NETFLIX / PRIME VIDEO / DISNEY+

Audit:

- Netflix
- Amazon Prime Video
- Disney+

Respect the existing browser architecture.

Where internal browser DRM support is unavailable:

- use system browser / Chrome
- provide a clear UI action
- report browser state honestly

Do NOT claim unsupported DRM functionality.

---

# 20. ONLINE SERVICE BRANDING

Audit every online service card.

Required:

- Real/official branding
- Correct logo
- Correct aspect ratio
- Correct sizing
- Readable text
- No fake/generated logos
- No placeholder graphics

At minimum:

- Netflix
- Prime Video
- Disney+
- YouTube
- Spotify
- Telegram

Also audit every additional online service already present in the project.

---

# 21. LIBRARY MANAGEMENT

Audit:

- Add Movie location
- Add TV location
- Add Music location
- Remove location
- Scan
- Rescan
- Scan status
- Scan progress
- Scan results
- Scan errors
- Refresh
- Duplicate handling
- Missing-file handling
- Mounted-drive handling

Use the existing scanner/library manager.

Do NOT duplicate scanner logic inside the UI.

---

# 22. SEARCH

Audit unified search:

- Movies
- TV Shows
- Music
- People
- Artwork
- Result cards
- Result navigation
- Details
- Play
- Empty state
- Error state

---

# 23. FAVORITES / WATCHLIST / COLLECTIONS

Audit:

- Add
- Remove
- Display
- Persistence
- Details
- Play
- Search integration
- Home integration
- Navigation

---

# 24. SETTINGS

Settings must become the actual JPML control center.

## APPEARANCE

- Dark
- Light
- System

Theme switching must visibly work at runtime.

Audit:

- ThemeManager
- Signal connections
- QSS refresh
- Application palette
- Existing widgets
- Runtime lifecycle
- Style overrides

## METADATA

- TMDB
- OMDb
- IMDb-related configuration
- API keys
- Provider behavior
- Provider priority
- Connection/test behavior where supported

## LIBRARY

- Locations
- Add
- Remove
- Scan
- Rescan

## PLAYER

- Player backend
- mpv
- VLC
- Playback preferences
- Subtitle preferences
- Audio preferences
- Resume
- Keyboard shortcuts
- Other existing player settings

## BROWSER / ONLINE

- Browser behavior
- External browser behavior
- Online-service behavior where supported

---

# 25. NAVIGATION

Audit the complete navigation graph.

Required primary areas:

- Home
- Movies
- TV Shows
- Music
- Search
- Favorites
- Watchlist
- Collections
- Browser / Online
- Player
- Settings

No existing product capability should remain unreachable without an intentional architectural reason.

---

# 26. UI / BACKEND INTEGRATION

Preferred architecture:

UI

→ UI data adapter

→ Existing service/repository

→ Existing domain/backend contract

Avoid:

UI

→ duplicate business logic

→ duplicate database logic

→ duplicate backend

Every integration should reuse the frozen backend.

---

# 27. REAL DATA VALIDATION

At minimum validate against real existing library data.

### Babylon Berlin

Verify:

- Library visibility
- Poster
- Backdrop
- Details
- Metadata
- People
- Seasons
- Episodes
- Watch state
- Resume/play where applicable

Artwork must be verified against the existing artwork repository/cache.

---

# 28. REAL MEDIA VALIDATION

Where real media exists, test:

- Movie playback
- TV playback
- Music playback
- Resume
- Progress
- Player controls
- Player settings
- Error handling

Do not rely only on mocks.

---

# 29. TESTING

Existing tests MUST remain green.

Add targeted regression tests where practical.

Minimum test categories:

- Home
- Navigation
- Movies
- TV Shows
- TV Time
- Music
- Details
- People
- Artwork
- Search
- Settings
- Theme switching
- Library management
- Player
- Player settings
- Browser
- YouTube
- Telegram
- Spotify
- Streaming services
- TMDB
- OMDb/IMDb
- Playback/resume

Run:

- Existing backend tests
- Existing UI tests
- New regression tests
- Real-data validation
- Real-media validation where available

---

# 30. NO SILENT PLACEHOLDERS

The following are NOT complete:

- Empty screen
- Fake logo
- Static "Ready" status
- Button with no action
- Menu item with no destination
- Metadata class that is never connected
- Artwork record that never renders
- Player without its available settings
- Browser status saying Ready while no browser is visible
- Music backend without Music UI
- TV metadata without TV episode UI
- TMDB configuration that does not affect runtime
- OMDb configuration that does not affect runtime
- Online service card with fake branding

---

# 31. DEFINITION OF DONE

JPML UI/Integration is complete only when:

1. All UI areas are audited.
2. Existing backend contracts are reused.
3. No unnecessary backend rewrite occurs.
4. Home works.
5. Movies work.
6. TV Shows work.
7. TV Time is audited/integrated.
8. Music works.
9. People work.
10. TMDB is audited end-to-end.
11. OMDb/IMDb is audited end-to-end.
12. Artwork rendering works.
13. Player works.
14. Player settings work where supported.
15. Browser is visible and usable.
16. YouTube is integrated.
17. Telegram is integrated.
18. Spotify is integrated.
19. Netflix/Prime/Disney+ are correctly handled.
20. Library management works.
21. Search works.
22. Favorites/watchlist/collections work.
23. Theme switching works.
24. Settings work.
25. Navigation exposes intended product areas.
26. Existing tests remain green.
27. New regression tests pass.
28. Real data has been validated.
29. Real media has been validated where available.
30. No known existing backend capability is silently hidden behind an incomplete UI.

---

# 32. AGENT EXECUTION RULE

The agent must work in this order:

1. FORENSIC AUDIT
2. MAP EXISTING BACKEND CONTRACTS
3. MAP EXISTING UI
4. IDENTIFY INTEGRATION GAPS
5. FIX UI/INTEGRATION
6. TEST
7. REGRESSION TEST
8. REAL DATA VALIDATION
9. REAL MEDIA VALIDATION
10. FINAL AUDIT

Do NOT implement from assumptions.

Do NOT rebuild functionality that already exists.

Do NOT mark a feature complete merely because code exists.

---

# 33. FINAL REPORT REQUIRED

At completion report:

## Completed

Every completed feature.

## Partially Completed

Every incomplete feature.

## Backend Changes

If any backend file was modified:

- Exact file
- Exact reason
- Why UI-only integration was insufficient
- Exact behavior changed
- Tests proving the change

## UI Changes

- Files changed
- Features changed
- Runtime behavior

## Tests

Report:

- Total
- Passed
- Failed
- Skipped
- UI tests
- Backend regression tests
- Real-data tests
- Real-media tests

## Known Limitations

Explicitly document every remaining limitation.

---

# 34. FINAL PRINCIPLE

The goal is NOT to build a new JPML.

The goal is to finish the existing JPML product.

Backend is frozen.

UI and integration are the remaining focus.

Every existing capability must either:

1. Work through the UI,

or

2. Have a documented, proven architectural/external limitation.

Nothing should be silently forgotten.

---

# 35. REQUIRED COVERAGE CHECKLIST

Before declaring completion, explicitly check:

[ ] Home
[ ] Movies
[ ] TV Shows
[ ] TV Time
[ ] Music
[ ] People
[ ] Search
[ ] Favorites
[ ] Watchlist
[ ] Collections
[ ] Continue Watching
[ ] Trending
[ ] Recommendations
[ ] Library Manager
[ ] Scanner UI
[ ] TMDB
[ ] OMDb
[ ] IMDb IDs
[ ] Artwork
[ ] Poster rendering
[ ] Backdrop rendering
[ ] Episode artwork
[ ] People artwork
[ ] Music artwork
[ ] Video Player
[ ] Music Player
[ ] Player Settings
[ ] Playback
[ ] Resume
[ ] Watch State
[ ] Browser
[ ] YouTube
[ ] Telegram
[ ] Spotify
[ ] Netflix
[ ] Prime Video
[ ] Disney+
[ ] Online Service Branding
[ ] Dark Theme
[ ] Light Theme
[ ] System Theme
[ ] Settings
[ ] Navigation
[ ] Real Data Validation
[ ] Real Media Validation
[ ] Existing Tests
[ ] New Regression Tests

---

## STATUS

**Backend:** FROZEN  
**UI:** INTEGRATION / COMPLETION  
**Scope:** COMPLETE  
**Do not restart backend phases.**
