"""CLI: pull a fresh snapshot, solve IV, redraw the surface, wait for Enter,
repeat. Writes figures/surface.html each round; open that file once and
refresh it in the browser to see the latest pass.
"""
import os
import sys
import time

# Add the repo root to sys.path so optionsengine can be imported.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from optionsengine import config
from optionsengine.yahoo.snapshot import fetch_snapshot
from optionsengine.quotes import clean_quotes
from optionsengine.validation import add_our_iv
from optionsengine.surface import add_log_moneyness, build_surface
from optionsengine.plotting import plot_surface

OUTPUT_PATH = os.path.join(REPO_ROOT, "figures", "surface.html")
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

min_years, max_years = config.EXPIRY_YEARS_BOUNDS
moneyness_min, moneyness_max = config.MONEYNESS_BOUNDS

while True:
    start = time.time()

    raw = fetch_snapshot(
        underlying=config.ACTIVE,
        r=config.r,
        min_years=min_years,
        max_years=max_years,
        moneyness_min=moneyness_min,
        moneyness_max=moneyness_max,
        pacing_seconds=config.PACING_SECONDS,
    )
    cleaned = clean_quotes(raw, config.ACTIVE.weekly_root, config.ACTIVE.monthly_root,
                            config.AM_SETTLEMENT_HOUR, config.PM_SETTLEMENT_HOUR, config.r)
    solved = add_our_iv(cleaned, config.r)
    solved = add_log_moneyness(solved)

    surface = build_surface(solved, iv_column="iv_ours")
    fig = plot_surface(surface, title=f"{config.ACTIVE_SYMBOL} Implied Volatility Surface")
    fig.write_html(OUTPUT_PATH)

    elapsed = time.time() - start
    print(f"Refreshed {OUTPUT_PATH} ({len(solved)} quotes) in {elapsed:.1f}s", flush=True)
    input("Press Enter to refresh again (Ctrl+C to stop)... ")
