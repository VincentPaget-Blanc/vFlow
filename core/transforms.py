"""Numeric scale transforms used by vFlow."""

from __future__ import annotations

import numpy as np


def forward_transform(values, scale: str, cofactor: float = 150.0) -> np.ndarray:
    """Transform raw values into display/analysis space."""
    a = np.asarray(values, float)
    if scale == "asinh":
        return np.arcsinh(a / cofactor)
    if scale == "logicle":
        return np.sign(a) * np.log10(1.0 + np.abs(a) / cofactor)
    if scale == "biexp":
        return np.sign(a) * np.log1p(np.abs(a))
    if scale == "log":
        return np.where(a > 0, np.log10(a), np.nan)
    return a


def inverse_transform(values, scale: str, cofactor: float = 150.0) -> np.ndarray:
    """Invert values from display/analysis space back to raw space."""
    a = np.asarray(values, float)
    if scale == "asinh":
        return np.sinh(a) * cofactor
    if scale == "logicle":
        return np.sign(a) * (10 ** np.abs(a) - 1.0) * cofactor
    if scale == "biexp":
        return np.sign(a) * (np.exp(np.abs(a)) - 1.0)
    if scale == "log":
        return 10.0 ** a
    return a


def transform_xy(
    x_raw,
    y_raw,
    x_scale: str,
    y_scale: str,
    cofactor: float = 150.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Transform x/y arrays and return a finite mask."""
    xt = forward_transform(np.asarray(x_raw, float), x_scale, cofactor)
    yt = forward_transform(np.asarray(y_raw, float), y_scale, cofactor)
    return xt, yt, np.isfinite(xt) & np.isfinite(yt)

