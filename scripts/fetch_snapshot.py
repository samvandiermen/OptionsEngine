"""CLI: pull one option chain snapshot for the active index and write it to
data/snapshots/, named from the moment the data is actually from (asof).
"""
import os
import sys
import time
from zoneinfo import ZoneInfo

# Add the repo root to sys.path so optionsengine can be imported.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from optionsengine import config
from optionsengine.yahoo.snapshot import fetch_snapshot

min_years, max_years = config.EXPIRY_YEARS_BOUNDS
moneyness_min, moneyness_max = config.MONEYNESS_BOUNDS

start = time.time()

df = fetch_snapshot(
    index_config=config.ACTIVE,
    r=config.r,
    min_years=min_years,
    max_years=max_years,
    moneyness_min=moneyness_min,
    moneyness_max=moneyness_max,
    pacing_seconds=config.PACING_SECONDS,
)

elapsed = time.time() - start

asof = df["asof"].iloc[0]  # UTC, used as-is everywhere except the filename below
local_asof = asof.astimezone(ZoneInfo("Europe/Amsterdam"))
filename = f"{config.ACTIVE_SYMBOL.lower()}_{local_asof:%Y%m%d_%H%M}.csv"
path = os.path.join(REPO_ROOT, "data", "snapshots", filename)
df.to_csv(path, index=False)

print(f"Wrote {len(df)} rows to {path} in {elapsed:.1f}s")
