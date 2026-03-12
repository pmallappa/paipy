#!/usr/bin/env python3
"""
time_utils.py -- Shared Time Utilities.

Consistent timestamp generation across the hook system.
Reads timezone from settings.json via principal.timezone.
"""

from datetime import datetime, timezone, timedelta
from typing import NamedTuple

try:
    import zoneinfo
    _HAS_ZONEINFO = True
except ImportError:
    _HAS_ZONEINFO = False

from .identity import get_principal


def _get_timezone() -> str:
    """Get configured timezone from settings.json (defaults to UTC)."""
    return get_principal().timezone or "UTC"


def _now_in_tz() -> datetime:
    """Get current datetime in the configured timezone."""
    tz_name = _get_timezone()
    if _HAS_ZONEINFO:
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
            return datetime.now(tz)
        except Exception:
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)


def get_pst_timestamp() -> str:
    """Get full timestamp string: 'YYYY-MM-DD HH:MM:SS TZ'."""
    dt = _now_in_tz()
    tz_abbr = dt.strftime("%Z") or "UTC"
    return dt.strftime(f"%Y-%m-%d %H:%M:%S {tz_abbr}")


def get_pst_date() -> str:
    """Get date only: 'YYYY-MM-DD'."""
    return _now_in_tz().strftime("%Y-%m-%d")


def get_year_month() -> str:
    """Get year-month for directory structure: 'YYYY-MM'."""
    return get_pst_date()[:7]


def get_iso_timestamp() -> str:
    """Get ISO8601 timestamp with timezone offset."""
    dt = _now_in_tz()
    utc_dt = datetime.now(timezone.utc)
    diff = dt.replace(tzinfo=None) - utc_dt.replace(tzinfo=None)
    total_seconds = int(diff.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    abs_seconds = abs(total_seconds)
    hours = abs_seconds // 3600
    minutes = (abs_seconds % 3600) // 60
    offset = f"{sign}{hours:02d}:{minutes:02d}"
    return dt.strftime(f"%Y-%m-%dT%H:%M:%S{offset}")


def get_filename_timestamp() -> str:
    """Get timestamp formatted for filenames: 'YYYY-MM-DD-HHMMSS'."""
    return _now_in_tz().strftime("%Y-%m-%d-%H%M%S")


class TimestampComponents(NamedTuple):
    year: int
    month: str
    day: str
    hours: str
    minutes: str
    seconds: str


def get_pst_components() -> TimestampComponents:
    """Get timestamp components for custom formatting."""
    dt = _now_in_tz()
    return TimestampComponents(
        year=dt.year,
        month=f"{dt.month:02d}",
        day=f"{dt.day:02d}",
        hours=f"{dt.hour:02d}",
        minutes=f"{dt.minute:02d}",
        seconds=f"{dt.second:02d}",
    )


def get_timezone_display() -> str:
    """Get timezone string for display."""
    dt = _now_in_tz()
    return dt.strftime("%Z") or _get_timezone()
