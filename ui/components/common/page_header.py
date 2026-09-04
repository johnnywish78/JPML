"""Page header: big title plus optional trailing controls (sort, actions)."""
from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.themes.tokens import Spacing, Typography


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        self._subtitle_text = subtitle
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, Spacing.XL)
        layout.setSpacing(Spacing.M)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel(title)
        self._title.setStyleSheet(
            f"font-size: {Typography.PAGE_PX}px; font-weight: 600; background: transparent;"
        )
        left_layout.addWidget(self._title)
        if subtitle:
            self._subtitle = QLabel(subtitle)
            self._subtitle.setObjectName("SecondaryLabel")
            self._subtitle.setStyleSheet(
                f"font-size: {Typography.METADATA_PX + 1}px; background: transparent; margin-top: 4px;"
            )
            left_layout.addWidget(self._subtitle)
        else:
            self._subtitle = None
        layout.addWidget(left)
        layout.addStretch(1)
        self._controls = QHBoxLayout()
        self._controls.setSpacing(Spacing.S)
        layout.addLayout(self._controls)

    def add_control(self, widget) -> None:
        self._controls.addWidget(widget)

    def set_count(self, count: int | None) -> None:
        if self._subtitle is not None:
            self._subtitle.setText(self._apply_count(count))

    def _apply_count(self, count: int | None) -> str:
        base = self._subtitle_text
        if count is None:
            return base
        try:
            return base.format(n=count)
        except (IndexError, KeyError):
            return f"{base} · {count}"

    def set_title(self, title: str) -> None:
        self._title.setText(title)
