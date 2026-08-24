"""Implied volatility solver for European options under Black-Scholes.

There is no formula for it. Black-Scholes turns volatility into a price, and that
cannot be rearranged, so we have to search for the volatility that fits.

Two methods, tried in order:

    Newton-Raphson   converges quadratically near the root but can misbehave 
                    (overshoot to a negative sigma, or stall) when vega is very small. 
    bisection        converges linearly, but guaranteed to converge, used whenever Newton gives up.

Every result records which method solved it. That is what lets us report how
often the fallback was needed and see where those quotes sit on the surface.
"""

import math
from optionsengine.pricing import bs_price, check_inputs, normalise_option_type
from optionsengine.greeks import vega

# The range of volatilities we search: 0.01% to 500% a year.
SIGMA_BOUNDS = (1e-4, 5.0)

# The model price must land within this of the market price to call it solved.
PRICE_TOL = 1e-8

# Vega floor below which the price is too flat in volatility to trust, as a
# fraction of S so it scales with the underlying.
MIN_VEGA_FRACTION = 1e-6

# Maximum number of iterations: Newton is fast but can fail, bisection is slow but can't.
MAX_NEWTON = 50
MAX_BISECTION = 200


class IVResult:
    """The answer, plus how we got there.

    iv          the implied volatility, or NaN if there is no answer
    method      'newton', 'bisection', or 'failed'
    iterations  how many times we had to price the option
    reason      why it failed, empty if it did not
    """

    def __init__(self, iv, method, iterations, reason):
        self.iv = iv
        self.method = method
        self.iterations = iterations
        self.reason = reason


def _failed(reason, iterations=0):
    return IVResult(float("nan"), "failed", iterations, reason)


def _initial_guess(price, S, T):
    """Brenner-Subrahmanyam: sigma is roughly sqrt(2*pi/T) * price / S.

    Exact for an at-the-money option and rough everywhere else, which is all we
    need from a starting point. Better than hard-coding 0.20.

    Minimum sigma is 5%. Starting any lower puts vega near zero too, so
    Newton's first step is unreliable and it gives up immediately, falling
    back to bisection even when the real answer was easy to reach.
    """
    guess = math.sqrt(2 * math.pi / T) * price / S
    return min(max(guess, 0.05), SIGMA_BOUNDS[1])


def _newton(price, S, K, T, r, option_type, guess):
    """Attempt Newton-Raphson iteration.
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
        if not math.isfinite(sigma) or not SIGMA_BOUNDS[0] <= sigma <= SIGMA_BOUNDS[1]:
            return None, i

    return None, MAX_NEWTON


def _bisection(price, S, K, T, r, option_type):
    """Halve the range until it closes on the answer.

    We already know the answer lies within SIGMA_BOUNDS, because the caller
    checked that the market price sits between the prices at those two
    volatilities. Price rises with volatility, so comparing the middle of the
    range to the target tells us which half to keep.

    Slow compared to Newton, but it cannot fail or run away.
    """
    lo, hi = SIGMA_BOUNDS

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
    """Solve for Black-Scholes implied volatility given a market price.
    
    Tries Newton-Raphson first (fast, quadratic convergence); falls back
    to bisection (slower, but guaranteed given a valid bracket) if Newton
    gives up.

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

    Examples
    --------
    >>> from optionsengine.pricing import bs_price
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
    low_price = bs_price(S, K, T, r, SIGMA_BOUNDS[0], option_type)
    high_price = bs_price(S, K, T, r, SIGMA_BOUNDS[1], option_type)

    if price < low_price:
        return _failed("price below the no-arbitrage minimum")
    if price > high_price:
        return _failed(f"price implies volatility above {SIGMA_BOUNDS[1]:.0%}")

    guess = _initial_guess(price, S, T)
    sigma, iterations = _newton(price, S, K, T, r, option_type, guess)
    method = "newton"

    if sigma is None:
        sigma_extra, it_extra = _bisection(price, S, K, T, r, option_type)
        sigma, iterations, method = sigma_extra, iterations + it_extra, "bisection"

    # Matching the price is not enough. Where the price hardly moves with
    # volatility, many different volatilities match it equally well and the
    # one we happened to land on means nothing, so say so instead.
    if vega(S, K, T, r, sigma) < MIN_VEGA_FRACTION * S:
        return _failed("price barely moves with volatility here", iterations)

    return IVResult(sigma, method, iterations, "")
