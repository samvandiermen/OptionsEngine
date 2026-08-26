"""Tests for surface.py: log-moneyness and the per-expiry interpolated grid.

Builds small synthetic quotes rather than pulling live data -- these are
pure functions, so no network is needed.
"""
import math
import numpy as np
import pandas as pd
import pytest
from optionsengine.surface import add_log_moneyness, build_surface


def test_add_log_moneyness():
    quotes = pd.DataFrame({"strike": [90.0, 100.0, 110.0], "forward": [100.0, 100.0, 100.0]})
    result = add_log_moneyness(quotes)
    assert result["log_moneyness"].iloc[0] == pytest.approx(math.log(0.9))
    assert result["log_moneyness"].iloc[1] == pytest.approx(0.0)
    assert result["log_moneyness"].iloc[2] == pytest.approx(math.log(1.1))


def test_build_surface_has_one_row_per_expiry_sorted_by_years():
    grid = np.linspace(-0.1, 0.1, 5)
    quotes = pd.DataFrame({
        "years_to_expiry": [0.5, 0.5, 0.5, 0.1, 0.1, 0.1],
        "log_moneyness": [-0.15, 0.0, 0.15, -0.15, 0.0, 0.15],
        "iv": [0.22, 0.20, 0.23, 0.30, 0.25, 0.32],
    })
    surface = build_surface(quotes, iv_column="iv", log_moneyness_grid=grid)
    assert list(surface.index) == [0.1, 0.5]
    assert list(surface.columns) == list(grid)


def test_build_surface_passes_through_the_input_points():
    grid = np.array([-0.1, 0.0, 0.1])
    quotes = pd.DataFrame({
        "years_to_expiry": [1.0, 1.0, 1.0],
        "log_moneyness": [-0.1, 0.0, 0.1],
        "iv": [0.25, 0.20, 0.22],
    })
    surface = build_surface(quotes, iv_column="iv", log_moneyness_grid=grid)
    assert surface.loc[1.0].tolist() == pytest.approx([0.25, 0.20, 0.22])


def test_build_surface_does_not_extrapolate_beyond_the_smile():
    grid = np.array([-0.2, 0.0, 0.2])
    quotes = pd.DataFrame({
        "years_to_expiry": [1.0, 1.0, 1.0],
        "log_moneyness": [-0.1, 0.0, 0.1],
        "iv": [0.25, 0.20, 0.22],
    })
    surface = build_surface(quotes, iv_column="iv", log_moneyness_grid=grid)
    assert math.isnan(surface.loc[1.0, -0.2])
    assert math.isnan(surface.loc[1.0, 0.2])
    assert not math.isnan(surface.loc[1.0, 0.0])


def test_build_surface_skips_expiries_with_fewer_than_two_points():
    grid = np.array([0.0])
    quotes = pd.DataFrame({
        "years_to_expiry": [1.0, 2.0, 2.0],
        "log_moneyness": [0.0, -0.05, 0.05],
        "iv": [0.20, 0.21, 0.19],
    })
    surface = build_surface(quotes, iv_column="iv", log_moneyness_grid=grid)
    assert list(surface.index) == [2.0]


def test_build_surface_drops_missing_iv_before_interpolating():
    grid = np.array([0.0])
    quotes = pd.DataFrame({
        "years_to_expiry": [1.0, 1.0, 1.0],
        "log_moneyness": [-0.1, 0.0, 0.1],
        "iv": [0.25, float("nan"), 0.22],
    })
    # the NaN row is dropped, leaving two usable points -- still interpolates
    surface = build_surface(quotes, iv_column="iv", log_moneyness_grid=grid)
    assert not math.isnan(surface.loc[1.0, 0.0])


def test_build_surface_drops_duplicate_log_moneyness():
    grid = np.array([0.0])
    quotes = pd.DataFrame({
        "years_to_expiry": [1.0, 1.0, 1.0],
        "log_moneyness": [-0.1, 0.0, 0.0],
        "iv": [0.25, 0.20, 0.21],
    })
    surface = build_surface(quotes, iv_column="iv", log_moneyness_grid=grid)
    assert not math.isnan(surface.loc[1.0, 0.0])
