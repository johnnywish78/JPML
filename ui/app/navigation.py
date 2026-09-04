"""Route model and centralized navigation with history.

Back navigation always returns to the previous route in history —
never to a default screen.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6.QtCore import QObject, pyqtSignal


@dataclass(frozen=True, slots=True)
class Route:
    screen: str
    params: dict = field(default_factory=dict)


class Navigation(QObject):
    stack_changed = pyqtSignal()
    route_changed = pyqtSignal(object)  # Route

    def __init__(self, initial: str = "home") -> None:
        super().__init__()
        self._history: list[Route] = []
        self._index: int = -1

    @property
    def current_route(self) -> Route | None:
        if 0 <= self._index < len(self._history):
            return self._history[self._index]
        return None

    @property
    def can_go_back(self) -> bool:
        return self._index > 0

    @property
    def can_go_forward(self) -> bool:
        return self._index < len(self._history) - 1

    def navigate(self, screen: str, **params) -> None:
        route = Route(screen, params)
        # drop any "forward" tail, then push
        del self._history[self._index + 1:]
        self._history.append(route)
        self._index += 1
        self._emit()

    def back(self) -> Route | None:
        if not self.can_go_back:
            return None
        self._index -= 1
        self._emit()
        return self._history[self._index]

    def forward(self) -> Route | None:
        if not self.can_go_forward:
            return None
        self._index += 1
        self._emit()
        return self._history[self._index]

    def _emit(self) -> None:
        self.stack_changed.emit()
        self.route_changed.emit(self.current_route)
