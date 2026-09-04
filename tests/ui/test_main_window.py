"""MainWindow construction, shell parts and the screen registry."""
from __future__ import annotations

from PyQt6.QtWidgets import QStackedWidget, QWidget

from ui.app.main_window import MainWindow
from ui.app.navigation import Route
from ui.components.navigation.sidebar import Sidebar
from ui.components.navigation.top_bar import TopBar

from conftest import ALL_ROUTES


def test_main_window_shell_is_complete(window):
    assert window.windowTitle() == "JPML — Johnny's Personal Media Library"
    assert window.centralWidget() is not None
    assert isinstance(window._sidebar, Sidebar)
    assert isinstance(window._top_bar, TopBar)
    assert isinstance(window._stack, QStackedWidget)
    assert window._stack.count() >= 1
    # the sidebar's initial state pushes "home" onto history at startup
    assert window.navigation.current_route == Route("home")


def test_attach_exposes_app_state(window, qapp):
    state = getattr(qapp, "jpml_state", None)
    assert state is not None
    assert state.player_backend == "mock"
    assert state.theme is not None


def test_services_composition_attached(window):
    assert window.services is not None
    assert window.services.extras["player_backend"] == "mock"
    assert window.navigation is not None


def test_all_registered_routes_construct_successfully(window):
    for route in ALL_ROUTES:
        assert route in window._screen_factories, f"route {route!r} not registered"
        widget = window._screen_for(route)
        assert isinstance(widget, QWidget), f"route {route!r} did not construct"
    assert set(window._screens) >= set(ALL_ROUTES)


def test_navigation_visits_every_registered_route(window):
    for route in ALL_ROUTES:
        window.navigation.navigate(route)
        current = window._stack.currentWidget()
        assert current is window._screens[route], (
            f"navigating to {route!r} did not show its screen"
        )
    window.navigation.navigate("home")
    assert window._stack.currentWidget() is window._screens["home"]


def test_fresh_player_window_is_constructible(qapp):
    win = MainWindow(player_backend="mock")
    try:
        assert win._player_backend == "mock"
        assert "player" in win._screen_factories
        assert set(win._screen_factories) >= set(ALL_ROUTES)
    finally:
        win.close()
        qapp.processEvents()
