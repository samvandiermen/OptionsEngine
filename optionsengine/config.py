"""Settings for the live data pipeline: underlying, risk-free rate, chain window, pacing."""

# Risk-free rate, constant, not fetched live.
r = 0.04

# Which underlying is active. Change this to switch underlying.
ACTIVE_SYMBOL = "SPX"

# Chain window: how far from the money and how far out in time to pull.
MONEYNESS_BOUNDS = (0.80, 1.20)  # K / F
EXPIRY_YEARS_BOUNDS = (7 / 365, 1.0)  # one week to one year

# Seconds between yfinance requests, to stay under Yahoo's rate limit.
PACING_SECONDS = 0.1

# Settlement times, hours after midnight ET. Same for every underlying.
AM_SETTLEMENT_HOUR = 9.5  # monthly/LEAPS root
PM_SETTLEMENT_HOUR = 16.0  # weekly root


class UnderlyingConfig:
    """One underlying's Yahoo ticker and its two contractSymbol roots.

    yahoo_ticker    Yahoo ticker, e.g. '^SPX'
    weekly_root     PM-settled weekly root, e.g. 'SPXW'
    monthly_root    AM-settled monthly root, e.g. 'SPX'
    exchange_tz     zoneinfo name of the exchange, e.g. 'America/New_York'
    """

    def __init__(self, yahoo_ticker, weekly_root, monthly_root, exchange_tz):
        self.yahoo_ticker = yahoo_ticker
        self.weekly_root = weekly_root
        self.monthly_root = monthly_root
        self.exchange_tz = exchange_tz


# One row per supported underlying.
UNDERLYINGS = {
    "SPX": UnderlyingConfig(yahoo_ticker="^SPX", weekly_root="SPXW", monthly_root="SPX",
                             exchange_tz="America/New_York"),
}

# The active underlying's config.
ACTIVE = UNDERLYINGS[ACTIVE_SYMBOL]
