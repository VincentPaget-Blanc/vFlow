"""Auto-gating threshold helpers."""

from __future__ import annotations

import numpy as np

def _get_rng(seed: int) -> np.random.Generator:
    """Return a fresh fixed-seed generator so repeated analyses are reproducible."""
    return np.random.default_rng(seed)


def sensitivity_parameters(sensitivity: float) -> dict:
    """Map the legacy 1-10 sensitivity slider to auto-gate parameters."""
    s = float(sensitivity)
    t = (s - 1.0) / 9.0
    gmm_max_comp = max(2, min(8, round(2 + t * 6)))
    kde_prominence = 200.0 * (1.001 / 200.0) ** t
    mv_prominence = 100.0 * (1.0 / 100.0) ** t
    bw_factor = 5.0 * (0.05 / 5.0) ** t
    min_peak_frac = 0.15 * (0.001 / 0.15) ** t
    otsu_min_frac = 0.25 * (0.0005 / 0.25) ** t

    return {
        "gmm_max_comp": gmm_max_comp,
        "kde_prominence": max(1.001, kde_prominence),
        "mv_prominence": max(1.0, mv_prominence),
        "bw_factor": max(0.05, bw_factor),
        "min_peak_frac": max(0.001, min_peak_frac),
        "otsu_min_frac": max(0.0005, otsu_min_frac),
    }


def finite_transformed_channel_values(
    dataframes,
    channel: str,
    scale: str,
    *,
    cofactor: float,
    transform_params: dict | None = None,
) -> np.ndarray:
    """Collect finite transformed channel values across active DataFrames."""
    from vflow.core.transforms import forward_transform

    parts = []
    for df in dataframes:
        if channel not in df.columns:
            continue
        values = df[channel].to_numpy(dtype=float, copy=False)
        transformed = forward_transform(
            values, scale, cofactor, transform_params=transform_params)
        parts.append(transformed[np.isfinite(transformed)])
    return np.concatenate(parts) if parts else np.array([])


def finite_raw_channel_values(dataframes, channel: str) -> np.ndarray:
    """Collect finite raw channel values across active DataFrames."""
    parts = []
    for df in dataframes:
        if channel not in df.columns:
            continue
        values = df[channel].to_numpy(dtype=float, copy=False)
        parts.append(values[np.isfinite(values)])
    return np.concatenate(parts) if parts else np.array([])



def finite_displayable_raw_channel_values(
    dataframes,
    channel: str,
    scale: str,
    *,
    cofactor: float,
    transform_params: dict | None = None,
) -> np.ndarray:
    """Collect raw values whose selected-axis transform is finite/displayable."""
    from vflow.core.transforms import forward_transform

    parts = []
    for df in dataframes:
        if channel not in df.columns:
            continue
        values = df[channel].to_numpy(dtype=float, copy=False)
        transformed = forward_transform(
            values, scale, cofactor, transform_params=transform_params)
        valid = np.isfinite(values) & np.isfinite(transformed)
        parts.append(values[valid])
    return np.concatenate(parts) if parts else np.array([])


def percent_at_or_below(values: np.ndarray, threshold: float) -> float:
    """Return percentage of finite values in the lower (<= threshold) gate band."""
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return 0.0
    return float(np.mean(values <= threshold)) * 100.0

def percent_below(values: np.ndarray, threshold: float) -> float:
    """Return percent of finite raw values below a threshold."""
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return 0.0
    return float(np.mean(values < threshold)) * 100.0


def two_axis_threshold_status(
    method_label: str,
    *,
    x_threshold: float,
    y_threshold: float,
    x_percent_below: float,
    y_percent_below: float,
) -> str:
    """Return the legacy status line for two-axis auto-gate methods."""
    return (
        f"\u2713 {method_label}: X @ {x_threshold:,.0f} "
        f"({x_percent_below:.1f}% at/below)"
        f"  |  Y @ {y_threshold:,.0f} ({y_percent_below:.1f}% at/below)"
    )


def cluster_min_fraction(sensitivity: float) -> float:
    """Return legacy HDBSCAN/DBSCAN min-cluster fraction for sensitivity."""
    t = (float(sensitivity) - 1.0) / 9.0
    return 0.10 * (0.003 / 0.10) ** t


def cluster_size_parameters(n_points: int, min_fraction: float) -> tuple[int, int]:
    """Return legacy (min_cluster_size, min_samples) for cluster auto-gate."""
    min_cluster_size = max(5, int(min_fraction * n_points))
    min_samples = max(3, min_cluster_size // 5)
    return min_cluster_size, min_samples


def normalize_points_unit_square(points: np.ndarray) -> np.ndarray:
    """Normalize 2D points to the legacy [0, 1] square coordinate system."""
    mins = points.min(axis=0)
    maxs = points.max(axis=0)
    ranges = np.where(maxs > mins, maxs - mins, 1.0)
    return (points - mins) / ranges


def dbscan_eps_from_neighbor_distances(distances: np.ndarray) -> float:
    """Return the legacy DBSCAN fallback eps from nearest-neighbor distances."""
    eps = float(np.percentile(distances[:, 1], 10)) * 2.0
    return max(eps, 0.01)


def cluster_polygons_status(
    *,
    algorithm: str,
    gates_created: int,
    noise_count: int,
    labels_count: int,
) -> str:
    """Return the legacy cluster-polygons completion status line."""
    noise_pct = noise_count / labels_count * 100 if labels_count else 0.0
    return (
        f"\u2713 Cluster Polygons ({algorithm}): {gates_created} gate(s)"
        + (f"  |  {noise_pct:.1f}% noise points" if noise_count > 0 else "")
    )




class ClusterPolygonInsufficientData(ValueError):
    """Raised when cluster auto-gating has fewer than 20 valid 2-D points."""


class ClusterPolygonPrepared:
    """Prepared deterministic cluster input with v4.2 sampling semantics."""

    __slots__ = (
        "transformed_x", "transformed_y", "raw_x", "raw_y", "points_normalized",
        "min_cluster_size", "min_samples", "n_total",
    )

    def __init__(self, *, transformed_x, transformed_y, raw_x, raw_y,
                 points_normalized, min_cluster_size, min_samples, n_total):
        self.transformed_x = transformed_x
        self.transformed_y = transformed_y
        self.raw_x = raw_x
        self.raw_y = raw_y
        self.points_normalized = points_normalized
        self.min_cluster_size = int(min_cluster_size)
        self.min_samples = int(min_samples)
        self.n_total = int(n_total)


class ClusterPolygonComputation:
    """Pure cluster-polygons result used by the Tk orchestration layer."""

    __slots__ = (
        "algorithm_tag", "algorithm_label", "polygons", "noise_count",
        "labels_count", "n_total", "cluster_count",
    )

    def __init__(self, *, algorithm_tag, algorithm_label, polygons,
                 noise_count, labels_count, n_total, cluster_count):
        self.algorithm_tag = algorithm_tag
        self.algorithm_label = algorithm_label
        self.polygons = polygons
        self.noise_count = int(noise_count)
        self.labels_count = int(labels_count)
        self.n_total = int(n_total)
        self.cluster_count = int(cluster_count)


def kde_valley_supported(
    data: np.ndarray,
    threshold: float,
    bw_factor: float,
    min_prominence: float,
    min_peak_frac: float,
) -> bool:
    """Return whether a KDE threshold is backed by a genuine two-sided valley.

    This is the exact v4.2 validator previously embedded in ``FlowApp``.  It
    intentionally rejects tail-percentile fallbacks that are not supported by
    substantive peaks on both sides of the candidate valley.
    """
    from scipy.signal import savgol_filter
    from scipy.stats import gaussian_kde

    vals = np.asarray(data, float)
    vals = vals[np.isfinite(vals)]
    if len(vals) < 10 or np.ptp(vals) <= 1e-12:
        return False
    try:
        kde = gaussian_kde(vals, bw_method="scott")
        if bw_factor != 1.0:
            kde.set_bandwidth(bw_method=kde.factor * bw_factor)
        grid = np.linspace(float(vals.min()), float(vals.max()), 2048)
        dens = kde(grid)
        win = min(51, max(5, (len(dens) // 10) | 1))
        smooth = savgol_filter(dens, window_length=win, polyorder=3)
        dy = np.gradient(smooth, grid)
    except (np.linalg.LinAlgError, ValueError, FloatingPointError):
        return False
    peaks = np.where(np.diff(np.sign(dy)) < 0)[0]
    valleys = np.where(np.diff(np.sign(dy)) > 0)[0]
    if len(peaks) < 2 or len(valleys) == 0:
        return False
    vi = int(valleys[np.argmin(np.abs(grid[valleys] - float(threshold)))])
    step = abs(grid[1] - grid[0]) if len(grid) > 1 else np.inf
    if abs(float(grid[vi]) - float(threshold)) > max(step * 4.0, 1e-12):
        return False
    left = peaks[peaks < vi]
    right = peaks[peaks > vi]
    if len(left) == 0 or len(right) == 0:
        return False
    li = left[np.argmax(smooth[left])]
    ri = right[np.argmax(smooth[right])]
    valley_height = max(float(smooth[vi]), 1e-12)
    peak_height = max(float(np.max(smooth)), 1e-12)
    return bool(
        smooth[li] >= min_prominence * valley_height
        and smooth[ri] >= min_prominence * valley_height
        and smooth[li] >= min_peak_frac * peak_height
        and smooth[ri] >= min_peak_frac * peak_height
    )


def prepare_cluster_polygon_data(
    transformed_x: np.ndarray,
    transformed_y: np.ndarray,
    raw_x: np.ndarray,
    raw_y: np.ndarray,
    *,
    min_fraction: float,
    max_points: int = 10_000,
) -> ClusterPolygonPrepared:
    """Prepare the exact v4.2 finite/subsampled/normalized clustering payload."""
    xt_all = np.asarray(transformed_x)
    yt_all = np.asarray(transformed_y)
    xr_all = np.asarray(raw_x)
    yr_all = np.asarray(raw_y)

    valid = np.isfinite(xt_all) & np.isfinite(yt_all)
    xt, yt = xt_all[valid], yt_all[valid]
    xr, yr = xr_all[valid], yr_all[valid]
    n_total = len(xt)
    if n_total < 20:
        raise ClusterPolygonInsufficientData("Not enough data.")

    if n_total > max_points:
        idx = _get_rng(42).choice(n_total, max_points, replace=False)
        xt_s, yt_s = xt[idx], yt[idx]
        xr_s, yr_s = xr[idx], yr[idx]
    else:
        xt_s, yt_s = xt, yt
        xr_s, yr_s = xr, yr

    points_normalized = normalize_points_unit_square(
        np.column_stack([xt_s, yt_s])
    )
    min_cluster_size, min_samples = cluster_size_parameters(
        len(xt_s), min_fraction
    )
    return ClusterPolygonPrepared(
        transformed_x=xt_s,
        transformed_y=yt_s,
        raw_x=xr_s,
        raw_y=yr_s,
        points_normalized=points_normalized,
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        n_total=n_total,
    )


def fit_cluster_polygons(
    prepared: ClusterPolygonPrepared,
    *,
    hdbscan_cls,
    dbscan_cls,
    convex_hull_cls,
) -> ClusterPolygonComputation:
    """Fit HDBSCAN/DBSCAN and map transform-space hulls back to raw vertices."""
    if hdbscan_cls is not None:
        clust = hdbscan_cls(
            min_cluster_size=prepared.min_cluster_size,
            min_samples=prepared.min_samples,
            cluster_selection_method="eom",
        ).fit(prepared.points_normalized)
        algorithm_tag = "hdbscan"
        algorithm_label = "HDBSCAN"
    else:
        from sklearn.neighbors import NearestNeighbors

        nbrs = NearestNeighbors(n_neighbors=2).fit(prepared.points_normalized)
        dists, _ = nbrs.kneighbors(prepared.points_normalized)
        eps = dbscan_eps_from_neighbor_distances(dists)
        clust = dbscan_cls(
            eps=eps, min_samples=prepared.min_samples
        ).fit(prepared.points_normalized)
        algorithm_tag = "dbscan"
        algorithm_label = "DBSCAN"

    labels = clust.labels_
    unique_labels = [label for label in set(labels) if label != -1]
    polygons = []
    for cluster_label in sorted(unique_labels):
        mask = labels == cluster_label
        cxt = prepared.transformed_x[mask]
        cyt = prepared.transformed_y[mask]
        cxr = prepared.raw_x[mask]
        cyr = prepared.raw_y[mask]
        pts_t = np.column_stack([cxt, cyt])
        if len(pts_t) < 3:
            continue
        try:
            hull = convex_hull_cls(pts_t)
            hv_idx = hull.vertices
            vx_raw = cxr[hv_idx]
            vy_raw = cyr[hv_idx]
            verts = list(zip(vx_raw.tolist(), vy_raw.tolist()))
        except Exception:
            # A failed hull means this cluster cannot be represented faithfully
            # as the polygon gate requested by this method.  The legacy
            # bounding-box fallback silently enlarged degenerate/collinear
            # clusters and could include events that were never members of the
            # fitted cluster.  Fail closed for that cluster instead.
            continue
        polygons.append(tuple((float(x), float(y)) for x, y in verts))

    return ClusterPolygonComputation(
        algorithm_tag=algorithm_tag,
        algorithm_label=algorithm_label,
        polygons=tuple(polygons),
        noise_count=int((labels == -1).sum()),
        labels_count=len(labels),
        n_total=prepared.n_total,
        # Count only clusters that produced a faithful polygon.  This lets the
        # UI take its existing no-cluster path before replacing prior auto gates
        # when every fitted cluster is geometrically unrepresentable.
        cluster_count=len(polygons),
    )


def compute_cluster_polygons(
    transformed_x: np.ndarray,
    transformed_y: np.ndarray,
    raw_x: np.ndarray,
    raw_y: np.ndarray,
    *,
    min_fraction: float,
    hdbscan_cls,
    dbscan_cls,
    convex_hull_cls,
    max_points: int = 10_000,
) -> ClusterPolygonComputation:
    """Convenience composition of preparation + fit for non-UI callers."""
    prepared = prepare_cluster_polygon_data(
        transformed_x,
        transformed_y,
        raw_x,
        raw_y,
        min_fraction=min_fraction,
        max_points=max_points,
    )
    return fit_cluster_polygons(
        prepared,
        hdbscan_cls=hdbscan_cls,
        dbscan_cls=dbscan_cls,
        convex_hull_cls=convex_hull_cls,
    )


def gmm_component_count(value) -> int:
    """Clamp a requested GMM component count to the legacy 1-8 range."""
    return max(1, min(8, int(value)))


def gmm_multi_status(
    *,
    x_components: int,
    x_crossings: int,
    y_components: int,
    y_crossings: int,
) -> str:
    """Return the legacy GMM Multi completion status line."""
    return (
        f"\u2713 GMM Multi \u2014 X: {x_components} comp \u2192 "
        f"{x_crossings} crossing(s)  "
        f"|  Y: {y_components} comp \u2192 {y_crossings} crossing(s)  "
        "|  Uncheck unwanted thresholds in the Threshold panel"
    )


def weighted_gaussian_crossing_between_means(
    left_mean: float,
    left_std: float,
    left_weight: float,
    right_mean: float,
    right_std: float,
    right_weight: float,
) -> float | None:
    """Return the supported weighted-Gaussian crossing between adjacent means.

    A separator is accepted only when the left component dominates at the left
    mean and the right component dominates at the right mean.  Without that
    bracketing condition there is no unambiguous adjacent-population crossing
    between the fitted means, so ``None`` is returned instead of a nearest-grid
    surrogate.
    """
    from scipy.optimize import brentq

    values = np.asarray(
        [left_mean, left_std, left_weight, right_mean, right_std, right_weight],
        dtype=float,
    )
    if not np.isfinite(values).all():
        return None
    lm, ls, lw, rm, rs, rw = (float(value) for value in values)
    if not (lm < rm and ls > 0.0 and rs > 0.0 and lw > 0.0 and rw > 0.0):
        return None

    def log_density_difference(x: float) -> float:
        left = np.log(lw) - np.log(ls) - ((x - lm) ** 2) / (2.0 * ls**2)
        right = np.log(rw) - np.log(rs) - ((x - rm) ** 2) / (2.0 * rs**2)
        return float(left - right)

    at_left = log_density_difference(lm)
    at_right = log_density_difference(rm)
    if not (np.isfinite(at_left) and np.isfinite(at_right)):
        return None
    if at_left <= 0.0 or at_right >= 0.0:
        return None

    try:
        crossing = float(brentq(log_density_difference, lm, rm))
    except (RuntimeError, ValueError):
        return None
    if not np.isfinite(crossing) or not (lm < crossing < rm):
        return None
    return crossing


def fit_gmm_crossings(
    data_t: np.ndarray,
    n_components: int,
    scale_name: str,
    inverse_transform,
) -> tuple[list[float], str, dict | None]:
    """Fit exact-N 1D GMM and return raw equal-density crossings plus metadata."""
    from sklearn.mixture import GaussianMixture

    data_t = data_t[np.isfinite(data_t)]
    if len(data_t) < max(10, n_components * 3):
        return [], "not enough data", None

    max_points = 30_000
    if len(data_t) > max_points:
        data_t = data_t[_get_rng(42).choice(len(data_t), max_points, replace=False)]

    data_2d = data_t.reshape(-1, 1)
    best_ll, best_gmm = -np.inf, None
    for seed in range(5):
        for init in ("kmeans", "random"):
            try:
                gmm = GaussianMixture(
                    n_components=n_components,
                    covariance_type="full",
                    n_init=3,
                    init_params=init,
                    random_state=seed,
                )
                gmm.fit(data_2d)
                ll = gmm.score(data_2d)
                if ll > best_ll:
                    best_ll, best_gmm = ll, gmm
            except Exception:
                pass

    if best_gmm is None:
        return [], "fit failed", None

    order = np.argsort(best_gmm.means_.flatten())
    means = best_gmm.means_.flatten()[order]
    weights = best_gmm.weights_[order]
    stds = np.sqrt(best_gmm.covariances_.reshape(n_components, -1)[:, 0][order])

    thresholds_raw = []
    for i in range(n_components - 1):
        threshold_t = weighted_gaussian_crossing_between_means(
            means[i], stds[i], weights[i],
            means[i + 1], stds[i + 1], weights[i + 1],
        )
        if threshold_t is None:
            continue
        thresholds_raw.append(float(inverse_transform(np.array([threshold_t]), scale_name)[0]))

    means_raw = [
        float(inverse_transform(np.array([mean]), scale_name)[0])
        for mean in means
    ]
    summary = "  |  ".join(
        f"C{i + 1} \u03bc\u2248{means_raw[i]:,.0f} w={weights[i]:.0%}"
        for i in range(n_components)
    )
    params = {
        "means_t": [float(mean) for mean in means],
        "means_raw": means_raw,
        "weights": [float(weight) for weight in weights],
        "stds_t": [float(std) for std in stds],
        "scale": scale_name,
        "data_range_t": (float(data_t.min()), float(data_t.max())),
        "n_data": len(data_t),
    }
    return thresholds_raw, summary, params


def gmm_thresholds(data: np.ndarray, max_components: int = 3) -> list:
    """BIC-best 1D GMM threshold valleys between adjacent components."""
    try:
        from scipy.stats import norm as _norm
        from sklearn.mixture import GaussianMixture
    except ImportError as exc:
        raise RuntimeError("scikit-learn required: pip install scikit-learn") from exc

    data = data[np.isfinite(data)]
    if len(data) < 10:
        return []

    gmm_max_fit = 30_000
    if len(data) > gmm_max_fit:
        data = data[_get_rng(42).choice(len(data), gmm_max_fit, replace=False)]
    data = data.reshape(-1, 1)

    best_bic, best_gmm, best_n = np.inf, None, 1
    for n in range(1, max_components + 1):
        try:
            g = GaussianMixture(
                n_components=n,
                n_init=5,
                covariance_type="full",
                random_state=42,
            )
            g.fit(data)
            b = g.bic(data)
            if b < best_bic:
                best_bic, best_gmm, best_n = b, g, n
        except Exception:
            pass
    if best_n == 1 or best_gmm is None:
        return []

    order = np.argsort(best_gmm.means_.flatten())
    means = best_gmm.means_.flatten()[order]
    weights = best_gmm.weights_[order]
    stds = np.sqrt(best_gmm.covariances_[order][:, 0, 0])
    thresholds = []
    for i in range(best_n - 1):
        lo_x = means[i] - 3 * stds[i]
        hi_x = means[i + 1] + 3 * stds[i + 1]
        x = np.linspace(lo_x, hi_x, 2000)
        dens = sum(weights[j] * _norm.pdf(x, means[j], stds[j]) for j in range(best_n))
        lo_idx = int(np.searchsorted(x, means[i]))
        hi_idx = int(np.searchsorted(x, means[i + 1]))
        if hi_idx > lo_idx:
            thresholds.append(float(x[lo_idx + np.argmin(dens[lo_idx:hi_idx])]))
        else:
            thresholds.append(float((means[i] + means[i + 1]) / 2.0))
    return thresholds


def derivative_threshold(
    data: np.ndarray,
    min_prominence: float = 5.0,
    bw_factor: float = 1.0,
    min_peak_frac: float = 0.01,
) -> float:
    """Find a gate threshold separating populations via KDE valley detection."""
    data = np.asarray(data, dtype=float)
    data = data[np.isfinite(data)]
    if len(data) < 10:
        raise ValueError("KDE valley detection requires at least 10 finite values.")
    if not np.isfinite(np.ptp(data)) or np.ptp(data) <= 1e-12:
        raise ValueError("KDE valley detection requires a non-degenerate distribution.")

    from scipy.signal import savgol_filter
    from scipy.stats import gaussian_kde

    kde_max = 30_000
    if len(data) > kde_max:
        data = data[_get_rng(7).choice(len(data), kde_max, replace=False)]

    try:
        kde = gaussian_kde(data, bw_method="scott")
        if bw_factor != 1.0:
            kde.set_bandwidth(bw_method=kde.factor * bw_factor)
    except (np.linalg.LinAlgError, ValueError) as exc:
        raise ValueError("KDE could not be fitted to this distribution.") from exc

    x = np.linspace(data.min(), data.max(), 2048)
    y = kde(x)
    win = min(51, max(5, (len(y) // 10) | 1))
    y_s = savgol_filter(y, window_length=win, polyorder=3)
    dy = np.gradient(y_s, x)
    peak_val = float(np.max(y_s))

    peak_idx_all = np.where(np.diff(np.sign(dy)) < 0)[0]
    valley_idx_all = np.where(np.diff(np.sign(dy)) > 0)[0]

    valid_valleys = []
    for vi in valley_idx_all:
        left_peaks = peak_idx_all[peak_idx_all < vi]
        right_peaks = peak_idx_all[peak_idx_all > vi]
        if len(left_peaks) == 0 or len(right_peaks) == 0:
            continue
        vdepth = max(float(y_s[vi]), 1e-12)
        li = left_peaks[np.argmax(y_s[left_peaks])]
        ri = right_peaks[np.argmax(y_s[right_peaks])]
        lbest = float(y_s[li])
        rbest = float(y_s[ri])
        if (
            lbest >= min_prominence * vdepth
            and rbest >= min_prominence * vdepth
            and lbest >= min_peak_frac * peak_val
            and rbest >= min_peak_frac * peak_val
        ):
            midpt = (float(x[li]) + float(x[ri])) / 2.0
            dist_mid = abs(float(x[vi]) - midpt)
            valid_valleys.append((vi, dist_mid))

    if valid_valleys:
        best_vi = min(valid_valleys, key=lambda t: t[1])[0]
        return float(x[best_vi])

    raise ValueError(
        "No supported two-population KDE valley was detected; refusing to "
        "substitute a tail percentile as a biological threshold."
    )


def otsu_threshold(
    data: np.ndarray,
    n_bins: int = 512,
    min_class_fraction: float = 0.0,
) -> float:
    """Otsu threshold in transform space."""
    data = np.asarray(data, dtype=float)
    data = data[np.isfinite(data)]
    if len(data) < 2:
        raise ValueError("Otsu thresholding requires at least two finite values.")
    if not np.isfinite(np.ptp(data)) or np.ptp(data) <= 1e-12:
        raise ValueError("Otsu thresholding requires a non-degenerate distribution.")
    if int(n_bins) < 2:
        raise ValueError("Otsu thresholding requires at least two histogram bins.")
    min_class_fraction = float(min_class_fraction)
    if not np.isfinite(min_class_fraction) or not (0.0 <= min_class_fraction < 0.5):
        raise ValueError("min_class_fraction must be finite and in [0, 0.5).")

    hist, bin_edges = np.histogram(data, bins=int(n_bins))
    hist = hist.astype(float)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    total = hist.sum()

    w0 = np.cumsum(hist) / total
    cm0 = np.cumsum(hist * bin_centers)
    mu0 = cm0 / (np.cumsum(hist) + 1e-12)

    total_mean = float(np.sum(hist * bin_centers) / total)
    w1 = 1.0 - w0
    mu1 = np.zeros_like(w1)
    np.divide(total_mean - w0 * mu0, w1, out=mu1, where=(w1 > 1e-9))

    between_var = w0 * w1 * (mu0 - mu1) ** 2
    valid_split = (w0 > 0.0) & (w1 > 0.0)
    if min_class_fraction > 0:
        valid_split &= (w0 >= min_class_fraction) & (w1 >= min_class_fraction)
    between_var = np.where(valid_split, between_var, -np.inf)
    if not np.isfinite(between_var).any():
        raise ValueError(
            "No Otsu split satisfies the requested minimum class fraction."
        )
    idx = int(np.argmax(between_var))
    return float(bin_centers[idx])
