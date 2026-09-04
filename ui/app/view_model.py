"""View-model base classes shared by all screens.

A view model is the only place a screen may touch backend services.
It owns the screen's ScreenState and publishes plain Python data
(models/dataclasses) that widgets render.
"""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal

from ui.app.app_state import ScreenState
from ui.app.composition import ServiceComposition
from ui.app.navigation import Navigation


@dataclass(slots=True)
class UiContext:
    """Everything a screen may need, injected by the application shell."""

    services: ServiceComposition
    navigation: Navigation
    theme_changed: object = None  # bound later by MainWindow


class BaseViewModel(QObject):
    state_changed = pyqtSignal(object, object)  # ScreenState, payload

    def __init__(self, context: UiContext) -> None:
        super().__init__()
        self.context = context
        self._state: ScreenState = ScreenState.INITIAL

    @property
    def state(self) -> ScreenState:
        return self._state

    def set_state(self, state: ScreenState, payload: object = None) -> None:
        self._state = state
        self.state_changed.emit(state, payload)

    def reset(self) -> None:
        self.set_state(ScreenState.INITIAL)

    def fail(self, error: Exception | str | None = None) -> None:
        """Enter ERROR state without exposing tracebacks."""
        self.set_state(ScreenState.ERROR, error)
