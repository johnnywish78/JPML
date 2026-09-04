"""Top bar: page title, context breadcrumbs, and global search field."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
)

from ui.themes.tokens import Spacing, Typography


class TopBar(QFrame):
    search_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(64)
        self._build()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Spacing.XXL3, 0, 0, 0)
        layout.setSpacing(Spacing.L)

        self._title = QLabel("Home")
        self._title.setStyleSheet(
            f"font-size: {Typography.PAGE_PX - 6}px; font-weight: {600}; "
            "background: transparent;"
        )
        layout.addWidget(self._title)

        self._breadcrumb = QLabel("")
        self._breadcrumb.setObjectName("MutedLabel")
        self._breadcrumb.setStyleSheet(
            f"font-size: {Typography.METADATA_PX}px; background: transparent;"
        )
        layout.addWidget(self._breadcrumb)

        layout.addStretch(1)

        search = QLineEdit()
        search.setPlaceholderText("Search movies, shows, people, music…")
        search.setFixedWidth(340)
        search.setClearButtonEnabled(True)
        search.setStyleSheet(
            "border-radius: 18px; padding-left: 18px;"
        )
        search.returnPressed.connect(
            lambda: self.search_requested.emit(search.text().strip())
        )
        search.textChanged.connect(
            lambda text: self.search_requested.emit(text.strip())
        )
        self._search_field = search
        layout.addWidget(search)

    # -- public API ----------------------------------------------------------

    def set_title(self, title: str, breadcrumb: str = "") -> None:
        self._title.setText(title)
        self._breadcrumb.setText(breadcrumb)

    def set_search_enabled(self, enabled: bool) -> None:
        self._search_field.setEnabled(enabled)

    def focus_search(self) -> None:
        self._search_field.setFocus()
