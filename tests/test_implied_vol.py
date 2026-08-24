"""Tests for the implied volatility solver.

The main test is a round trip: pick a volatility, price the option with it, then
ask the solver to recover it. It should hand back what we started with.

The rest cover the awkward parts -- when Newton gives up, when a quote cannot be
solved at all, and whether the answer matches an independent solver.
"""

import math
import pytest
from scipy.optimize import brentq
from optionsengine.pricing import bs_price
from optionsengine.implied_vol import SIGMA_BOUNDS, implied_volatility

R = 0.03

# Strikes measured in standard deviations from the money, not in percent.
#
# Percent is the wrong yardstick. A strike 10% away is ordinary with a year to
# run and absurd with a week to run: the same 10% is under one standard
# deviation in the first case and about seven in the second. Real chains are
# quoted around the money in this sense, so sigma * sqrt(T) is the scale that
# keeps every combination below a plausible one.
ROUND_TRIP = [
    (S, S * math.exp(z * sigma * math.sqrt(T)), T, sigma, option_type)
    for S in (100.0, 5000.0)
    for T in (7 / 365, 30 / 365, 0.25, 1.0)
    for sigma in (0.10, 0.15, 0.20, 0.35, 0.60)
    for z in (-2.5, -1.5, -0.5, 0.0, 0.5, 1.5, 2.5)
    for option_type in ("call", "put")
]


@pytest.mark.parametrize("S, K, T, sigma, option_type", ROUND_TRIP)
def test_round_trip_recovers_the_volatility(S, K, T, sigma, option_type):
    """Price it with a known volatility, then solve for it and get it back.

    Not machine precision, because we stop once the price matches to within
    PRICE_TOL and that leaves roughly PRICE_TOL divided by vega in the
    volatility. Near the money vega is healthy, so what is left is tiny.
    """
    price = bs_price(S, K, T, R, sigma, option_type)
    result = implied_volatility(price, S, K, T, R, option_type)

    assert result.method != "failed", result.reason
    assert result.iv == pytest.approx(sigma, abs=1e-6)


def test_newton_solves_ordinary_options_quickly():
    """Newton converges fast, which is the whole reason it goes first."""
    price = bs_price(100.0, 105.0, 0.5, R, 0.25, "call")
    result = implied_volatility(price, 100.0, 105.0, 0.5, R, "call")

    assert result.method == "newton"
    assert result.iterations <= 6


@pytest.mark.parametrize(
    "S, K, T, sigma, option_type",
    [
        (100.0, 150.0, 0.05, 0.80, "call"),
        (100.0, 60.0, 0.02, 1.00, "put"),
        (100.0, 200.0, 0.08, 0.50, "call"),
    ],
)
def test_bisection_takes_over_and_still_gets_it_right(S, K, T, sigma, option_type):
    """Far from the money with little time left, Newton gives up.

    Vega is small there, so dividing by it throws the next guess outside the
    range we are searching. Bisection cannot do that: it only ever halves a
    range it already knows contains the answer.
    """
    price = bs_price(S, K, T, R, sigma, option_type)
    result = implied_volatility(price, S, K, T, R, option_type)

    assert result.method == "bisection"
    assert result.iv == pytest.approx(sigma, abs=1e-4)


@pytest.mark.parametrize("option_type", ["call", "put"])
def test_agrees_with_an_independent_solver(option_type):
    """Cross-check against scipy's brentq on the same problem.

    Ours is hand-written, so this confirms the answer rather than the method.
    """
    S, K, T, sigma = 100.0, 108.0, 0.4, 0.32
    price = bs_price(S, K, T, R, sigma, option_type)

    expected = brentq(
        lambda v: bs_price(S, K, T, R, v, option_type) - price,
        *SIGMA_BOUNDS,
        xtol=1e-12,
    )
    result = implied_volatility(price, S, K, T, R, option_type)
    assert result.iv == pytest.approx(expected, abs=1e-6)


@pytest.mark.parametrize("price", [0.0, -1.0, float("nan"), float("inf")])
def test_unusable_prices_fail_without_raising(price):
    """A missing or nonsense quote is data to filter out, not a crash."""
    result = implied_volatility(price, 100.0, 100.0, 0.5, R, "call")

    assert result.method == "failed"
    assert math.isnan(result.iv)
    assert result.reason


def test_price_below_the_no_arbitrage_minimum_fails():
    """No volatility can produce a price under the floor, so do not pretend."""
    floor = max(100.0 - 90.0 * math.exp(-R * 0.5), 0.0)
    result = implied_volatility(floor - 1.0, 100.0, 90.0, 0.5, R, "call")

    assert result.method == "failed"
    assert "no-arbitrage" in result.reason


def test_price_above_the_search_range_fails():
    result = implied_volatility(99.9, 100.0, 100.0, 0.5, R, "call")

    assert result.method == "failed"
    assert math.isnan(result.iv)


@pytest.mark.parametrize(
    "S, K, T, option_type",
    [
        (100.0, 300.0, 1 / 365, "put"),
        (100.0, 10.0, 1 / 365, "call"),
    ],
)
def test_deep_in_the_money_near_expiry_has_no_answer(S, K, T, option_type):
    """The price sits on its no-arbitrage bound and stops responding to
    volatility, so every volatility fits equally well and none of them mean
    anything. Reporting a number here would be the worst outcome: it would look
    like a real data point on the surface."""
    price = bs_price(S, K, T, R, 0.20, option_type)
    result = implied_volatility(price, S, K, T, R, option_type)

    assert result.method == "failed"
    assert math.isnan(result.iv)
    assert "barely moves" in result.reason


def test_far_out_of_the_money_near_expiry_has_no_answer():
    """A strike seven standard deviations away with a week to run.

    Worth a fraction of a cent, and in the market it would be quoted 0.00 bid.
    There is no volatility to recover from a price like that, so the solver
    says so rather than returning a number that would look real on a surface.
    """
    S, K, T, sigma = 100.0, 110.0, 7 / 365, 0.10
    price = bs_price(S, K, T, R, sigma, "call")
    result = implied_volatility(price, S, K, T, R, "call")

    assert result.method == "failed"
    assert "barely moves" in result.reason


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(S=-1.0, K=100.0, T=0.5),
        dict(S=100.0, K=0.0, T=0.5),
        dict(S=100.0, K=100.0, T=0.0),
        dict(S=100.0, K=100.0, T=-0.5),
    ],
)
def test_bad_contract_details_raise(kwargs):
    """These come from our own code, not from the market, so they are bugs."""
    with pytest.raises(ValueError):
        implied_volatility(5.0, r=R, option_type="call", **kwargs)


def test_successful_result_is_a_plain_float():
    result = implied_volatility(10.0, 100.0, 100.0, 1.0, R, "call")

    assert result.method == "newton"
    assert type(result.iv) is float
    assert result.reason == ""
