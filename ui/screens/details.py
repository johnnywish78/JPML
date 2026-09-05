"""Details — media hero, metadata, actions, similar items.

Displays title, year, overview, genres, backdrop/poster, progress,
external IDs (IMDb/TMDB), cast/crew, similar items, and for TV shows:
seasons and episodes.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.app import data
from ui.app.screen_actions import ScreenActions
from ui.components.cards.person_card import PersonCard
from ui.components.common.page_header import PageHeader
from ui.components.common.screen import BaseScreen
from ui.components.media.artwork import Artwork
from ui.components.media.media_grid import MediaGridView
from ui.components.media.media_row import CardFactory, MediaRow, SectionHeader
from ui.models import EntityRef
from ui.themes.tokens import Spacing, Typography


class DetailsScreen(BaseScreen, ScreenActions):
    def __init__(self, context) -> None:
        super().__init__(context)
        self._kind = ""
        self._entity_id = 0
        self._ref: EntityRef | None = None

    def empty_title(self) -> str:
        return "Can't find this item"

    def empty_subtitle(self) -> str:
        return "It may have been removed from your library."

    def page_title(self) -> str:
        return "Details"

    def on_activated(self) -> None:
        if self._scan_in_progress():
            self._begin_watch_scan()
            self.show_scanning("Scanning your library...")
            return
        self._stop_watching_scan()
        route = self.context.navigation.current_route
        if route is None:
            return
        self._kind = str(route.params.get("kind", "movie"))
        self._entity_id = int(route.params.get("entity_id", 0))
        self.load()

    def load(self) -> None:
        self.start_async_load(self._gather)

    def _gather(self, services):
        ref = data.entity_ref_for_details(services, self._kind, self._entity_id)
        extra: dict = {}
        if self._kind in ("movie", "tv"):
            extra["genres"] = (
                data.fetch_movie_genres(services, self._entity_id)
                if self._kind == "movie"
                else data.fetch_tv_genres(services, self._entity_id)
            )
            extra["similar"] = (
                data.fetch_similar(services, ref) if ref is not None else []
            )
            extra["external_ids"] = data.fetch_external_ids(
                services, self._kind, self._entity_id
            )
            extra["people"] = data.fetch_people_by_entity(
                services, self._kind, self._entity_id
            )
            if self._kind == "tv":
                seasons = services.metadata_repository.list_seasons(self._entity_id)
                extra["seasons"] = seasons
                # Fetch episodes for each season
                for season in seasons:
                    season["episodes"] = services.metadata_repository.list_episodes(season["id"])
        elif self._kind == "album":
            all_tracks = data.fetch_tracks(services)
            extra["tracks"] = [
                t for t in all_tracks if t.album_id == self._entity_id
            ]
        elif self._kind == "artist":
            all_albums = data.fetch_albums(services)
            extra["albums"] = [
                a for a in all_albums if a.extra.get("artist_id") == self._entity_id
            ]
        return (ref, extra)

    def handle_data(self, payload) -> None:
        self.clear_content()
        ref, extra = payload
        if ref is None:
            self.show_empty()
            return
        self._ref = ref
        self._render(ref, extra)
        self.show_content()

    # -- rendering ----------------------------------------------------------

    def _render(self, ref: EntityRef, extra: dict) -> None:
        if ref.kind in ("movie", "tv", "album", "artist", "track", "person"):
            self._render_media(ref, extra)

    def _render_media(self, ref: EntityRef, extra: dict) -> None:
        header = self._media_header(ref)
        self.add_to_content(header)

        play_row = QHBoxLayout()
        play_row.setSpacing(Spacing.M)
        play_button = QPushButton("▶  Play" if ref.kind != "track" else "▶  Play")
        play_button.setObjectName("PrimaryButton")
        play_button.setCursor(Qt.CursorShape.PointingHandCursor)
        play_button.clicked.connect(lambda: self.play_entity(ref))
        play_row.addWidget(play_button)

        fav_button = QPushButton(
            "♥  In Favorites" if ref.is_favorite else "♡  Add to Favorites"
        )
        fav_button.setObjectName("GhostButton")
        fav_button.setCursor(Qt.CursorShape.PointingHandCursor)
        fav_button.clicked.connect(lambda: self.entity_action(ref, "favorite"))
        play_row.addWidget(fav_button)

        wl_button = QPushButton(
            "−  In Watchlist" if ref.in_watchlist else "+  Add to Watchlist"
        )
        wl_button.setObjectName("GhostButton")
        wl_button.setCursor(Qt.CursorShape.PointingHandCursor)
        wl_button.clicked.connect(lambda: self.entity_action(ref, "watchlist"))
        play_row.addWidget(wl_button)
        play_row.addStretch(1)
        wrap = QWidget()
        wrap_layout = QVBoxLayout(wrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.addLayout(play_row)
        self.add_to_content(wrap)

        if ref.kind == "movie" or ref.kind == "tv":
            genres = extra.get("genres") or []
            if genres:
                chips = QLabel(" · ".join(genres))
                chips.setObjectName("SecondaryLabel")
                chips.setStyleSheet(
                    f"font-size: {Typography.METADATA_PX}px; margin-top: 10px; "
                    "background: transparent;"
                )
                self.add_to_content(chips)

            # External IDs
            external_ids = extra.get("external_ids") or []
            if external_ids:
                id_labels = []
                for eid in external_ids:
                    provider = eid.get("provider", "")
                    ext_id = eid.get("external_id", "")
                    if provider == "imdb" and ext_id:
                        id_labels.append(f"IMDb: {ext_id}")
                    elif provider == "tmdb" and ext_id:
                        id_labels.append(f"TMDB: {ext_id}")
                if id_labels:
                    ids_label = QLabel("  ·  ".join(id_labels))
                    ids_label.setObjectName("SecondaryLabel")
                    ids_label.setStyleSheet(
                        f"font-size: {Typography.METADATA_PX}px; margin-top: 6px; "
                        "background: transparent;"
                    )
                    self.add_to_content(ids_label)

            # Cast / crew
            people = extra.get("people") or []
            if people:
                self._cast_row(people)

            similar = extra.get("similar") or []
            if similar:
                self._section_row("You Might Also Like", similar)

            # TV seasons
            if ref.kind == "tv":
                seasons = extra.get("seasons") or []
                if seasons:
                    self._seasons_row(seasons)
        elif ref.kind == "album":
            tracks = extra.get("tracks") or []
            if tracks:
                self._track_list(tracks)
        elif ref.kind == "artist":
            albums = extra.get("albums") or []
            if albums:
                self._section_row("Albums", albums, square=True)
        elif ref.kind == "person":
            # Show person bio if available
            if getattr(ref, "overview", None):
                bio = QLabel(ref.overview)
                bio.setWordWrap(True)
                bio.setFixedWidth(640)
                bio.setStyleSheet(
                    f"font-size: {Typography.METADATA_PX}px; color: #A7ABB5; "
                    "background: transparent;"
                )
                self.add_to_content(bio)

    def _media_header(self, ref: EntityRef) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, Spacing.M)
        layout.setSpacing(Spacing.XL)

        kind = ref.artwork_kind
        if kind == "backdrop":
            art_w, art_h = 320, 180
        elif kind in ("album", "artist", "person"):
            art_w = art_h = 220
        else:
            art_w, art_h = 150, 225
        art = Artwork(art_w, art_h, kind=kind,
                      kind_glyph={"album": "♫", "artist": "🎵", "person": "👤"}.get(kind, "▦"))
        art.set_source(
            (ref.artwork or {}).get("local_path") if ref.artwork else None,
        )
        layout.addWidget(art)

        text = QWidget()
        tl = QVBoxLayout(text)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(6)
        title = QLabel(ref.title)
        title.setStyleSheet(
            f"font-size: {Typography.HERO_PX - 12}px; font-weight: 700; "
            "background: transparent;"
        )
        tl.addWidget(title)
        meta_bits = []
        if ref.year:
            meta_bits.append(str(ref.year))
        if ref.meta:
            meta_bits.append(ref.meta)
        if meta_bits:
            meta = QLabel(" · ".join(meta_bits))
            meta.setObjectName("SecondaryLabel")
            meta.setStyleSheet(
                f"font-size: {Typography.METADATA_PX + 1}px; background: transparent;"
            )
            tl.addWidget(meta)
        if getattr(ref, "overview", None):
            overview = QLabel(ref.overview)
            overview.setWordWrap(True)
            overview.setFixedWidth(640)
            overview.setStyleSheet(
                f"font-size: {Typography.METADATA_PX}px; color: #A7ABB5; "
                "background: transparent;"
            )
            tl.addWidget(overview)
        if ref.progress is not None:
            label = QLabel(
                f"Playback progress: {max(0, min(100, int(ref.progress * 100)))}%"
                + (f" · {ref.progress_label}" if ref.progress_label else "")
            )
            label.setObjectName("SecondaryLabel")
            label.setStyleSheet(
                f"font-size: {Typography.METADATA_PX}px; background: transparent;"
            )
            tl.addWidget(label)
        if ref.completed:
            completed = QLabel("Completed ✓")
            completed.setStyleSheet(
                "font-size: 13px; color: #3DBE7B; background: transparent;"
            )
            tl.addWidget(completed)
        layout.addWidget(text)
        layout.addStretch(1)
        return header

    def _cast_row(self, people: list[dict]) -> None:
        """Render cast/crew as a horizontal scrollable row."""
        header = SectionHeader("Cast & Crew")
        self.add_to_content(header)
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(Spacing.M)
        for person in people[:20]:
            card = PersonCard(120, parent=row)
            person_ref = EntityRef(
                kind="person",
                entity_id=person["id"],
                title=person["name"],
                overview=person.get("biography"),
                artwork_kind="person",
            )
            if person.get("artwork"):
                person_ref.artwork = person["artwork"]
            card.set_entity(person_ref)
            card.details_requested.connect(
                lambda r=person_ref: self.open_details(r)
            )
            lay.addWidget(card)
        self.add_to_content(row)

    def _seasons_row(self, seasons: list[dict]) -> None:
        """Render seasons as sections with episodes."""
        for season in seasons:
            season_num = season.get("season_number", 0)
            season_header = SectionHeader(f"Season {season_num}")
            self.add_to_content(season_header)

            episodes = season.get("episodes") or []
            for ep in episodes:
                ep_widget = QWidget()
                ep_lay = QHBoxLayout(ep_widget)
                ep_lay.setContentsMargins(Spacing.M, Spacing.S, Spacing.M, Spacing.S)

                ep_num = QLabel(f"E{ep.get('episode_number', 0):02d}")
                ep_num.setFixedWidth(50)
                ep_num.setStyleSheet(
                    f"font-size: {Typography.METADATA_PX}px; font-weight: 600; "
                    "background: transparent;"
                )
                ep_title = QLabel(ep.get("title") or f"Episode {ep.get('episode_number', 0)}")
                ep_title.setStyleSheet(
                    f"font-size: {Typography.CARD_PX}px; background: transparent;"
                )
                ep_lay.addWidget(ep_num)
                ep_lay.addWidget(ep_title)
                if ep.get("overview"):
                    ep_overview = QLabel(ep["overview"][:100] + ("..." if len(ep["overview"]) > 100 else ""))
                    ep_overview.setObjectName("SecondaryLabel")
                    ep_overview.setStyleSheet(
                        f"font-size: {Typography.METADATA_PX}px; background: transparent;"
                    )
                    ep_lay.addWidget(ep_overview)
                ep_lay.addStretch(1)
                self.add_to_content(ep_widget)

    def _section_row(
        self, title: str, items: list[EntityRef], square: bool = False
    ) -> None:
        header = SectionHeader(title)
        self.add_to_content(header)
        factory = CardFactory()
        factory._width = 170  # noqa: SLF001
        row = MediaRow(factory, self.container)
        for entity in items[:12]:
            card = factory.card(row)
            card.set_entity(entity)
            row.add_card(card)
            card.play_requested.connect(lambda ref: self.play_entity(ref))
            card.details_requested.connect(lambda ref: self.open_details(ref))
            card.action_requested.connect(
                lambda ref, action: self.entity_action(ref, action)
            )
            card.menu_requested.connect(
                lambda ref, pos: self.entity_context_menu(ref, pos)
            )
        self.add_to_content(row)

    def _track_list(self, tracks) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        for index, track in enumerate(tracks[:60], start=1):
            row_widget = QHBoxLayout()
            row_widget.setSpacing(Spacing.M)
            number = QLabel(str(track.track_number or index))
            number.setFixedWidth(28)
            number.setStyleSheet(
                f"color: #6F7480; font-size: {Typography.METADATA_PX}px; "
                "background: transparent;"
            )
            title = QLabel(track.title)
            title.setStyleSheet(
                f"font-size: {Typography.CARD_PX}px; background: transparent;"
            )
            title.setFixedWidth(320)
            artist = QLabel(track.meta)
            artist.setObjectName("SecondaryLabel")
            artist.setStyleSheet(
                f"font-size: {Typography.METADATA_PX}px; background: transparent;"
            )
            row_widget.addWidget(number)
            row_widget.addWidget(title)
            row_widget.addWidget(artist)
            row_widget.addStretch(1)
            play = QPushButton("▶")
            play.setObjectName("IconButton")
            play.setCursor(Qt.CursorShape.PointingHandCursor)
            play.clicked.connect(lambda _=False, ref=track: self.play_entity(ref))
            row_widget.addWidget(play)
            wrap = QWidget()
            wrap_layout = QVBoxLayout(wrap)
            wrap_layout.setContentsMargins(0, 0, 0, 0)
            wrap_layout.addLayout(row_widget)
            layout.addWidget(wrap)
        header = SectionHeader("Tracks")
        self.add_to_content(header)
        self.add_to_content(container)

    def refresh_theme(self) -> None:
        pass
