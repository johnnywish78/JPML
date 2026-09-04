"""Application bootstrap construction (headless)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: sitecustomize injected via PYTHONPATH for the bounded run.py smoke:
#: makes QApplication.exec quit itself after a short delay so the
#: subprocess terminates on its own.
_SMOKE_BOOTSTRAP = """
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

_orig_init = QApplication.__init__


def _patched_init(self, *args, **kwargs):
    _orig_init(self, *args, **kwargs)
    timer = QTimer(self)
    timer.setSingleShot(True)
    timer.timeout.connect(self.quit)
    timer.start(4000)


QApplication.__init__ = _patched_init
"""


def test_qt_application_boots_and_is_identified(qapp):
    assert qapp is not None
    assert qapp.applicationName() == "JPML"
    assert os.environ.get("QT_QPA_PLATFORM") == "offscreen"


def test_bootstrap_playback_factories():
    from app.bootstrap import (
        create_event_bus,
        create_player_controller,
        create_playback_service,
    )

    bus = create_event_bus()
    service = create_playback_service(backend_name="mock")
    controller = create_player_controller(backend_name="mock", event_bus=bus)
    assert service is not None
    assert controller is not None


def test_ui_service_composition_is_wired():
    from app.services.collections import CollectionsService
    from app.services.discovery import DiscoveryService
    from app.services.favorites import FavoritesService
    from app.services.music import MusicService
    from app.services.search import SearchService
    from app.services.statistics import StatisticsService
    from app.services.watchlist import WatchlistService
    from ui.app.composition import ServiceComposition, build_services, close_services

    composition = build_services()
    try:
        assert isinstance(composition, ServiceComposition)
        assert isinstance(composition.favorites, FavoritesService)
        assert isinstance(composition.watchlist, WatchlistService)
        assert isinstance(composition.collections, CollectionsService)
        assert isinstance(composition.search, SearchService)
        assert isinstance(composition.statistics, StatisticsService)
        assert isinstance(composition.music, MusicService)
        assert isinstance(composition.discovery, DiscoveryService)
        assert composition.event_bus is not None
        assert composition.media_repository is not None
        assert composition.metadata_repository is not None
    finally:
        close_services(composition)


def test_run_py_launches_headless_and_exits_cleanly(tmp_path):
    """Bounded smoke: real run.py entry point, offscreen, auto-exit."""
    site = tmp_path / "smokesite"
    site.mkdir()
    (site / "sitecustomize.py").write_text(_SMOKE_BOOTSTRAP, encoding="utf-8")

    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONPATH"] = str(site)

    proc = subprocess.run(
        [sys.executable, "run.py", "--backend", "mock", "--theme", "dark"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"stderr:\n{proc.stderr[-2000:]}"
    assert "Traceback" not in proc.stderr, proc.stderr[-2000:]
