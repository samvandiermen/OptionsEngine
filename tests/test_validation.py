"""Tests for validation.py: our IV vs Yahoo's, MAE/RMSE by bucket and method.

Builds small synthetic quotes rather than pulling live data -- these are
pure functions once you have a DataFrame, so no network is needed.
"""
import math
import pandas as pd
import pytest
from optionsengine.pricing import bs_price
from optionsengine.validation import (
    add_our_iv, add_error, add_moneyness_bucket, mae_rmse, mae_rmse_by,
    method_distribution,
)


def test_add_our_iv_recovers_a_known_volatility():
    S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.04, 0.20
    price = bs_price(S, K, T, r, sigma, "call")
    quotes = pd.DataFrame({
        "mid": [price],
        "underlying_price": [S],
        "strike": [K],
        "years_to_expiry": [T],
        "right": ["C"],
    })
    result = add_our_iv(quotes, r)
    assert result["iv_ours"].iloc[0] == pytest.approx(sigma, abs=1e-4)
    assert result["iv_method"].iloc[0] in ("newton", "bisection")


def test_add_error_is_ours_minus_yahoos():
    quotes = pd.DataFrame({"iv_ours": [0.22, float("nan")], "implied_vol_yahoo": [0.20, 0.25]})
    result = add_error(quotes)
    assert result["iv_error"].iloc[0] == pytest.approx(0.02)
    assert math.isnan(result["iv_error"].iloc[1])


def test_add_moneyness_bucket_uses_strike_over_forward():
    quotes = pd.DataFrame({"strike": [92.0, 100.0], "forward": [100.0, 100.0]})
    result = add_moneyness_bucket(quotes)
    # 92/100 = 0.92 -> (0.90, 0.95]; 100/100 = 1.00 -> (0.95, 1.00]
    assert str(result["moneyness_bucket"].iloc[0]) == "(0.9, 0.95]"
    assert str(result["moneyness_bucket"].iloc[1]) == "(0.95, 1.0]"


def test_mae_rmse_matches_hand_computed_values():
    # errors 0.01, -0.02, 0.03, and a failed solve (NaN) that must be dropped
    quotes = pd.DataFrame({"iv_error": [0.01, -0.02, 0.03, float("nan")]})
    mae, rmse = mae_rmse(quotes)
    assert mae == pytest.approx((0.01 + 0.02 + 0.03) / 3)
    assert rmse == pytest.approx(math.sqrt((0.01**2 + 0.02**2 + 0.03**2) / 3))


def test_mae_rmse_by_splits_correctly_between_groups():
    quotes = pd.DataFrame({
        "iv_error": [0.01, 0.03, 0.10, 0.20],
        "group": ["a", "a", "b", "b"],
    })
    result = mae_rmse_by(quotes, "group")
    assert result.loc["a", "mae"] == pytest.approx(0.02)
    assert result.loc["b", "mae"] == pytest.approx(0.15)


def test_method_distribution_gives_proportions():
    quotes = pd.DataFrame({"iv_method": ["newton", "newton", "newton", "bisection"]})
    result = method_distribution(quotes)
    assert result["newton"] == pytest.approx(0.75)
    assert result["bisection"] == pytest.approx(0.25)
