"""Explicit screen lifecycle states used by every view model."""
from __future__ import annotations

from enum import Enum


class ScreenState(str, Enum):
    INITIAL = "initial"
    LOADING = "loading"
    READY = "ready"
    EMPTY = "empty"
    ERROR = "error"
    SCANNING = "scanning"


STATE_LABELS: dict[ScreenState, str] = {
    ScreenState.INITIAL: "",
    ScreenState.LOADING: "Loading…",
    ScreenState.READY: "",
    ScreenState.EMPTY: "",
    ScreenState.ERROR: "Something went wrong",
    ScreenState.SCANNING: "Scanning your library…",
}
