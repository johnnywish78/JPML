"""Theme switching: dark / light / system plus window refresh."""
from __future__ import annotations

from ui.themes.dark import DARK
from ui.themes.light import LIGHT
from ui.themes.theme_manager import ThemeManager, ThemeMode


def test_theme_manager_switches_dark_and_light(qapp):
    manager = ThemeManager(qapp, qapp.styleHints())
    seen: list[str] = []
    manager.theme_changed.connect(seen.append)

    manager.set_mode(ThemeMode.DARK)
    assert manager.mode == ThemeMode.DARK
    assert manager.tokens is DARK
    assert f"background-color: {DARK.background}" in qapp.styleSheet()
    assert f"background-color: {LIGHT.background}" not in qapp.styleSheet()

    manager.set_mode(ThemeMode.LIGHT)
    assert manager.mode == ThemeMode.LIGHT
    assert manager.tokens is LIGHT
    assert f"background-color: {LIGHT.background}" in qapp.styleSheet()
    assert f"background-color: {DARK.background}" not in qapp.styleSheet()

    assert seen[-1] == "light"
    assert qapp.styleSheet()  # a real stylesheet is applied


def test_theme_manager_system_mode_resolves(qapp):
    manager = ThemeManager(qapp, qapp.styleHints())
    manager.set_mode(ThemeMode.SYSTEM)
    assert manager.mode == ThemeMode.SYSTEM
    assert manager.tokens in (DARK, LIGHT)
    manager.refresh()  # must not raise regardless of system scheme
    assert qapp.styleSheet() != ""


def test_dark_and_light_stylesheets_differ(qapp):
    manager = ThemeManager(qapp, qapp.styleHints())
    manager.set_mode(ThemeMode.DARK)
    dark_qss = qapp.styleSheet()
    manager.set_mode(ThemeMode.LIGHT)
    light_qss = qapp.styleSheet()
    assert dark_qss != light_qss


def test_window_applies_chosen_theme(window, qapp):
    assert window.theme_manager is not None
    assert window.theme_manager.mode == ThemeMode.DARK
    assert window.theme_manager.tokens is DARK
    assert f"background-color: {DARK.background}" in qapp.styleSheet()


def test_window_switch_to_light_refreshes_loaded_screens(window, qapp):
    # Visit real screens (navigation loads them and builds their grids),
    # then exercise a live theme switch — the realistic path.
    for route in ("home", "movies", "favorites"):
        window.navigation.navigate(route)
    from conftest import wait_until

    movies = window._screens["movies"]
    assert wait_until(lambda: movies.state() in ("ready", "empty", "error"))

    window.theme_manager.set_mode(ThemeMode.LIGHT)
    qapp.processEvents()
    assert window.theme_manager.tokens is LIGHT
    assert f"background-color: {LIGHT.background}" in qapp.styleSheet()

    window.theme_manager.set_mode(ThemeMode.DARK)
    qapp.processEvents()
    assert window.theme_manager.tokens is DARK
    assert f"background-color: {DARK.background}" in qapp.styleSheet()
