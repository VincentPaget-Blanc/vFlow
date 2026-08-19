"""Tk/matplotlib-free planning for gate geometry interaction lifecycle.

The frozen v4.1.11 ``FlowApp`` remains responsible for event handling,
coordinate transforms, axis-limit snapshot reads, gate geometry mutation,
cache invalidation, rendering, and Tk state.  These helpers make plain-Python
decisions or sequence controller-owned callbacks after legacy call sites have
read or materialized values in their original order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DrawInteractionPlan:
    """Plain state decisions installed before a fresh draw gesture."""

    moving_gate: bool = True
    drag_last_draw: float = 0.0


def plan_draw_start() -> DrawInteractionPlan:
    """Return the frozen draw-start moving/throttle decisions."""
    return DrawInteractionPlan()


@dataclass(frozen=True)
class HandleDragStartPlan:
    """Plain decisions applied after legacy handle-drag payload creation."""

    drag_last_draw: float
    select_gate_id: int | None


def plan_handle_drag_start(
    *,
    gate_id: int,
    selected_gate_id: int | None,
) -> HandleDragStartPlan:
    """Preserve first-frame throttle reset and conditional gate selection."""
    return HandleDragStartPlan(
        drag_last_draw=0.0,
        select_gate_id=gate_id if gate_id != selected_gate_id else None,
    )


@dataclass(frozen=True)
class GateMoveStartPlan:
    """Plain whole-gate move payload plus transient selection decisions."""

    payload: dict[str, Any]
    drag_last_draw: float
    clear_interior_hover: bool
    select_gate_id: int | None


def plan_gate_move_start(
    *,
    gate_id: int,
    gate: dict[str, Any],
    original_gate_snapshot: dict[str, Any],
    original_pixel_points: Any,
    press_pixel_point: Any,
    frozen_xlim: list,
    frozen_ylim: list,
    selected_gate_id: int | None,
) -> GateMoveStartPlan:
    """Package already-materialized legacy move state without new side effects.

    ``FlowApp`` intentionally materializes ``gate_id``, the Tk-safe snapshot,
    press point, and frozen axis-limit lists in the same order as v4.1.11
    before calling this helper.  This keeps even partial exception behavior at
    the event boundary unchanged.
    """
    return GateMoveStartPlan(
        payload={
            "gate_id": gate_id,
            "gate": gate,
            "orig": original_gate_snapshot,
            "press_px": press_pixel_point,
            "orig_px": original_pixel_points,
            "frozen_xlim": frozen_xlim,
            "frozen_ylim": frozen_ylim,
        },
        drag_last_draw=0.0,
        clear_interior_hover=True,
        select_gate_id=gate_id if gate_id != selected_gate_id else None,
    )



def resolve_release_interaction_path(
    *,
    get_handle_drag,
    get_gate_move,
    get_moving_gate,
) -> str:
    """Return the frozen top-level gate-release interaction path.

    The three sources are lazy getters so the legacy left-to-right truth-test
    and exception order is preserved exactly.  This helper selects only the
    controller path; gate lookup, mutation, render-snapshot teardown, Tk materialization,
    deletion and finalization remain owned by ``FlowApp``.
    """
    if get_handle_drag():
        return "handle_drag"
    if get_gate_move():
        return "gate_move"
    if not get_moving_gate():
        return "inactive"
    return "fresh_draw"


@dataclass(frozen=True)
class FreshDrawReleaseGuard:
    """Already-ordered fresh-draw guard result with successful coordinates."""

    gate: Any
    should_discard: bool
    x: Any = None
    y: Any = None


def run_handle_drag_release_side_effect_sequence(
    *,
    resolve_gate,
    clear_handle_drag,
    clear_hover_gate_id,
    clear_frozen_xlim,
    clear_frozen_ylim,
    end_render_snapshot,
    finish_gate,
) -> None:
    """Run the frozen handle-drag release callback sequence.

    Gate lookup and every mutable/render operation remain controller-owned.
    The callbacks are invoked in legacy order so the repeated handle-drag read
    occurs during gate resolution, cleanup mutations retain their historical
    partial-state cutoffs, render teardown precedes the final gate truth test,
    and finalization runs only for a truthy resolved gate.
    """
    gate = resolve_gate()
    clear_handle_drag()
    clear_hover_gate_id()
    clear_frozen_xlim()
    clear_frozen_ylim()
    end_render_snapshot()
    if gate:
        finish_gate(gate)


def run_gate_move_release_side_effect_sequence(
    *,
    resolve_gate,
    clear_gate_move,
    clear_interior_hover_gate_id,
    clear_frozen_xlim,
    clear_frozen_ylim,
    end_render_snapshot,
    finish_gate,
) -> None:
    """Run the frozen gate-body-move release callback sequence.

    The move payload, mutable controller attributes, render teardown and gate
    finalization remain controller-owned.  The callbacks are invoked in the
    original order so the second move-payload read occurs during gate
    acquisition, cleanup failures retain their historical partial state, and
    finalization remains unconditional after successful render teardown.
    """
    gate = resolve_gate()
    clear_gate_move()
    clear_interior_hover_gate_id()
    clear_frozen_xlim()
    clear_frozen_ylim()
    end_render_snapshot()
    finish_gate(gate)


def resolve_fresh_draw_release_guard(
    *,
    get_gate,
    get_x_coord,
    get_y_coord,
) -> FreshDrawReleaseGuard:
    """Preserve the frozen fresh-draw guard and coordinate read order.

    The sources are lazy callbacks so a falsey gate prevents coordinate reads,
    a missing X coordinate prevents the first Y read, and a successful guard
    performs the historical second X-then-Y reads.  Discard side effects, gate
    type dispatch, geometry mutation and finalization remain owned by FlowApp.
    """
    gate = get_gate()
    if not gate or get_x_coord() is None or get_y_coord() is None:
        return FreshDrawReleaseGuard(gate=gate, should_discard=True)
    x, y = get_x_coord(), get_y_coord()
    return FreshDrawReleaseGuard(
        gate=gate,
        should_discard=False,
        x=x,
        y=y,
    )


def run_fresh_draw_discard_side_effect_sequence(
    *,
    end_render_snapshot,
    get_gate_for_truth_test,
    get_applied,
    get_gate_id,
    delete_gate,
) -> None:
    """Run the frozen fresh-draw discard callback sequence.

    Concrete render teardown, gate access and gate deletion remain
    controller-owned.  Lazy callbacks preserve the original second truth test
    of the already-resolved gate, delayed ``applied``/ID reads, ordinary Python
    truth semantics, and immediate exception cutoffs.
    """
    end_render_snapshot()
    if get_gate_for_truth_test() and not get_applied():
        gate_id = get_gate_id()
        delete_gate(gate_id)


def resolve_fresh_draw_finalization_path(*, get_gate_type) -> str:
    """Select the frozen post-guard finalization branch.

    The concrete gate-type lookup remains a lazy controller callback so its
    timing and exceptions stay at the legacy boundary.  This helper owns only
    the original comparison sequence: crosshair first, then rectangle/ellipse,
    otherwise defer to the polygon-or-unknown early-return path.
    """
    gate_type = get_gate_type()
    if gate_type == "crosshair":
        return "crosshair"
    if gate_type in ("rectangle", "ellipse"):
        return "shape"
    return "deferred"


def run_crosshair_release_side_effect_sequence(
    *,
    apply_geometry,
    get_threshold_plan,
    materialize_x_threshold_vars,
    materialize_y_threshold_var,
    mark_applied,
    clear_draw_marker,
    end_render_snapshot,
    finish_gate,
) -> None:
    """Run the frozen crosshair release callback sequence.

    Every concrete operation remains controller-owned.  Callbacks are invoked
    one at a time in the original order so an exception stops at the same
    partial-state boundary as frozen v4.1.11.  The helper does not inspect or
    mutate gate, Tk, event, geometry, threshold, cache, or render state.
    """
    apply_geometry()
    threshold_plan = get_threshold_plan()
    materialize_x_threshold_vars(threshold_plan)
    materialize_y_threshold_var(threshold_plan)
    mark_applied()
    clear_draw_marker()
    end_render_snapshot()
    finish_gate()


def run_shape_release_side_effect_sequence(
    *,
    apply_geometry,
    is_degenerate,
    end_render_snapshot,
    get_gate_id,
    delete_gate,
    mark_applied,
    clear_draw_marker,
    finish_gate,
) -> None:
    """Run the frozen rectangle/ellipse release callback sequence.

    Concrete geometry mutation, degeneracy computation, gate-ID lookup, gate
    deletion, draw-state mutation, render teardown and finalization remain
    controller-owned.  The helper owns only the legacy branch and callback
    order, so any exception still stops at the same partial-state boundary.
    """
    apply_geometry()
    if is_degenerate():
        end_render_snapshot()
        gate_id = get_gate_id()
        delete_gate(gate_id)
        return
    mark_applied()
    clear_draw_marker()
    end_render_snapshot()
    finish_gate()


def run_handle_drag_motion_presentation_sequence(
    *,
    resolve_redraw_time,
    commit_redraw_time,
    preview_gate,
    restore_frozen_axes,
    render_frame,
) -> bool:
    """Run the frozen handle-drag post-geometry presentation sequence.

    The controller retains the clock read, exact 16 ms throttle arithmetic,
    drag-timestamp mutation, preview implementation, repeated handle-payload
    frozen-axis reads and restoration exception policy, and final rendering.
    This helper owns only callback order and the controller-decided throttle.
    """
    redraw_time = resolve_redraw_time()
    if redraw_time is None:
        return False
    commit_redraw_time(redraw_time)
    preview_gate()
    restore_frozen_axes()
    render_frame()
    return True


def run_gate_move_motion_presentation_sequence(
    *,
    resolve_redraw_time,
    commit_redraw_time,
    preview_gate,
    restore_frozen_axes,
    render_frame,
) -> bool:
    """Run the frozen gate-body-move post-geometry presentation sequence.

    The controller retains the clock read, 16 ms throttle arithmetic, live
    drag-timestamp mutation, preview implementation, frozen-axis reads and
    exception policy, and final rendering operation.  This helper owns only
    callback order and the already-controller-decided throttled early return.
    """
    redraw_time = resolve_redraw_time()
    if redraw_time is None:
        return False
    commit_redraw_time(redraw_time)
    preview_gate()
    restore_frozen_axes()
    render_frame()
    return True


def run_polygon_motion_presentation_sequence(
    *,
    resolve_redraw_time,
    commit_redraw_time,
    preview_gate,
    render_frame,
) -> bool:
    """Run the frozen polygon rubber-band presentation/throttle sequence.

    The controller retains polygon cursor coordinate reads and mutation, the
    clock read, exact 16 ms throttle arithmetic, drag-timestamp mutation,
    preview implementation, and final rendering.  This helper owns only the
    callback order after the legacy cursor-update decision has completed.
    """
    redraw_time = resolve_redraw_time()
    if redraw_time is None:
        return False
    commit_redraw_time(redraw_time)
    preview_gate()
    render_frame()
    return True


def run_fresh_draw_motion_presentation_sequence(
    *,
    resolve_redraw_time,
    commit_redraw_time,
    preview_gate,
    restore_frozen_axes,
    render_frame,
) -> bool:
    """Run the frozen fresh-draw post-geometry presentation sequence.

    The controller retains event/gate guards, incremental geometry mutation,
    the clock read, exact 16 ms throttle arithmetic, drag-timestamp mutation,
    preview implementation, frozen-axis guard/exception policy, and rendering.
    This helper owns only callback order after geometry updates have completed.
    """
    redraw_time = resolve_redraw_time()
    if redraw_time is None:
        return False
    commit_redraw_time(redraw_time)
    preview_gate()
    restore_frozen_axes()
    render_frame()
    return True


def gate_pixel_delta(*, current_pixel: Any, press_pixel: Any):
    """Return one frozen v4.1.11 cursor-minus-press pixel delta.

    Keeping X and Y as separate calls lets ``FlowApp`` retain the original
    expression/read order: X is fully subtracted before Y is even read.
    """
    return current_pixel - press_pixel


def translate_gate_pixel_points(
    *,
    original_pixel_points: Any,
    delta_x: Any,
    delta_y: Any,
):
    """Return original gate pixels translated by an already-ordered delta.

    The caller intentionally computes X then Y deltas before entering this
    helper so legacy exception ordering remains exact.  This helper owns only
    construction of the two-element NumPy offset and broadcasting addition.
    """
    import numpy as np

    return original_pixel_points + np.array([delta_x, delta_y])
