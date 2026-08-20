from __future__ import annotations

import numpy as np
import pytest

from vflow.app.cache import AnalysisCache
from vflow.app.session import ApplicationSession
from vflow.app.state import AnalysisState
from vflow.core.gate_masks import compute_gate_regions
from vflow.legacy import vflow_app as legacy
from vflow.services.gate_evaluation import evaluate_gate_regions


class _AxesRecorder:
    def __init__(self):
        self.calls = []

    def scatter(self, x, y, **kwargs):
        self.calls.append((np.asarray(x).copy(), np.asarray(y).copy(), dict(kwargs)))


def _bare_app():
    app = legacy.FlowApp.__new__(legacy.FlowApp)
    app.__dict__["_app_session"] = ApplicationSession()
    app.x_channel = "X"
    app.y_channel = "Y"
    app.x_scale = "asinh"
    app.y_scale = "asinh"
    app.cofactor = 150.0
    app.ax = _AxesRecorder()
    app._plot_dot = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("unexpected density fallback")
    )
    return app


def test_density_render_cache_reuses_numeric_payload_across_style_changes(monkeypatch):
    rng = np.random.default_rng(2026)
    x = rng.normal(200.0, 700.0, 5000).astype(np.float64)
    y = rng.normal(300.0, 900.0, 5000).astype(np.float64)
    app = _bare_app()
    xt, yt, valid = app._transform_xy(x, y)

    app._plot_density(
        x, y, xt, yt, valid, 4.0, 0.4, "first", _cache_path="sample.fcs"
    )
    assert len(app._density_cache) == 1
    first = app.ax.calls[-1]

    monkeypatch.setattr(
        legacy,
        "gaussian_kde",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("KDE reran on cache hit")),
    )
    app._plot_density(
        x, y, xt, yt, valid, 9.0, 0.8, "restyled", _cache_path="sample.fcs"
    )
    second = app.ax.calls[-1]

    np.testing.assert_array_equal(second[0], first[0])
    np.testing.assert_array_equal(second[1], first[1])
    np.testing.assert_array_equal(second[2]["c"], first[2]["c"])
    assert second[2]["vmin"] == first[2]["vmin"]
    assert second[2]["vmax"] == first[2]["vmax"]
    assert second[2]["s"] == 9.0
    assert second[2]["alpha"] == 0.8
    assert second[2]["label"].startswith("restyled")


def test_density_cache_is_context_keyed_and_data_generation_keyed():
    rng = np.random.default_rng(7)
    x = rng.normal(size=1000).astype(np.float64)
    y = rng.normal(size=1000).astype(np.float64)
    app = _bare_app()
    xt, yt, valid = app._transform_xy(x, y)
    app._plot_density(x, y, xt, yt, valid, 4, 0.5, "a", _cache_path="p")
    assert len(app._density_cache) == 1

    app._data_generation += 1
    app._plot_density(x, y, xt, yt, valid, 4, 0.5, "a", _cache_path="p")
    assert len(app._density_cache) == 2

    app.x_scale = "linear"
    app._plot_density(x, y, x, y, np.isfinite(x) & np.isfinite(y), 4, 0.5, "a", _cache_path="p")
    assert len(app._density_cache) == 3


def test_density_cache_policy_preserves_base_density_across_gate_only_evictions():
    cache = AnalysisCache()
    cache.transforms["t"] = 1
    cache.gate_masks["g"] = 2
    cache.scatter["s"] = 3
    cache.density["d"] = 4

    cache.clear_scatter()
    assert cache.density == {"d": 4}
    cache.scatter["s"] = 3
    cache.clear_gate_dependent()
    assert cache.density == {"d": 4}
    cache.clear_all()
    assert cache.density == {}


def test_density_cache_partial_eviction_is_bounded():
    cache = AnalysisCache()
    for i in range(4):
        cache.density[i] = i
    cache.put_density_render(4, "new", max_entries=4, evict_count=2)
    assert list(cache.density) == [2, 3, 4]


def _gate(kind: str):
    g = {"id": 3, "name": kind, "type": kind, "applied": True, "color": "#f00"}
    if kind == "rectangle":
        g.update(x0=-100.0, y0=-50.0, x1=800.0, y1=900.0)
    elif kind == "ellipse":
        g.update(x0=-100.0, y0=-50.0, x1=800.0, y1=900.0)
    elif kind == "polygon":
        g.update(vertices=[(-100.0, -50.0), (700.0, -100.0), (900.0, 600.0), (200.0, 1000.0)])
    else:
        g.update(x_boundaries=[150.0], y_boundary=250.0, x_thresh_vars=[], y_thresh_var=None)
    return g


@pytest.mark.parametrize("scale", ["linear", "asinh", "log", "biexp", "logicle"])
@pytest.mark.parametrize("kind", ["rectangle", "ellipse", "polygon", "crosshair"])
def test_gate_evaluator_matches_core_single_transform_contract(scale, kind):
    rng = np.random.default_rng(abs(hash((scale, kind))) % (2**32))
    if scale == "log":
        x = np.exp(rng.normal(3.0, 2.0, 1500)).astype(np.float64)
        y = np.exp(rng.normal(3.0, 2.0, 1500)).astype(np.float64)
        x[::97] = 0.0
        y[::101] = -1.0
    else:
        x = rng.normal(100.0, 900.0, 1500).astype(np.float64)
        y = rng.normal(200.0, 1000.0, 1500).astype(np.float64)
        x[::97] = np.nan
        y[::101] = np.inf

    state = AnalysisState(
        x_channel="X", y_channel="Y", x_scale=scale, y_scale=scale, cofactor=150.0
    )
    gate = _gate(kind)
    expected_regions, expected_colors = compute_gate_regions(
        gate,
        x,
        y,
        x_scale=scale,
        y_scale=scale,
        cofactor=150.0,
        x_channel="X",
        y_channel="Y",
    )
    actual_regions, actual_colors = evaluate_gate_regions(
        gate, x, y, analysis_state=state, analysis_cache=AnalysisCache()
    )
    assert actual_colors == expected_colors
    assert list(actual_regions) == list(expected_regions)
    for name in expected_regions:
        np.testing.assert_array_equal(actual_regions[name], expected_regions[name])
