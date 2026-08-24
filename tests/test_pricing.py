"""Tests for the Black-Scholes pricer.

The strategy here is to check the formula against things we know independently
of the code: published textbook values, put-call parity, and the limiting cases
where the option price has an obvious answer. If all of those hold, the pricer
is trustworthy enough to build the Greeks and the IV solver on top of it.
"""

import math
import pytest
from optionsengine.pricing import bs_price, forward_price

# Hull, "Options, Futures and Other Derivatives" worked example:
# spot 42, strike 40, 6 months to expiry, 10% rate, 20% vol.
# The book quotes call = 4.76 and put = 0.81.
HULL = dict(S=42.0, K=40.0, T=0.5, r=0.10, sigma=0.20)


def test_matches_textbook_call_value():
    price = bs_price(option_type="call", **HULL)
    assert price == pytest.approx(4.76, abs=0.01)


def test_matches_textbook_put_value():
    price = bs_price(option_type="put", **HULL)
    assert price == pytest.approx(0.81, abs=0.01)


def test_put_call_parity():
    """C - P = S - K * exp(-rT) must hold exactly, for every set of inputs.

    Parity follows from a no-arbitrage argument, not from the Black-Scholes
    model, so it is a genuinely independent check on the two formulas: an
    algebra error in either one will almost certainly break it.
    """
    for S in (80.0, 100.0, 130.0):
        for K in (90.0, 100.0, 110.0):
            for T in (0.05, 0.5, 2.0):
                for sigma in (0.10, 0.35, 0.90):
                    r = 0.04
                    call = bs_price(S, K, T, r, sigma, "call")
                    put = bs_price(S, K, T, r, sigma, "put")
                    expected = S - K * math.exp(-r * T)
                    assert call - put == pytest.approx(expected, abs=1e-10)


def test_price_increases_with_volatility():
    """Price must be strictly increasing in sigma.

    This is the property the implied volatility solver depends on. Because the
    mapping sigma -> price is monotone, there is exactly one volatility that
    reproduces a given price, and bisection on a bracketing interval is
    guaranteed to find it. If this test ever fails, the bisection fallback in
    implied_vol.py is no longer safe.
    """
    for option_type in ("call", "put"):
        prices = [
            bs_price(100.0, 100.0, 1.0, 0.03, sigma, option_type)
            for sigma in [0.01, 0.05, 0.10, 0.25, 0.50, 1.00, 2.00, 3.00]
        ]
        for earlier, later in zip(prices, prices[1:]):
            assert later > earlier


def test_deep_out_of_the_money_is_nearly_worthless():
    call = bs_price(S=100.0, K=1000.0, T=0.1, r=0.03, sigma=0.2, option_type="call")
    put = bs_price(S=100.0, K=10.0, T=0.1, r=0.03, sigma=0.2, option_type="put")
    assert call == pytest.approx(0.0, abs=1e-8)
    assert put == pytest.approx(0.0, abs=1e-8)


def test_deep_in_the_money_call_approaches_discounted_intrinsic():
    """A call so far in the money it is certain to be exercised is worth
    S - K*exp(-rT): you will pay the strike at expiry, so you owe its
    present value today."""
    S, K, T, r = 1000.0, 10.0, 1.0, 0.03
    price = bs_price(S, K, T, r, 0.2, "call")
    assert price == pytest.approx(S - K * math.exp(-r * T), abs=1e-6)


def test_expired_option_is_worth_intrinsic_value():
    assert bs_price(120.0, 100.0, 0.0, 0.05, 0.3, "call") == pytest.approx(20.0)
    assert bs_price(80.0, 100.0, 0.0, 0.05, 0.3, "call") == pytest.approx(0.0)
    assert bs_price(80.0, 100.0, 0.0, 0.05, 0.3, "put") == pytest.approx(20.0)
    assert bs_price(120.0, 100.0, 0.0, 0.05, 0.3, "put") == pytest.approx(0.0)


def test_zero_volatility_discounts_the_strike():
    """With no uncertainty the payoff is known, so the call is worth
    max(S - K*exp(-rT), 0) -- the strike is discounted, the spot is not."""
    S, K, T, r = 100.0, 90.0, 2.0, 0.05
    expected = S - K * math.exp(-r * T)
    assert bs_price(S, K, T, r, 0.0, "call") == pytest.approx(expected)
    assert bs_price(S, K, T, r, 0.0, "put") == pytest.approx(0.0)


def test_price_stays_within_no_arbitrage_bounds():
    """max(S - K*exp(-rT), 0) <= C <= S, for any volatility.

    The IV solver checks these same bounds before iterating, so they need to
    hold for the pricer too.
    """
    S, K, T, r = 100.0, 105.0, 0.75, 0.04
    for sigma in (0.01, 0.2, 1.0, 3.0):
        call = bs_price(S, K, T, r, sigma, "call")
        lower = max(S - K * math.exp(-r * T), 0.0)
        assert lower <= call <= S


def test_accepts_ibkr_style_option_rights():
    """IBKR reports the option right as 'C' or 'P', so the pricer accepts both."""
    call_long = bs_price(100.0, 100.0, 1.0, 0.03, 0.2, "call")
    call_short = bs_price(100.0, 100.0, 1.0, 0.03, 0.2, "C")
    assert call_long == call_short


def test_forward_price():
    assert forward_price(S=100.0, T=1.0, r=0.05) == pytest.approx(100.0 * math.exp(0.05))
    assert forward_price(S=100.0, T=0.0, r=0.05) == pytest.approx(100.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(S=-1.0, K=100.0, T=1.0, r=0.03, sigma=0.2, option_type="call"),
        dict(S=100.0, K=0.0, T=1.0, r=0.03, sigma=0.2, option_type="call"),
        dict(S=100.0, K=100.0, T=-1.0, r=0.03, sigma=0.2, option_type="call"),
        dict(S=100.0, K=100.0, T=1.0, r=0.03, sigma=-0.2, option_type="call"),
        dict(S=100.0, K=100.0, T=1.0, r=0.03, sigma=0.2, option_type="banana"),
    ],
)
def test_invalid_inputs_raise(kwargs):
    """Bad inputs fail immediately rather than producing a silent NaN."""
    with pytest.raises(ValueError):
        bs_price(**kwargs)


def test_returns_plain_floats():
    """The pricer must return a builtin float in every branch.

    scipy returns numpy scalars, and the degenerate branches return plain
    floats, so without an explicit cast the return type would depend on the
    inputs. Downstream code (and CSV output) is simpler with one type.
    """
    normal = bs_price(100.0, 100.0, 1.0, 0.03, 0.2, "call")
    expired = bs_price(120.0, 100.0, 0.0, 0.03, 0.2, "call")
    zero_vol = bs_price(100.0, 90.0, 1.0, 0.03, 0.0, "call")
    for value in (normal, expired, zero_vol):
        assert type(value) is float
