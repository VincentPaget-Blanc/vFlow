"""Tk-free planning for axis, scale, and cofactor input callbacks.

This module preserves the frozen v4.1.11 input semantics while separating
validation/default decisions from ``FlowApp``'s Tk and application-state side
effects.  It deliberately does not mutate ``AnalysisState``, invalidate caches,
recompute gates, refresh plots, or touch Tk variables/dialogs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class AxisApplyPlan:
    """Decision for the legacy ``Apply Axes`` callback."""

    missing_axis: bool
    context_changed: bool
    refresh_only: bool
    swap_axes: bool


def plan_axis_apply(
    x_channel: Any,
    y_channel: Any,
    current_x_channel: Any,
    current_y_channel: Any,
) -> AxisApplyPlan:
    """Return the exact frozen-v4.1.11 axis-apply decision."""
    if not x_channel or not y_channel:
        return AxisApplyPlan(True, False, False, False)
    if x_channel == current_x_channel and y_channel == current_y_channel:
        return AxisApplyPlan(False, False, True, False)
    return AxisApplyPlan(
        False, True, False,
        bool(
            current_x_channel and current_y_channel
            and current_x_channel != current_y_channel
            and x_channel == current_y_channel
            and y_channel == current_x_channel
        ),
    )


@dataclass(frozen=True)
class ScaleApplyPlan:
    """Validated scale/cofactor values for ``_apply_scales``."""

    x_scale: Any
    y_scale: Any
    cofactor: float
    replacement_cofactor_text: str | None


def plan_scale_apply(x_scale: Any, y_scale: Any, cofactor_text: Any) -> ScaleApplyPlan:
    """Preserve the legacy scale callback's cofactor fallback behavior.

    The old callback catches *any* exception while parsing/validating the
    cofactor and falls back to 150.0 plus displayed text ``'150'``.  That broad
    exception boundary is intentionally retained here.
    """
    try:
        candidate = float(cofactor_text)
        if not np.isfinite(candidate) or candidate <= 0:
            raise ValueError
        return ScaleApplyPlan(x_scale, y_scale, candidate, None)
    except Exception:
        return ScaleApplyPlan(x_scale, y_scale, 150.0, "150")


@dataclass(frozen=True)
class CofactorTracePlan:
    """Decision for the write-trace callback while cofactor text is edited."""

    apply_value: float | None


def plan_cofactor_trace(cofactor_text: Any, current_cofactor: Any) -> CofactorTracePlan:
    """Return a new cofactor only when frozen v4.1.11 would apply one.

    Malformed intermediate text is ignored.  The original callback catches only
    ``TypeError`` and ``ValueError``; other unexpected exceptions intentionally
    remain visible rather than being silently swallowed.
    """
    try:
        value = float(cofactor_text)
        if (
            np.isfinite(value)
            and value > 0
            and not np.isclose(value, current_cofactor, rtol=0.0, atol=1e-12)
        ):
            return CofactorTracePlan(value)
    except (TypeError, ValueError):
        pass
    return CofactorTracePlan(None)


@dataclass(frozen=True)
class CofactorEntryPlan:
    """Validated focus-out/Return result for the cofactor entry."""

    cofactor: Any
    context_changed: bool
    display_text: str
    status_text: str | None


def plan_cofactor_entry(
    cofactor_text: Any,
    current_cofactor: Any,
) -> CofactorEntryPlan:
    """Preserve frozen-v4.1.11 cofactor-value validation and formatting."""
    try:
        value = float(cofactor_text)
        if not np.isfinite(value) or value <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return CofactorEntryPlan(
            cofactor=current_cofactor,
            context_changed=False,
            display_text=f"{current_cofactor:g}",
            status_text=(
                "Invalid cofactor rejected; continuing with "
                f"{current_cofactor:g}."
            ),
        )

    changed = not np.isclose(value, current_cofactor, rtol=0.0, atol=1e-12)
    applied = value if changed else current_cofactor
    return CofactorEntryPlan(
        cofactor=applied,
        context_changed=bool(changed),
        display_text=f"{applied:g}",
        status_text=None,
    )
