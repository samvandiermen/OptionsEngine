"""The five Greeks, in closed form.

Each one measures how the option price responds to a change in one input:

    delta   the underlying price
    gamma   the underlying price again, second derivative: how fast delta moves
    vega    volatility
    theta   time
    rho     the interest rate

These are the plain mathematical derivatives. Traders usually rescale them:
vega per 1% of volatility is vega / 100, theta per day is theta / 365.

Gamma and vega take no option type, because they are the same for calls and
puts. A call and a put with the same strike and expiry differ by a forward,
which is a straight line in S and has no volatility in it at all, so the
curvature and the volatility sensitivity have to match.
"""

import math
from scipy.stats import norm
from optionsengine.black_scholes import CALL, check_inputs, d1_d2, normalise_option_type


def _check(S, K, T, sigma, option_type=None):
    """Same checks as the pricer, plus T and sigma strictly above zero.

    The pricer allows T = 0 and sigma = 0 and returns the intrinsic value. The
    Greeks cannot: they are slopes, and at those points the slope is either
    infinite or undefined.
    """
    check_inputs(S, K, T, sigma, option_type)
    if T <= 0:
        raise ValueError(f"T must be positive for Greeks, got {T}")
    if sigma <= 0:
        raise ValueError(f"sigma must be positive for Greeks, got {sigma}")


def delta(S, K, T, r, sigma, option_type):
    """Change in option price per 1.00 change in the underlying.

        call:  N(d1)
        put:   N(d1) - 1

    Between 0 and 1 for a call, between -1 and 0 for a put.
    """
    option_type = normalise_option_type(option_type)
    _check(S, K, T, sigma, option_type)

    d1, _ = d1_d2(S, K, T, r, sigma)
    if option_type == CALL:
        return float(norm.cdf(d1))
    return float(norm.cdf(d1) - 1.0)


def gamma(S, K, T, r, sigma):
    """Change in delta per 1.00 change in the underlying.

        n(d1) / (S * sigma * sqrt(T))

    Always positive, and largest for options near the money.
    """
    _check(S, K, T, sigma)

    d1, _ = d1_d2(S, K, T, r, sigma)
    return float(norm.pdf(d1) / (S * sigma * math.sqrt(T)))


def vega(S, K, T, r, sigma):
    """Change in option price per 1.00 change in volatility.

        S * n(d1) * sqrt(T)

    Always positive. Divide by 100 for the change per 1% of volatility, which
    is how it is usually quoted.

    This is the number the implied volatility solver divides by, so where vega
    is near zero Newton-Raphson becomes unreliable and bisection takes over.
    """
    _check(S, K, T, sigma)

    d1, _ = d1_d2(S, K, T, r, sigma)
    return float(S * norm.pdf(d1) * math.sqrt(T))


def theta(S, K, T, r, sigma, option_type):
    """Change in option price per 1.00 year of time passing.

        call:  -S*n(d1)*sigma / (2*sqrt(T)) - r*K*exp(-rT)*N(d2)
        put:   -S*n(d1)*sigma / (2*sqrt(T)) + r*K*exp(-rT)*N(-d2)

    Usually negative: an option loses value as expiry approaches. Divide by
    365 for the change per calendar day.

    Note the sign convention. Theta is the derivative with respect to time
    passing, which is minus the derivative with respect to time remaining.
    """
    option_type = normalise_option_type(option_type)
    _check(S, K, T, sigma, option_type)

    d1, d2 = d1_d2(S, K, T, r, sigma)
    decay = -S * norm.pdf(d1) * sigma / (2 * math.sqrt(T))
    pv_K = K * math.exp(-r * T)

    if option_type == CALL:
        return float(decay - r * pv_K * norm.cdf(d2))
    return float(decay + r * pv_K * norm.cdf(-d2))


def rho(S, K, T, r, sigma, option_type):
    """Change in option price per 1.00 change in the interest rate.

        call:   K*T*exp(-rT)*N(d2)
        put:   -K*T*exp(-rT)*N(-d2)

    Positive for calls, negative for puts. Divide by 100 for the change per
    1% move in rates.
    """
    option_type = normalise_option_type(option_type)
    _check(S, K, T, sigma, option_type)

    _, d2 = d1_d2(S, K, T, r, sigma)
    pv_K_times_T = K * T * math.exp(-r * T)

    if option_type == CALL:
        return float(pv_K_times_T * norm.cdf(d2))
    return float(-pv_K_times_T * norm.cdf(-d2))
