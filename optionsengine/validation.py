"""
Compare our implied volatility against Yahoo's own, on cleaned quotes.

This is not a clean test of the model alone. We don't know how Yahoo computes
its IV, and it may reflect an older price than the bid/ask sitting next to it
in the same response. So any gap we see could come from our model, from
Yahoo's method, or from that timing mismatch.
"""
import numpy as np
import pandas as pd
from optionsengine.implied_vol import implied_vol

# Moneyness (K/F) bucket edges: finer near the money, where the action is.
MONEYNESS_BUCKET_EDGES = [0.80, 0.90, 0.95, 1.00, 1.05, 1.10, 1.20]


def add_our_iv(quotes, r):
    """Solve our own implied vol for each row, from the mid price.

    Needs mid, underlying_price, strike, years_to_expiry, right already
    present -- quotes.py's clean_quotes produces all of these.
    """
    def _solve(row):
        return implied_vol(row["mid"], row["underlying_price"], row["strike"],
                            row["years_to_expiry"], r, row["right"])

    quotes = quotes.copy()
    results = quotes.apply(_solve, axis=1)
    quotes["iv_ours"] = [result.iv for result in results]
    quotes["iv_method"] = [result.method for result in results]
    return quotes


def add_error(quotes):
    """Add iv_error = our IV minus Yahoo's. NaN wherever our solve failed."""
    quotes = quotes.copy()
    quotes["iv_error"] = quotes["iv_ours"] - quotes["implied_vol_yahoo"]
    return quotes


def add_moneyness_bucket(quotes, bucket_edges=MONEYNESS_BUCKET_EDGES):
    """Add a moneyness_bucket column: strike / forward, grouped into bands."""
    quotes = quotes.copy()
    moneyness = quotes["strike"] / quotes["forward"]
    quotes["moneyness_bucket"] = pd.cut(moneyness, bucket_edges)
    return quotes


def _mae(error):
    return error.dropna().abs().mean()


def _rmse(error):
    return np.sqrt((error.dropna() ** 2).mean())


def mae_rmse(quotes):
    """Mean absolute error and root mean squared error of iv_error.

    Drops rows where our solve failed (iv_error is NaN) -- those are
    counted separately, not folded into the accuracy numbers.
    """
    return _mae(quotes["iv_error"]), _rmse(quotes["iv_error"])


def mae_rmse_by(quotes, group_column):
    """MAE and RMSE of iv_error, grouped by group_column.

    Works for moneyness_bucket or iv_method -- any column worth breaking
    the error down by.
    """
    grouped = quotes.groupby(group_column, observed=True)["iv_error"]
    return pd.DataFrame({"mae": grouped.apply(_mae), "rmse": grouped.apply(_rmse)})


def method_distribution(quotes):
    """Fraction of quotes solved by each method: newton, bisection, failed."""
    return quotes["iv_method"].value_counts(normalize=True)
