"""Tests for chain.py: which expiries and strikes are worth asking for.

These are pure functions over plain data. No yfinance call or network access
is needed. The DataFrames here stand in for what option_chain() would return.
"""

import datetime
import pandas as pd
from optionsengine.yahoo.chain import select_expiries, select_root, select_moneyness

ASOF = datetime.datetime(2026, 8, 25, tzinfo=datetime.timezone.utc)


def test_select_expiries_keeps_the_window():
    expiries = ["2026-08-26", "2026-09-01", "2027-06-01", "2027-08-25", "2028-01-01"]
    kept = select_expiries(expiries, ASOF, min_years=7 / 365, max_years=1.0)
    # 2026-08-26 is 1 day out (below the one-week minimum), 2028-01-01 is well
    # past a year. 2026-09-01 and 2027-08-25 sit exactly on the two boundaries
    # and should still be kept, since the check is inclusive on both ends.
    assert kept == ["2026-09-01", "2027-06-01", "2027-08-25"]


def _contracts(*symbols):
    return pd.DataFrame({"contractSymbol": list(symbols)})


def test_select_root_keeps_weekly_when_only_weekly_is_listed():
    contracts = _contracts("SPXW260901C05000000", "SPXW260901P05000000")
    kept = select_root(contracts, weekly_root="SPXW", monthly_root="SPX")
    assert len(kept) == 2


def test_select_root_falls_back_to_monthly_when_thats_all_theres_is():
    contracts = _contracts("SPX270617C05000000", "SPX270617P05000000")
    kept = select_root(contracts, weekly_root="SPXW", monthly_root="SPX")
    assert len(kept) == 2


def test_select_root_prefers_weekly_when_both_are_listed():
    contracts = _contracts(
        "SPXW260918C05000000", "SPX260918C05000000", "SPXW260918P05000000"
    )
    kept = select_root(contracts, weekly_root="SPXW", monthly_root="SPX")
    assert list(kept["contractSymbol"]) == [
        "SPXW260918C05000000",
        "SPXW260918P05000000",
    ]


def test_select_moneyness_keeps_the_window():
    contracts = pd.DataFrame({"strike": [50.0, 80.0, 100.0, 120.0, 200.0]})
    # r=0 means the forward equals spot, so the window is exactly [80, 120].
    kept = select_moneyness(
        contracts, spot=100.0, r=0.0, years=1.0, moneyness_min=0.80, moneyness_max=1.20
    )
    assert list(kept["strike"]) == [80.0, 100.0, 120.0]


def test_select_moneyness_uses_the_forward_not_the_spot():
    """A positive r widens the window above spot, since F = S * exp(rT).

    F = 100 * exp(0.05 * 2) = 110.52, so the top of the window is 1.20 * F =
    132.6. A strike of 121 is above 1.20 * spot but still well inside the
    forward-based window, so it must be kept, not dropped.
    """
    contracts = pd.DataFrame({"strike": [119.0, 121.0]})
    kept = select_moneyness(
        contracts, spot=100.0, r=0.05, years=2.0, moneyness_min=0.80, moneyness_max=1.20
    )
    assert list(kept["strike"]) == [119.0, 121.0]
