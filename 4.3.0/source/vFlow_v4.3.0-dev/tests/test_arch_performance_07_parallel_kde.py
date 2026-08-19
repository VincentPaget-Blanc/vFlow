from __future__ import annotations

from vflow.rendering.flow_renderer import FlowRenderer
import vflow.rendering.flow_renderer as render_mod
import inspect
import threading
from collections import OrderedDict

import numpy as np
import pandas as pd

from vflow.app.session import ApplicationSession
from vflow.legacy import vflow_app as legacy
from vflow.plotting.kde_payloads import (
    KDERenderComputation,
    compute_density_render_payload,
    compute_kde_jobs_parallel,
)
from vflow.plotting.utils import sampled_indices, valid_values


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
    app._plot_dot = lambda *a, **k: None
    return app


def _historical_density_payload(x_raw, y_raw, xt, yt, valid):
    from scipy.interpolate import RegularGridInterpolator
    from scipy.stats import gaussian_kde

    xv = valid_values(xt, valid)
    yv = valid_values(yt, valid)
    xlo, xhi = np.nanpercentile(xv, [1, 99])
    ylo, yhi = np.nanpercentile(yv, [1, 99])
    core = (xv >= xlo) & (xv <= xhi) & (yv >= ylo) & (yv <= yhi)
    xc = xv[core]
    yc = yv[core]
    n = len(xc)
    idx = sampled_indices(n, legacy.KDE_SUBSAMPLE, seed=0)
    if idx is not None:
        kern = gaussian_kde(np.vstack([xc[idx], yc[idx]]))
    else:
        kern = gaussian_kde(np.vstack([xc, yc]))
    grid = 96
    xg = np.linspace(xlo, xhi, grid)
    yg = np.linspace(ylo, yhi, grid)
    xmg, ymg = np.meshgrid(xg, yg, indexing="ij")
    z = kern(np.vstack([xmg.ravel(), ymg.ravel()])).reshape(grid, grid)
    interp = RegularGridInterpolator(
        (xg, yg), z, method="linear", bounds_error=False, fill_value=float(z.min())
    )
    density = interp(np.column_stack([xv, yv]))
    xr = valid_values(x_raw, valid)
    yr = valid_values(y_raw, valid)
    n_valid = len(xr)
    keep = sampled_indices(n_valid, legacy.RENDER_CAP, seed=3)
    if keep is not None:
        xr = xr[keep]
        yr = yr[keep]
        dens_plot = density[keep]
    else:
        dens_plot = density
    order = np.argsort(dens_plot)
    vlo, vhi = np.nanpercentile(density, [1, 99])
    return xr[order], yr[order], dens_plot[order], float(vlo), float(vhi), n_valid


def test_density_pure_helper_matches_historical_algorithm_exactly():
    rng = np.random.default_rng(707)
    x = rng.normal(100.0, 700.0, 5000)
    y = 0.35 * x + rng.normal(20.0, 650.0, 5000)
    x[::421] = np.nan
    y[::389] = np.inf
    app = _bare_app()
    xt, yt, valid = app._transform_xy(x, y)
    expected = _historical_density_payload(x, y, xt, yt, valid)
    actual = compute_density_render_payload(x, y, xt, yt, valid)
    assert actual.action == "payload"
    for got, want in zip(actual.payload[:3], expected[:3]):
        np.testing.assert_array_equal(got, want)
    assert actual.payload[3:] == expected[3:]


def test_parallel_jobs_match_sequential_payloads_exactly():
    rng = np.random.default_rng(708)
    jobs = []
    sequential = {}
    for i in range(4):
        x = rng.normal(100 + i, 500, 1200)
        y = rng.normal(200 - i, 600, 1200)
        valid = np.isfinite(x) & np.isfinite(y)
        args = (x, y, x, y, valid)
        sequential[i] = compute_density_render_payload(*args)
        jobs.append((i, compute_density_render_payload, args, {}))
    parallel = compute_kde_jobs_parallel(jobs, max_workers=4)
    assert list(parallel) == [0, 1, 2, 3]
    for i in range(4):
        assert parallel[i].action == sequential[i].action == "payload"
        for got, want in zip(parallel[i].payload[:3], sequential[i].payload[:3]):
            np.testing.assert_array_equal(got, want)
        assert parallel[i].payload[3:] == sequential[i].payload[3:]


def test_parallel_orchestrator_runs_jobs_concurrently_and_preserves_input_order():
    barrier = threading.Barrier(2)
    names = []
    lock = threading.Lock()

    def work(value):
        with lock:
            names.append(threading.current_thread().name)
        barrier.wait(timeout=5)
        return KDERenderComputation("payload", value)

    jobs = [("a", work, (1,), {}), ("b", work, (2,), {})]
    result = compute_kde_jobs_parallel(jobs, max_workers=2)
    assert list(result) == ["a", "b"]
    assert result["a"].payload == 1
    assert result["b"].payload == 2
    assert len(set(names)) == 2
    assert all(name.startswith("vflow-kde") for name in names)


def test_parallel_orchestrator_captures_unexpected_exception_for_ordered_reraise():
    def work(value):
        if value == 2:
            raise RuntimeError("second-file failure")
        return KDERenderComputation("payload", value)

    result = compute_kde_jobs_parallel(
        [(1, work, (1,), {}), (2, work, (2,), {}), (3, work, (3,), {})],
        max_workers=3,
    )
    assert list(result) == [1, 2, 3]
    assert result[1].payload == 1
    assert result[2].action == "error"
    assert isinstance(result[2].error, RuntimeError)
    assert str(result[2].error) == "second-file failure"
    assert result[3].payload == 3


def test_precompute_requires_multiple_misses_and_does_not_commit_cache(monkeypatch):
    app = _bare_app()
    rng = np.random.default_rng(709)
    frames = OrderedDict()
    for i in range(2):
        frames[f"f{i}.fcs"] = pd.DataFrame({
            "X": rng.normal(size=800),
            "Y": rng.normal(size=800),
        })

    called = {}
    real_parallel = render_mod.compute_kde_jobs_parallel

    def wrapped(jobs):
        called["paths"] = [job[0] for job in jobs]
        return real_parallel(jobs, max_workers=2)

    monkeypatch.setattr(render_mod, "compute_kde_jobs_parallel", wrapped)
    results = app._precompute_cold_kde_payloads(frames, "Density")
    assert called["paths"] == ["f0.fcs", "f1.fcs"]
    assert list(results) == ["f0.fcs", "f1.fcs"]
    assert app._density_cache == {}

    # Cache commitment remains in the historical main-thread plot call.
    f0 = frames["f0.fcs"]
    x = f0["X"].to_numpy(copy=False)
    y = f0["Y"].to_numpy(copy=False)
    xt, yt, valid = app._transform_xy_cached("f0.fcs", x, y)
    app._plot_density(
        x, y, xt, yt, valid, 2.0, 0.5, "f0",
        _cache_path="f0.fcs", _precomputed=results["f0.fcs"],
    )
    assert len(app._density_cache) == 1


def test_single_cold_file_stays_on_direct_historical_path(monkeypatch):
    app = _bare_app()
    frame = pd.DataFrame({"X": np.arange(100.0), "Y": np.arange(100.0)})
    monkeypatch.setattr(
        legacy, "compute_kde_jobs_parallel",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("unexpected thread pool")),
    )
    assert app._precompute_cold_kde_payloads({"one.fcs": frame}, "Density") == {}


def test_precomputed_error_is_reraised_before_cache_commit():
    app = _bare_app()
    x = np.arange(50.0)
    y = np.arange(50.0)
    valid = np.ones(50, dtype=bool)
    error = RuntimeError("ordered error")
    try:
        app._plot_density(
            x, y, x, y, valid, 2, 0.5, "p",
            _cache_path="p", _precomputed=KDERenderComputation("error", error=error),
        )
    except RuntimeError as exc:
        assert exc is error
    else:
        raise AssertionError("expected worker error to be re-raised")
    assert app._density_cache == {}


def test_refresh_plot_wires_precomputed_payloads_into_all_density_contour_branches():
    source = inspect.getsource(FlowRenderer.render)
    assert "self.precompute_cold_kde_payloads(display, plot_type)" in source
    assert source.count("_precomputed=_kde_precomputed.get(path)") == 4


def test_parallel_constant_data_falls_back_without_interpolator_failure():
    app = _bare_app()
    frames = OrderedDict(
        (
            f"singular{i}.fcs",
            pd.DataFrame({"X": np.ones(100), "Y": np.ones(100)}),
        )
        for i in range(2)
    )
    density = app._precompute_cold_kde_payloads(frames, "Density")
    contour = app._precompute_cold_kde_payloads(frames, "Contour Plot")

    # B6 intentionally replaces the historical RegularGridInterpolator crash
    # with the renderer's existing dot fallback.  Constant channels contain no
    # density/contour structure to interpolate, and this also prevents the
    # exception from escaping through Tk variable-trace callbacks.
    assert [result.action for result in density.values()] == ["dot", "dot"]
    assert [result.action for result in contour.values()] == ["dot", "dot"]
    assert all(result.error is None for result in density.values())
    assert all(result.error is None for result in contour.values())
    assert app._density_cache == {}
    assert app._contour_cache == {}
