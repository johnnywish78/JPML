"""Shared fixtures for headless JPML UI tests.

All tests run with QT_QPA_PLATFORM=offscreen so no display is required.
A fresh in-memory SQLite database is used so every test starts from a
known empty state; the on-disk production database is never touched.
"""
from __future__ import annotations

import os
import sqlite3
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402
from PyQt6.QtCore import QEventLoop, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402

from ui.app.main_window import MainWindow  # noqa: E402
from ui.app.run_state import attach  # noqa: E402
from ui.themes.theme_manager import ThemeManager  # noqa: E402

#: Every screen route registered by ui.app.run_state.register_all.
ALL_ROUTES = (
    "home",
    "movies",
    "tv_shows",
    "people",
    "music",
    "trending",
    "recommendations",
    "favorites",
    "watchlist",
    "collections",
    "search",
    "details",
    "statistics",
    "settings",
    "player",
)

TERMINAL_STATES = ("ready", "empty", "error")


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(["jpml-ui-tests"])
    app.setApplicationName("JPML")
    app.setOrganizationName("JPML")
    app.setStyle("Fusion")
    yield app


def wait_until(condition, timeout: float = 20.0) -> bool:
    """Spin the event loop until *condition*() is true (or timeout)."""
    loop = QEventLoop()
    poll = QTimer()
    poll.setInterval(50)
    poll.timeout.connect(lambda: loop.quit() if condition() else None)
    stop = QTimer()
    stop.setSingleShot(True)
    stop.timeout.connect(loop.quit)
    poll.start()
    stop.start(max(1, int(timeout * 1000)))
    try:
        loop.exec()
    finally:
        poll.stop()
        stop.stop()
    return condition()


def find_label(widget, text: str) -> QLabel | None:
    for label in widget.findChildren(QLabel):
        if label.text() == text:
            return label
    return None


def find_label_starting_with(widget, prefix: str) -> QLabel | None:
    for label in widget.findChildren(QLabel):
        if label.text().startswith(prefix):
            return label
    return None


def visible_label_texts(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel)]


def _fresh_connection():
    """Return a fresh in-memory connection with schema initialised."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    from app.database.schema import initialize
    initialize(conn)
    return conn


@pytest.fixture(scope="session", autouse=True)
def _monkeypatch_fresh_db():
    """Replace the real DB connection with a fresh in-memory one for UI tests."""
    from app.database import connection as conn_mod
    import app.bootstrap as bootstrap_mod

    # bootstrap.py imports `connect` directly, so we must patch both
    # the module-level function and the cached import used by bootstrap.
    with mock.patch.object(conn_mod, "connect", _fresh_connection):
        bootstrap_mod.connect = _fresh_connection  # type: ignore[attr-defined]
        yield
    # restore
    bootstrap_mod.connect = conn_mod.connect  # type: ignore[attr-defined]


@pytest.fixture
def window(qapp):
    """A fully attached MainWindow (mock backend, dark theme)."""
    manager = ThemeManager(qapp, qapp.styleHints())
    win = MainWindow(player_backend="mock")
    args = SimpleNamespace(backend="mock", theme="dark")
    attach(qapp, win, manager, args)
    qapp.processEvents()
    yield win
    win.close()
    qapp.processEvents()
    for screen in getattr(win, "_screens", {}).values():
        worker = getattr(screen, "_worker", None)
        if worker is not None and worker.isRunning():
            worker.wait(3000)
        closer = getattr(screen, "shutdown", None)
        if callable(closer):
            try:
                closer()
            except Exception:  # noqa: BLE001 — test teardown only
                pass
