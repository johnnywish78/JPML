"""Settings — Appearance, Metadata, Player, and Library configuration."""
from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
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
        self._tmdb_key_edit: QLineEdit | None = None
        self._omdb_key_edit: QLineEdit | None = None
        self._player_combo: QComboBox | None = None
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, Spacing.L)
        outer.setSpacing(Spacing.L)

        header = PageHeader("Settings", subtitle="Configuration")
        outer.addWidget(header)

        # ---- Theme ----
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

        # ---- Metadata Providers ----
        provider_section = QLabel("Metadata Providers")
        provider_section.setObjectName("SecondaryLabel")
        provider_section.setStyleSheet(
            f"font-size: {Typography.SECTION_PX - 2}px; font-weight: 600; "
            "background: transparent;"
        )
        outer.addWidget(provider_section)

        provider_card = QFrame()
        provider_card.setObjectName("CardFrame")
        provider_lay = QVBoxLayout(provider_card)
        provider_lay.setContentsMargins(Spacing.M, Spacing.S, Spacing.M, Spacing.S)
        provider_lay.setSpacing(Spacing.M)

        # TMDB key
        tmdb_label = QLabel("TMDB API Key")
        tmdb_label.setStyleSheet(
            f"font-size: {Typography.METADATA_PX + 1}px; font-weight: 600; "
            "background: transparent;"
        )
        provider_lay.addWidget(tmdb_label)
        self._tmdb_key_edit = QLineEdit()
        self._tmdb_key_edit.setPlaceholderText("Enter TMDB API key...")
        self._tmdb_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._tmdb_key_edit.setStyleSheet(
            "border-radius: 6px; padding: 8px 12px; background: #1A1D26; "
            "color: #F5F5F7;"
        )
        provider_lay.addWidget(self._tmdb_key_edit)

        # OMDb key
        omdb_label = QLabel("OMDb API Key (optional)")
        omdb_label.setStyleSheet(
            f"font-size: {Typography.METADATA_PX + 1}px; font-weight: 600; "
            "background: transparent;"
        )
        provider_lay.addWidget(omdb_label)
        self._omdb_key_edit = QLineEdit()
        self._omdb_key_edit.setPlaceholderText("Enter OMDb API key...")
        self._omdb_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._omdb_key_edit.setStyleSheet(
            "border-radius: 6px; padding: 8px 12px; background: #1A1D26; "
            "color: #F5F5F7;"
        )
        provider_lay.addWidget(self._omdb_key_edit)

        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("PrimaryButton")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save_all)
        provider_lay.addWidget(save_btn)
        outer.addWidget(provider_card)

        # ---- Player ----
        player_section = QLabel("Player")
        player_section.setObjectName("SecondaryLabel")
        player_section.setStyleSheet(
            f"font-size: {Typography.SECTION_PX - 2}px; font-weight: 600; "
            "background: transparent;"
        )
        outer.addWidget(player_section)

        player_card = QFrame()
        player_card.setObjectName("CardFrame")
        player_lay = QVBoxLayout(player_card)
        player_lay.setContentsMargins(Spacing.M, Spacing.S, Spacing.M, Spacing.S)
        player_lay.setSpacing(Spacing.M)

        backend_label = QLabel("Backend")
        backend_label.setStyleSheet(
            f"font-size: {Typography.METADATA_PX + 1}px; font-weight: 600; "
            "background: transparent;"
        )
        player_lay.addWidget(backend_label)

        self._player_combo = QComboBox()
        self._player_combo.addItems(["VLC", "MPV", "Mock"])
        self._player_combo.setStyleSheet(
            "border-radius: 6px; padding: 8px 12px; background: #1A1D26; "
            "color: #F5F5F7; min-width: 120px;"
        )
        player_lay.addWidget(self._player_combo)

        outer.addWidget(player_card)

        # ---- Library ----
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
        manage = GhostButton("Manage Library Locations...")
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
        self._load_config()

    def _load_config(self) -> None:
        """Load current config values into the UI controls."""
        try:
            from app.config import load_config
            config = load_config()
            if self._tmdb_key_edit is not None:
                self._tmdb_key_edit.setText(config.tmdb.api_key)
            if self._omdb_key_edit is not None:
                self._omdb_key_edit.setText(config.omdb.api_key)
            if self._player_combo is not None:
                backend = config.player_backend
                idx = {"vlc": 0, "mpv": 1, "mock": 2}.get(backend, 0)
                self._player_combo.setCurrentIndex(idx)
            # Sync theme buttons
            theme = getattr(config, "theme", "dark")
            for button in self._buttons:
                button.setChecked(str(theme) == button.property("value"))
        except Exception:
            pass

    def _save_all(self) -> None:
        """Persist all settings to config."""
        try:
            from app.config import load_config, save_config
            config = load_config()
            tmdb_key = self._tmdb_key_edit.text() if self._tmdb_key_edit else ""
            omdb_key = self._omdb_key_edit.text() if self._omdb_key_edit else ""
            player_backend = self._player_combo.currentText().lower() if self._player_combo else "vlc"
            # Get current theme
            theme = "dark"
            for button in self._buttons:
                if button.isChecked():
                    theme = str(button.property("value"))
                    break
            config = config._replace(
                tmdb=config.tmdb._replace(api_key=tmdb_key.strip()),
                omdb=config.omdb._replace(api_key=omdb_key.strip()),
                player_backend=player_backend,
                theme=theme,
            )
            save_config(config)
            # Apply theme immediately
            manager = self._theme_manager()
            if manager is not None:
                manager.set_mode(theme, apply=True)
            self._toast("Settings saved")
        except Exception as exc:  # noqa: BLE001
            self._toast(f"Couldn't save: {exc.__class__.__name__}")

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

    def _toast(self, message: str) -> None:
        window = self.window() if hasattr(self, "window") else None
        if window is not None and hasattr(window, "toast"):
            window.toast(message)
        else:
            print(message)  # noqa: T201
