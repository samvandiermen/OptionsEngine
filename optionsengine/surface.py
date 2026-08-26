"""
Build an IV surface grid from cleaned, already-solved quotes.

Interpolates each expiry's own smile separately (log-moneyness -> IV), then
stacks the smiles across expiries. A vol surface is a term structure of
smiles, not one blob of scattered points, so each smile is only ever built
from its own strikes.
"""
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator

# The shared grid every smile is evaluated at, so expiries line up into one
# surface. Matches the chain window's moneyness bounds (ln 0.80, ln 1.20).
DEFAULT_LOG_MONEYNESS_GRID = np.linspace(-0.22, 0.18, 41)


def add_log_moneyness(quotes):
    """Add a log_moneyness column: ln(K / F). Needs forward already added."""
    quotes = quotes.copy()
    quotes["log_moneyness"] = np.log(quotes["strike"] / quotes["forward"])
    return quotes


def build_surface(quotes, iv_column, log_moneyness_grid=DEFAULT_LOG_MONEYNESS_GRID):
    """Interpolate each expiry's smile onto a shared log-moneyness grid.

    One row per expiry, indexed by years_to_expiry and sorted; one column
    per point in log_moneyness_grid. A grid point outside an expiry's own
    strike range comes back NaN. We never guess a smile shape past what
    that expiry's own quotes cover. Expiries with fewer than two usable
    quotes are skipped, since there's nothing to interpolate from.
    """
    rows = {}
    for years, group in quotes.groupby("years_to_expiry"):
        group = group.dropna(subset=[iv_column]).drop_duplicates(subset="log_moneyness")
        group = group.sort_values("log_moneyness")
        if len(group) < 2:
            continue
        smile = PchipInterpolator(group["log_moneyness"], group[iv_column], extrapolate=False)
        rows[years] = smile(log_moneyness_grid)

    surface = pd.DataFrame(rows, index=log_moneyness_grid).T
    return surface.sort_index()
