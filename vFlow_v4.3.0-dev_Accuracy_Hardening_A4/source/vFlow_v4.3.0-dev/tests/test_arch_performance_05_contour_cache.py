from __future__ import annotations

from vflow.rendering.flow_renderer import FlowRenderer
import inspect

import matplotlib
matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pytest
from scipy.interpolate import RegularGridInterpolator
from scipy.stats import gaussian_kde

from vflow.app.cache import AnalysisCache
from vflow.app.session import ApplicationSession
from vflow.legacy import vflow_app as legacy
from vflow.plotting.utils import apply_sample_indices, sampled_indices, valid_values


def _bare_app():
    app = legacy.FlowApp.__new__(legacy.FlowApp)
    app.__dict__["_app_session"] = ApplicationSession()
    app.x_channel = "X"
    app.y_channel = "Y"
    app.x_scale = "asinh"
    app.y_scale = "asinh"
    app.cofactor = 150.0
    fig, ax = plt.subplots(figsize=(4, 4), dpi=100)
    app.ax = ax
    return app, fig


def _historical_payload(app, x_raw, y_raw, xt, yt, valid, prob_level):
    xv = valid_values(xt, valid)
    yv = valid_values(yt, valid)
    n = len(xv)
    idx = sampled_indices(n, legacy.KDE_SUBSAMPLE, seed=0)
    if idx is not None:
        kern = gaussian_kde(np.vstack([xv[idx], yv[idx]]))
    else:
        kern = gaussian_kde(np.vstack([xv, yv]))

    grid = 96
    xg_t = np.linspace(xv.min(), xv.max(), grid)
    yg_t = np.linspace(yv.min(), yv.max(), grid)
    xmg, ymg = np.meshgrid(xg_t, yg_t, indexing="ij")
    z = kern(np.vstack([xmg.ravel(), ymg.ravel()])).reshape(grid, grid)
    xg_raw = app._inv(xmg, app.x_scale)
    yg_raw = app._inv(ymg, app.y_scale)
    s_z = np.sort(z.ravel())
    cum = np.cumsum(s_z) / s_z.sum()
    lv = float(np.interp(prob_level, cum, s_z))
    interp = RegularGridInterpolator(
        (xg_t, yg_t), z, method="linear", bounds_error=False, fill_value=float(z.min())
    )
    pt_dens = interp(np.column_stack([xv, yv]))
    outside = pt_dens < lv
    xo = valid_values(x_raw, valid)[outside]
    yo = valid_values(y_raw, valid)[outside]
    n_outside = len(xo)
    xo, yo = apply_sample_indices(
        xo, yo, indices=sampled_indices(n_outside, legacy.RENDER_CAP, seed=4)
    )
    return xg_raw, yg_raw, z, lv, xo, yo, n_outside


def test_contour_cached_payload_matches_historical_algorithm_exactly():
    rng = np.random.default_rng(505)
    x = rng.normal(120.0, 900.0, 1800)
    y = 0.45 * x + rng.normal(20.0, 700.0, 1800)
    x[::311] = np.nan
    y[::337] = np.inf
    app, fig = _bare_app()
    try:
        xt, yt, valid = app._transform_xy(x, y)
        expected = _historical_payload(app, x, y, xt, yt, valid, 0.05)
        app._plot_contour(
            x, y, xt, yt, valid, "#336699", "sample", 2.0, 0.7, 0.05,
            _cache_path="sample.fcs",
        )
        payload = next(iter(app._contour_cache.values()))
        np.testing.assert_array_equal(payload[2], expected[0])
        np.testing.assert_array_equal(payload[3], expected[1])
        np.testing.assert_array_equal(payload[4], expected[2])
        assert payload[5] == 0.05
        assert payload[6] == expected[3]
        np.testing.assert_array_equal(payload[7], expected[4])
        np.testing.assert_array_equal(payload[8], expected[5])
        assert payload[9] == expected[6]
    finally:
        plt.close(fig)


def test_contour_cache_hit_skips_kde_inverse_and_interpolation(monkeypatch):
    rng = np.random.default_rng(506)
    x = rng.normal(size=1200)
    y = 0.2 * x + rng.normal(size=1200)
    app, fig = _bare_app()
    try:
        xt, yt, valid = app._transform_xy(x, y)
        app._plot_contour(
            x, y, xt, yt, valid, "#112233", "sample", 2.0, 0.7, 0.05,
            _cache_path="p",
        )
        assert len(app._contour_cache) == 1

        monkeypatch.setattr(
            legacy, "gaussian_kde",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("KDE recomputed")),
        )
        monkeypatch.setattr(
            legacy, "RegularGridInterpolator",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("interpolation recomputed")),
        )
        app._inv = lambda *a, **k: (_ for _ in ()).throw(AssertionError("grid inverse recomputed"))
        app._plot_contour(
            x, y, xt, yt, valid, "#abcdef", "renamed", 5.0, 0.25, 0.05,
            _cache_path="p",
        )
        assert len(app._contour_cache) == 1
    finally:
        plt.close(fig)


def test_contour_cache_reuses_surface_across_probability_and_keys_context(monkeypatch):
    rng = np.random.default_rng(507)
    x = rng.normal(size=900)
    y = rng.normal(size=900)
    app, fig = _bare_app()
    try:
        xt, yt, valid = app._transform_xy(x, y)
        app._plot_contour(
            x, y, xt, yt, valid, "#112233", "p", 1, 1, 0.05, _cache_path="p"
        )
        assert len(app._contour_cache) == 1
        first_surface = next(iter(app._contour_cache.values()))[4]

        monkeypatch.setattr(
            legacy, "gaussian_kde",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("KDE surface recomputed")),
        )
        app._plot_contour(
            x, y, xt, yt, valid, "#445566", "p", 3, 0.2, 0.10, _cache_path="p"
        )
        assert len(app._contour_cache) == 1
        changed = next(iter(app._contour_cache.values()))
        assert changed[4] is first_surface
        assert changed[5] == 0.10

        # A new dataset generation must not reuse the old context. Restore the
        # real KDE constructor so the new generation can create its own surface.
        monkeypatch.setattr(legacy, "gaussian_kde", gaussian_kde)
        app._data_generation += 1
        app._plot_contour(
            x, y, xt, yt, valid, "#445566", "p", 3, 0.2, 0.10, _cache_path="p"
        )
        assert len(app._contour_cache) == 2
    finally:
        plt.close(fig)


def test_contour_cache_gate_and_style_invalidation_policy():
    cache = AnalysisCache()
    cache.transforms["t"] = 1
    cache.gate_masks["g"] = 2
    cache.scatter["s"] = 3
    cache.density["d"] = 4
    cache.marginals["m"] = 5
    cache.contours["c"] = 6

    cache.clear_scatter()
    assert cache.contours == {"c": 6}
    cache.scatter["s"] = 3
    cache.clear_gate_dependent()
    assert cache.contours == {"c": 6}
    cache.clear_all()
    assert cache.contours == {}


def test_contour_cache_partial_eviction_is_bounded():
    cache = AnalysisCache()
    for i in range(4):
        cache.contours[i] = i
    cache.put_contour_render(4, "new", max_entries=4, evict_count=2)
    assert list(cache.contours) == [2, 3, 4]


def test_contour_cache_existing_key_update_does_not_trigger_capacity_eviction():
    cache = AnalysisCache()
    for i in range(4):
        cache.contours[i] = i
    cache.put_contour_render(3, "updated", max_entries=4, evict_count=2)
    assert list(cache.contours) == [0, 1, 2, 3]
    assert cache.contours[3] == "updated"


def test_direct_plot_contour_path_does_not_create_cache_entry():
    rng = np.random.default_rng(508)
    x = rng.normal(size=800)
    y = rng.normal(size=800)
    app, fig = _bare_app()
    try:
        xt, yt, valid = app._transform_xy(x, y)
        app._plot_contour(x, y, xt, yt, valid, "#123456", "direct", 2, 0.6, 0.05)
        assert app._contour_cache == {}
    finally:
        plt.close(fig)


def test_refresh_plot_supplies_file_identity_to_contour_cache():
    source = inspect.getsource(FlowRenderer.render)
    assert source.count("_cache_path=path") >= 4  # Density, both Contour branches, marginals.
    assert "self.plot_contour(x_raw, y_raw, xt, yt, valid," in source
