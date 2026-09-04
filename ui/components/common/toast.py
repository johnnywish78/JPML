"""Minimal toast notification system (bottom-right, auto-dismiss)."""
from __future__ import annotations

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QLabel, QMenu, QWidget


class ToastHost:
    """Attaches transient toasts to a host window (bottom-right)."""

    DURATION_MS = 2600

    def __init__(self, host: QWidget) -> None:
        self._host = host
        self._label: QLabel | None = None
        self._timer = QTimer(host)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._hide)

    def show_message(self, text: str) -> None:
        if self._label is not None:
            self._label.close()
        self._label = QLabel(text, self._host)
        self._label.setObjectName("Toast")
        self._label.setFocusPolicy(self._label.focusPolicy() | 0)
        self._label.adjustSize()
        margin = 24
        x = self._host.width() - self._label.width() - margin * 2
        y = self._host.height() - self._label.height() - margin * 2
        self._label.move(max(margin, x), max(margin, y))
        self._label.raise_()
        self._label.show()
        self._timer.start(self.DURATION_MS)

    def _hide(self) -> None:
        if self._label is not None:
            self._label.close()
            self._label = None


def show_context_menu(menu: QMenu, at_widget: QWidget) -> None:
    menu.exec(at_widget.mapToGlobal(at_widget.rect().bottomLeft()))
