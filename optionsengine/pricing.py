"""
Black-Scholes pricing for European options.

This is the foundation of the whole project: the Greeks (greeks.py) are the
derivatives of the price function defined here, and the implied volatility
solver (implied_vol.py) runs this function backwards to find the volatility
that reproduces an observed market price.

Model assumptions (see README for full discussion):
    - The underlying follows geometric Brownian motion with constant
      volatility and constant risk-free rate.
    - No dividends are paid over the life of the option.
    - Options are European-style (exercisable only at expiry).
    - Markets are frictionless (no transaction costs, unlimited
      borrowing/lending at the risk-free rate, no arbitrage).

These functions price one option at a time. Handling many at once would run
faster, but we only ever price a few hundred, so readable formulas win.
"""

import math
from scipy.stats import norm

# Option types we accept.
CALL = "call"
PUT = "put"


def check_inputs(S, K, T, sigma, option_type=None):
    """Check the inputs make sense, and raise a clear error if they do not.

    Shared with greeks.py. Better to stop here than let a bad number become a
    wrong answer somewhere deep in the implied volatility solver.
    """
    if S <= 0:
        raise ValueError(f"Spot price S must be positive, got {S}")
    if K <= 0:
        raise ValueError(f"Strike K must be positive, got {K}")
    if T < 0:
        raise ValueError(f"Time to expiry T cannot be negative, got {T}")
    if sigma < 0:
        raise ValueError(f"Volatility sigma cannot be negative, got {sigma}")
    if option_type is not None and option_type not in (CALL, PUT):
        raise ValueError(f"option_type must be '{CALL}' or '{PUT}', got {option_type!r}")


def normalise_option_type(option_type):
    """Turn any spelling of call or put into one standard form.

    IBKR writes 'C' and 'P', people write 'call' and 'put'. Accept both, in
    any capitalisation.
    """
    text = str(option_type).strip().lower()
    if text in ("c", "call"):
        return CALL
    if text in ("p", "put"):
        return PUT
    raise ValueError(f"Unrecognised option type: {option_type!r}")


def d1_d2(S, K, T, r, sigma):
    """Compute the d1 and d2 terms of the Black-Scholes formula.

        d1 = [ln(S/K) + (r + sigma^2 / 2) * T] / (sigma * sqrt(T))
        d2 = d1 - sigma * sqrt(T)

    Needs T and sigma above zero. bs_price handles those cases before calling this.

    Parameters
    ----------
    S : spot price of the underlying
    K : strike price
    T : time to expiry, in years
    r : continuously-compounded risk-free rate (annualized)
    sigma : annualized volatility of the underlying's returns

    Returns
    -------
    float
    """
    d1 = (math.log(S / K) + T * (r + sigma**2 / 2)) / (sigma * math.sqrt(T))
    d2 = d1 - (sigma * math.sqrt(T))
    return d1, d2


def bs_price(S, K, T, r, sigma, option_type):
    """Black-Scholes price of a European option.

        C = S * N(d1) - K * exp(-rT) * N(d2)
        P = K * exp(-rT) * N(-d2) - S * N(-d1)

    N is the standard normal CDF, and d1, d2 come from d1_d2().

    Parameters
    ----------
    S : float
        Current price of the underlying, for example the level of an index.
    K : float
        Strike price.
    T : float
        Time to expiry in years (0.25 = three months).
    r : float
        Continuously compounded annual risk-free rate (0.04 = 4%).
    sigma : float
        Annualised volatility (0.20 = 20%).
    option_type : str
        'call' or 'put' (also accepts 'C' / 'P').

    Returns
    -------
    float
        The option's theoretical value in the same currency units as S and K.

    Examples
    --------
    >>> round(bs_price(100, 100, 1.0, 0.05, 0.2, "call"), 4)
    10.4506
    """
    option_type = normalise_option_type(option_type)
    check_inputs(S, K, T, sigma, option_type)

    pv_K = K * math.exp(-r * T)

    # Case 1: the option has expired and is worth its intrinsic value now.
    if T == 0:
        return max(S - K, 0.0) if option_type == CALL else max(K - S, 0.0)

    # Case 2: no volatility means no uncertainty, so the payoff is
    # already known. Note this is max(S - K*exp(-r*T), 0), not max(S - K, 0):
    # the strike is discounted because you do not pay it until expiry.
    if sigma == 0:
        if option_type == CALL:
            return max(S - pv_K, 0.0)
        return max(pv_K - S, 0.0)

    # The normal case.
    d1, d2 = d1_d2(S, K, T, r, sigma)

    # float() because scipy returns its own number type, while the cases
    # above return ordinary Python numbers. Keep one type everywhere.
    if option_type == CALL:
        return float(S * norm.cdf(d1) - pv_K * norm.cdf(d2))

    return float(pv_K * norm.cdf(-d2) - S * norm.cdf(-d1))


def forward_price(S, T, r):
    """The forward price of the underlying, F = S * exp(r * T).

    With no dividends, just today's price grown at the risk-free rate. The
    surface uses it as the centre of the smile: at the money means K = F.
    """
    return S * math.exp(r * T)
