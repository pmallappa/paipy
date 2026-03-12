"""Clock — consistent timestamp generation.

Provides static methods for all timestamp formats used across PAI.
Reads timezone from settings via Settings singleton.
Uses datetime.now(timezone.utc) — never the deprecated utcnow().
"""

from datetime import datetime, timezone
from typing import NamedTuple

try:
    import zoneinfo
    _HAS_ZONEINFO = True
except ImportError:
    _HAS_ZONEINFO = False


class TimestampComponents(NamedTuple):
    year: int
    month: str
    day: str
    hours: str
    minutes: str
    seconds: str


class Clock:
    """Static methods for every timestamp format PAI needs."""

    @staticmethod
    def _get_timezone_name() -> str:
        """Get configured timezone string from settings (defaults to UTC)."""
        from .settings import Settings
        return Settings.get().raw().get("principal", {}).get("timezone", "UTC") or "UTC"

    @staticmethod
    def _now_local() -> datetime:
        """Get current datetime in the configured timezone."""
        tz_name = Clock._get_timezone_name()
        if _HAS_ZONEINFO:
            try:
                tz = zoneinfo.ZoneInfo(tz_name)
                return datetime.now(tz)
            except Exception:
                pass
        return datetime.now(timezone.utc)

    @staticmethod
    def iso() -> str:
        """ISO8601 UTC timestamp: '2024-01-01T00:00:00Z'."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def filename() -> str:
        """Filename-safe UTC timestamp: '20240101_000000'."""
        return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    @staticmethod
    def year_month() -> str:
        """Year-month string: '2024-01'."""
        return datetime.now(timezone.utc).strftime("%Y-%m")

    @staticmethod
    def date() -> str:
        """Date string: '2024-01-01'."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    @staticmethod
    def timestamp() -> str:
        """Full timestamp in configured timezone: 'YYYY-MM-DD HH:MM:SS TZ'."""
        dt = Clock._now_local()
        tz_abbr = dt.strftime("%Z") or "UTC"
        return dt.strftime(f"%Y-%m-%d %H:%M:%S {tz_abbr}")

    @staticmethod
    def components() -> TimestampComponents:
        """Get timestamp components for custom formatting."""
        dt = Clock._now_local()
        return TimestampComponents(
            year=dt.year,
            month=f"{dt.month:02d}",
            day=f"{dt.day:02d}",
            hours=f"{dt.hour:02d}",
            minutes=f"{dt.minute:02d}",
            seconds=f"{dt.second:02d}",
        )

    @staticmethod
    def timezone_display() -> str:
        """Get timezone string for display."""
        dt = Clock._now_local()
        return dt.strftime("%Z") or Clock._get_timezone_name()
