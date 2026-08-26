"""Tests for time_utils.py: years to expiry and the AM/PM settlement lookup.

The important case here is the DST boundary -- a bug slipped through once
already (constructing both datetimes from the same tzinfo object makes
Python silently skip the offset change), so that scenario gets its own
test, not just a plausible-looking round number.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytest
from optionsengine.time_utils import years_to_expiry, resolve_settlement_hour

HOURS_PER_YEAR = 24 * 365


def test_same_day_hours():
    asof = datetime(2026, 8, 25, 9, 0, tzinfo=timezone.utc)
    years = years_to_expiry(asof, "2026-08-25", 16.0)
    assert years == pytest.approx(7 / HOURS_PER_YEAR)


def test_plain_week_same_time_of_day():
    asof = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    years = years_to_expiry(asof, "2026-09-08", 12.0)
    assert years == pytest.approx(168 / HOURS_PER_YEAR)


def test_dst_boundary_is_not_silently_dropped():
    """Regression test for a real bug: constructing the settlement datetime
    from asof.tzinfo directly makes Python skip timezone adjustment when
    subtracting two datetimes that share the same tzinfo object, silently
    losing the DST hour.

    2026-11-01 is when US DST ends. 11 wall-clock days at the same local
    hour should be 265 real hours elapsed, not 264, since the clocks fall
    back an hour partway through.
    """
    asof = datetime(2026, 10, 25, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    years = years_to_expiry(asof, "2026-11-05", 12.0)
    assert years == pytest.approx(265 / HOURS_PER_YEAR)


def test_resolve_settlement_hour_weekly():
    assert resolve_settlement_hour("SPXW", "SPXW", "SPX", 9.5, 16.0) == 16.0


def test_resolve_settlement_hour_monthly():
    assert resolve_settlement_hour("SPX", "SPXW", "SPX", 9.5, 16.0) == 9.5


def test_resolve_settlement_hour_unrecognised_root_raises():
    with pytest.raises(ValueError):
        resolve_settlement_hour("XYZ", "SPXW", "SPX", 9.5, 16.0)
