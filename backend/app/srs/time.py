"""UTC time helpers for SRS scheduling.

All ISO strings produced by this module are UTC and end with 'Z', with second precision:
YYYY-MM-DDTHH:MM:SSZ
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utc_now() -> datetime:
    """Return timezone-aware UTC 'now'."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return current time as UTC ISO string with second precision and trailing 'Z'."""
    return utc_datetime_to_iso_z(utc_now())


def utc_datetime_to_iso_z(dt: datetime) -> str:
    """Format a datetime as UTC ISO string with second precision and trailing 'Z'."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    dt = dt.replace(microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")


def parse_iso_z(s: str) -> datetime:
    """Parse an ISO-8601 string ending with 'Z' (or '+00:00') into UTC datetime.

    Accepts both second precision and fractional seconds.
    """
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def add_minutes_iso(now: datetime, minutes: int) -> str:
    return utc_datetime_to_iso_z(now + timedelta(minutes=minutes))


def add_hours_iso(now: datetime, hours: int) -> str:
    return utc_datetime_to_iso_z(now + timedelta(hours=hours))


def add_days_iso(now: datetime, days: int) -> str:
    return utc_datetime_to_iso_z(now + timedelta(days=days))
