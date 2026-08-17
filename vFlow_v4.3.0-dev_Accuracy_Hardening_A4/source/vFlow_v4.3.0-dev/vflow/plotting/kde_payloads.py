"""Pure numerical KDE render-payload helpers.

Architecture / Performance 07 keeps SciPy/NumPy KDE work away from Tk and
Matplotlib so independent cold-file payloads can be computed concurrently.
Workers never mutate application/cache state; callers commit results later in
the historical display-file order.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import os
from typing import Callable, Sequence

import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.stats import gaussian_kde

from vflow.config.constants import KDE_SUBSAMPLE, RENDER_CAP
from vflow.core.transforms import inverse_transform
from vflow.plotting.utils import (
    apply_sample_indices,
    sampled_indices,
    valid_values,
)

KDE_PRECOMPUTE_MAX_WORKERS = min(4, os.cpu_count() or 1)


@dataclass(frozen=True)
class KDERenderComputation:
    """One pure numerical render computation result.

    ``action`` is one of ``payload``, ``dot``, ``skip``, or ``error``.
    Expected singular-KDE conditions are represented by ``dot`` exactly like
    the historical plotting helpers. Unexpected exceptions are captured only
    by the parallel orchestration wrapper and re-raised later by the main
    render loop in deterministic display-file order.
    """

    action: str
    payload: object = None
    error: Exception | None = None


def compute_density_render_payload(
    x_raw: np.ndarray,
    y_raw: np.ndarray,
    xt: np.ndarray,
    yt: np.ndarray,
    valid: np.ndarray,
) -> KDERenderComputation:
    """Return the frozen Density numerical display payload without drawing."""
    xv = valid_values(xt, valid)
    yv = valid_values(yt, valid)
    if len(xv) < 2 or len(yv) < 2:
        return KDERenderComputation("dot")

    xlo, xhi = np.nanpercentile(xv, [1, 99])
    ylo, yhi = np.nanpercentile(yv, [1, 99])
    core = (xv >= xlo) & (xv <= xhi) & (yv >= ylo) & (yv <= yhi)
    xc = xv[core]
    yc = yv[core]
    n = len(xc)
    if n < 2:
        return KDERenderComputation("skip")

    try:
        idx = sampled_indices(n, KDE_SUBSAMPLE, seed=0)
        if idx is not None:
            kern = gaussian_kde(np.vstack([xc[idx], yc[idx]]))
        else:
            kern = gaussian_kde(np.vstack([xc, yc]))
    except (np.linalg.LinAlgError, ValueError):
        return KDERenderComputation("dot")

    grid = 96
    xg = np.linspace(xlo, xhi, grid)
    yg = np.linspace(ylo, yhi, grid)
    xmg, ymg = np.meshgrid(xg, yg, indexing="ij")
    z = kern(np.vstack([xmg.ravel(), ymg.ravel()])).reshape(grid, grid)
    interp = RegularGridInterpolator(
        (xg, yg), z, method="linear",
        bounds_error=False, fill_value=float(z.min()),
    )
    density = interp(np.column_stack([xv, yv]))

    xr = valid_values(x_raw, valid)
    yr = valid_values(y_raw, valid)
    n_valid = len(xr)
    keep = sampled_indices(n_valid, RENDER_CAP, seed=3)
    if keep is not None:
        xr = xr[keep]
        yr = yr[keep]
        dens_plot = density[keep]
    else:
        dens_plot = density
    order = np.argsort(dens_plot)
    vlo, vhi = np.nanpercentile(density, [1, 99])
    return KDERenderComputation(
        "payload",
        (
            xr[order], yr[order], dens_plot[order],
            float(vlo), float(vhi), n_valid,
        ),
    )


def compute_contour_surface_payload(
    xt: np.ndarray,
    yt: np.ndarray,
    valid: np.ndarray,
    *,
    x_scale: str,
    y_scale: str,
    cofactor: float,
    x_transform_params: dict | None = None,
    y_transform_params: dict | None = None,
) -> KDERenderComputation:
    """Return the frozen probability-independent Contour KDE/grid payload."""
    xv = valid_values(xt, valid)
    yv = valid_values(yt, valid)
    n = len(xv)
    if n < 20:
        return KDERenderComputation("dot")

    try:
        idx = sampled_indices(n, KDE_SUBSAMPLE, seed=0)
        if idx is not None:
            kern = gaussian_kde(np.vstack([xv[idx], yv[idx]]))
        else:
            kern = gaussian_kde(np.vstack([xv, yv]))
    except (np.linalg.LinAlgError, ValueError):
        return KDERenderComputation("dot")

    grid = 96
    xg_t = np.linspace(xv.min(), xv.max(), grid)
    yg_t = np.linspace(yv.min(), yv.max(), grid)
    xmg, ymg = np.meshgrid(xg_t, yg_t, indexing="ij")
    z = kern(np.vstack([xmg.ravel(), ymg.ravel()])).reshape(grid, grid)
    xg_raw = inverse_transform(
        xmg, x_scale, cofactor, transform_params=x_transform_params)
    yg_raw = inverse_transform(
        ymg, y_scale, cofactor, transform_params=y_transform_params)
    return KDERenderComputation(
        "payload",
        (
            xg_t, yg_t, xg_raw, yg_raw, z,
            None, None, None, None, None,
        ),
    )


def _capture_job(function: Callable, args: tuple, kwargs: dict) -> KDERenderComputation:
    try:
        return function(*args, **kwargs)
    except Exception as exc:  # deterministic main-thread re-raise by caller
        return KDERenderComputation("error", error=exc)


def compute_kde_jobs_parallel(
    jobs: Sequence[tuple[object, Callable, tuple, dict]],
    *,
    max_workers: int = KDE_PRECOMPUTE_MAX_WORKERS,
) -> dict:
    """Compute independent KDE jobs concurrently and return keyed results.

    The returned mapping follows the input sequence order. With fewer than two
    jobs the caller should normally keep the historical direct path; accepting
    one job here remains useful to focused tests and returns the same result.
    """
    jobs = list(jobs)
    if not jobs:
        return {}
    workers = max(1, min(int(max_workers), len(jobs)))
    if workers == 1:
        return {
            key: _capture_job(function, args, kwargs)
            for key, function, args, kwargs in jobs
        }
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="vflow-kde") as executor:
        futures = [
            executor.submit(_capture_job, function, args, kwargs)
            for _, function, args, kwargs in jobs
        ]
        return {
            job[0]: future.result()
            for job, future in zip(jobs, futures)
        }
