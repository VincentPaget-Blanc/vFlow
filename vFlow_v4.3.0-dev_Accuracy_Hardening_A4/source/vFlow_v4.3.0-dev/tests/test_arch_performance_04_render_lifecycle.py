from __future__ import annotations

from vflow.rendering.flow_renderer import FlowRenderer
import inspect

import matplotlib
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FixedLocator

from vflow.legacy import vflow_app as legacy
from vflow.plotting.render_lifecycle import (
    clear_data_artists_preserve_axis_state,
    reset_refresh_axes,
)


def test_content_reset_removes_refresh_artists_but_preserves_axis_tick_objects():
    fig, ax = plt.subplots()
    ax.set_xscale("symlog", linthresh=1.0)
    ax.set_yscale("symlog", linthresh=1.0)
    ax.xaxis.set_minor_locator(FixedLocator([-10, -2, -1, 1, 2, 10]))
    ax.yaxis.set_minor_locator(FixedLocator([-10, -2, -1, 1, 2, 10]))
    ax.scatter([1, 2], [2, 3], label="points")
    ax.plot([1, 2], [3, 4], label="line")
    ax.fill_between([1, 2], [0, 0], [1, 2])
    ax.text(1.5, 2.5, "annotation")
    ax.imshow(np.arange(4).reshape(2, 2), extent=(1, 2, 1, 2))
    ax.legend()
    fig.canvas.draw()

    x_major = tuple(ax.xaxis.majorTicks)
    x_minor = tuple(ax.xaxis.minorTicks)
    y_major = tuple(ax.yaxis.majorTicks)
    y_minor = tuple(ax.yaxis.minorTicks)

    clear_data_artists_preserve_axis_state(ax)

    assert list(ax.collections) == []
    assert list(ax.lines) == []
    assert list(ax.patches) == []
    assert list(ax.texts) == []
    assert list(ax.images) == []
    assert ax.legend_ is None
    assert ax.get_xscale() == "symlog"
    assert ax.get_yscale() == "symlog"
    assert tuple(ax.xaxis.majorTicks) == x_major
    assert tuple(ax.xaxis.minorTicks) == x_minor
    assert tuple(ax.yaxis.majorTicks) == y_major
    assert tuple(ax.yaxis.minorTicks) == y_minor
    plt.close(fig)


def test_content_reset_restores_fresh_unit_limits_and_autoscale():
    fig, ax = plt.subplots()
    ax.scatter([100, 200], [-50, 50])
    ax.set_xlim(90, 210)
    ax.set_ylim(-60, 60)
    ax.set_autoscalex_on(False)
    ax.set_autoscaley_on(False)

    clear_data_artists_preserve_axis_state(ax)

    assert ax.get_xlim() == (0.0, 1.0)
    assert ax.get_ylim() == (0.0, 1.0)
    assert ax.get_autoscalex_on() is True
    assert ax.get_autoscaley_on() is True
    plt.close(fig)


def test_content_reset_restarts_default_property_cycle_like_axes_clear():
    fig, ax = plt.subplots()
    first, = ax.plot([0, 1], [0, 1])
    second, = ax.plot([0, 1], [1, 2])
    assert first.get_color() != second.get_color()

    clear_data_artists_preserve_axis_state(ax)
    after, = ax.plot([0, 1], [2, 3])

    assert after.get_color() == first.get_color()
    plt.close(fig)


def test_reset_refresh_axes_preserve_false_uses_historical_full_clear():
    class FakeAxis:
        def __init__(self):
            self.clears = 0

        def clear(self):
            self.clears += 1

    a = FakeAxis()
    b = FakeAxis()
    reset_refresh_axes((a, None, b), preserve_axis_state=False)
    assert a.clears == 1
    assert b.clears == 1


def test_reset_refresh_axes_preserve_true_does_not_call_axes_clear():
    class FakeAxis:
        def __init__(self):
            self.clears = 0
            self.collections = []
            self.lines = []
            self.patches = []
            self.texts = []
            self.artists = []
            self.images = []
            self.tables = []
            self.legend_ = None
            self.containers = []
            self.xlim = None
            self.ylim = None

        def clear(self):
            self.clears += 1

        def set_prop_cycle(self, value):
            assert value is None

        def relim(self, visible_only=False):
            assert visible_only is False

        def set_xlim(self, lo, hi, auto=None):
            self.xlim = (lo, hi, auto)

        def set_ylim(self, lo, hi, auto=None):
            self.ylim = (lo, hi, auto)

    ax = FakeAxis()
    reset_refresh_axes((ax,), preserve_axis_state=True)
    assert ax.clears == 0
    assert ax.xlim == (0.0, 1.0, True)
    assert ax.ylim == (0.0, 1.0, True)


def test_refresh_plot_retains_axis_state_only_outside_contour_mode():
    source = inspect.getsource(FlowRenderer.render)
    assert "plot_type != 'Contour Plot'" in source
    assert "plan.x_scale != 'log'" in source
    assert "plan.y_scale != 'log'" in source
    assert "reset_refresh_axes(" in source


def test_refresh_plot_explicitly_disables_grid_on_retained_axes():
    source = inspect.getsource(FlowRenderer.render)
    assert "if host.show_grid_var.get():" in source
    assert "host.ax.grid(True, alpha=0.25, color=T['grid'])" in source
    assert "host.ax.grid(False)" in source
