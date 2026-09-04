"""Applies JPML themes as a global Qt stylesheet.

A single stylesheet generator means Dark and Light use identical
components — only token values differ.
"""
from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QStyleHints
from PyQt6.QtWidgets import QApplication

from ui.themes.dark import DARK
from ui.themes.light import LIGHT
from ui.themes.tokens import Motion, Radius


class ThemeMode(str):
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"


def _is_system_dark(hints: "QStyleHints") -> bool:
    """Return True when the OS/system theme is dark.

    PyQt6 does not consistently expose the scoped QStyleHints.ColorScheme
    enum as a named attribute, so we compare the returned value against
    the documented integer values (Unknown=0, Dark=1, Light=2).
    """
    try:
        value = int(hints.colorScheme())
    except (TypeError, ValueError):
        return True
    return value == 1  # ColorScheme.Dark


def _build_qss(t) -> str:  # noqa: ANN001 — ThemeTokens
    return f"""
* {{
    outline: none;
}}
QWidget {{
    background-color: transparent;
    color: {t.text_primary};
    font-size: 15px;
}}
QMainWindow, #AppBackground {{
    background-color: {t.background};
}}
#SidebarBackground {{
    background-color: {t.surface};
}}
QToolTip {{
    background-color: {t.menu_background};
    color: {t.text_primary};
    border: 1px solid {t.border};
    padding: 6px 10px;
    border-radius: {Radius.CONTROL}px;
}}
QLabel {{
    background: transparent;
}}
QLabel#MutedLabel {{
    color: {t.text_muted};
}}
QLabel#SecondaryLabel {{
    color: {t.text_secondary};
}}
QLabel#BrandMuted {{
    color: {t.text_muted};
    font-size: 11px;
}}
QLabel#SectionLabel {{
    color: {t.text_muted};
    font-size: 11px;
    font-weight: {600};
    letter-spacing: 1.2px;
}}
QLabel#NavActiveLabel {{
    color: {t.text_primary};
    font-weight: 500;
}}
QLabel#NavLabel {{
    color: {t.text_secondary};
    font-weight: 500;
}}

QPushButton {{
    background-color: {t.elevated};
    color: {t.text_primary};
    border: 1px solid {t.border};
    border-radius: {Radius.BUTTON}px;
    padding: 8px 16px;
    font-size: 14px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {t.card_hover};
    border-color: {t.border_strong};
}}
QPushButton:pressed {{
    background-color: {t.elevated};
}}
QPushButton:disabled {{
    color: {t.text_muted};
    border-color: {t.border};
    background-color: {t.surface};
}}
QPushButton#PrimaryButton {{
    background-color: {t.accent};
    border: none;
    color: {t.text_on_accent};
}}
QPushButton#PrimaryButton:hover {{
    background-color: {t.accent_hover};
}}
QPushButton#PrimaryButton:pressed {{
    background-color: {t.accent_pressed};
}}
QPushButton#PrimaryButton:disabled {{
    background-color: {t.elevated};
    color: {t.text_muted};
}}
QPushButton#GhostButton {{
    background-color: transparent;
    border: 1px solid {t.border};
    color: {t.text_primary};
}}
QPushButton#GhostButton:hover {{
    background-color: {t.elevated};
}}
QPushButton#DangerButton {{
    background-color: transparent;
    border: 1px solid {t.danger};
    color: {t.danger};
}}
QPushButton#DangerButton:hover {{
    background-color: {t.danger};
    color: {t.text_on_accent};
}}

#NavButton {{
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: {Radius.BUTTON}px;
    text-align: left;
    padding: 10px 12px 10px 11px;
    color: {t.text_secondary};
    font-size: 14px;
    font-weight: 500;
}}
#NavButton:hover {{
    background-color: {t.elevated};
}}
#NavButton[active="true"] {{
    background-color: {t.card};
    color: {t.text_primary};
    border-left: 3px solid {t.accent};
}}

#IconButton {{
    background: transparent;
    border: none;
    border-radius: {Radius.BUTTON}px;
    color: {t.text_secondary};
    padding: 8px;
}}
#IconButton:hover {{
    background-color: {t.elevated};
    color: {t.text_primary};
}}
#IconButton:disabled {{
    color: {t.text_muted};
}}

#CardFrame {{
    background-color: {t.card};
    border: 1px solid {t.border};
    border-radius: {Radius.CARD}px;
}}
#ElevatedFrame {{
    background-color: {t.elevated};
    border: 1px solid {t.border};
    border-radius: {Radius.SURFACE}px;
}}

QLineEdit, QComboBox {{
    background-color: {t.input_field};
    border: 1px solid {t.border};
    border-radius: {Radius.CONTROL}px;
    padding: 8px 12px;
    color: {t.text_primary};
    selection-background-color: {t.accent};
}}
QLineEdit:focus, QComboBox:focus {{
    border-color: {t.accent};
}}
QLineEdit:disabled {{
    color: {t.text_muted};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {t.menu_background};
    border: 1px solid {t.border};
    border-radius: {Radius.CONTROL}px;
    selection-background-color: {t.menu_hover};
    color: {t.text_primary};
    padding: 4px;
}}

QMenu {{
    background-color: {t.menu_background};
    border: 1px solid {t.border};
    border-radius: {Radius.CONTROL}px;
    padding: 6px;
}}
QMenu::item {{
    padding: 7px 22px;
    border-radius: {Radius.CONTROL}px;
    color: {t.text_primary};
}}
QMenu::item:selected {{
    background-color: {t.menu_hover};
}}
QMenu::separator {{
    height: 1px;
    background: {t.border};
    margin: 5px 8px;
}}

QLabel#ProgressLabel {{
    color: {t.text_secondary};
    font-size: 11px;
}}

QSlider::groove:horizontal {{
    height: 4px;
    background: {t.progress_track};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {t.accent};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
    background: {t.text_primary};
}}
QSlider::handle:horizontal:hover {{
    background: {t.text_on_accent};
}}
#VolumeSlider::groove:horizontal {{
    height: 4px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {t.scrollbar};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t.scrollbar_hover};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {t.scrollbar};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {t.scrollbar_hover};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}

#Toast {{
    background-color: {t.elevated};
    border: 1px solid {t.border_strong};
    border-radius: {Radius.BUTTON}px;
    padding: 10px 16px;
}}
#ToastLabel {{
    color: {t.text_primary};
    font-size: 13px;
    background: transparent;
}}
#SkeletonBlock {{
    background-color: {t.skeleton};
    border-radius: {Radius.CARD}px;
}}
"""


class ThemeManager(QObject):
    """Owns the active theme; re-applies a single global stylesheet on change."""

    theme_changed = pyqtSignal(str)  # theme name: "dark" | "light"

    def __init__(self, app: QApplication, hints: QStyleHints) -> None:
        super().__init__()
        self._app = app
        self._hints = hints
        self._mode: ThemeMode = ThemeMode.DARK
        self._active_tokens = DARK
        hints.colorSchemeChanged.connect(self._on_system_scheme_changed)
        self.set_mode(ThemeMode.DARK, apply=True)

    # -- public API ------------------------------------------------------------

    @property
    def mode(self) -> ThemeMode:
        return self._mode

    @property
    def tokens(self):
        return self._active_tokens

    def set_mode(self, mode: str, *, apply: bool = True) -> None:
        mode_value = ThemeMode(mode)
        self._mode = mode_value
        if apply:
            self.refresh()

    def refresh(self) -> None:
        if self._mode == ThemeMode.SYSTEM:
            dark = _is_system_dark(self._hints)
        else:
            dark = self._mode == ThemeMode.DARK
        tokens = DARK if dark else LIGHT
        self._active_tokens = tokens
        self._app.setStyleSheet(_build_qss(tokens))
        self.theme_changed.emit(tokens.name)

    # -- internals --------------------------------------------------------------

    def _on_system_scheme_changed(self) -> None:
        if self._mode == ThemeMode.SYSTEM:
            self.refresh()


def motion_ms(kind: str) -> int:
    return {
        "micro": Motion.MICRO,
        "standard": Motion.STANDARD,
        "page": Motion.PAGE,
        "cinematic": Motion.CINEMATIC,
    }.get(kind, Motion.STANDARD)
