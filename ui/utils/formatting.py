"""Display formatting helpers — deterministic, no backend imports."""
from __future__ import annotations


def format_seconds(total: float) -> str:
    """122.4 -> '2:02' or 7553 -> '1:59:13'."""
    if total is None or total <= 0:
        return "0:00"
    total = int(total)
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def format_duration_label(total: float) -> str:
    """Human label for durations: '2h 5m', '45m', '30s'."""
    if total is None or total <= 0:
        return ""
    total = int(total)
    hours, rem = divmod(total, 3600)
    minutes = rem // 60
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    if minutes:
        return f"{minutes}m"
    return f"{total}s"


def format_year(year: int | None) -> str:
    if year is None:
        return ""
    return str(year)


def join_meta(*parts: str | None) -> str:
    """Join non-empty metadata fragments with ' · '."""
    return " · ".join(p for p in (str(x) for x in parts) if p and p.strip())


def first_present(*values: str | None) -> str:
    for value in values:
        if value and str(value).strip():
            return str(value).strip()
    return ""
