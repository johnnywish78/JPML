"""Shared presentation models used by screens and cards.

These are display-only projections of backend data. Screens build
them from service results; cards only render them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EntityRef:
    """A display-ready media entity."""

    kind: str  # movie | tv | episode | artist | album | track | person
    entity_id: int
    title: str
    year: int | None = None
    overview: str | None = None
    meta: str = ""  # preformatted '2010 · Action · Sci-Fi'
    progress: float | None = None  # 0.0 .. 1.0
    progress_label: str = ""
    file_path: str | None = None
    artwork: dict[str, Any] | None = None
    artwork_kind: str = "poster"  # poster | backdrop | album | artist | person
    is_favorite: bool = False
    in_watchlist: bool = False
    completed: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def key(self) -> tuple[str, int]:
        return (self.kind, self.entity_id)
