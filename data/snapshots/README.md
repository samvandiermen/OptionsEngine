# Option chain snapshots

Each CSV here is one moment of an option chain: every contract we asked for, its bid and
ask, the price of the underlying at that same moment, and a timestamp.

They are written by `scripts/fetch_snapshot.py`. Which index it fetches is set in
`config.py`, and the file name records it.

Files named `sample_*.csv` are committed to git, so the notebooks run for someone with no
internet access at all. Everything else stays on your machine.

The prices are delayed by 15 minutes.
