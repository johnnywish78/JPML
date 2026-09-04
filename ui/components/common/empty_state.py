"""Reusable empty- and error-state widgets.

Empty states are contextual (optionally with primary/secondary
actions); error states never expose tracebacks.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.themes.tokens import Radius, Spacing, Typography

from .button import GhostButton, PrimaryButton


class EmptyState(QWidget):
    def __init__(
        self,
        title: str,
        subtitle: str = "",
        action_text: str | None = None,
        secondary_text: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            Spacing.XXL3, Spacing.XXL4 * 2, Spacing.XXL3, Spacing.XXL4
        )
        layout.setSpacing(Spacing.M)

        icon = QLabel("◌")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"font-size: 44px; color: #6F7480; padding-bottom: 16px;"
        )
        label_style = (
            f"font-size: {Typography.SECTION_PX}px; font-weight: {600};"
            "background: transparent;"
        )
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(label_style)
        layout.addWidget(icon)
        layout.addWidget(title_label)
        self.action_button = None
        self.action_button_secondary = None

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("SecondaryLabel")
            subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            subtitle_label.setWordWrap(True)
            subtitle_label.setStyleSheet(
                f"font-size: {Typography.METADATA_PX + 1}px; background: transparent;"
            )
            layout.addWidget(subtitle_label)

        if action_text or secondary_text:
            button_row = QHBoxLayout()
            button_row.setSpacing(Spacing.S)
            button_row.addStretch(1)
            if action_text:
                action = PrimaryButton(action_text)
                action.setFixedWidth(210)
                button_row.addWidget(action)
                self.action_button = action
            if secondary_text:
                secondary = GhostButton(secondary_text)
                secondary.setFixedWidth(180)
                button_row.addWidget(secondary)
                self.action_button_secondary = secondary
            if action_text:
                layout.addSpacing(Spacing.M)
            button_row.addStretch(1)
            layout.addLayout(button_row)

        layout.addStretch(1)


class ErrorState(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            Spacing.XXL3, Spacing.XXL4 * 2, Spacing.XXL3, Spacing.XXL4
        )
        layout.setSpacing(Spacing.M)

        icon = QLabel("⚠")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"font-size: 40px; color: #6F7480; padding-bottom: 16px;"
        )
        title = QLabel("Something went wrong")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font-size: {Typography.SECTION_PX}px; font-weight: {600}; "
            "background: transparent;"
        )
        subtitle = QLabel("We couldn't load this section.")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setObjectName("SecondaryLabel")
        subtitle.setStyleSheet(
            f"font-size: {Typography.METADATA_PX + 1}px; background: transparent;"
        )
        retry = PrimaryButton("Retry")
        retry.setFixedWidth(160)
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(Spacing.S)
        layout.addWidget(retry, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)

        self.retry_button = retry


def make_card_frame(parent=None, radius: int = Radius.CARD) -> QFrame:
    frame = QFrame(parent)
    frame.setObjectName("CardFrame")
    return frame
