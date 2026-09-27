"""
Which expiries and strikes are worth asking yfinance for.

Three pure functions, no network calls. snapshot.py does the fetching and calls
these to decide what to keep. This is kept separate from quotes.py on purpose.
This file controls what we request and keep at all. quotes.py later decides
what to trust as a fair price, once there is real bid/ask to judge by.
"""
import datetime
from optionsengine.pricing import forward_price


def select_expiries(available_expiries, asof, min_years, max_years):
    """Keep expiries whose time to expiry, counted from asof, falls in [min_years, max_years].

    Uses a rough whole-day count, not the precise ACT/365 AM/PM settlement
    convention that time_utils.py uses for pricing. Deciding whether an expiry
    is in the window does not need that precision. Only the IV solving does.
    """
    selected = []
    for expiry in available_expiries:
        expiry_date = datetime.date.fromisoformat(expiry)
        years = (expiry_date - asof.date()).days / 365
        if min_years <= years <= max_years:
            selected.append(expiry)
    return selected


def select_root(contracts, weekly_root, monthly_root):
    """Keep the weekly (PM-settled) contracts if that root is listed for this
    expiry, otherwise fall back to the monthly (AM-settled) root.

    Standard monthly dates list both roots for the same expiry date. Weekly is
    preferred. Monthly is the only choice once the weekly listing calendar runs out.
    """
    root = contracts["contractSymbol"].str.extract(r"^([A-Z]+)\d")[0]
    if (root == weekly_root).any():
        return contracts[root == weekly_root]
    return contracts[root == monthly_root]


def select_moneyness(contracts, spot, r, years, moneyness_min, moneyness_max):
    """Keep strikes within [moneyness_min, moneyness_max] of the forward price.

    This only bounds how far from the money we keep strikes, not which side is
    OTM. That split is quotes.py's job, once we have bid/ask to judge by.
    """
    forward = forward_price(spot, years, r)
    lo, hi = moneyness_min * forward, moneyness_max * forward
    return contracts[(contracts["strike"] >= lo) & (contracts["strike"] <= hi)]
