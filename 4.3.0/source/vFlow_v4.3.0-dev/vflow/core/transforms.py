"""Numeric scale transforms used by vFlow."""

from __future__ import annotations

from typing import Mapping

import numpy as np

from .logicle import logicle_forward, logicle_inverse, validate_logicle_params

# ``biexp`` and ``logicle`` are retained as compatibility aliases for historical
# vFlow sessions/API callers. They intentionally preserve the old signed-log
# formulas. New UI/session provenance uses explicit ``legacy_*`` identifiers.
LEGACY_SCALE_ALIASES = {
    "biexp": "legacy_biexp",
    "logicle": "legacy_logicle",
}
CANONICAL_SCALES = frozenset(
    {"linear", "log", "asinh", "legacy_biexp", "legacy_logicle", "logicle_gml2"}
)
VALID_SCALES = frozenset(set(CANONICAL_SCALES) | set(LEGACY_SCALE_ALIASES))


def canonical_scale_name(scale: str) -> str:
    if scale not in VALID_SCALES:
        raise ValueError(
            f"Unsupported scale {scale!r}; expected one of {sorted(VALID_SCALES)}"
        )
    return LEGACY_SCALE_ALIASES.get(scale, scale)


def scale_uses_cofactor(scale: str) -> bool:
    return canonical_scale_name(scale) in {"asinh", "legacy_logicle"}


def scale_uses_logicle_params(scale: str) -> bool:
    return canonical_scale_name(scale) == "logicle_gml2"


def _validate_cofactor(scale: str, cofactor: float) -> float:
    value = float(cofactor)
    if scale_uses_cofactor(scale):
        if not np.isfinite(value) or value <= 0:
            raise ValueError(
                f"{scale} cofactor must be finite and > 0; got {cofactor!r}"
            )
    return value


def normalized_transform_params(
    scale: str, transform_params: Mapping | None
) -> dict[str, float] | None:
    """Validate/normalize parameters relevant to ``scale`` for provenance/cache use."""
    canonical = canonical_scale_name(scale)
    if canonical == "logicle_gml2":
        return validate_logicle_params(transform_params)
    return None


def forward_transform(
    values,
    scale: str,
    cofactor: float = 150.0,
    *,
    transform_params: Mapping | None = None,
) -> np.ndarray:
    """Transform raw values into display/analysis space.

    Historical ``biexp``/``logicle`` names retain their frozen vFlow signed-log
    behavior. ``logicle_gml2`` is the standards-compatible Gating-ML Logicle
    transform and uses explicit T/W/M/A parameters.
    """
    canonical = canonical_scale_name(scale)
    cofactor = _validate_cofactor(scale, cofactor)
    a = np.asarray(values, float)
    if canonical == "asinh":
        return np.arcsinh(a / cofactor)
    if canonical == "legacy_logicle":
        return np.sign(a) * np.log10(1.0 + np.abs(a) / cofactor)
    if canonical == "legacy_biexp":
        return np.sign(a) * np.log1p(np.abs(a))
    if canonical == "logicle_gml2":
        return logicle_forward(a, transform_params)
    if canonical == "log":
        out = np.full(a.shape, np.nan, dtype=float)
        positive = a > 0
        out[positive] = np.log10(a[positive])
        return out
    return a


def inverse_transform(
    values,
    scale: str,
    cofactor: float = 150.0,
    *,
    transform_params: Mapping | None = None,
) -> np.ndarray:
    """Invert values from display/analysis space back to raw space."""
    canonical = canonical_scale_name(scale)
    cofactor = _validate_cofactor(scale, cofactor)
    a = np.asarray(values, float)
    if canonical == "asinh":
        return np.sinh(a) * cofactor
    if canonical == "legacy_logicle":
        return np.sign(a) * (10 ** np.abs(a) - 1.0) * cofactor
    if canonical == "legacy_biexp":
        return np.sign(a) * (np.exp(np.abs(a)) - 1.0)
    if canonical == "logicle_gml2":
        return logicle_inverse(a, transform_params)
    if canonical == "log":
        return 10.0 ** a
    return a


def transform_xy(
    x_raw,
    y_raw,
    x_scale: str,
    y_scale: str,
    cofactor: float = 150.0,
    *,
    x_transform_params: Mapping | None = None,
    y_transform_params: Mapping | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Transform x/y arrays and return their shared finite/displayable mask."""
    x = np.asarray(x_raw, float)
    y = np.asarray(y_raw, float)
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y):
        raise ValueError("X/Y arrays must be one-dimensional and equal length.")
    xt = forward_transform(
        x, x_scale, cofactor, transform_params=x_transform_params)
    yt = forward_transform(
        y, y_scale, cofactor, transform_params=y_transform_params)
    return xt, yt, np.isfinite(xt) & np.isfinite(yt)
