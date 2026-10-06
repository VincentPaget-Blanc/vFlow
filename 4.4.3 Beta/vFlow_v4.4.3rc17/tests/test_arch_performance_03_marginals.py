from __future__ import annotations

from vflow.rendering.flow_renderer import FlowRenderer
import numpy as np
import pytest

from vflow.app.cache import AnalysisCache
from vflow.app.session import ApplicationSession
from vflow.legacy import vflow_app as legacy
from vflow.plotting.utils import sampled_indices


class _StairsRecorder:
    def __init__(self):
        self.calls = []

    def stairs(self, counts, edges, **kwargs):
        self.calls.append((np.asarray(counts).copy(), np.asarray(edges).copy(), dict(kwargs)))


class _HistRecorder:
    def __init__(self):
        self.calls = []

    def hist(self, values, bins, **kwargs):
        counts, edges = np.histogram(values, bins=bins)
        self.calls.append((np.asarray(values).copy(), np.asarray(edges).copy(), dict(kwargs)))
        return counts, edges, []


def _bare_app(*, stairs=True):
    app = legacy.FlowApp.__new__(legacy.FlowApp)
    app.__dict__["_app_session"] = ApplicationSession()
    app.x_channel = "X"
    app.y_channel = "Y"
    app.x_scale = "asinh"
    app.y_scale = "asinh"
    app.cofactor = 150.0
    app.ax_top = _StairsRecorder() if stairs else _HistRecorder()
    app.ax_right = _StairsRecorder() if stairs else _HistRecorder()
    return app


def _legacy_expected(app, x_raw, y_raw, xt, yt, valid):
    xv = xt[valid]
    yv = yt[valid]
    xr = x_raw[valid]
    yr = y_raw[valid]
    idx = sampled_indices(len(xr), 30_000, seed=5)
    if idx is not None:
        xr_h = xr[idx]
        yr_h = yr[idx]
    else:
        xr_h = xr
        yr_h = yr
    x_edges = app._inv(np.linspace(xv.min(), xv.max(), 121), app.x_scale)
    y_edges = app._inv(np.linspace(yv.min(), yv.max(), 121), app.y_scale)
    x_counts, _ = np.histogram(xr_h, bins=x_edges)
    y_counts, _ = np.histogram(yr_h, bins=y_edges)
    return x_counts, x_edges, y_counts, y_edges


@pytest.mark.parametrize("n", [1473, 75_000])
def test_marginal_cached_payload_matches_historical_bins_exactly(n):
    rng = np.random.default_rng(4300 + n)
    x = rng.normal(150.0, 800.0, n).astype(np.float64)
    y = rng.normal(250.0, 950.0, n).astype(np.float64)
    x[::997] = np.nan
    y[::991] = np.inf
    app = _bare_app()
    xt, yt, valid = app._transform_xy(x, y)

    expected = _legacy_expected(app, x, y, xt, yt, valid)
    app._plot_marginals(x, y, xt, yt, valid, "#123456", _cache_path="sample.fcs")
    payload = next(iter(app._marginal_cache.values()))

    for got, exp in zip(payload[:4], expected):
        np.testing.assert_array_equal(got, exp)
    assert payload[4] == int(valid.sum())
    np.testing.assert_array_equal(app.ax_top.calls[0][0], expected[0])
    np.testing.assert_array_equal(app.ax_top.calls[0][1], expected[1])
    np.testing.assert_array_equal(app.ax_right.calls[0][0], expected[2])
    np.testing.assert_array_equal(app.ax_right.calls[0][1], expected[3])
    assert app.ax_right.calls[0][2]["orientation"] == "horizontal"


def test_marginal_cache_hit_skips_histogram_and_edge_recomputation(monkeypatch):
    rng = np.random.default_rng(22)
    x = rng.normal(size=5000)
    y = rng.normal(size=5000)
    app = _bare_app()
    xt, yt, valid = app._transform_xy(x, y)
    app._plot_marginals(x, y, xt, yt, valid, "#111111", _cache_path="p")
    first_top = app.ax_top.calls[-1]
    first_right = app.ax_right.calls[-1]

    monkeypatch.setattr(
        legacy.np,
        "histogram",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("histogram recomputed")),
    )
    app._inv = lambda *a, **k: (_ for _ in ()).throw(AssertionError("edges recomputed"))
    app._plot_marginals(x, y, xt, yt, valid, "#abcdef", _cache_path="p")

    np.testing.assert_array_equal(app.ax_top.calls[-1][0], first_top[0])
    np.testing.assert_array_equal(app.ax_right.calls[-1][0], first_right[0])
    assert app.ax_top.calls[-1][2]["color"] == "#abcdef"


def test_marginal_cache_is_context_and_generation_keyed():
    rng = np.random.default_rng(33)
    x = rng.normal(size=2500)
    y = rng.normal(size=2500)
    app = _bare_app()
    xt, yt, valid = app._transform_xy(x, y)
    app._plot_marginals(x, y, xt, yt, valid, "#1", _cache_path="p")
    assert len(app._marginal_cache) == 1

    app._data_generation += 1
    app._plot_marginals(x, y, xt, yt, valid, "#1", _cache_path="p")
    assert len(app._marginal_cache) == 2

    app.x_scale = "linear"
    app.y_scale = "linear"
    valid_linear = np.isfinite(x) & np.isfinite(y)
    app._plot_marginals(x, y, x, y, valid_linear, "#1", _cache_path="p")
    assert len(app._marginal_cache) == 3


def test_marginal_cache_policy_matches_base_render_cache_invalidation():
    cache = AnalysisCache()
    cache.transforms["t"] = 1
    cache.gate_masks["g"] = 2
    cache.scatter["s"] = 3
    cache.density["d"] = 4
    cache.marginals["m"] = 5

    cache.clear_scatter()
    assert cache.marginals == {"m": 5}
    cache.scatter["s"] = 3
    cache.clear_gate_dependent()
    assert cache.marginals == {"m": 5}
    cache.clear_all()
    assert cache.marginals == {}


def test_marginal_cache_partial_eviction_is_bounded():
    cache = AnalysisCache()
    for i in range(4):
        cache.marginals[i] = i
    cache.put_marginal_render(4, "new", max_entries=4, evict_count=2)
    assert list(cache.marginals) == [2, 3, 4]


def test_historical_direct_plot_marginals_path_remains_available():
    rng = np.random.default_rng(44)
    x = rng.normal(size=1000)
    y = rng.normal(size=1000)
    app = _bare_app(stairs=False)
    xt, yt, valid = app._transform_xy(x, y)
    xr, yr, xe, ye = app._plot_marginals(x, y, xt, yt, valid, "#778899")
    np.testing.assert_array_equal(xr, x[valid])
    np.testing.assert_array_equal(yr, y[valid])
    assert xe.shape == (121,)
    assert ye.shape == (121,)
    assert len(app.ax_top.calls) == 1
    assert len(app.ax_right.calls) == 1


def test_stepfilled_hist_and_stairs_are_pixel_identical_both_orientations():
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    rng = np.random.default_rng(55)
    values = rng.normal(size=5000)
    edges = np.linspace(-4.0, 4.0, 121)
    counts, _ = np.histogram(values, bins=edges)

    def render(kind, orientation):
        fig, ax = plt.subplots(figsize=(4, 2), dpi=100)
        if orientation == "vertical":
            ax.set_xlim(-4.0, 4.0)
            ax.set_ylim(0.0, float(counts.max()) * 1.1)
        else:
            ax.set_ylim(-4.0, 4.0)
            ax.set_xlim(0.0, float(counts.max()) * 1.1)
        if kind == "hist":
            ax.hist(
                values,
                bins=edges,
                color="#336699",
                alpha=0.55,
                histtype="stepfilled",
                orientation=orientation,
                linewidth=0.5,
            )
        else:
            ax.stairs(
                counts,
                edges,
                fill=True,
                color="#336699",
                alpha=0.55,
                orientation=orientation,
                linewidth=0.5,
            )
        canvas = FigureCanvasAgg(fig)
        canvas.draw()
        image = np.asarray(canvas.buffer_rgba()).copy()
        plt.close(fig)
        return image

    for orientation in ("vertical", "horizontal"):
        np.testing.assert_array_equal(render("hist", orientation), render("stairs", orientation))


def test_default_render_path_does_not_unconditionally_accumulate_full_raw_arrays():
    import inspect

    source = inspect.getsource(FlowRenderer.render)
    assert "_need_raw_parts = _need_fit_raw or (_gmm_overlay_gate is not None)" in source
    assert "if valid.any() and _need_raw_parts:" in source
