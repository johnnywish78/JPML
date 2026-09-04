"""Create/rename collection dialog (single input + submit)."""
from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton


class CollectionDialog(QDialog):
    """Create or rename a collection."""

    def __init__(self, mode: str = "create", parent=None) -> None:
        super().__init__(parent)
        self._mode = mode
        self.setModal(True)
        self.setMinimumWidth(440)
        self._result: str | None = None
        self._title_attr = "title"

        if mode == "create":
            window_title = "New Collection"
            heading = "New Collection"
            placeholder = "e.g. Christopher Nolan, Horror, Weekend Movies"
            submit = "Create"
        else:
            window_title = "Rename Collection"
            heading = "Rename Collection"
            placeholder = "New name"
            submit = "Save"

        self.setWindowTitle(window_title)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        label = QLabel(heading)
        label.setStyleSheet("font-size: 20px; font-weight: 600; background: transparent;")

        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder)
        self._input.setMaxLength(120)
        self._input.returnPressed.connect(self._on_submit)

        self._error = QLabel("")
        self._error.setStyleSheet("color: #D7263D; font-size: 13px; background: transparent;")
        self._error.hide()

        actions = QHBoxLayout()
        actions.addStretch(1)
        self._cancel = QPushButton("Cancel")
        self._cancel.setObjectName("GhostButton")
        self._submit = QPushButton(submit)
        self._submit.setObjectName("PrimaryButton")
        actions.addWidget(self._cancel)
        actions.addWidget(self._submit)

        layout.addWidget(label)
        layout.addSpacing(4)
        layout.addWidget(self._input)
        layout.addWidget(self._error)
        layout.addSpacing(8)
        layout.addLayout(actions)

        self._cancel.clicked.connect(self.reject)
        self._submit.clicked.connect(self._on_submit)
        self._input.setFocus()

    def set_name(self, name: str) -> None:
        self._input.setText(name)

    def _on_submit(self) -> None:
        value = self._input.text().strip()
        if not value:
            self._error.setText("Please enter a name.")
            self._error.show()
            return
        self._error.hide()
        self._result = value
        self.accept()

    @property
    def name(self) -> str | None:
        return self._result


def create_collection(parent=None) -> str | None:
    """Runs a create dialog; returns the chosen name or None."""
    dialog = CollectionDialog("create", parent)
    dialog.exec()
    return dialog.name


def rename_collection(current_name: str, parent=None) -> str | None:
    """Runs a rename dialog; returns the chosen name or None."""
    dialog = CollectionDialog("rename", parent)
    dialog.set_name(current_name)
    dialog.exec()
    return dialog.name
