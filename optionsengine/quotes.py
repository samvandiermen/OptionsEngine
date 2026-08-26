"""
Quote hygiene: turn the raw snapshot into quotes worth solving implied
volatility from. Adds years to expiry and the forward price, drops bad
quotes, then keeps OTM only -- calls above the forward, puts below.
"""
import re
import pandas as pd
from optionsengine.pricing import forward_price
from optionsengine.time_utils import years_to_expiry, resolve_settlement_hour

ROOT_PATTERN = re.compile(r"^([A-Z]+)\d")

# A spread wider than this fraction of the mid price is too wide to trust.
MAX_SPREAD_FRACTION = 0.5


def add_years_to_expiry(quotes, weekly_root, monthly_root, am_hour, pm_hour):
    """Add a years_to_expiry column, using each row's own settlement time."""
    def _years(row):
        root = ROOT_PATTERN.match(row["contract_symbol"]).group(1)
        hour = resolve_settlement_hour(root, weekly_root, monthly_root, am_hour, pm_hour)
        return years_to_expiry(row["asof"], row["expiry"], hour)

    quotes = quotes.copy()
    quotes["years_to_expiry"] = quotes.apply(_years, axis=1)
    return quotes


def add_forward(quotes, r):
    """Add a forward column: F = S * exp(rT). Needs years_to_expiry already added."""
    quotes = quotes.copy()
    quotes["forward"] = quotes.apply(
        lambda row: forward_price(row["underlying_price"], row["years_to_expiry"], r), axis=1
    )
    return quotes


def add_mid_price(quotes):
    """Add a mid column: (bid + ask) / 2, never last traded."""
    quotes = quotes.copy()
    quotes["mid"] = (quotes["bid"] + quotes["ask"]) / 2
    return quotes


def drop_bad_quotes(quotes, max_spread_fraction=MAX_SPREAD_FRACTION):
    """Drop missing, zero-bid, crossed/locked, or too-wide-spread quotes."""
    quotes = quotes.dropna(subset=["bid", "ask"])
    quotes = quotes[quotes["bid"] > 0]
    quotes = quotes[quotes["ask"] > quotes["bid"]]  # drops crossed and locked markets
    mid = (quotes["bid"] + quotes["ask"]) / 2
    spread_fraction = (quotes["ask"] - quotes["bid"]) / mid
    return quotes[spread_fraction <= max_spread_fraction]


def select_otm(quotes):
    """Keep calls at or above the forward, puts at or below. Needs forward already added."""
    calls = quotes[(quotes["right"] == "C") & (quotes["strike"] >= quotes["forward"])]
    puts = quotes[(quotes["right"] == "P") & (quotes["strike"] <= quotes["forward"])]
    return pd.concat([calls, puts])


def clean_quotes(quotes, weekly_root, monthly_root, am_hour, pm_hour, r,
                  max_spread_fraction=MAX_SPREAD_FRACTION):
    """Run the full pipeline: drop bad quotes, add years/forward/mid, keep OTM only."""
    quotes = drop_bad_quotes(quotes, max_spread_fraction)
    quotes = add_years_to_expiry(quotes, weekly_root, monthly_root, am_hour, pm_hour)
    quotes = add_forward(quotes, r)
    quotes = add_mid_price(quotes)
    return select_otm(quotes)
