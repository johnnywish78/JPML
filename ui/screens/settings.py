"""Settings — Appearance (Dark / Light / System) + Library entry point.

Theme switching is live: clicking a mode updates the ThemeManager,
regenerates the global QSS and refreshes the visible UI immediately.
The frozen backend exposes no UI-settings surface, so no settings are
persisted to the backend.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.app.view_model import UiContext
from ui.components.common.button import GhostButton
from ui.components.common.page_header import PageHeader
from ui.themes.tokens import Spacing, Typography


class _OptionButton(QPushButton):
    def __init__(self, label: str, value: str, parent=None) -> None:
        super().__init__(label, parent)
        self.setProperty("value", value)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(52)
        self.setStyleSheet(
            "text-align: left; padding: 14px 18px;"
        )


class SettingsScreen(QWidget):
    def __init__(self, context: UiContext) -> None:
        super().__init__()
        self.context = context
        self._group: QButtonGroup | None = None
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, Spacing.L)
        outer.setSpacing(Spacing.L)

        header = PageHeader("Settings", subtitle="Appearance")
        outer.addWidget(header)

        section = QLabel("Theme")
        section.setObjectName("SecondaryLabel")
        section.setStyleSheet(
            f"font-size: {Typography.SECTION_PX - 2}px; font-weight: 600; "
            "background: transparent;"
        )
        outer.addWidget(section)

        card = QFrame()
        card.setObjectName("CardFrame")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(Spacing.S, Spacing.S, Spacing.S, Spacing.S)
        lay.setSpacing(Spacing.S)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        options = [
            ("Dark", "dark"),
            ("Light", "light"),
            ("System", "system"),
        ]
        for label, value in options:
            button = _OptionButton(label, value, card)
            self._group.addButton(button)
            lay.addWidget(button)
        self._buttons: list[_OptionButton] = list(self._group.buttons())
        self._group.buttonClicked.connect(self._on_click)
        outer.addWidget(card)

        library_section = QLabel("Library")
        library_section.setObjectName("SecondaryLabel")
        library_section.setStyleSheet(
            f"font-size: {Typography.SECTION_PX - 2}px; font-weight: 600; "
            "background: transparent;"
        )
        outer.addWidget(library_section)

        library_card = QFrame()
        library_card.setObjectName("CardFrame")
        library_lay = QVBoxLayout(library_card)
        library_lay.setContentsMargins(Spacing.M, Spacing.S, Spacing.M, Spacing.S)
        library_lay.setSpacing(Spacing.S)
        library_label = QLabel(
            "Add a media folder, manage scan locations and run library scans."
        )
        library_label.setObjectName("SecondaryLabel")
        library_label.setWordWrap(True)
        library_label.setStyleSheet("background: transparent;")
        manage = GhostButton("Manage Library Locations…")
        manage.clicked.connect(
            lambda: self.context.navigation.navigate("library")
        )
        library_lay.addWidget(library_label)
        library_lay.addWidget(manage)
        outer.addWidget(library_card)

        outer.addStretch(1)

    def on_activated(self) -> None:
        self._sync_current()
        self._update_styles()

    def _sync_current(self) -> None:
        manager = self._theme_manager()
        mode = getattr(manager, "mode", "dark") if manager is not None else "dark"
        for button in self._buttons:
            button.setChecked(str(mode) == button.property("value"))

    def _on_click(self, button) -> None:
        value = str(button.property("value"))
        self._set_theme(value)
        self._update_styles()

    def _set_theme(self, value: str) -> None:
        manager = self._theme_manager()
        if manager is not None:
            manager.set_mode(value)

    def _theme_manager(self):
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        state = getattr(app, "jpml_state", None) if app is not None else None
        return getattr(state, "theme", None) if state is not None else None

    def _update_styles(self) -> None:
        # Reflect the active mode on the option buttons using live tokens.
        manager = self._theme_manager()
        tokens = getattr(manager, "tokens", None)
        accent = getattr(tokens, "accent", "#D7263D")
        text = getattr(tokens, "text_primary", "#F5F5F7")
        border = getattr(tokens, "border", "#232733")
        for button in self._buttons:
            active = button.isChecked()
            button.setStyleSheet(
                f"QPushButton {{ text-align:left; padding:14px 18px; "
                f"border:1px solid {accent if active else border}; "
                f"border-radius:10px; background:transparent; "
                f"font-size:15px; font-weight:{'600' if active else '500'}; "
                f"color:{accent if active else text}; }}"
                f"QPushButton:hover {{ background:rgba(215,38,61,0.06); }}"
            )
        self.update()

    def refresh_theme(self) -> None:
        self._update_styles()

    def shutdown(self) -> None:
        pass
