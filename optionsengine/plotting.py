"""
Plotly charts for the IV surface: the full 3D surface, individual smiles,
and the ATM term structure. Takes a surface.py grid as input. Never touches
yfinance and never interpolates anything itself.
"""
import numpy as np
import plotly.graph_objects as go


def plot_surface(surface, title="Implied Volatility Surface"):
    """3D surface: log-moneyness x time to expiry x implied vol.

    Grid lines are evenly spaced in value on both axes, not tied to where
    the real expiries happen to fall -- years_to_expiry isn't evenly spaced
    in the data, but the grid drawn over the surface still is.
    """
    x_min, x_max = surface.columns.min(), surface.columns.max()
    y_min, y_max = surface.index.min(), surface.index.max()
    z_min = np.floor(np.nanmin(surface.values) / 0.05) * 0.05
    z_max = np.ceil(np.nanmax(surface.values) / 0.05) * 0.05
    grid_line_color = "rgba(211, 211, 211, 0.95)"  # lightgrey, mostly opaque
    fig = go.Figure(go.Surface(
        x=surface.columns, y=surface.index, z=surface.values,
        colorscale="Viridis",
        contours=dict(
            # Always 20 mesh lines regardless of range -- separate from the
            # axis tick steps below, which stay fixed at 0.05 / 0.1.
            x=dict(show=True, color=grid_line_color, width=1,
                   start=x_min, end=x_max, size=(x_max - x_min) / 20),
            y=dict(show=True, color=grid_line_color, width=1,
                   start=y_min, end=y_max, size=(y_max - y_min) / 20),
        ),
    ))
    fig.update_layout(
        title=title,
        scene=dict(
            xaxis_title="log-moneyness ln(K/F)",
            yaxis_title="years to expiry",
            zaxis_title="implied vol",
            xaxis=dict(range=[-0.2, 0.2], dtick=0.05),
            yaxis=dict(dtick=0.1),
            zaxis=dict(range=[z_min, z_max], dtick=0.05),
            aspectmode="cube",  # equal visual proportions, not scaled to raw data ranges
        ),
    )
    return fig


def plot_smiles(surface, years_to_expiry=None, title="Volatility Smiles"):
    """One line per expiry: implied vol against log-moneyness.

    years_to_expiry picks which rows to plot, matched exactly against the
    surface's index. None plots every expiry, which gets crowded fast for
    a full config window.
    """
    rows = surface.index if years_to_expiry is None else years_to_expiry
    fig = go.Figure()
    for years in rows:
        fig.add_trace(go.Scatter(x=surface.columns, y=surface.loc[years],
                                  mode="lines", name=f"{years:.3f}y"))
    fig.update_layout(title=title, xaxis_title="log-moneyness ln(K/F)",
                       yaxis_title="implied vol")
    return fig


def plot_term_structure(surface, title="ATM Term Structure"):
    """ATM implied vol against time to expiry.

    Uses whichever grid column sits closest to log-moneyness zero -- the
    default grid lands exactly on zero, but a custom grid might not.
    """
    atm_column = surface.columns[np.argmin(np.abs(surface.columns))]
    fig = go.Figure(go.Scatter(x=surface.index, y=surface[atm_column], mode="lines+markers"))
    fig.update_layout(title=title, xaxis_title="years to expiry", yaxis_title="ATM implied vol")
    return fig
