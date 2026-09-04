"""Reusable confirmation dialog for destructive actions."""
from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton


class ConfirmationDialog(QDialog):
    """Modal confirm for delete/collection-destructive actions."""

    def __init__(
        self,
        title: str,
        message: str,
        confirm_text: str = "Delete",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)
        self._result: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        heading = QLabel(title)
        heading.setStyleSheet("font-size: 20px; font-weight: 600; background: transparent;")
        body = QLabel(message)
        body.setWordWrap(True)
        body.setObjectName("SecondaryLabel")
        body.setStyleSheet("font-size: 14px; background: transparent;")

        actions = QHBoxLayout()
        actions.addStretch(1)
        self._cancel = QPushButton("Cancel")
        self._cancel.setObjectName("GhostButton")
        self._confirm = QPushButton(confirm_text)
        self._confirm.setObjectName("DangerButton")
        actions.addWidget(self._cancel)
        actions.addWidget(self._confirm)

        layout.addWidget(heading)
        layout.addWidget(body)
        layout.addSpacing(8)
        layout.addLayout(actions)

        self._cancel.clicked.connect(self._on_cancel)
        self._confirm.clicked.connect(self._on_confirm)

    def _on_cancel(self) -> None:
        self._result = False
        self.reject()

    def _on_confirm(self) -> None:
        self._result = True
        self.accept()

    @property
    def confirmed(self) -> bool:
        return self._result


def confirm(title: str, message: str, confirm_text: str = "Delete", parent=None) -> bool:
    """Convenience runner. Returns True when the action was confirmed."""
    dialog = ConfirmationDialog(title, message, confirm_text, parent)
    dialog.exec()
    return dialog.confirmed
