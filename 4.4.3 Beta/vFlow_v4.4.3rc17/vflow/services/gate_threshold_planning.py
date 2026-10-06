"""Tk-free planning for legacy crosshair threshold-variable installation.

The frozen v4.1.11 UI stores threshold activation state in Tk ``BooleanVar``
objects embedded inside legacy gate dictionaries.  This module does *not*
replace those variables or make typed gate state authoritative.  It only
centralizes the deterministic truth-value plans used when manual and automatic
crosshair geometry is finalized.  ``FlowApp`` remains responsible for creating
Tk variables and mutating the live gate dictionary in the original order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ThresholdVariablePlan:
    """Plain-Python values from which ``FlowApp`` creates legacy Tk variables."""

    x_values: tuple[bool, ...]
    y_value: bool | None
    y_values: tuple[bool, ...]


def manual_crosshair_threshold_plan() -> ThresholdVariablePlan:
    """Return the frozen manual-crosshair threshold activation plan.

    Manual drawing always creates exactly one active X threshold and one active
    scalar Y threshold.  The existing ``y_thresh_vars`` list is intentionally
    not part of this mutation; ``FlowApp`` therefore continues to leave that
    legacy field untouched at the manual-draw call site.
    """
    return ThresholdVariablePlan(
        x_values=(True,),
        y_value=True,
        y_values=(),
    )


def single_y_auto_threshold_plan(x_boundaries: Iterable) -> ThresholdVariablePlan:
    """Return the legacy plan used by single-Y automatic crosshair gates."""
    return ThresholdVariablePlan(
        x_values=tuple(True for _ in x_boundaries),
        y_value=True,
        y_values=(),
    )


def multi_y_auto_threshold_plan(
    x_boundaries: Iterable,
    y_boundaries: Iterable | None,
) -> ThresholdVariablePlan:
    """Return the legacy plan used by the GMM multi-crossing auto gate.

    X crossings are all active.  If the Y crossing collection is truthy, every
    Y crossing is active and the scalar Y toggle is absent.  With no Y
    crossings, both scalar and multi-Y toggle state are absent/empty exactly as
    in frozen v4.1.11.
    """
    ybs = tuple(y_boundaries or ())
    return ThresholdVariablePlan(
        x_values=tuple(True for _ in x_boundaries),
        y_value=None,
        y_values=tuple(True for _ in ybs),
    )
