"""Personal Browser screen.

Uses PyQt6 WebEngine when available; falls back to a message when the
dependency is missing. Services requiring DRM (Netflix, Prime, Disney+)
open in the system browser.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.themes.tokens import Spacing, Typography


# ---------------------------------------------------------------------------
# WebEngine availability
# ---------------------------------------------------------------------------

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # type: ignore
    _WEBENGINE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _WEBENGINE_AVAILABLE = False


class BrowserScreen(QWidget):
    """Browser screen with navigation controls."""

    def __init__(self, context, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self._webview: QWebEngineView | None = None
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        tlay = QHBoxLayout(toolbar)
        tlay.setContentsMargins(Spacing.M, Spacing.S, Spacing.M, Spacing.S)
        tlay.setSpacing(Spacing.S)

        self._btn_back = QPushButton("←")
        self._btn_back.setObjectName("IconButton")
        self._btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_back.clicked.connect(self._go_back)

        self._btn_forward = QPushButton("→")
        self._btn_forward.setObjectName("IconButton")
        self._btn_forward.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_forward.clicked.connect(self._go_forward)

        self._btn_reload = QPushButton("⟳")
        self._btn_reload.setObjectName("IconButton")
        self._btn_reload.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_reload.clicked.connect(self._reload)

        self._url_bar = QLineEdit()
        self._url_bar.setPlaceholderText("Enter URL or search...")
        self._url_bar.setStyleSheet(
            "border-radius: 8px; padding: 6px 12px; background: #1A1D26; "
            "color: #F5F5F7;"
        )
        self._url_bar.returnPressed.connect(self._go)

        self._btn_go = QPushButton("Go")
        self._btn_go.setObjectName("GhostButton")
        self._btn_go.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_go.clicked.connect(self._go)

        tlay.addWidget(self._btn_back)
        tlay.addWidget(self._btn_forward)
        tlay.addWidget(self._btn_reload)
        tlay.addWidget(self._url_bar, 1)
        tlay.addWidget(self._btn_go)

        outer.addWidget(toolbar)

        # Web view or fallback
        if _WEBENGINE_AVAILABLE:
            self._webview = QWebEngineView()
            self._webview.urlChanged.connect(self._on_url_changed)
            outer.addWidget(self._webview, 1)
        else:
            self._fallback_widget = self._build_fallback()
            outer.addWidget(self._fallback_widget, 1)

    def _build_fallback(self) -> QWidget:
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("🌐")
        icon.setStyleSheet("font-size: 48px; background: transparent;")
        title = QLabel("Web Browser")
        title.setStyleSheet(
            f"font-size: {Typography.SECTION_PX}px; font-weight: 700; "
            "color: #F5F5F7; background: transparent;"
        )
        subtitle = QLabel(
            "QtWebEngine is not installed. Install PyQt6-WebEngine to enable "
            "the browser, or use the links below to open services in your "
            "system browser."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"font-size: {Typography.METADATA_PX}px; color: #A7ABB5; "
            "background: transparent; margin-top: 12px;"
        )
        lay.addWidget(icon)
        lay.addWidget(title)
        lay.addWidget(subtitle)
        return widget

    def _go(self) -> None:
        url_text = self._url_bar.text().strip()
        if not url_text:
            return
        if not url_text.startswith(("http://", "https://")):
            url_text = "https://" + url_text
        url = QUrl(url_text)
        if self._webview is not None:
            self._webview.setUrl(url)
        else:
            import webbrowser
            webbrowser.open(url_text)

    def _go_back(self) -> None:
        if self._webview is not None:
            self._webview.back()

    def _go_forward(self) -> None:
        if self._webview is not None:
            self._webview.forward()

    def _reload(self) -> None:
        if self._webview is not None:
            self._webview.reload()

    def _on_url_changed(self, url: QUrl) -> None:
        self._url_bar.setText(url.toString())

    def navigate_to(self, url: str) -> None:
        if self._webview is not None:
            self._webview.setUrl(QUrl(url))
        else:
            import webbrowser
            webbrowser.open(url)

    def refresh_theme(self) -> None:
        self.update()
