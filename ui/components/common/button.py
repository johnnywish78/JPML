"""Shared button primitives styled by the active theme."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton


class PrimaryButton(QPushButton):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("PrimaryButton")


class GhostButton(QPushButton):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("GhostButton")


class DangerButton(QPushButton):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("DangerButton")


class IconButton(QPushButton):
    """Square, icon-only button with tooltip for accessibility."""

    def __init__(self, icon_text: str, tooltip: str, parent=None) -> None:
        super().__init__(icon_text, parent)
        self.setObjectName("IconButton")
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setMinimumSize(34, 34)
