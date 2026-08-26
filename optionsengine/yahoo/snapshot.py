"""
Pull the yfinance option chain within the configured window and shape it into
one flat DataFrame of raw quotes.

Records raw values and calculates nothing. Mid price, hygiene and implied
volatility all happen later, on the table this returns.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import time
import pandas as pd
import yfinance as yf
from optionsengine.yahoo.chain import select_expiries, select_root, select_moneyness

RAW_COLUMNS = [
    "expiry", "strike", "right", "contract_symbol", "bid", "ask", "last",
    "volume", "open_interest", "implied_vol_yahoo", "underlying_price", "asof",
]


def fetch_snapshot(underlying, r, min_years, max_years, moneyness_min, moneyness_max,
                    pacing_seconds):
    """Pull one chain snapshot for the given underlying and return a raw DataFrame.

    One row per contract kept: expiry, strike, right, the raw contract symbol,
    bid, ask, last, volume, open interest, Yahoo's own implied vol, the
    underlying price, and asof. Nothing here is a fair price yet. quotes.py
    decides that later.
    """
    ticker = yf.Ticker(underlying.yahoo_ticker)
    info = ticker.info
    spot = info["regularMarketPrice"]
    asof = datetime.fromtimestamp(info["regularMarketTime"], tz=ZoneInfo(underlying.exchange_tz))

    expiries = select_expiries(ticker.options, asof, min_years, max_years)

    rows = []
    for i, expiry in enumerate(expiries):
        if i > 0:
            time.sleep(pacing_seconds)  # stay under Yahoo's rate limit

        chain = ticker.option_chain(expiry)
        years = (datetime.fromisoformat(expiry).date() - asof.date()).days / 365

        for right, contracts in (("C", chain.calls), ("P", chain.puts)):
            contracts = select_root(contracts, underlying.weekly_root, underlying.monthly_root)
            contracts = select_moneyness(contracts, spot, r, years, moneyness_min, moneyness_max)
            for _, row in contracts.iterrows():
                rows.append({
                    "expiry": expiry,
                    "strike": row["strike"],
                    "right": right,
                    "contract_symbol": row["contractSymbol"],
                    "bid": row["bid"],
                    "ask": row["ask"],
                    "last": row["lastPrice"],
                    "volume": row["volume"],
                    "open_interest": row["openInterest"],
                    "implied_vol_yahoo": row["impliedVolatility"],
                    "underlying_price": spot,
                    "asof": asof,
                })

    return pd.DataFrame(rows, columns=RAW_COLUMNS)
