"""JPML application shell: sidebar + stacked screens + top bar.

Owns the Navigation instance, the ThemeManager, the service
composition, and global keyboard handling. Individual screens are
plain QWidget providers registered by name.
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.app.composition import build_services
from ui.app.navigation import Navigation, Route
from ui.app.view_model import UiContext
from ui.components.common.toast import ToastHost
from ui.components.navigation.sidebar import (
    DISCOVER_SECTION,
    LIBRARY_SECTION,
    MY_LIBRARY_SECTION,
    NAV_ITEMS,
    Sidebar,
)
from ui.components.navigation.top_bar import TopBar
from ui.themes.tokens import Layout, Spacing
from ui.themes.theme_manager import ThemeManager, ThemeMode


def _route_title(route: Route) -> tuple[str, str]:
    section_of: dict[str, str] = {}
    for section, items in NAV_ITEMS.items():
        for item in items:
            section_of[item.route] = section
    section = section_of.get(route.screen, "")
    if route.screen == "settings":
        title, crumb = "Settings", ""
    elif route.screen in ("details", "player", "collection_detail"):
        base = {
            "details": "Details",
            "player": "Now Playing",
            "collection_detail": "Collection",
        }[route.screen]
        crumb = base
        title = str(route.params.get("title") or base)
    else:
        label = route.screen
        for section_name in (LIBRARY_SECTION, DISCOVER_SECTION, MY_LIBRARY_SECTION):
            for item in NAV_ITEMS.get(section_name, []):
                if item.route == route.screen:
                    label = item.label
        title = label
        crumb = section.lower() if section else ""
    return title, crumb


class MainWindow(QMainWindow):
    """Official JPML desktop application window."""

    def __init__(self, *, player_backend: str = "vlc") -> None:
        super().__init__()
        self.setWindowTitle("JPML — Johnny's Personal Media Library")
        self.resize(1440, 900)
        self.setMinimumSize(1280, 720)

        self.services = build_services()
        self.services.extras["player_backend"] = player_backend
        self.navigation = Navigation(initial="home")
        self.theme_manager: ThemeManager | None = None  # set by attach()
        self._context = UiContext(
            services=self.services,
            navigation=self.navigation,
        )
        self._player_backend = player_backend
        self._screens: dict[str, QWidget] = {}
        self._screen_factories: dict[str, Callable[[], QWidget]] = {}
        self._current_screen_name: str | None = None

        self._build_shell()
        self._register_screens()
        self._on_route_changed(self.navigation.current_route)

    def _register_screens(self) -> None:
        from ui.app import run_state

        run_state.register_all(self, self._player_backend)

        # global keys
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self._on_global_search)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._on_escape)
        self._back_shortcut = QShortcut(QKeySequence("Alt+Left"), self)
        self._back_shortcut.activated.connect(self._on_back)

        # search debounce
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._run_pending_search)
        self._pending_query: str = ""

        self.navigation.route_changed.connect(self._on_route_changed)

    # -- shell construction ------------------------------------------------------

    def _build_shell(self) -> None:
        central = QWidget()
        central.setObjectName("AppBackground")
        self.setCentralWidget(central)

        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._sidebar = Sidebar()
        self._sidebar.navigation_requested.connect(self._on_sidebar_nav)
        outer.addWidget(self._sidebar)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._top_bar = TopBar()
        self._top_bar.search_requested.connect(self._on_search_input)
        right_layout.addWidget(self._top_bar)

        content_wrap = QWidget()
        content_layout = QVBoxLayout(content_wrap)
        content_layout.setContentsMargins(
            Layout.CONTENT_PAD_H, Layout.CONTENT_PAD_TOP,
            Layout.CONTENT_PAD_H, Layout.CONTENT_PAD_BOTTOM,
        )
        self._stack = QStackedWidget()
        content_layout.addWidget(self._stack)
        right_layout.addWidget(content_wrap, 1)

        outer.addWidget(right, 1)

        self._toast_host = ToastHost(self)

    # -- screen registration -------------------------------------------------------

    def register_screen(self, name: str, factory: Callable[[], QWidget]) -> None:
        self._screen_factories[name] = factory

    def _screen_for(self, name: str) -> QWidget:
        if name not in self._screens:
            widget = self._screen_factories[name](self._context)
            self._screens[name] = widget
        return self._screens[name]

    # -- theme -----------------------------------------------------------------------

    def set_theme_manager(self, manager: ThemeManager, mode: ThemeMode) -> None:
        self.theme_manager = manager
        manager.theme_changed.connect(self._on_theme_changed)
        manager.set_mode(mode)

    def _on_theme_changed(self, theme_name: str) -> None:
        for widget in self._screens.values():
            refresher = getattr(widget, "refresh_theme", None)
            if callable(refresher):
                refresher()

    # -- navigation ----------------------------------------------------------------------

    def _on_sidebar_nav(self, route: str) -> None:
        current = self.navigation.current_route
        # The sidebar re-emits when set_active_route() programmatically
        # checks its buttons after a route change; ignore that echo so
        # history is not polluted with duplicate entries.
        if current is not None and current.screen == route:
            return
        self.navigation.navigate(route)

    def _on_route_changed(self, route: Route | None, initial: bool = False) -> None:
        if route is None:
            route = Route("home")
        widget = self._screen_for(route.screen)
        index = self._stack.indexOf(widget)
        if index < 0:
            index = self._stack.addWidget(widget)
        self._stack.setCurrentIndex(index)
        self._current_screen_name = route.screen
        title, crumb = _route_title(route)
        self._top_bar.set_title(title, crumb)
        show_search = route.screen not in ("player",)
        self._top_bar.set_search_enabled(show_search)
        self._sidebar.set_active_route(route.screen)
        activator = getattr(widget, "on_activated", None)
        if callable(activator):
            activator()

    def back(self) -> bool:
        previous = self.navigation.back()
        return previous is not None

    def goto(self, route: Route) -> None:
        self.navigation.navigate(route.screen, **route.params)

    # -- global actions ----------------------------------------------------------------------

    def _on_global_search(self) -> None:
        self._top_bar.focus_search()

    def _on_search_input(self, query: str) -> None:
        self._pending_query = query
        if not query:
            if self.navigation.current_route and \
                    self.navigation.current_route.screen == "search":
                self.navigation.back()
            self._search_timer.stop()
            return
        self._search_timer.start()

    def _run_pending_search(self) -> None:
        query = self._pending_query.strip()
        if not query:
            return
        self.navigation.navigate("search", query=query)

    def _on_escape(self) -> None:
        route = self.navigation.current_route
        if route and route.screen == "player":
            self.navigation.back()
            return
        # ask the current screen to handle escape first (menus/filters)
        widget = self._stack.currentWidget()
        handler = getattr(widget, "handle_escape", None)
        if callable(handler) and handler() is True:
            return
        self.back()

    def _on_back(self) -> None:
        self.back()

    # -- toast helper -------------------------------------------------------------------------

    def toast(self, message: str) -> None:
        self._toast_host.show_message(message)

    # -- teardown -----------------------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        closer = getattr(self, "_close_all_screens", None)
        if callable(closer):
            closer()
        super().closeEvent(event)

    def _close_all_screens(self) -> None:
        from PyQt6.QtWidgets import QApplication

        from ui.app import library_flow

        worker = library_flow.current_scan_worker(QApplication.instance())
        if worker is not None and worker.isRunning():
            worker.wait(10_000)
        for widget in self._screens.values():
            closer = getattr(widget, "shutdown", None)
            if callable(closer):
                try:
                    closer()
                except Exception:
                    pass
