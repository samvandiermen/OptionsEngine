"""Everything that talks to Interactive Brokers.

The only folder that knows IBKR exists. It fetches prices and hands back an
ordinary pandas table, so nothing else in the project needs a connection.
"""
