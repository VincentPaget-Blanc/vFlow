"""Shared plotting/performance helpers."""

from __future__ import annotations

import functools

import numpy as np


@functools.lru_cache(maxsize=256)
def hex_to_rgba(hex_color: str, alpha: float) -> np.ndarray:
    """Convert a '#rrggbb' or '#rgb' color to an immutable float32 RGBA array."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    arr = np.array([r, g, b, float(alpha)], dtype=np.float32)
    arr.flags.writeable = False
    return arr


def get_rng(seed: int) -> np.random.Generator:
    """Return a fresh fixed-seed generator for deterministic subsampling."""
    return np.random.default_rng(seed)


def set_spines_color(ax, color: str) -> None:
    """Set all axes spine colors."""
    for spine in ax.spines.values():
        spine.set_color(color)


def sampled_indices(length: int, cap: int, *, seed: int) -> np.ndarray | None:
    """Return deterministic sampled indices when length exceeds cap."""
    if length <= cap:
        return None
    return get_rng(seed).choice(length, cap, replace=False)


def apply_sample_indices(*arrays, indices):
    """Apply an optional index array to each array."""
    if indices is None:
        return arrays
    return tuple(array[indices] for array in arrays)


def valid_values(values: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Return values selected by a validity mask."""
    return values[valid]


def evict_oldest_cache_entries(cache: dict, *, max_entries: int, evict_count: int) -> None:
    """Evict the oldest cache entries when a dict-like cache reaches capacity."""
    if len(cache) < max_entries:
        return
    for key in list(cache)[:evict_count]:
        del cache[key]


GMM_COMPONENT_COLORS = [
    "#ff6b6b",
    "#74d7e8",
    "#ffd93d",
    "#6bcb77",
    "#c77dff",
    "#ff9a3c",
    "#4d96ff",
    "#ff6bcd",
    "#4ecdc4",
    "#a3e048",
]


def gmm_component_label(index: int, mean_raw: float, weight: float) -> str:
    """Return the legacy GMM overlay legend label for one component."""
    return f"C{index + 1}  \u03bc={mean_raw:,.0f}  w={weight:.2f}"


def gmm_overlay_legend_layout(orientation: str, n_components: int) -> tuple:
    """Return legacy (bbox, loc, ncol) for GMM overlay legends."""
    if orientation == "horizontal":
        bbox = (0.0, 1.0)
        loc = "upper left"
    else:
        bbox = (1.0, 0.0)
        loc = "lower right"
    return bbox, loc, 2 if n_components > 3 else 1


def gmm_overlay_curves(
    gmm_params: dict,
    *,
    inverse_transform,
    n_total: int,
    n_bins: int = 120,
    n_points: int = 1024,
) -> list[dict]:
    """Return curve data for legacy GMM marginal overlays."""
    from scipy.stats import norm as _norm

    means_t = gmm_params["means_t"]
    means_raw = gmm_params["means_raw"]
    weights = gmm_params["weights"]
    stds_t = gmm_params["stds_t"]
    scale = gmm_params["scale"]
    lo_t, hi_t = gmm_params["data_range_t"]

    x_t = np.linspace(lo_t, hi_t, n_points)
    x_raw = inverse_transform(x_t, scale)
    bw_t = (hi_t - lo_t) / n_bins
    scale_factor = n_total * bw_t

    curves = []
    for i, mean_t in enumerate(means_t):
        pdf_t = weights[i] * _norm.pdf(x_t, mean_t, stds_t[i])
        curves.append(
            {
                "x_raw": x_raw,
                "pdf_count": pdf_t * scale_factor,
                "color": GMM_COMPONENT_COLORS[i % len(GMM_COMPONENT_COLORS)],
                "label": gmm_component_label(i, means_raw[i], weights[i]),
            }
        )
    return curves


def threshold_band_labels(fluorophore: str, n_bands: int) -> list[str]:
    """Return legacy marginal threshold-band labels."""
    if n_bands <= 0:
        return []
    if n_bands == 1:
        return [fluorophore]
    if n_bands == 2:
        return [f"{fluorophore}\u2212", f"{fluorophore}+"]
    if n_bands == 3:
        return [f"{fluorophore}\u2212", f"{fluorophore}(m)", f"{fluorophore}+"]
    mids = [f"{fluorophore}(m{i})" for i in range(1, n_bands - 1)]
    return [f"{fluorophore}\u2212"] + mids + [f"{fluorophore}+"]


def threshold_band_boundaries(axis_limits: tuple, thresholds_raw: list) -> list:
    """Return sorted marginal band boundaries from axis limits and thresholds."""
    lo_raw, hi_raw = axis_limits
    return [lo_raw] + sorted(thresholds_raw) + [hi_raw]
