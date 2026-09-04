"""Navigation history: navigate / back / forward, unit and via window."""
from __future__ import annotations

from ui.app.navigation import Navigation, Route


def test_navigate_pushes_route_and_emits_signals():
    nav = Navigation(initial="home")
    assert nav.current_route is None  # history starts empty

    routes: list[Route] = []
    nav.route_changed.connect(lambda route: routes.append(route))

    nav.navigate("movies")
    assert nav.current_route == Route("movies")
    assert routes[-1] == Route("movies")
    assert not nav.can_go_back

    nav.navigate("tv_shows", source="home")
    assert nav.current_route == Route("tv_shows", {"source": "home"})
    assert nav.can_go_back


def test_back_and_forward():
    nav = Navigation()
    nav.navigate("home")
    nav.navigate("movies")
    nav.navigate("music")

    assert nav.back() == Route("movies")
    assert nav.current_route == Route("movies")
    assert nav.can_go_forward

    assert nav.forward() == Route("music")
    assert nav.current_route == Route("music")
    assert not nav.can_go_forward

    # bottom of history: back returns None
    assert nav.back() == Route("movies")
    assert nav.back() == Route("home")
    assert nav.back() is None


def test_navigate_drops_forward_tail():
    nav = Navigation()
    nav.navigate("home")
    nav.navigate("movies")
    nav.back()
    nav.navigate("music")  # drops the "movies" forward entry
    assert not nav.can_go_forward
    assert nav.current_route == Route("music")
    assert nav.back() == Route("home")


def test_window_back_returns_false_at_bottom(window):
    # the sidebar's initial state pushes "home" onto history at startup
    assert window.navigation.current_route == Route("home")
    assert window.back() is False  # single-entry history
    window.navigation.navigate("movies")
    window.navigation.navigate("tv_shows")
    assert window.back() is True
    assert window.navigation.current_route == Route("movies")
    assert window._stack.currentWidget() is window._screens["movies"]


def test_window_back_returns_to_the_real_previous_route(window):
    window.navigation.navigate("movies")
    # back goes to the actual previous route in history (home), never to
    # a fabricated default
    assert window.back() is True
    assert window.navigation.current_route == Route("home")
    assert window._stack.currentWidget() is window._screens["home"]
    assert window.back() is False  # bottom of history


def test_window_goto_with_params(window):
    window.goto(Route("details", {"kind": "movie", "entity_id": 1, "title": "X"}))
    assert window.navigation.current_route == Route(
        "details", {"kind": "movie", "entity_id": 1, "title": "X"}
    )
    assert window._stack.currentWidget() is window._screens["details"]
    assert window._top_bar._title.text() == "X"


def test_top_bar_title_follows_route(window):
    window.navigation.navigate("movies")
    assert window._top_bar._title.text() == "Movies"
    window.navigation.navigate("settings")
    assert window._top_bar._title.text() == "Settings"
