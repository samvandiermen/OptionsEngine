"""
Time to expiry, in years, ACT/365, measured from asof to the contract's real
settlement moment. Not whole days, and not the wall clock -- the quote's own
moment matters, since getting this wrong can move the answer a lot.
"""
from datetime import date, datetime, timezone


def years_to_expiry(asof, expiry, settlement_hour):
    """Years from asof to settlement_hour (ET) on expiry, ACT/365.

    expiry is an ISO date string, e.g. '2026-09-01'. settlement_hour is hours
    after midnight, e.g. 9.5 for 09:30, 16.0 for 16:00. asof must already be
    in the exchange's own timezone, which is how snapshot.py builds it.
    """
    expiry_date = date.fromisoformat(expiry)
    hour = int(settlement_hour)
    minute = round((settlement_hour - hour) * 60)
    settlement = datetime(expiry_date.year, expiry_date.month, expiry_date.day,
                           hour, minute, tzinfo=asof.tzinfo)

    # asof and settlement can be on opposite sides of a DST change (e.g. an
    # August quote against a December LEAPS expiry). Converting both to UTC
    # first forces Python to actually apply that offset difference -- left
    # as local time, subtraction silently ignores it when both datetimes
    # share the same tzinfo object, which these always do.
    hours = (settlement.astimezone(timezone.utc) - asof.astimezone(timezone.utc)).total_seconds() / 3600
    return hours / (24 * 365)


def resolve_settlement_hour(root, weekly_root, monthly_root, am_hour, pm_hour):
    """Which settlement hour applies, based on the contract's root."""
    if root == weekly_root:
        return pm_hour
    if root == monthly_root:
        return am_hour
    raise ValueError(f"Unrecognised root: {root!r}")
