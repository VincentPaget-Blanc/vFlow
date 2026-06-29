"""Auto-gating threshold helpers."""

from __future__ import annotations

import numpy as np

_RNG: dict = {}


def _get_rng(seed: int) -> np.random.Generator:
    if seed not in _RNG:
        _RNG[seed] = np.random.default_rng(seed)
    return _RNG[seed]


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
    data = data[np.isfinite(data)]
    if len(data) == 0:
        return 0.0
    if len(data) < 10:
        return float(np.percentile(data, 10))

    from scipy.signal import savgol_filter
    from scipy.stats import gaussian_kde

    kde_max = 30_000
    if len(data) > kde_max:
        data = data[_get_rng(7).choice(len(data), kde_max, replace=False)]

    try:
        kde = gaussian_kde(data, bw_method="scott")
        if bw_factor != 1.0:
            kde.set_bandwidth(bw_method=kde.factor * bw_factor)
    except (np.linalg.LinAlgError, ValueError):
        return float(np.percentile(data, 5))

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

    main_peak = int(np.argmax(y_s))
    level = 0.05 * peak_val
    for i in range(main_peak - 1, -1, -1):
        if y_s[i] <= level:
            return float(x[i])
    return float(np.percentile(data, 5))


def otsu_threshold(
    data: np.ndarray,
    n_bins: int = 512,
    min_class_fraction: float = 0.0,
) -> float:
    """Otsu threshold in transform space."""
    data = data[np.isfinite(data)]
    if len(data) < 2:
        return float(np.median(data)) if len(data) else 0.0

    hist, bin_edges = np.histogram(data, bins=n_bins)
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
    if min_class_fraction > 0:
        too_small = (w0 < min_class_fraction) | (w1 < min_class_fraction)
        between_var = np.where(too_small, -1.0, between_var)
    idx = int(np.argmax(between_var))
    return float(bin_centers[idx])
