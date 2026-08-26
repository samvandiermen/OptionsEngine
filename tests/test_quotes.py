"""Tests for quotes.py: hygiene, mid price, and OTM selection.

Builds small DataFrames shaped like what snapshot.py returns, rather than
pulling live data -- these are pure functions, so no network is needed.
"""
from datetime import datetime, timezone
import pandas as pd
import pytest
from optionsengine.pricing import forward_price
from optionsengine.time_utils import years_to_expiry
from optionsengine.quotes import (
    add_years_to_expiry, add_forward, add_mid_price, drop_bad_quotes,
    select_otm, clean_quotes,
)

ASOF = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


def test_add_years_to_expiry_uses_the_right_settlement_per_row():
    quotes = pd.DataFrame({
        "contract_symbol": ["SPXW260901C07670000", "SPX260901C07670000"],
        "expiry": ["2026-09-01", "2026-09-01"],
        "asof": [ASOF, ASOF],
    })
    result = add_years_to_expiry(quotes, weekly_root="SPXW", monthly_root="SPX",
                                  am_hour=9.5, pm_hour=16.0)
    expected_weekly = years_to_expiry(ASOF, "2026-09-01", 16.0)
    expected_monthly = years_to_expiry(ASOF, "2026-09-01", 9.5)
    assert result["years_to_expiry"].iloc[0] == pytest.approx(expected_weekly)
    assert result["years_to_expiry"].iloc[1] == pytest.approx(expected_monthly)


def test_add_forward_matches_forward_price():
    quotes = pd.DataFrame({"underlying_price": [100.0], "years_to_expiry": [0.5]})
    result = add_forward(quotes, r=0.04)
    assert result["forward"].iloc[0] == pytest.approx(forward_price(100.0, 0.5, 0.04))


def test_add_mid_price():
    quotes = pd.DataFrame({"bid": [1.0, 2.0], "ask": [1.2, 2.4]})
    result = add_mid_price(quotes)
    assert list(result["mid"]) == [1.1, 2.2]


def test_drop_bad_quotes_removes_each_kind_of_bad_row():
    # 0: good  1: missing bid  2: zero bid  3: crossed  4: locked  5: wide spread
    quotes = pd.DataFrame({
        "bid": [1.0, None, 0.0, 2.0, 1.5, 1.0],
        "ask": [1.1, 1.0, 0.5, 1.9, 1.5, 3.0],
    })
    result = drop_bad_quotes(quotes, max_spread_fraction=0.5)
    assert list(result.index) == [0]


def test_select_otm_keeps_calls_above_and_puts_below_forward():
    quotes = pd.DataFrame({
        "right": ["C", "C", "P", "P"],
        "strike": [110.0, 90.0, 90.0, 110.0],
        "forward": [100.0, 100.0, 100.0, 100.0],
    })
    result = select_otm(quotes)
    assert set(result.index) == {0, 2}


def test_select_otm_boundary_is_inclusive():
    quotes = pd.DataFrame({
        "right": ["C", "P"],
        "strike": [100.0, 100.0],
        "forward": [100.0, 100.0],
    })
    result = select_otm(quotes)
    assert len(result) == 2


def test_clean_quotes_runs_the_full_pipeline():
    quotes = pd.DataFrame({
        "contract_symbol": ["SPXW260901C07670000", "SPXW260901P07670000"],
        "expiry": ["2026-09-01", "2026-09-01"],
        "asof": [ASOF, ASOF],
        "right": ["C", "P"],
        "strike": [7700.0, 7600.0],
        "bid": [10.0, 10.0],
        "ask": [10.5, 10.5],
        "underlying_price": [7677.28, 7677.28],
    })
    result = clean_quotes(quotes, weekly_root="SPXW", monthly_root="SPX",
                           am_hour=9.5, pm_hour=16.0, r=0.04)
    assert "mid" in result.columns
    assert "forward" in result.columns
    assert len(result) == 2
