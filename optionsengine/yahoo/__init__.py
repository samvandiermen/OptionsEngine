"""Everything that talks to yfinance.

The only folder that knows yfinance exists. It fetches prices and hands back an
ordinary pandas table, so nothing else in the project needs a network call.
"""
