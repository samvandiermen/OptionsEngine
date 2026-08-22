"""Implied volatility: the volatility that makes the model price match the market.

There is no formula for it. Black-Scholes turns volatility into a price, and that
cannot be rearranged, so we have to search for the volatility that fits.

Two methods, tried in order:

    Newton-Raphson   fast, usually three or four steps, but needs vega and can
                     wander outside the range we are searching
    bisection        slow but cannot fail, used whenever Newton gives up

Bisection is safe because price always rises with volatility, which is pinned by
a test in test_black_scholes.py. One price means exactly one volatility, so
repeatedly halving a range that contains it must close in on the answer.

Every result records which method solved it. That is what lets us report how
often the fallback was needed and see where those quotes sit on the surface.
"""

import math
from typing import NamedTuple
from optionsengine.black_scholes import bs_price, check_inputs, normalise_option_type
from optionsengine.greeks import vega

# The range of volatilities we search: 0.01% to 500% a year. Anything outside
# this is not a real quote.
SIGMA_MIN = 1e-4
SIGMA_MAX = 5.0

# Close enough, in price units. Prices are around 1 to 1000, so this is far
# tighter than any real quote.
PRICE_TOL = 1e-8

# How much the price has to move with volatility before we trust an answer,
# as a fraction of the underlying price. Vega scales with S, so a plain number
# would mean something different for a 100 stock and a 5000 index.
#
# Below this the price is flat in volatility: a rounding-level change in the
# quote swings the answer wildly, so there is no volatility to recover. Deep
# in-the-money options close to expiry are the usual case.
MIN_VEGA_FRACTION = 1e-6

MAX_NEWTON = 50
MAX_BISECTION = 200


class IVResult(NamedTuple):
    """The answer, plus how we got there.

    iv          the implied volatility, or NaN if there is no answer
    method      'newton', 'bisection', or 'failed'
    iterations  how many times we had to price the option
    reason      why it failed, empty if it did not
    """

    iv: float
    method: str
    iterations: int
    reason: str


def _failed(reason, iterations=0):
    return IVResult(float("nan"), "failed", iterations, reason)


def _initial_guess(price, S, T):
    """Brenner-Subrahmanyam: sigma is roughly sqrt(2*pi/T) * price / S.

    Exact for an at-the-money option and rough everywhere else, which is all we
    need from a starting point. Better than hard-coding 0.20.

    Kept at 5% or above. A tiny starting guess has almost no vega, so Newton
    would stall on its first step and hand over for no good reason.
    """
    guess = math.sqrt(2 * math.pi / T) * price / S
    return min(max(guess, 0.05), SIGMA_MAX)


def _newton(price, S, K, T, r, option_type, guess):
    """Follow the slope to the answer.

    Each step assumes the price curve is a straight line with slope vega, and
    jumps to where that line would hit the target:

        sigma <- sigma - (model price - market price) / vega

    Returns (sigma, iterations) if it worked, or (None, iterations) if it gave
    up, in which case bisection takes over.
    """
    sigma = guess

    for i in range(1, MAX_NEWTON + 1):
        gap = bs_price(S, K, T, r, sigma, option_type) - price
        if abs(gap) < PRICE_TOL:
            return sigma, i

        slope = vega(S, K, T, r, sigma)
        if slope < MIN_VEGA_FRACTION * S:
            return None, i

        sigma = sigma - gap / slope
        if not math.isfinite(sigma) or not SIGMA_MIN <= sigma <= SIGMA_MAX:
            return None, i

    return None, MAX_NEWTON


def _bisect(price, S, K, T, r, option_type):
    """Halve the range until it closes on the answer.

    We already know the answer lies between SIGMA_MIN and SIGMA_MAX, because the
    caller checked that the market price sits between the prices at those two
    volatilities. Price rises with volatility, so comparing the middle of the
    range to the target tells us which half to keep.

    Slow compared to Newton, but it cannot fail or run away.
    """
    lo, hi = SIGMA_MIN, SIGMA_MAX

    for i in range(1, MAX_BISECTION + 1):
        mid = 0.5 * (lo + hi)
        gap = bs_price(S, K, T, r, mid, option_type) - price

        if abs(gap) < PRICE_TOL or hi - lo < 1e-12:
            return mid, i

        if gap < 0:
            lo = mid  # model price too low, so volatility must be higher
        else:
            hi = mid

    return 0.5 * (lo + hi), MAX_BISECTION


def implied_volatility(price, S, K, T, r, option_type):
    """Find the volatility that reproduces an observed option price.

    Parameters
    ----------
    price : float
        The option's market price.
    S, K, T, r : float
        Underlying price, strike, years to expiry, risk-free rate.
    option_type : str
        'call' or 'put' (also accepts 'C' / 'P').

    Returns
    -------
    IVResult
        With iv set to NaN if no volatility in the searched range fits.

    Bad market data gives a failed result rather than an exception, because a
    junk quote is something to filter out, not a bug. Bad S, K or T still raise:
    those come from us, not the market.

    Examples
    --------
    >>> from optionsengine.black_scholes import bs_price
    >>> market = bs_price(100, 105, 0.5, 0.03, 0.28, "call")
    >>> result = implied_volatility(market, 100, 105, 0.5, 0.03, "call")
    >>> round(result.iv, 6)
    0.28
    """
    option_type = normalise_option_type(option_type)
    check_inputs(S, K, T, 0.0, option_type)
    if T <= 0:
        raise ValueError(f"T must be positive to solve for volatility, got {T}")

    if not math.isfinite(price) or price <= 0:
        return _failed("no usable price")

    # The prices at the two ends of our search range. Because price rises with
    # volatility, anything outside them cannot be matched by any volatility.
    low_price = bs_price(S, K, T, r, SIGMA_MIN, option_type)
    high_price = bs_price(S, K, T, r, SIGMA_MAX, option_type)

    if price < low_price:
        return _failed("price below the no-arbitrage minimum")
    if price > high_price:
        return _failed(f"price implies volatility above {SIGMA_MAX:.0%}")

    guess = _initial_guess(price, S, T)
    sigma, used = _newton(price, S, K, T, r, option_type, guess)
    method = "newton"

    if sigma is None:
        extra, more = _bisect(price, S, K, T, r, option_type)
        sigma, used, method = extra, used + more, "bisection"

    # Matching the price is not enough. Where the price hardly moves with
    # volatility, many different volatilities match it equally well and the
    # one we happened to land on means nothing, so say so instead.
    if vega(S, K, T, r, sigma) < MIN_VEGA_FRACTION * S:
        return _failed("price barely moves with volatility here", used)

    return IVResult(sigma, method, used, "")
