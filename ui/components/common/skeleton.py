"""Skeleton placeholders for stable loading layouts (no jumping)."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QWidget

from ui.themes.tokens import Radius, Spacing


class SkeletonBlock(QLabel):
    def __init__(self, width: int, height: int, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SkeletonBlock")
        self.setFixedSize(width, height)


class MediaCardSkeleton(QWidget):
    """2:3 poster with text lines below — mirrors MediaCard layout."""

    def __init__(self, width: int = 158, parent=None) -> None:
        super().__init__(parent)
        from PyQt6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.S)
        poster = SkeletonBlock(width, int(width * 3 / 2))
        line1 = SkeletonBlock(width, 12)
        line2 = SkeletonBlock(int(width * 0.6), 10)
        layout.addWidget(poster)
        layout.addWidget(line1)
        layout.addWidget(line2)
        self.setFixedWidth(width)


class RowSkeleton(QWidget):
    """A horizontal row of card skeletons with a title bar."""

    def __init__(self, card_width: int = 158, count: int = 5, parent=None) -> None:
        super().__init__(parent)
        from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(Spacing.S)
        title = SkeletonBlock(180, 18)
        v.addWidget(title)
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(Spacing.L)
        for _ in range(count):
            h.addWidget(MediaCardSkeleton(card_width, parent=self))
        h.addStretch(1)
        v.addLayout(h)


class HeroSkeleton(QWidget):
    def __init__(self, height: int = 480, parent=None) -> None:
        from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout

        super().__init__(parent)
        self.setFixedHeight(height)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName("CardFrame")
        outer.addWidget(frame)
        content = QHBoxLayout(frame)
        content.setContentsMargins(Spacing.XXL3, Spacing.XXL4, 0, 0)
        content.addStretch(1)
        block = QFrame()
        block.setObjectName("CardFrame")
        w = 160
        block.setFixedSize(w, int(w * 3 / 2))
        content.addWidget(block)
        content.addStretch(1)


class TextSkeleton(QWidget):
    """Two text lines, e.g. inside a detail area."""

    def __init__(self, width: int = 420, parent=None) -> None:
        from PyQt6.QtWidgets import QVBoxLayout

        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.S)
        layout.addWidget(SkeletonBlock(width, 16))
        layout.addWidget(SkeletonBlock(int(width * 0.8), 12))
