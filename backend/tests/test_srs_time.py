"""Unit tests for SRS time helpers."""

from datetime import datetime, timezone

from app.srs.time import add_days_iso, add_hours_iso, add_minutes_iso, parse_iso_z, utc_datetime_to_iso_z


def test_utc_datetime_to_iso_z_second_precision():
    dt = datetime(2025, 12, 13, 0, 0, 0, 999999, tzinfo=timezone.utc)
    assert utc_datetime_to_iso_z(dt) == "2025-12-13T00:00:00Z"


def test_parse_iso_z_accepts_z_and_fractional_seconds():
    assert parse_iso_z("2025-12-13T00:00:00Z").tzinfo is not None
    assert parse_iso_z("2025-12-13T00:00:00.123456Z").tzinfo is not None


def test_add_minutes_iso_rollover():
    now = datetime(2025, 12, 31, 23, 59, 0, tzinfo=timezone.utc)
    assert add_minutes_iso(now, 2) == "2026-01-01T00:01:00Z"


def test_add_hours_iso_rollover():
    now = datetime(2025, 12, 31, 23, 0, 0, tzinfo=timezone.utc)
    assert add_hours_iso(now, 24) == "2026-01-01T23:00:00Z"


def test_add_days_iso_rollover():
    now = datetime(2025, 12, 30, 0, 0, 0, tzinfo=timezone.utc)
    assert add_days_iso(now, 4) == "2026-01-03T00:00:00Z"
