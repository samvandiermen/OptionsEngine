"""Tests for the Greeks.

A Greek is the slope of the price curve, so there are two ways to get one: the
closed-form formula, or bumping an input and measuring how much the price moved.
These tests compute both and check they agree.

That makes it an independent check. The formulas are easy to get subtly wrong --
a sign in theta, a missing exp(-rT) in rho -- and re-deriving them by hand
repeats the same error-prone work. The bump only uses bs_price, which is already
tested against published values in test_pricing.py.
"""

import pytest
from optionsengine.pricing import bs_price
from optionsengine.greeks import all_greeks, delta, gamma, rho, theta, vega

# A spread of situations: at the money, either side of the money, close to
# expiry, and index-sized numbers where the absolute values look very different.
CASES = [
    dict(S=100.0, K=100.0, T=1.00, r=0.03, sigma=0.20),
    dict(S=100.0, K=130.0, T=0.50, r=0.03, sigma=0.25),
    dict(S=100.0, K=70.0, T=0.50, r=0.03, sigma=0.25),
    dict(S=100.0, K=100.0, T=0.05, r=0.05, sigma=0.60),
    dict(S=5000.0, K=5200.0, T=2.00, r=0.04, sigma=0.15),
]

RIGHTS = ["call", "put"]


def slope(price_at, x, h):
    """Central difference: how fast price changes as x moves.

    Bumps x both ways rather than just up. The error then shrinks with h
    squared instead of h, which buys several extra digits of agreement for
    free and keeps floating-point noise from causing false failures.
    """
    return (price_at(x + h) - price_at(x - h)) / (2 * h)


def curvature(price_at, x, h):
    """Second central difference: how fast the slope itself changes."""
    return (price_at(x + h) - 2 * price_at(x) + price_at(x - h)) / (h * h)


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("option_type", RIGHTS)
def test_delta_matches_bumping_the_underlying(case, option_type):
    S, K, T, r, sigma = case["S"], case["K"], case["T"], case["r"], case["sigma"]
    h = 1e-4 * S

    measured = slope(lambda s: bs_price(s, K, T, r, sigma, option_type), S, h)
    assert delta(S, K, T, r, sigma, option_type) == pytest.approx(measured, rel=1e-6)


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("option_type", RIGHTS)
def test_gamma_matches_bumping_the_underlying_twice(case, option_type):
    """Gamma is a second derivative, so it needs a bigger bump.

    Dividing by h squared magnifies rounding noise, so too small an h makes the
    measurement worse, not better.
    """
    S, K, T, r, sigma = case["S"], case["K"], case["T"], case["r"], case["sigma"]
    h = 1e-3 * S

    measured = curvature(lambda s: bs_price(s, K, T, r, sigma, option_type), S, h)
    assert gamma(S, K, T, r, sigma) == pytest.approx(measured, rel=1e-4)


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("option_type", RIGHTS)
def test_vega_matches_bumping_volatility(case, option_type):
    S, K, T, r, sigma = case["S"], case["K"], case["T"], case["r"], case["sigma"]
    h = 1e-5

    measured = slope(lambda v: bs_price(S, K, T, r, v, option_type), sigma, h)
    assert vega(S, K, T, r, sigma) == pytest.approx(measured, rel=1e-6)


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("option_type", RIGHTS)
def test_theta_matches_bumping_time(case, option_type):
    """Note the minus sign.

    Theta is the change as time *passes*, but T counts time *remaining*, so the
    two run in opposite directions.
    """
    S, K, T, r, sigma = case["S"], case["K"], case["T"], case["r"], case["sigma"]
    h = 1e-5

    measured = -slope(lambda t: bs_price(S, K, t, r, sigma, option_type), T, h)
    assert theta(S, K, T, r, sigma, option_type) == pytest.approx(measured, rel=1e-5)


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("option_type", RIGHTS)
def test_rho_matches_bumping_the_rate(case, option_type):
    S, K, T, r, sigma = case["S"], case["K"], case["T"], case["r"], case["sigma"]
    h = 1e-6

    measured = slope(lambda rate: bs_price(S, K, T, rate, sigma, option_type), r, h)
    assert rho(S, K, T, r, sigma, option_type) == pytest.approx(measured, rel=1e-6)


@pytest.mark.parametrize("case", CASES)
def test_gamma_and_vega_are_the_same_for_calls_and_puts(case):
    """Measured from the call price and from the put price, they agree.

    This is why gamma() and vega() take no option type.
    """
    S, K, T, r, sigma = case["S"], case["K"], case["T"], case["r"], case["sigma"]

    from_call = curvature(lambda s: bs_price(s, K, T, r, sigma, "call"), S, 1e-3 * S)
    from_put = curvature(lambda s: bs_price(s, K, T, r, sigma, "put"), S, 1e-3 * S)
    assert from_call == pytest.approx(from_put, rel=1e-6)

    from_call = slope(lambda v: bs_price(S, K, T, r, v, "call"), sigma, 1e-5)
    from_put = slope(lambda v: bs_price(S, K, T, r, v, "put"), sigma, 1e-5)
    assert from_call == pytest.approx(from_put, rel=1e-6)


@pytest.mark.parametrize("case", CASES)
def test_call_delta_minus_put_delta_is_one(case):
    """Follows from put-call parity: the difference in price is S - K*exp(-rT),
    whose slope in S is exactly 1."""
    S, K, T, r, sigma = case["S"], case["K"], case["T"], case["r"], case["sigma"]

    call_delta = delta(S, K, T, r, sigma, "call")
    put_delta = delta(S, K, T, r, sigma, "put")
    assert call_delta - put_delta == pytest.approx(1.0, abs=1e-12)


@pytest.mark.parametrize("case", CASES)
def test_signs_and_ranges(case):
    S, K, T, r, sigma = case["S"], case["K"], case["T"], case["r"], case["sigma"]

    assert 0.0 <= delta(S, K, T, r, sigma, "call") <= 1.0
    assert -1.0 <= delta(S, K, T, r, sigma, "put") <= 0.0
    assert gamma(S, K, T, r, sigma) > 0.0
    assert vega(S, K, T, r, sigma) > 0.0
    assert rho(S, K, T, r, sigma, "call") > 0.0
    assert rho(S, K, T, r, sigma, "put") < 0.0


def test_at_the_money_options_lose_value_over_time():
    """Theta is negative at the money, for both calls and puts.

    Only checked at the money on purpose. A deep in-the-money European put can
    have positive theta: exercise is nearly certain, and waiting means waiting
    longer to receive the strike.
    """
    assert theta(100.0, 100.0, 1.0, 0.03, 0.2, "call") < 0.0
    assert theta(100.0, 100.0, 1.0, 0.03, 0.2, "put") < 0.0


@pytest.mark.parametrize("bad", [dict(T=0.0), dict(sigma=0.0)])
def test_greeks_refuse_zero_time_or_zero_volatility(bad):
    """The pricer allows these and returns the intrinsic value. A slope there is
    either infinite or undefined, so the Greeks raise instead of inventing one."""
    args = dict(S=100.0, K=100.0, T=1.0, r=0.03, sigma=0.2)
    args.update(bad)

    with pytest.raises(ValueError):
        delta(args["S"], args["K"], args["T"], args["r"], args["sigma"], "call")
    with pytest.raises(ValueError):
        gamma(args["S"], args["K"], args["T"], args["r"], args["sigma"])


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("option_type", RIGHTS)
def test_all_greeks_matches_the_individual_functions(case, option_type):
    S, K, T, r, sigma = case["S"], case["K"], case["T"], case["r"], case["sigma"]

    g = all_greeks(S, K, T, r, sigma, option_type)
    assert g.delta == delta(S, K, T, r, sigma, option_type)
    assert g.gamma == gamma(S, K, T, r, sigma)
    assert g.vega == vega(S, K, T, r, sigma)
    assert g.theta == theta(S, K, T, r, sigma, option_type)
    assert g.rho == rho(S, K, T, r, sigma, option_type)


def test_greeks_return_plain_floats():
    values = [
        delta(100.0, 100.0, 1.0, 0.03, 0.2, "call"),
        gamma(100.0, 100.0, 1.0, 0.03, 0.2),
        vega(100.0, 100.0, 1.0, 0.03, 0.2),
        theta(100.0, 100.0, 1.0, 0.03, 0.2, "call"),
        rho(100.0, 100.0, 1.0, 0.03, 0.2, "call"),
    ]
    for value in values:
        assert type(value) is float
