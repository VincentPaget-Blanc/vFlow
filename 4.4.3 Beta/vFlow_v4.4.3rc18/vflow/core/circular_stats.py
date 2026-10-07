"""Circular statistics helpers for vector/polar analysis."""

from __future__ import annotations

import numpy as np

Y_ORIENTATION_CARTESIAN = "cartesian_y_up"
Y_ORIENTATION_IMAGE = "image_y_down"
VALID_Y_ORIENTATIONS = frozenset({Y_ORIENTATION_CARTESIAN, Y_ORIENTATION_IMAGE})
ANGLE_CONVENTION = "0 deg = +X; positive = counter-clockwise after Y-orientation normalization"


def normalize_y_orientation(value: str) -> str:
    if value not in VALID_Y_ORIENTATIONS:
        raise ValueError(
            f"Unsupported Y-coordinate orientation {value!r}; expected one of "
            f"{sorted(VALID_Y_ORIENTATIONS)}")
    return value



def common_columns(dataframes: list) -> list:
    """Return sorted column names common to all DataFrames."""
    sets = [set(df.columns) for df in dataframes]
    return sorted(set.intersection(*sets)) if sets else []


def mean_resultant_length(angles: np.ndarray) -> float:
    """Mean Resultant Length over finite angular observations."""
    angles = np.asarray(angles, dtype=float)
    angles = angles[np.isfinite(angles)]
    n = len(angles)
    if n == 0:
        return 0.0
    return float(
        np.sqrt(np.sum(np.cos(angles)) ** 2 + np.sum(np.sin(angles)) ** 2) / n
    )


def circular_mean_direction(angles: np.ndarray) -> float:
    """Circular mean direction in radians in (-pi, pi] over finite observations."""
    angles = np.asarray(angles, dtype=float)
    angles = angles[np.isfinite(angles)]
    if len(angles) == 0:
        return float("nan")
    mean_sin = float(np.mean(np.sin(angles)))
    mean_cos = float(np.mean(np.cos(angles)))
    # When the mean resultant is numerically zero, direction is undefined.
    # Returning atan2(tiny_roundoff, tiny_roundoff) would manufacture a
    # plausible-looking angle (e.g. 90° for an antipodal pair).
    if np.hypot(mean_sin, mean_cos) <= 64.0 * np.finfo(float).eps:
        return float("nan")
    return float(np.arctan2(mean_sin, mean_cos))


def rayleigh_p_value(angles: np.ndarray) -> float:
    """Rayleigh test p-value using the Zar approximation used by CircStat."""
    angles = np.asarray(angles, dtype=float)
    angles = angles[np.isfinite(angles)]
    n = len(angles)
    if n < 2:
        return 1.0
    r_bar = mean_resultant_length(angles)
    resultant = n * r_bar
    radicand = 1.0 + 4.0 * n + 4.0 * (n**2 - resultant**2)
    # R <= n theoretically; clamp only a possible tiny floating-point
    # undershoot of the non-negative radicand for perfectly aligned samples.
    p = np.exp(np.sqrt(max(0.0, radicand)) - (1.0 + 2.0 * n))
    return float(np.clip(p, 0.0, 1.0))


def is_directionally_significant(
    angles: np.ndarray,
    *,
    mrl_threshold: float,
    alpha: float = 0.05,
) -> bool:
    """Return True when Rayleigh p-value and MRL both meet significance criteria."""
    mrl = mean_resultant_length(angles)
    return bool(rayleigh_p_value(angles) < alpha and mrl >= mrl_threshold)


def vector_direction_stats(
    angles: np.ndarray,
    *,
    mrl_threshold: float,
    alpha: float = 0.05,
) -> dict:
    """Return the polar vector direction statistics used by display and export."""
    angles = np.asarray(angles, dtype=float)
    angles = angles[np.isfinite(angles)]
    n = len(angles)
    if n == 0:
        return {
            "n": 0,
            "mrl": None,
            "rayleigh_p": None,
            "mean_dir_deg": None,
            "significant": None,
        }
    mrl = mean_resultant_length(angles)
    p_value = rayleigh_p_value(angles)
    mean_direction = circular_mean_direction(angles)
    mean_dir_deg = (
        float(np.degrees(mean_direction)) if np.isfinite(mean_direction) else None
    )
    return {
        "n": n,
        "mrl": mrl,
        "rayleigh_p": p_value,
        "mean_dir_deg": mean_dir_deg,
        "significant": bool(p_value < alpha and mrl >= mrl_threshold),
    }


def format_rayleigh_p_value(p_value: float | None) -> str:
    """Format Rayleigh p-values for the polar stats tree."""
    if p_value is None:
        return "\u2014"
    return f"{p_value:.4f}" if p_value >= 0.0001 else "<0.0001"


def format_polar_stats_values(stats: dict) -> tuple:
    """Return the legacy polar stats tree values tuple."""
    if stats["n"] == 0:
        return ("0", "\u2014", "\u2014", "\u2014", "\u2014")
    sig = "\u2713" if stats["significant"] else "n.s."
    return (
        f"{stats['n']:,}",
        f"{stats['mrl']:.3f}",
        format_rayleigh_p_value(stats["rayleigh_p"]),
        (f"{stats['mean_dir_deg']:.1f}" if stats['mean_dir_deg'] is not None else "\u2014"),
        sig,
    )


def build_polar_stats_export_row(
    *,
    file_name: str,
    source_path: str = "",
    gate: str,
    region: str,
    angles: np.ndarray | None,
    mrl_threshold: float,
    x_ch1: str,
    y_ch1: str,
    x_ch2: str,
    y_ch2: str,
    y_coordinate_orientation: str = Y_ORIENTATION_CARTESIAN,
) -> dict:
    """Build one legacy polar vector statistics export row."""
    y_coordinate_orientation = normalize_y_orientation(y_coordinate_orientation)
    if angles is None:
        stats = vector_direction_stats(np.array([]), mrl_threshold=mrl_threshold)
    else:
        stats = vector_direction_stats(angles, mrl_threshold=mrl_threshold)
    row = {
        "File": file_name,
        "Source_Path": source_path,
        "Gate": gate,
        "Region": region,
        "N_vectors": stats["n"],
        "MRL": None,
        "Rayleigh_p": None,
        "Mean_dir_deg": None,
        "Significant": None,
        "X_Ch1": x_ch1,
        "Y_Ch1": y_ch1,
        "X_Ch2": x_ch2,
        "Y_Ch2": y_ch2,
        "Y_Coordinate_Orientation": y_coordinate_orientation,
        "Angle_Convention": ANGLE_CONVENTION,
    }
    if stats["n"] == 0:
        return row
    row["MRL"] = round(stats["mrl"], 6)
    row["Rayleigh_p"] = (
        round(stats["rayleigh_p"], 6)
        if stats["rayleigh_p"] >= 1e-6
        else stats["rayleigh_p"]
    )
    row["Mean_dir_deg"] = (
        round(stats["mean_dir_deg"], 3)
        if stats["mean_dir_deg"] is not None else None
    )
    row["Significant"] = stats["significant"]
    return row


def auto_detect_vector_columns(columns: list) -> tuple[str, str, str, str]:
    """Return legacy auto-detected x1, y1, x2, y2 vector coordinate columns."""

    import re

    def _unique_in_order(values):
        seen = set()
        out = []
        for value in values:
            if value not in seen:
                seen.add(value)
                out.append(value)
        return out

    x_cols = [
        col
        for col in columns
        if col.lower().startswith("x_")
        or "centroid_x" in col.lower()
        or ("centroid" in col.lower() and "x" in col.lower().split("_"))
    ]
    y_cols = [
        col
        for col in columns
        if col.lower().startswith("y_")
        or "centroid_y" in col.lower()
        or ("centroid" in col.lower() and "y" in col.lower().split("_"))
    ]

    x_cols = _unique_in_order(x_cols)
    y_cols = _unique_in_order(y_cols)

    x_microns = [col for col in x_cols if "micron" in col.lower()]
    y_microns = [col for col in y_cols if "micron" in col.lower()]
    if x_microns:
        x_cols = x_microns
    if y_microns:
        y_cols = y_microns

    def _axis_identity(column: str, axis: str) -> str:
        lower = column.lower()
        prefix = axis + "_"
        if lower.startswith(prefix):
            return lower[len(prefix):]
        marker = f"centroid_{axis}"
        if marker in lower:
            return lower.replace(marker, "centroid_", 1)
        parts = lower.split("_")
        if "centroid" in parts and axis in parts:
            removed = False
            kept = []
            for part in parts:
                if part == axis and not removed:
                    removed = True
                    continue
                kept.append(part)
            return "_".join(kept)
        return lower

    x_by_key: dict[str, str] = {}
    y_by_key: dict[str, str] = {}
    key_order: dict[str, int] = {}
    for index, column in enumerate(columns):
        if column in x_cols:
            key = _axis_identity(column, "x")
            x_by_key.setdefault(key, column)
            key_order.setdefault(key, index)
        if column in y_cols:
            key = _axis_identity(column, "y")
            y_by_key.setdefault(key, column)
            key_order.setdefault(key, index)

    paired_keys = [key for key in x_by_key if key in y_by_key]

    def _pair_sort_key(key: str):
        match = re.search(
            r"(?:^|[_-])(?:ch|channel)[_-]?(\d+)(?:[_-]|$)", key
        )
        if match:
            return (0, int(match.group(1)), key_order.get(key, 10**9))
        return (1, key_order.get(key, 10**9), key)

    if paired_keys:
        paired_keys.sort(key=_pair_sort_key)
        pairs = [(x_by_key[key], y_by_key[key]) for key in paired_keys]
        first = pairs[0]
        second = pairs[1] if len(pairs) >= 2 else first
        return first[0], first[1], second[0], second[1]

    # Do not guess across unrelated X/Y names. Positional fallback can silently
    # pair different objects/channels and produce entirely wrong vectors. If no
    # shared identity token exists, leave auto-detection blank so the user must
    # choose the four columns explicitly.
    return "", "", "", ""


def vectors_from_coordinate_columns(
    df,
    mask: np.ndarray,
    x1_col: str,
    y1_col: str,
    x2_col: str,
    y2_col: str,
    *,
    y_coordinate_orientation: str = Y_ORIENTATION_CARTESIAN,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Return vector angles/magnitudes using an explicit Y-coordinate convention.

    Output angles always use mathematical polar coordinates: 0 degrees is +X
    and positive angles are counter-clockwise. Image coordinates (+Y downward)
    are reflected to Cartesian +Y-up before ``atan2``.
    """
    y_coordinate_orientation = normalize_y_orientation(y_coordinate_orientation)
    for col in (x1_col, y1_col, x2_col, y2_col):
        if not col or col not in df.columns:
            return None, None
    mask = np.asarray(mask, dtype=bool)
    if mask.ndim != 1 or len(mask) != len(df):
        raise ValueError("Vector population mask must match the DataFrame row count.")
    sub = df.loc[mask, [x1_col, y1_col, x2_col, y2_col]]
    if len(sub) == 0:
        return np.array([]), np.array([])

    x1 = sub[x1_col].to_numpy(dtype=float, copy=False)
    y1 = sub[y1_col].to_numpy(dtype=float, copy=False)
    x2 = sub[x2_col].to_numpy(dtype=float, copy=False)
    y2 = sub[y2_col].to_numpy(dtype=float, copy=False)
    finite = np.isfinite(x1) & np.isfinite(y1) & np.isfinite(x2) & np.isfinite(y2)
    if not finite.any():
        return np.array([]), np.array([])

    dx = x2[finite] - x1[finite]
    dy = y2[finite] - y1[finite]
    if y_coordinate_orientation == Y_ORIENTATION_IMAGE:
        dy = -dy
    finite_vec = np.isfinite(dx) & np.isfinite(dy)
    dx = dx[finite_vec]
    dy = dy[finite_vec]
    magnitudes = np.hypot(dx, dy)
    # A zero-length displacement has no defined direction.  NumPy's
    # arctan2(0, 0) returns 0, which would otherwise create an artificial
    # 0-degree population and bias MRL/Rayleigh statistics.
    directional = np.isfinite(magnitudes) & (magnitudes > 0.0)
    dx = dx[directional]
    dy = dy[directional]
    magnitudes = magnitudes[directional]
    return np.arctan2(dy, dx), magnitudes
