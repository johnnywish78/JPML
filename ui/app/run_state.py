"""Binds the UI application: theme, player backend and screen registry."""
from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from ui.app.main_window import MainWindow
from ui.themes.theme_manager import ThemeManager, ThemeMode


class AppState:
    """Held on the QApplication instance (app.jpml_state)."""

    def __init__(self, theme_manager: ThemeManager, player_backend: str) -> None:
        self.theme = theme_manager
        self.player_backend = player_backend
        #: the running library scan worker, if any (shared UI state)
        self.scan_worker = None


def attach(
    app: QApplication,
    window: MainWindow,
    theme_manager: ThemeManager,
    args,
) -> None:
    """Wires theme + player backend. Screen registration already happens
    during MainWindow construction."""
    app.jpml_state = AppState(theme_manager, args.backend)  # type: ignore[attr-defined]
    window.set_theme_manager(theme_manager, ThemeMode(args.theme))


def register_all(window: MainWindow, player_backend: str) -> None:
    """Registers every screen factory with the shell.

    Player selection is backend-agnostic: the PlayerScreen talks to
    PlayerController, which owns the concrete backend (vlc/mpv/mock).
    """
    from ui.screens.browser import BrowserScreen
    from ui.screens.collections import CollectionsScreen
    from ui.screens.details import DetailsScreen
    from ui.screens.favorites import FavoritesScreen
    from ui.screens.home import HomeScreen
    from ui.screens.library import LibraryScreen
    from ui.screens.music import MusicScreen
    from ui.screens.people import PeopleScreen
    from ui.screens.player import PlayerScreen
    from ui.screens.movies import MoviesScreen
    from ui.screens.recommendations import RecommendationsScreen
    from ui.screens.search import SearchScreen
    from ui.screens.settings import SettingsScreen
    from ui.screens.services import ServicesScreen
    from ui.screens.statistics import StatisticsScreen
    from ui.screens.trending import TrendingScreen
    from ui.screens.tv_shows import TvShowsScreen
    from ui.screens.tv_time import TvTimeScreen
    from ui.screens.watchlist import WatchlistScreen

    window.register_screen("home", lambda ctx: HomeScreen(ctx))
    window.register_screen("movies", lambda ctx: MoviesScreen(ctx))
    window.register_screen("tv_shows", lambda ctx: TvShowsScreen(ctx))
    window.register_screen("tv_time", lambda ctx: TvTimeScreen(ctx))
    window.register_screen("people", lambda ctx: PeopleScreen(ctx))
    window.register_screen("music", lambda ctx: MusicScreen(ctx))
    window.register_screen("library", lambda ctx: LibraryScreen(ctx))
    window.register_screen("trending", lambda ctx: TrendingScreen(ctx))
    window.register_screen("recommendations", lambda ctx: RecommendationsScreen(ctx))
    window.register_screen("favorites", lambda ctx: FavoritesScreen(ctx))
    window.register_screen("watchlist", lambda ctx: WatchlistScreen(ctx))
    window.register_screen("collections", lambda ctx: CollectionsScreen(ctx))
    window.register_screen("search", lambda ctx: SearchScreen(ctx))
    window.register_screen("details", lambda ctx: DetailsScreen(ctx))
    window.register_screen("statistics", lambda ctx: StatisticsScreen(ctx))
    window.register_screen("settings", lambda ctx: SettingsScreen(ctx))
    window.register_screen("services", lambda ctx: ServicesScreen(ctx))
    window.register_screen("browser", lambda ctx: BrowserScreen(ctx))

    def _player_factory(ctx):
        return PlayerScreen(ctx, backend_name=player_backend)

    window.register_screen("player", _player_factory)
