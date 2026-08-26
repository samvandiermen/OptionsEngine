"""Tests for plotting.py: that each chart is wired to the right data.

Not testing what the charts look like -- just that x/y/z end up mapped to
the right columns, since a swapped axis or wrong column is an easy mistake
that would look fine in code and wrong in the picture.
"""
import numpy as np
import pandas as pd
import pytest
from optionsengine.plotting import plot_surface, plot_smiles, plot_term_structure

SURFACE = pd.DataFrame(
    [[0.25, 0.20, 0.22], [0.30, 0.24, 0.26]],
    index=[0.1, 0.5],
    columns=[-0.1, 0.0, 0.1],
)


def test_plot_surface_maps_axes_correctly():
    fig = plot_surface(SURFACE)
    assert fig.data[0].type == "surface"
    assert list(fig.data[0].x) == list(SURFACE.columns)
    assert list(fig.data[0].y) == list(SURFACE.index)
    assert np.array_equal(fig.data[0].z, SURFACE.values)
    assert fig.layout.scene.aspectmode == "cube"
    assert fig.data[0].colorscale[0][1].lower() == "#440154"  # Viridis' darkest color


def test_plot_surface_grid_lines_are_evenly_spaced_and_light_grey():
    fig = plot_surface(SURFACE)
    assert len(fig.data) == 1  # grid lines are contours on the surface trace, not extra traces
    x_range = SURFACE.columns.max() - SURFACE.columns.min()
    y_range = SURFACE.index.max() - SURFACE.index.min()
    contours = fig.data[0].contours
    assert contours.x.show and contours.x.color == "rgba(211, 211, 211, 0.95)"
    assert contours.x.start == pytest.approx(SURFACE.columns.min())
    assert contours.x.end == pytest.approx(SURFACE.columns.max())
    assert contours.x.size == pytest.approx(x_range / 20)  # always 20 mesh lines, not a fixed step
    assert contours.y.show and contours.y.color == "rgba(211, 211, 211, 0.95)"
    assert contours.y.start == pytest.approx(SURFACE.index.min())
    assert contours.y.end == pytest.approx(SURFACE.index.max())
    assert contours.y.size == pytest.approx(y_range / 20)  # always 20 mesh lines, not a fixed step


def test_plot_surface_axis_ranges_and_ticks():
    fig = plot_surface(SURFACE)
    scene = fig.layout.scene
    assert scene.xaxis.range == (-0.2, 0.2)  # fixed view window, not derived from the data
    assert scene.xaxis.dtick == pytest.approx(0.05)
    assert scene.yaxis.dtick == pytest.approx(0.1)
    # z floors/ceils to the nearest 0.05 around the data's actual min/max (0.20 and 0.30 here)
    assert scene.zaxis.range == pytest.approx((0.20, 0.30))
    assert scene.zaxis.dtick == pytest.approx(0.05)


def test_plot_smiles_defaults_to_one_trace_per_expiry():
    fig = plot_smiles(SURFACE)
    assert len(fig.data) == 2
    assert list(fig.data[0].y) == list(SURFACE.loc[0.1])
    assert list(fig.data[1].y) == list(SURFACE.loc[0.5])


def test_plot_smiles_filters_to_the_requested_expiries():
    fig = plot_smiles(SURFACE, years_to_expiry=[0.5])
    assert len(fig.data) == 1
    assert fig.data[0].name == "0.500y"
    assert list(fig.data[0].x) == list(SURFACE.columns)
    assert list(fig.data[0].y) == list(SURFACE.loc[0.5])


def test_plot_term_structure_uses_the_column_closest_to_zero():
    # columns are -0.1, 0.0, 0.1 -- 0.0 is the exact ATM column
    fig = plot_term_structure(SURFACE)
    assert list(fig.data[0].x) == list(SURFACE.index)
    assert list(fig.data[0].y) == list(SURFACE[0.0])


def test_plot_term_structure_finds_the_nearest_column_when_grid_has_no_exact_zero():
    off_grid = pd.DataFrame([[0.25, 0.22], [0.30, 0.26]], index=[0.1, 0.5], columns=[-0.05, 0.03])
    fig = plot_term_structure(off_grid)
    # 0.03 is closer to zero than -0.05, so that column should be used
    assert list(fig.data[0].y) == list(off_grid[0.03])
