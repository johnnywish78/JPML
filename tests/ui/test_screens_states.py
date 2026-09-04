"""Screen lifecycle states: empty library, player missing-file, errors.

All cases run against the real empty database (read-only).
"""
from __future__ import annotations

from ui.app.app_state import ScreenState
from ui.app.navigation import Navigation
from ui.app.view_model import BaseViewModel, UiContext
from ui.models import EntityRef

from conftest import find_label, find_label_starting_with, visible_label_texts, wait_until


def _terminal_reached(screen) -> bool:
    return screen.state() in ("ready", "empty", "error")


# --------------------------------------------------------------------------- #
# Empty-library states                                                        #
# --------------------------------------------------------------------------- #


def test_home_empty_library_state(window):
    window.navigation.navigate("home")
    screen = window._screens["home"]
    assert wait_until(lambda: _terminal_reached(screen))
    assert screen.state() == "empty"
    assert find_label(screen._empty_widget, "Your library is empty") is not None


def test_movies_empty_library_state(window):
    window.navigation.navigate("movies")
    screen = window._screens["movies"]
    assert wait_until(lambda: _terminal_reached(screen))
    assert screen.state() == "empty"
    assert find_label(screen._empty_widget, "No Movies Yet") is not None


def test_favorites_empty_state_with_action(window):
    window.navigation.navigate("favorites")
    screen = window._screens["favorites"]
    assert wait_until(lambda: _terminal_reached(screen))
    assert screen.state() == "empty"
    assert find_label(screen._empty_widget, "Your Favorites are Empty") is not None
    assert screen._empty_widget.action_button is not None
    assert screen._empty_widget.action_button.text() == "Browse Movies"
    screen._empty_widget.action_button.click()
    assert window.navigation.current_route.screen == "movies"


def test_watchlist_empty_state(window):
    window.navigation.navigate("watchlist")
    screen = window._screens["watchlist"]
    assert wait_until(lambda: _terminal_reached(screen))
    assert screen.state() == "empty"
    assert find_label(screen._empty_widget, "Your Watchlist is Empty") is not None


def test_details_unknown_entity_shows_empty(window):
    window.navigation.navigate("details", kind="movie", entity_id=999999, title="X")
    screen = window._screens["details"]
    assert wait_until(lambda: _terminal_reached(screen))
    assert screen.state() == "empty"
    assert find_label(screen._empty_widget, "Can't find this item") is not None


# --------------------------------------------------------------------------- #
# Player missing-file state                                                   #
# --------------------------------------------------------------------------- #


def test_player_without_params_shows_unavailable(window):
    window.navigation.navigate("player")
    screen = window._screens["player"]
    assert screen._controller is None  # nothing was started
    assert screen._views._stack.currentWidget() is screen._missing_widget
    assert find_label_starting_with(screen._missing_widget, "The media file")


def test_player_missing_file_shows_unavailable_not_playback(window):
    window.navigation.navigate(
        "player",
        kind="movie",
        entity_id=1,
        title="Gone",
        file_path="/nonexistent/jpml-ui-test-no-such-file.mp4",
    )
    screen = window._screens["player"]
    assert screen._controller is None
    assert screen._views._stack.currentWidget() is screen._missing_widget
    message = screen._missing_msg.text()
    assert "not available" in message
    # no traceback-ish content leaks into the player state widget
    assert "Traceback" not in message


def test_player_route_disables_top_bar_search(window):
    window.navigation.navigate("player")
    assert window._top_bar._search_field.isEnabled() is False
    window.navigation.navigate("home")
    assert window._top_bar._search_field.isEnabled() is True


# --------------------------------------------------------------------------- #
# Error-state behavior (no tracebacks exposed)                                #
# --------------------------------------------------------------------------- #


def test_screen_error_state_hides_exception_details(window, monkeypatch):
    import ui.app.data as data_mod

    def boom(services):
        raise RuntimeError("db exploded with details")

    monkeypatch.setattr(data_mod, "fetch_continue_watching", boom)

    window.navigation.navigate("home")
    screen = window._screens["home"]
    assert wait_until(lambda: _terminal_reached(screen))
    assert screen.state() == "error"

    texts = visible_label_texts(screen._error_widget)
    assert any("Something went wrong" in t for t in texts)
    for text in visible_label_texts(screen):
        assert "Traceback" not in text
        assert "db exploded" not in text
    assert screen._error_widget.retry_button is not None


def test_view_model_fail_enters_error_state():
    events: list[tuple[ScreenState, object]] = []

    class _VM(BaseViewModel):
        pass

    vm = _VM(UiContext(services=None, navigation=Navigation()))
    vm.state_changed.connect(lambda state, payload: events.append((state, payload)))

    error = ValueError("inner detail")
    vm.fail(error)
    assert vm.state is ScreenState.ERROR
    state, payload = events[-1]
    assert state is ScreenState.ERROR
    assert payload is error


def test_entity_action_failure_toasts_friendly_message(window):
    window.navigation.navigate("home")
    screen = window._screens["home"]

    toasts: list[str] = []
    window._toast_host.show_message = toasts.append

    ref = EntityRef(kind="movie", entity_id=999999, title="Nope")
    screen.entity_action(ref, "favorite")

    assert toasts, "expected a friendly toast on failure"
    assert "LookupError" in toasts[-1]
    assert "Traceback" not in toasts[-1]
    assert "line " not in toasts[-1]


def test_no_traceback_anywhere_after_full_navigate_cycle(window):
    """Navigate through every route and verify no widget contains traceback text."""
    from conftest import ALL_ROUTES

    for route in ALL_ROUTES:
        window.navigation.navigate(route)
        for text in visible_label_texts(window._stack.currentWidget()):
            assert "Traceback" not in text
