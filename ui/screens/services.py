"""Online Services — quick-launch cards for streaming and communication.

Services that require DRM (Netflix, Prime Video, Disney+) open in the
system browser. Others open in JPML's built-in browser when available.
"""
from __future__ import annotations

import webbrowser
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.app.view_model import UiContext
from ui.components.common.page_header import PageHeader
from ui.themes.tokens import Spacing, Typography


# Official service URLs
_SERVICES = [
    ("YouTube", "https://www.youtube.com", "Video platform"),
    ("Telegram", "https://web.telegram.org", "Messaging"),
    ("Spotify", "https://open.spotify.com", "Music streaming"),
    ("Netflix", "https://www.netflix.com", "TV & movies (DRM)"),
    ("Prime Video", "https://www.primevideo.com", "TV & movies (DRM)"),
    ("Disney+", "https://www.disneyplus.com", "TV & movies (DRM)"),
]

# Services that should use system browser due to DRM
_DRM_SERVICES = {"Netflix", "Prime Video", "Disney+"}


class ServiceCard(QFrame):
    """Card for an online service."""

    launched = Signal = None  # placeholder — not used

    def __init__(self, name: str, url: str, description: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CardFrame")
        self._url = url
        self._name = name
        self._use_system = name in _DRM_SERVICES

        lay = QVBoxLayout(self)
        lay.setContentsMargins(Spacing.L, Spacing.L, Spacing.L, Spacing.L)
        lay.setSpacing(Spacing.M)

        icon = QLabel(self._icon_for(name))
        icon.setStyleSheet(
            f"font-size: 32px; background: transparent;"
        )
        lay.addWidget(icon)

        title = QLabel(name)
        title.setStyleSheet(
            f"font-size: {Typography.CARD_PX + 2}px; font-weight: 600; "
            "background: transparent;"
        )
        lay.addWidget(title)

        desc = QLabel(description)
        desc.setObjectName("SecondaryLabel")
        desc.setStyleSheet(
            f"font-size: {Typography.METADATA_PX}px; background: transparent;"
        )
        desc.setWordWrap(True)
        lay.addWidget(desc)

        if self._use_system:
            note = QLabel("Opens in system browser")
            note.setObjectName("MutedLabel")
            note.setStyleSheet(
                f"font-size: {Typography.METADATA_PX - 1}px; background: transparent;"
            )
            lay.addWidget(note)

        lay.addStretch(1)

        self.launch_btn = QPushButton("Open")
        self.launch_btn.setObjectName("GhostButton")
        self.launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launch_btn.clicked.connect(self._open)
        lay.addWidget(self.launch_btn)

    @staticmethod
    def _icon_for(name: str) -> str:
        icons = {
            "YouTube": "▶",
            "Telegram": "✈",
            "Spotify": "♫",
            "Netflix": "N",
            "Prime Video": "P",
            "Disney+": "D",
        }
        return icons.get(name, "🔗")

    def _open(self) -> None:
        if self._use_system:
            webbrowser.open(self._url)
        else:
            # Try to navigate via browser screen if available
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            state = getattr(app, "jpml_state", None) if app else None
            window = getattr(state, "window", None) if state else None
            if window is not None and hasattr(window, "navigation"):
                window.navigation.navigate("browser", url=self._url)
            else:
                webbrowser.open(self._url)


class ServicesScreen(QWidget):
    """Online services launcher."""

    def __init__(self, context: UiContext, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.setObjectName("AppBackground")
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, Spacing.L)
        outer.setSpacing(Spacing.L)

        header = PageHeader("Online Services", subtitle="Quick links")
        outer.addWidget(header)

        grid = QWidget()
        grid_lay = QVBoxLayout(grid)
        grid_lay.setContentsMargins(0, 0, 0, 0)
        grid_lay.setSpacing(Spacing.L)

        for name, url, desc in _SERVICES:
            card = ServiceCard(name, url, desc)
            grid_lay.addWidget(card)

        outer.addWidget(grid, 1)

    def refresh_theme(self) -> None:
        self.update()
