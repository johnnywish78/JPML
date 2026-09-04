"""JPML official desktop runtime entry point.

Usage:
    .venv/bin/python run.py [--backend vlc|mpv|mock] [--theme dark|light|system]
"""
from __future__ import annotations

import argparse
import sys

from PyQt6.QtWidgets import QApplication


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="jpml")
    parser.add_argument(
        "--backend",
        default="vlc",
        choices=["vlc", "mpv", "mock"],
        help="player backend used for playback",
    )
    parser.add_argument(
        "--theme",
        default="dark",
        choices=["dark", "light", "system"],
        help="initial UI theme",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("JPML")
    app.setApplicationDisplayName("JPML — Johnny's Personal Media Library")
    app.setOrganizationName("JPML")
    app.setStyle("Fusion")

    from ui.themes.theme_manager import ThemeManager

    theme_manager = ThemeManager(app, app.styleHints())

    from ui.app.main_window import MainWindow
    from ui.app.run_state import attach  # sets app.jpml_state + registers screens

    window = MainWindow()
    attach(app, window, theme_manager, args)

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
