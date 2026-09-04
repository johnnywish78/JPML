"""The JPML sidebar: branding, navigation groups, settings at bottom."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.themes.tokens import Radius, Spacing, Typography

BRAND_TITLE = "JPML"
BRAND_SUBTITLE = "Johnny's Personal Media Library"
BRAND_VERSION = "v1.0"


class NavItem:
    def __init__(self, route: str, label: str, glyph: str) -> None:
        self.route = route
        self.label = label
        self.glyph = glyph


LIBRARY_SECTION = "LIBRARY"
DISCOVER_SECTION = "DISCOVER"
MY_LIBRARY_SECTION = "MY LIBRARY"

NAV_ITEMS: dict[str, list[NavItem]] = {
    LIBRARY_SECTION: [
        NavItem("home", "Home", "⌂"),
        NavItem("movies", "Movies", "▣"),
        NavItem("tv_shows", "TV Shows", "▤"),
        NavItem("people", "People", "♟"),
        NavItem("music", "Music", "♫"),
        NavItem("library", "Library", "⊞"),
    ],
    DISCOVER_SECTION: [
        NavItem("trending", "Trending", "↗"),
        NavItem("recommendations", "Recommendations", "✦"),
    ],
    MY_LIBRARY_SECTION: [
        NavItem("favorites", "Favorites", "♥"),
        NavItem("watchlist", "Watchlist", "+"),
        NavItem("collections", "Collections", "⧉"),
    ],
}


class Sidebar(QFrame):
    navigation_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarBackground")
        self.setFixedWidth(260)
        self._buttons: dict[str, QPushButton] = {}
        self._build()

    # -- construction ----------------------------------------------------------

    def _header(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(Spacing.XL, Spacing.XXL, Spacing.XL, Spacing.M)
        layout.setSpacing(2)

        brand = QLabel(BRAND_TITLE)
        brand.setStyleSheet(
            f"font-size: 30px; font-weight: 800; "
            f"letter-spacing: 4px; color: #D7263D; background: transparent;"
        )
        subtitle = QLabel(BRAND_SUBTITLE)
        subtitle.setObjectName("SecondaryLabel")
        subtitle.setStyleSheet(
            "font-size: 11px; letter-spacing: 0.6px; "
            "background: transparent;"
        )
        version = QLabel(BRAND_VERSION)
        version.setObjectName("BrandMuted")
        version.setStyleSheet("letter-spacing: 1px;")

        layout.addWidget(brand)
        layout.addWidget(subtitle)
        layout.addWidget(version)
        return container

    def _separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background: #232733; max-height: 1px;")
        return line

    def _section_label(self, text: str) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(Spacing.L, Spacing.XL, Spacing.L, 3)
        label = QLabel(text)
        label.setObjectName("SectionLabel")
        layout.addWidget(label)
        return container

    def _nav_button(self, item: NavItem) -> QPushButton:
        button = QPushButton(f"  {item.glyph}   {item.label}")
        button.setObjectName("NavButton")
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setProperty("active", False)
        button.setMinimumHeight(38)
        button.toggled.connect(lambda checked, r=item.route: self._toggled(r, checked))
        return button

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, Spacing.L, 0, Spacing.L)
        layout.setSpacing(0)

        layout.addWidget(self._header())
        layout.addWidget(self._separator())
        layout.addSpacing(Spacing.S)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for section, items in NAV_ITEMS.items():
            layout.addWidget(self._section_label(section))
            for item in items:
                button = self._nav_button(item)
                self._group.addButton(button)
                self._buttons[item.route] = button
                layout.addWidget(button)

        layout.addStretch(1)

        settings_button = QPushButton("  ⚙   Settings")
        settings_button.setObjectName("NavButton")
        settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_button.setMinimumHeight(38)
        settings_button.clicked.connect(lambda: self.navigation_requested.emit("settings"))
        self._settings_button = settings_button
        layout.addWidget(settings_button)
        layout.addSpacing(Spacing.M)

        self._group.buttonClicked.connect(self._set_active)

    # -- public API --------------------------------------------------------------

    def set_active_route(self, route: str) -> None:
        for name, button in self._buttons.items():
            is_active = name == route
            button.setChecked(is_active)
            button.setProperty("active", is_active)
            button.style().unpolish(button)
            button.style().polish(button)
        active_is_settings = route == "settings"
        self._settings_button.setProperty("active", active_is_settings)
        self._settings_button.style().unpolish(self._settings_button)
        self._settings_button.style().polish(self._settings_button)
        if not active_is_settings and route in self._buttons:
            # keep exclusive group consistent
            self._buttons[route].setChecked(True)

    # -- internals -----------------------------------------------------------------

    def _toggled(self, route: str, checked: bool) -> None:
        if checked:
            self.navigation_requested.emit(route)

    def _set_active(self, _button) -> None:
        pass
