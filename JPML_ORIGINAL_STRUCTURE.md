عالی. Checkpoint 1 کاملاً سبز است.
۳۰/۳۰ تست، diff --check تمیز، و تغییرات دقیقاً همان Scope مورد انتظار Phase 1 هستند.

الان Phase 1 را commit کنیم. این دستور را بزن:

cd ~/Desktop/JPML

git add \
  app/database/schema.py \
  app/domain/__init__.py \
  app/domain/media.py \
  app/library/__init__.py \
  app/library/scanner.py \
  app/library/library_repository.py \
  app/library/media_repository.py \
  app/library/coordinator.py \
  tests/test_database.py \
  tests/test_domain.py \
  tests/test_library.py \
  tests/test_scanner.py

echo "=== STAGED ==="
git status --short

echo
echo "=== STAGED DIFF CHECK ==="
git diff --cached --check

echo
echo "=== STAGED STAT ==="
git diff --cached --stat

echo
echo "=== FINAL TEST BEFORE COMMIT ==="
.venv/bin/python -m pytest -q

اگر خروجی همچنان 30 passed و diff --cached --check خالی بود، این commit را بزن:

git commit -m "feat: implement library filesystem core"

و بعد:

echo
echo "============================================================"
echo "JPML — CHECKPOINT 1"
echo "============================================================"

git log -1 --oneline
git status --short

هدف نهایی این Checkpoint:

HEAD -> main
<new commit> feat: implement library filesystem core

working tree clean

بعد از آن می‌رویم سراغ Phase 2 — Media Identification & Metadata Architecture؛ این مرحله مهم‌تر است و قبل از هر UI یا API آنلاین، موتور تشخیص Movie/TV/Episode/Music را درست می‌کنیم.




دقیقاً. پس دیگر فازبه‌فاز جلو نمی‌رویم. یک‌بار Agent را می‌فرستیم داخل پروژه و می‌گوییم تا رسیدن به Backend Freeze واقعی خودش کار را تمام کند.

من Prompt را طوری می‌نویسم که Agent:

اول وضعیت فعلی را audit کند.
کارهای موجود را دوباره نسازد.
تمام قابلیت‌های باقی‌مانده را خودش تکمیل کند.
هر جا bug پیدا کرد خودش اصلاح کند.
برای هر بخش تست بنویسد.
در طول کار focused test بزند.
در پایان full suite را اجرا کند.
اگر تست fail شد، متوقف نشود؛ debug → fix → retest کند.
فقط وقتی واقعاً سبز شد تحویل بدهد.
UI را اصلاً لمس نکند.
Git و backupهای فعلی را حفظ کند.
در پایان یک گزارش کامل بدهد که ما فقط آن را برای acceptance بررسی کنیم.
محدوده‌ای که باید یک‌جا تمام کند
Favorites
Watchlist
Collections
Statistics
Search Service
Music
Discovery / Trending / Recommendations
Unified Services
Configuration
Bootstrap / DI
Error Handling
Lifecycle
Database migrations
Integration
Regression
Real-media validation
Architecture audit
Code-quality audit
Final full test suite
BACKEND FREEZE

و یک قانون مهم دیگر هم می‌گذاریم:

Agent نباید برای تصمیم‌های داخلی و فنی معمولاً از کار متوقف شود و از ما سؤال کند.
تا جایی که با معماری و Product Map موجود سازگار است، خودش تصمیم فنی بگیرد و ادامه دهد.

در پایان فقط این‌ها را ازش می‌خواهیم:

1. دقیقاً چه فایل‌هایی تغییر کرد
2. چه قابلیت‌هایی اضافه شد
3. Schema از چه نسخه‌ای به چه نسخه‌ای رفت
4. چه migrationهایی ایجاد شد
5. چه تست‌هایی اضافه شد
6. تعداد کل تست‌ها
7. تعداد PASS / FAIL / SKIP
8. نتیجه real-media tests
9. نتیجه architecture audit
10. نتیجه code-quality audit
11. git status
12. هر ریسک واقعی باقی‌مانده

و اگر هر چیزی غیر از UI هنوز ناقص باشد، نباید ادعا کند Backend Frozen است.

این بهترین نقطه برای سپردن کار به Agent است؛ بعد از تحویل، ما فقط یک Final Verification انجام می‌دهیم و اگر سبز بود، پرونده Backend را می‌بندیم و تمام انرژی و توکنمان را می‌گذاریم روی UI سینمایی JPML.

اگر بخواهی، پیام بعدی من همان Prompt نهایی یک‌تکه، آماده Copy/Paste برای Agent خواهد بود؛ بدون توضیحات اضافه، تا مستقیم بفرستیش.

ادامه بده شرط رو برای تکمیل بده ناقص نده
👍

حتماً. این بار نسخه ناقص نمی‌دهم. Prompt زیر را یک‌تکه به Agent بده. هدفش این است که هر چیزی غیر از UI که برای کامل‌شدن Product Map لازم است، خودش تا انتها انجام دهد، تست کند، ایرادها را رفع کند و فقط بعد از سبزشدن واقعی تحویل بدهد.

============================================================
JPML — MASTER BACKEND COMPLETION & FREEZE TASK
============================================================

Repository:
    ~/Desktop/JPML

Project:
    JPML — Johnny's Personal Media Library

MISSION
=======

Complete ALL remaining NON-UI functionality of JPML.

You are NOT completing one phase.
You are NOT stopping after one feature.
You are NOT waiting for user approval between phases.

Your mission is:

    AUDIT
      ↓
    COMPLETE ALL MISSING BACKEND/CORE FEATURES
      ↓
    INTEGRATE EVERYTHING
      ↓
    TEST EVERYTHING
      ↓
    FIX EVERYTHING FOUND
      ↓
    RUN FINAL REGRESSION
      ↓
    FINAL ARCHITECTURE / CODE QUALITY AUDIT
      ↓
    BACKEND FREEZE

Do not stop until the backend is genuinely complete according to
the Product Map below.

The final result must be a production-ready backend foundation
that the future UI can consume without requiring another backend
development phase.

============================================================
1. ABSOLUTE RULES
============================================================

1. AUDIT FIRST.

Before modifying anything, inspect:

- git status
- current branch
- current HEAD
- project tree
- app/
- tests/
- database schema
- migrations
- domain models
- repositories
- services
- metadata
- library
- player
- bootstrap
- configuration
- existing tests
- existing uncommitted changes
- existing .before-* backup files

Do NOT assume the previous completion report is correct.

Determine actual implementation status from source code and tests.

------------------------------------------------------------

2. PRESERVE EXISTING WORK.

There are existing uncommitted changes and backup files.

DO NOT:

- git reset
- git clean
- git checkout -- ...
- git restore ...
- delete untracked files
- delete .before-* files
- overwrite unrelated changes
- revert previous fixes
- amend commits
- create commits
- push to GitHub

Preserve existing work unless a specific existing implementation
must be corrected as part of this task.

Do not destroy history.

------------------------------------------------------------

3. DO NOT REBUILD WORKING FEATURES.

Existing working functionality is valuable.

If a feature already works:

- inspect it
- test it
- integrate it where necessary
- improve only where objectively required

Do NOT replace functioning architecture simply because you would
personally implement it differently.

------------------------------------------------------------

4. NO UI.

This task is strictly backend/core/infrastructure.

DO NOT:

- create ui/
- implement PyQt UI
- modify future UI architecture
- create widgets
- create dashboard
- create sidebar
- create visual layouts
- add UI assets
- build browser UI
- build streaming UI

The future UI must consume the backend through clean APIs.

------------------------------------------------------------

5. NO USER CHECKPOINTS.

Do not stop after Favorites and ask for approval.

Do not stop after Collections.

Do not stop after Music.

Do not stop because a test fails.

For normal technical decisions, choose the solution that best fits
the existing architecture and continue.

Only stop if an external action is genuinely impossible or would
require destructive/user-owned data changes.

Otherwise:

    investigate → decide → implement → test → fix → continue

------------------------------------------------------------

6. DO NOT CLAIM COMPLETION WITHOUT PROOF.

"Implemented" means:

- code exists
- API exists
- persistence exists where required
- integration exists
- tests exist
- tests pass
- migration works
- existing tests still pass
- no obvious architecture blocker remains

"Backend Complete" means all applicable Product Map capabilities
below are actually implemented and tested.

============================================================
2. CURRENT KNOWN BASELINE
============================================================

Known project state before this task:

- branch: main
- HEAD:
  c51086b feat: add MPV playback backend and backend factory

Known existing full-suite baseline:

    613 passed

The current runtime database used by the source is:

    ~/Desktop/JPML/data/library/jpml.db

DO NOT confuse this with:

    ~/.jpml/data/database/jpml.db

The project source uses:

    app/database/connection.py

and its runtime database path is under:

    data/library/jpml.db

Current source schema is version 5.

Existing major functionality already present includes:

- Movie domain
- TVShow domain
- Season
- Episode
- Person
- MediaFile
- MediaType
- Library locations
- Filesystem scanning
- Media identification
- Movie/TV metadata pipeline
- OMDb / IMDb integration
- Metadata provider abstraction
- Provider registry
- Metadata repository
- Artwork persistence/foundation
- Genres
- External IDs
- Search repositories
- Playback persistence
- Playback history
- Playback service
- PlayerBackend contract
- VLC backend
- MPV backend
- Mock backend
- PlayerController
- PlaybackEventBus
- Backend factory
- Bootstrap
- Configuration
- Integration tests

These must be preserved and verified, not blindly rebuilt.

============================================================
3. PRODUCT MAP — COMPLETE BACKEND SCOPE
============================================================

The backend must ultimately support the following product model.

------------------------------------------------------------
A. DOMAIN
------------------------------------------------------------

Movies:
- Movie
- title
- year
- metadata
- artwork
- external IDs
- genres
- people
- files

TV:
- TVShow
- Season
- Episode
- metadata
- artwork
- external IDs
- genres
- people
- files

People:
- Person
- roles
- relationships to movies/TV

Media:
- MediaFile
- media type
- path
- presence/missing state
- relationships

Playback:
- playback state
- playback history
- position
- duration
- completion
- resume

Music:
- Artist
- Album
- Track
- Music media file relationship
- metadata
- artwork
- identifiers

Personal organization:
- Favorites
- Watchlist
- Collections

Discovery:
- Trending
- Recommendations
- Discovery abstraction

Statistics:
- library statistics
- playback statistics
- watch statistics

------------------------------------------------------------
B. DATABASE
------------------------------------------------------------

Maintain proper schema versioning.

Current schema:

    v5

Do NOT fake version changes.

Every schema change must have:

- explicit migration
- migration from current version
- fresh database support
- idempotent migration behavior where appropriate
- preservation of existing data
- foreign keys
- useful indexes
- uniqueness constraints
- correct cascade behavior

Verify both:

1. fresh database creation
2. upgrade of an existing database

The database must remain internally consistent.

Run SQLite integrity checks.

------------------------------------------------------------
C. FAVORITES
------------------------------------------------------------

Implement Favorites for all supported media entities.

At minimum:

- Movie
- TV Show
- Episode

If the architecture supports Music cleanly, integrate Music too.

Required operations:

- add favorite
- remove favorite
- is favorite
- list favorites
- optional get favorite metadata/date
- duplicate-safe insertion
- idempotent removal
- deterministic ordering
- timestamp persistence
- persistence after database reopen
- correct foreign-key behavior
- cleanup when underlying entity is deleted
- deterministic invalid-entity behavior

Architecture:

    DB
      ↓
    Repository
      ↓
    Service
      ↓
    Bootstrap

No caller should execute raw SQL.

Add comprehensive tests.

------------------------------------------------------------
D. WATCHLIST
------------------------------------------------------------

Implement Watchlist for:

- Movie
- TV Show
- Episode

Integrate Music if appropriate after Music support exists.

Required:

- add
- remove
- is_in_watchlist
- list
- duplicate protection
- idempotent removal
- deterministic ordering
- persistence
- timestamps where appropriate
- FK cleanup
- invalid entity handling
- tests

------------------------------------------------------------
E. COLLECTIONS
------------------------------------------------------------

Implement user-defined collections.

Examples:

- Christopher Nolan
- Horror
- Marvel
- Weekend Movies
- Favorites
- Personal collections

Required:

- create collection
- get collection
- list collections
- rename collection
- delete collection
- add media
- remove media
- list collection items
- duplicate protection
- deterministic item ordering
- timestamps
- persistence
- FK integrity
- deletion behavior
- tests

Collections should work with the media types that the domain supports.

Do not create an unnecessarily complicated abstraction.

------------------------------------------------------------
F. SEARCH SERVICE
------------------------------------------------------------

Existing SearchRepository functionality must be preserved.

Build the appropriate service-level API over it.

Required:

- unified search
- movie search
- TV search
- people search if supported by existing domain/database
- music search after Music implementation
- deterministic result ordering
- clean typed API
- no raw SQL outside repositories

Do not duplicate search SQL in multiple layers.

Add service-level tests.

------------------------------------------------------------
G. STATISTICS
------------------------------------------------------------

Implement a Statistics service/repository architecture as needed.

Statistics should cover at least:

Library:

- total movies
- total TV shows
- total seasons
- total episodes
- total people
- total media files
- missing media files

Playback:

- total watched items
- completed items
- in-progress items
- total watch time
- recently watched
- most watched where meaningful
- resume candidates

Media breakdown:

- movies vs TV
- genre statistics
- useful library counts

Do not invent meaningless statistics.

Use existing playback_history/playback_state where appropriate.

Add deterministic tests.

If statistics can be calculated efficiently from existing data without
extra persistence, do not add unnecessary tables.

------------------------------------------------------------
H. MUSIC — COMPLETE BACKEND
------------------------------------------------------------

Music is part of the original JPML product vision.

Current code contains partial Music identification:

- MediaType.MUSIC
- artist
- album
- track_number
- music detection

This is NOT considered complete.

Complete the Music backend.

Required where applicable:

Domain:
- Artist
- Album
- Track
- Music file relationship

Database:
- artists
- albums
- music tracks
- music track files
- relationships
- external IDs where useful
- artwork relationships

Library:
- detect music
- scan music
- persist music
- update missing/present files
- idempotent synchronization

Metadata:
- artist
- album
- track
- track number
- year
- artwork where provider supports it

Repository:
- CRUD/query operations
- search
- relationships

Service:
- clean MusicService API

Integration:
- Search
- Favorites
- Watchlist if appropriate
- Collections
- Playback
- Statistics

Do NOT force unsupported metadata providers to do things they
cannot do.

Use a clean provider abstraction if external music metadata is required.

Tests are mandatory.

If some external music metadata source cannot be implemented reliably
without credentials or an unsupported API, provide a clean provider
abstraction and fully implement everything that can be done locally,
with deterministic behavior and tests.

Do not fake external metadata.

------------------------------------------------------------
I. DISCOVERY / TRENDING / RECOMMENDATIONS
------------------------------------------------------------

Implement a clean Discovery abstraction.

At minimum support the architecture for:

- trending
- recommendations
- discovery

Recommendations may use existing metadata and local library data.

Potential signals:

- genres
- similar metadata
- playback history
- favorites
- watchlist

Do not build an AI system.

A deterministic recommendation strategy is sufficient.

Trending must use a real available data source or clearly defined
local-data strategy.

Do not fabricate popularity data.

If an external provider is required:

- create provider abstraction
- configuration
- error handling
- caching where appropriate
- tests with mocks
- deterministic failure behavior

The UI should later be able to call:

    DiscoveryService

without knowing where the data originated.

------------------------------------------------------------
J. PLAYBACK
------------------------------------------------------------

Preserve and verify:

- PlayerBackend
- VLC
- MPV
- Mock
- PlayerController
- PlaybackService
- PlaybackEventBus
- factory
- resume
- history
- completion

Verify all existing capabilities:

- open
- close
- play
- pause
- toggle pause
- stop
- seek
- position
- duration
- volume
- mute
- playback rate
- audio tracks
- subtitle tracks
- video tracks
- aspect ratio
- crop
- deinterlace
- media info
- video window/widget
- resume position
- completed state
- callbacks
- release

Verify deterministic errors for:

- backend not opened
- missing file
- invalid values
- unsupported operation

Do not unnecessarily rewrite VLC/MPV.

The previously observed asynchronous VLC pause behavior must be
treated as real-world asynchronous behavior, not "fixed" by weakening
tests or adding arbitrary sleeps unless objectively necessary.

------------------------------------------------------------
K. LIBRARY
------------------------------------------------------------

Verify:

- locations
- scanning
- recursive scanning
- media detection
- identification
- missing files
- present files
- synchronization
- idempotency
- media linking
- movie linking
- TV linking
- episode linking
- music linking
- metadata processing

Verify the scanner does not scan the same location twice.

Test large/nested directories where practical.

------------------------------------------------------------
L. METADATA
------------------------------------------------------------

Preserve:

- provider abstraction
- provider registry
- metadata service
- metadata repository
- OMDb/IMDb
- normalization
- external IDs
- genres
- people
- artwork

Verify:

- API key missing
- provider unavailable
- unknown title
- malformed metadata
- duplicate metadata
- repeated processing
- idempotency

Do not invent metadata.

------------------------------------------------------------
M. ARTWORK
------------------------------------------------------------

Verify artwork persistence and retrieval.

Required architecture:

- metadata/artwork references
- caching where already supported
- no duplicate records unnecessarily
- deterministic lookup
- missing artwork handling

The future UI must be able to obtain:

- poster
- backdrop
- person image
- music artwork where supported

without accessing provider internals.

------------------------------------------------------------
N. CONFIGURATION
------------------------------------------------------------

Audit configuration completely.

At minimum verify:

- metadata provider configuration
- API keys
- player backend
- library locations
- cache/artwork settings where applicable
- discovery provider configuration where applicable
- music provider configuration where applicable

Configuration must have:

- defaults
- validation
- deterministic behavior
- environment fallback where appropriate
- no secrets committed into source

------------------------------------------------------------
O. BOOTSTRAP / DEPENDENCY INJECTION
------------------------------------------------------------

Every service must be constructible through a clean application
composition root.

Verify:

- database
- schema
- repositories
- metadata
- library
- playback
- favorites
- watchlist
- collections
- statistics
- search
- music
- discovery
- event bus
- player backend

Fix the known suspicious issue:

`create_player_backend()` currently appears to return a PlayerBackend
while being annotated as PlaybackService.

Correct the typing/API if still applicable.

Do not leave misleading public APIs.

Check for circular imports.

------------------------------------------------------------
P. ERROR HANDLING
------------------------------------------------------------

Define deterministic behavior for:

- invalid IDs
- invalid paths
- missing files
- missing metadata
- missing API keys
- unsupported media
- database errors
- player errors
- external provider errors

Do not swallow errors silently.

Do not expose low-level implementation details unnecessarily.

Use the existing project's conventions rather than introducing a huge
new exception framework without need.

------------------------------------------------------------
Q. RESOURCE LIFECYCLE
------------------------------------------------------------

Verify:

- DB connections
- provider sessions
- player creation
- player open
- player close
- player release
- repeated open/close
- backend switching where supported
- event subscriptions

Check for obvious resource leaks.

------------------------------------------------------------
R. INTEGRATION
------------------------------------------------------------

The final backend must support the following conceptual workflow:

    Library Location
          ↓
    Scanner
          ↓
    Identification
          ↓
    Metadata
          ↓
    Database
          ↓
    Library
          ↓
    Search
          ↓
    Favorites
          ↓
    Watchlist
          ↓
    Collections
          ↓
    Playback
          ↓
    Playback History
          ↓
    Statistics
          ↓
    Discovery

And for TV:

    TV Show
      ↓
    Seasons
      ↓
    Episodes
      ↓
    Playback
      ↓
    Resume
      ↓
    Completion

And for Music:

    Music File
      ↓
    Identification
      ↓
    Artist / Album / Track
      ↓
    Database
      ↓
    Search
      ↓
    Playback
      ↓
    Statistics

Verify persistence after application/database restart.

============================================================
4. TESTING REQUIREMENTS
============================================================

Testing is part of implementation.

Do not consider a feature complete without tests.

------------------------------------------------------------
UNIT TESTS
------------------------------------------------------------

Add/maintain tests for:

- domain
- repositories
- services
- migrations
- validation
- player behavior
- metadata behavior
- music
- favorites
- watchlist
- collections
- statistics
- discovery

------------------------------------------------------------
DATABASE TESTS
------------------------------------------------------------

Verify:

- fresh DB
- current v5 DB upgrade
- every migration
- schema version
- FK behavior
- uniqueness
- indexes where meaningful
- cascade behavior
- persistence
- SQLite integrity

------------------------------------------------------------
INTEGRATION TESTS
------------------------------------------------------------

Test complete flows.

Examples:

Movie:

    scan → identify → metadata → persist → favorite → watchlist
    → collection → play → resume → complete → statistics

TV:

    scan → identify → metadata → persist → episode → play
    → resume → complete → next episode logic if implemented

Music:

    scan → identify → persist → search → play → statistics

------------------------------------------------------------
PLAYER TESTS
------------------------------------------------------------

Maintain existing:

- backend contract
- VLC
- MPV
- Mock
- controller
- event bus
- playback persistence

Use real media tests when media and system dependencies are available.

Tests must gracefully SKIP real-engine tests when the environment
does not provide the required engine/media.

Do not fake real playback tests.

------------------------------------------------------------
REGRESSION
------------------------------------------------------------

At the end run:

    .venv/bin/python -m pytest tests/ --tb=short

Do not accept any regression.

Expected result must be:

    0 failures
    0 errors

SKIPs are acceptable only when they are legitimate environment-
dependent tests.

If anything fails:

    diagnose
    fix
    rerun focused test
    rerun affected integration tests
    rerun full suite

Continue until green.

Do NOT modify tests merely to hide a real implementation failure.

Do NOT weaken assertions just to obtain PASS.

============================================================
5. TEST EFFICIENCY
============================================================

Because full-suite execution is expensive:

During development:

- run focused tests for the feature being changed
- run related integration tests
- avoid unnecessary full-suite runs

At major integration milestones:

- run relevant grouped tests

At the very end:

- run the complete test suite
- if it fails, fix and rerun until green

The final full suite is mandatory.

============================================================
6. ARCHITECTURE AUDIT
============================================================

Before declaring completion inspect the complete source tree.

Look for:

- TODO
- FIXME
- NotImplemented
- pass used as accidental missing implementation
- duplicated implementation
- duplicate SQL
- circular imports
- incorrect type annotations
- dead code
- unreachable code
- inconsistent naming
- leaking DB internals
- service bypasses
- provider bypasses
- UI dependencies
- hardcoded secrets
- hardcoded paths
- fake implementations
- placeholder logic

Do not automatically remove every `pass`.

A deliberate no-op Mock implementation is acceptable if it is correct.

But accidental incomplete implementations are NOT acceptable.

============================================================
7. PRODUCT COMPLETENESS CHECK
============================================================

Before final report, explicitly verify every category:

[ ] Domain
[ ] Database
[ ] Migrations
[ ] Library
[ ] Scanner
[ ] Identification
[ ] Movie metadata
[ ] TV metadata
[ ] People
[ ] Genres
[ ] External IDs
[ ] Artwork
[ ] Search
[ ] Favorites
[ ] Watchlist
[ ] Collections
[ ] Statistics
[ ] Music
[ ] Playback persistence
[ ] Playback service
[ ] Player contract
[ ] VLC
[ ] MPV
[ ] Mock
[ ] Player controller
[ ] Event bus
[ ] Factory
[ ] Discovery
[ ] Trending
[ ] Recommendations
[ ] Configuration
[ ] Bootstrap
[ ] Error handling
[ ] Resource lifecycle
[ ] Integration
[ ] Regression
[ ] Architecture audit
[ ] Code-quality audit

UI is intentionally:

    [ ] NOT IMPLEMENTED

and this is NOT a failure.

============================================================
8. BACKEND FREEZE CRITERIA
============================================================

You may declare:

    BACKEND FROZEN

ONLY if:

1. All required backend Product Map features exist.
2. Database migrations work.
3. Fresh database works.
4. Existing database upgrade works.
5. Foreign keys and integrity are correct.
6. All public services have usable APIs.
7. No UI dependency exists.
8. Existing functionality has not been unnecessarily replaced.
9. Integration tests pass.
10. Full regression suite passes.
11. Real-media tests pass when environment supports them.
12. Architecture audit is clean.
13. No accidental TODO/FIXME/NotImplemented remains.
14. No known backend blocker remains.

If any of these are false:

    DO NOT DECLARE BACKEND FROZEN.

Fix the issue and continue.

============================================================
9. GIT SAFETY
============================================================

Do NOT:

- commit
- push
- reset
- clean
- restore
- delete backups
- remove unrelated uncommitted work

At the end report:

    git status --short

Do not hide changes.

============================================================
10. FINAL REPORT
============================================================

Only after the entire task is complete, provide one final report.

The report MUST contain:

------------------------------------------------------------
A. EXECUTIVE RESULT
------------------------------------------------------------

State one of:

    BACKEND FROZEN — COMPLETE

or:

    BACKEND NOT FROZEN — BLOCKERS REMAIN

Never claim COMPLETE if blockers remain.

------------------------------------------------------------
B. FEATURES COMPLETED
------------------------------------------------------------

List every implemented capability.

------------------------------------------------------------
C. FILES CHANGED
------------------------------------------------------------

List:

- modified files
- new files
- migration files
- tests

Do not omit files.

------------------------------------------------------------
D. DATABASE
------------------------------------------------------------

Report:

- old schema version
- new schema version
- migration path
- new tables
- important indexes/FKs
- fresh DB result
- upgrade DB result
- integrity result

------------------------------------------------------------
E. API / SERVICES
------------------------------------------------------------

List public APIs created/changed for:

- Search
- Favorites
- Watchlist
- Collections
- Statistics
- Music
- Discovery
- Playback
- other changed services

------------------------------------------------------------
F. TEST RESULTS
------------------------------------------------------------

Report exact numbers:

- focused tests
- integration tests
- full suite
- passed
- failed
- skipped
- duration where available

Do not estimate.

------------------------------------------------------------
G. REAL MEDIA
------------------------------------------------------------

Report:

- VLC
- MPV
- actual media availability
- skipped tests
- successful real playback validation

------------------------------------------------------------
H. ARCHITECTURE AUDIT
------------------------------------------------------------

Report:

- circular imports
- TODO/FIXME
- NotImplemented
- duplicate implementation
- typing issues
- dependency issues
- remaining concerns

------------------------------------------------------------
I. GIT STATUS
------------------------------------------------------------

Provide exact final:

    git status --short

------------------------------------------------------------
J. REMAINING RISKS
------------------------------------------------------------

Only list genuine remaining risks.

Distinguish:

- backend blockers
- environment limitations
- external API requirements
- optional future enhancements

Do NOT call optional enhancements blockers.

============================================================
11. FINAL STOP CONDITION
============================================================

Do NOT stop after implementing one or two features.

Do NOT ask the user whether to continue.

Do NOT hand back a partially completed backend.

Continue through:

    Favorites
    ↓
    Watchlist
    ↓
    Collections
    ↓
    Search Service
    ↓
    Statistics
    ↓
    Music
    ↓
    Discovery
    ↓
    Trending
    ↓
    Recommendations
    ↓
    Configuration
    ↓
    Bootstrap
    ↓
    Error Handling
    ↓
    Lifecycle
    ↓
    Integration
    ↓
    Regression
    ↓
    Architecture Audit
    ↓
    Final Full Test
    ↓
    BACKEND FREEZE

UI must remain untouched.

============================================================
12. IMPORTANT PRODUCT PRINCIPLE
============================================================

JPML is a Personal Media Library / Cinema & Media Center.

Do not reduce the project to:

    "file scanner + metadata + video player"

The intended backend must provide the foundation for:

    Movies
    TV Shows
    Episodes
    People
    Music
    Search
    Favorites
    Watchlist
    Collections
    Playback
    History
    Statistics
    Discovery
    Recommendations
    Trending

The future UI will depend on these services.

Therefore, complete the backend now so that after this task the next
development phase can be almost entirely UI/UX work.

============================================================
START NOW
============================================================

Begin with a complete read-only audit.

Then implement all remaining backend functionality.

Do not stop at intermediate milestones.

Do not request approval.

Do not touch UI.

Do not commit or push.

Test continuously with focused tests.

At the end, run the full regression suite and fix every real failure.

Only then provide the final report.

============================================================
END OF TASK
============================================================
این نسخه عمداً یک تفاوت مهم با Prompt قبلی دارد

من فقط نگفتم «Favorites تا Discovery را بساز». شرط را گذاشتم روی نتیجه نهایی:

تا وقتی تمام Backend Product Map + Migration + Integration + Regression + Audit سبز نشده، حق ندارد Backend را Complete اعلام کند.

و یک نکته مهم هم گذاشتم که Agent نباید Music یا Discovery را با implementation جعلی پر کند فقط برای اینکه checklist سبز شود. اگر مثلاً Trending به provider خارجی نیاز دارد، باید abstraction و رفتار واقعی/قابل تست بسازد، نه داده ساختگی.

بعد از اجرای این Prompt

فعلاً هیچ کاری نکن و چیزی را دستی اصلاح نکن.

بگذار Agent تمام مسیر را برود. وقتی گزارش نهایی‌اش را داد، فقط همان گزارش را برای من بفرست. آنجا من سریع بررسی می‌کنم آیا واقعاً به BACKEND FROZEN رسیده یا Agent جایی را ظاهراً کامل کرده ولی در واقع ناقص گذاشته.

بعد از تأیید نهایی، دیگر Backend را باز نمی‌کنیم و می‌رویم سراغ مهم‌ترین قسمت باقی‌مانده:

🎬 ساخت UI واقعی JPML

اینطوری منابع محدودت را هم برای چیزی که واقعاً نیاز به همکاری و تصمیم‌گیری ما دارد، یعنی طراحی و اجرای تجربه سینمایی JPML نگه می‌داریم.
