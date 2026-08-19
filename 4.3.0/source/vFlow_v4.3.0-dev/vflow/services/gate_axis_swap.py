"""Pure planning helpers for swapping the active X/Y channels.

A true X<->Y swap is not a new scientific channel context: it is the same
pair of measurements viewed on opposite axes.  Gates therefore need their
axis-oriented geometry/provenance transposed rather than being made inactive.

This module is intentionally Tk-free.  It returns plain threshold activity
flags so the UI layer can recreate its legacy BooleanVar wrappers transactionally.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

from vflow.core.threshold_state import ThresholdState


@dataclass(frozen=True)
class CrosshairAxisSwap:
    x_boundaries: tuple[float, ...]
    y_boundary: float | None
    y_boundaries: tuple[float, ...] | None
    x_active: tuple[bool, ...]
    y_active: bool | None
    y_actives: tuple[bool, ...]


@dataclass(frozen=True)
class GateAxisSwapPlan:
    """Axis-oriented assignments for one gate after X/Y transposition."""

    geometry: Mapping[str, Any]
    crosshair: CrosshairAxisSwap | None = None


def is_pure_axis_swap(new_x, new_y, old_x, old_y) -> bool:
    """Return True only for a real swap of two distinct existing channels."""
    return bool(
        old_x and old_y and old_x != old_y
        and new_x == old_y and new_y == old_x
    )


def swap_analysis_context_axes(context: Mapping[str, Any]) -> dict:
    """Return *context* with every axis-affine field transposed.

    Shared values such as ``cofactor`` remain unchanged.  Unknown provenance
    keys are retained verbatim so future schema additions are not discarded.
    """
    result = copy.deepcopy(dict(context))
    pairs = (
        ("x_channel", "y_channel"),
        ("x_scale", "y_scale"),
        ("x_transform_params", "y_transform_params"),
    )
    for x_key, y_key in pairs:
        x_present = x_key in context
        y_present = y_key in context
        x_value = copy.deepcopy(context.get(x_key))
        y_value = copy.deepcopy(context.get(y_key))
        if y_present:
            result[x_key] = y_value
        else:
            result.pop(x_key, None)
        if x_present:
            result[y_key] = x_value
        else:
            result.pop(y_key, None)
    return result


def _normalized_crosshair_axis_state(gate: Mapping[str, Any]):
    """Return X/Y thresholds plus semantic active flags.

    Legacy length-mismatch behavior means a threshold collection is treated as
    fully active.  Normalising here preserves that *effective* membership when
    the collection moves to the opposite axis.
    """
    thresholds = ThresholdState.from_gate(dict(gate))

    xbs = tuple(gate.get("x_boundaries") or ())
    x_flags = thresholds.x_flags
    if len(x_flags) != len(xbs):
        x_flags = tuple(True for _ in xbs)

    ybs_raw = gate.get("y_boundaries")
    if ybs_raw:
        ybs = tuple(ybs_raw)
        y_flags = thresholds.y_flags
        if len(y_flags) != len(ybs):
            y_flags = tuple(True for _ in ybs)
    else:
        yb = gate.get("y_boundary")
        ybs = () if yb is None else (yb,)
        y_flags = () if yb is None else (bool(thresholds.y_flag),)

    return xbs, tuple(bool(v) for v in x_flags), ybs, tuple(bool(v) for v in y_flags)


def plan_gate_axis_swap(gate: Mapping[str, Any]) -> GateAxisSwapPlan:
    """Build a non-mutating X/Y transposition plan for one legacy gate."""
    gate_type = gate.get("type", "crosshair")

    if gate_type == "crosshair":
        old_xbs, old_x_flags, old_ybs, old_y_flags = _normalized_crosshair_axis_state(gate)

        # Original Y thresholds become X thresholds.
        new_xbs = old_ybs
        new_x_flags = old_y_flags

        # Original X thresholds become the legacy scalar-or-multi Y encoding.
        if len(old_xbs) == 0:
            new_yb = None
            new_ybs = None
            new_y_active = None
            new_y_actives = ()
        elif len(old_xbs) == 1:
            new_yb = old_xbs[0]
            new_ybs = None
            new_y_active = old_x_flags[0]
            new_y_actives = ()
        else:
            new_yb = None
            new_ybs = old_xbs
            new_y_active = None
            new_y_actives = old_x_flags

        geometry = {}
        if "gmm_x_params" in gate or "gmm_y_params" in gate:
            geometry["gmm_x_params"] = copy.deepcopy(gate.get("gmm_y_params"))
            geometry["gmm_y_params"] = copy.deepcopy(gate.get("gmm_x_params"))

        return GateAxisSwapPlan(
            geometry=geometry,
            crosshair=CrosshairAxisSwap(
                x_boundaries=tuple(new_xbs),
                y_boundary=new_yb,
                y_boundaries=None if new_ybs is None else tuple(new_ybs),
                x_active=tuple(new_x_flags),
                y_active=new_y_active,
                y_actives=tuple(new_y_actives),
            ),
        )

    if gate_type in ("rectangle", "ellipse"):
        return GateAxisSwapPlan(
            geometry={
                "x0": gate.get("y0"),
                "y0": gate.get("x0"),
                "x1": gate.get("y1"),
                "y1": gate.get("x1"),
            }
        )

    if gate_type == "polygon":
        vertices = gate.get("vertices") or []
        return GateAxisSwapPlan(
            geometry={
                "vertices": [(y, x) for x, y in vertices],
            }
        )

    # Unknown gate types remain geometrically untouched but can still have their
    # analysis context transposed by the caller.  This preserves fail-closed
    # behavior in the evaluator rather than inventing geometry.
    return GateAxisSwapPlan(geometry={})



def apply_serialized_gate_axis_swap_plan(
    gate: dict,
    plan: GateAxisSwapPlan,
) -> None:
    """Commit an axis swap to a sanitized JSON-style gate dictionary.

    Gate-session loading operates on plain boolean threshold fields before Tk
    variables exist. Keeping that representation explicit avoids creating a
    second, subtly different axis-swap implementation in the I/O coordinator.
    """
    for key, value in plan.geometry.items():
        gate[key] = copy.deepcopy(value)

    cross = plan.crosshair
    if cross is None:
        return
    gate["x_boundaries"] = list(cross.x_boundaries)
    gate["y_boundary"] = cross.y_boundary
    gate["y_boundaries"] = (
        None if cross.y_boundaries is None else list(cross.y_boundaries)
    )
    gate["x_thresh_active"] = list(cross.x_active)
    gate["y_thresh_active"] = (
        bool(cross.y_active) if cross.y_active is not None else False
    )
    gate["y_thresh_actives"] = list(cross.y_actives)

def apply_gate_axis_swap_plan(
    gate: dict,
    plan: GateAxisSwapPlan,
    *,
    boolean_var_factory=lambda *, value: value,
) -> None:
    """Commit one already-validated gate-axis swap plan in place.

    ``boolean_var_factory`` keeps this module Tk-free while allowing FlowApp to
    recreate its legacy ``BooleanVar`` wrappers.  Callers should build plans for
    every affected gate before invoking this function so the operation remains
    transactional with respect to malformed input geometry/state.
    """
    for key, value in plan.geometry.items():
        gate[key] = copy.deepcopy(value)

    cross = plan.crosshair
    if cross is None:
        return

    gate["x_boundaries"] = list(cross.x_boundaries)
    gate["y_boundary"] = cross.y_boundary
    gate["y_boundaries"] = (
        None if cross.y_boundaries is None else list(cross.y_boundaries)
    )
    gate["x_thresh_vars"] = [
        boolean_var_factory(value=value) for value in cross.x_active
    ]
    gate["y_thresh_var"] = (
        boolean_var_factory(value=cross.y_active)
        if cross.y_active is not None else None
    )
    gate["y_thresh_vars"] = [
        boolean_var_factory(value=value) for value in cross.y_actives
    ]
