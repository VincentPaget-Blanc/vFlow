"""Tk-free ownership and planning for transient gate interaction presentation.

The live gate dictionaries intentionally remain in the legacy UI during the
pure structural refactor because crosshair threshold entries still contain Tk
variables.  This module centralizes only plain presentation identifiers and
small deterministic decisions for hover/pin interactions.  Hit-testing,
matplotlib/Tk event handling, cursor rendering, previews, gate geometry,
statistics, masks, and serialization remain outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vflow.core.gates import line_hover_test_plan


@dataclass
class GateInteractionState:
    """Plain selected/draw/hover gate references for one FlowApp instance."""

    selected_gate_id: int | None = None
    draw_gate_id: int | None = None
    hover_gate_id: int | None = None
    hover_handle_key: tuple | None = None
    interior_hover_gate_id: int | None = None
    pinned_gate_id: int | None = None

    def clear_gate_references(self) -> None:
        """Reset gate interaction references without touching geometry or widgets."""
        self.selected_gate_id = None
        self.draw_gate_id = None
        self.hover_gate_id = None
        self.hover_handle_key = None
        self.interior_hover_gate_id = None
        self.pinned_gate_id = None


@dataclass
class GateHoverCache:
    """Plain presentation caches used by hover hit-testing and cursor lookup.

    ``handle_pixel_cache`` is rebuilt by the existing draw-event/UI code; this
    class only centralizes ownership.  The line-test position is explicit from
    construction so callers observe a stable ``None`` state before the first
    throttled line-test position is committed.
    """

    handle_pixel_cache: dict = field(default_factory=dict)
    _last_line_test_pos: object = field(default=None, repr=False)

    def get_last_line_test_pos(self):
        return self._last_line_test_pos

    def set_last_line_test_pos(self, value) -> None:
        self._last_line_test_pos = value

    def clear(self) -> None:
        """Reset presentation caches without touching gate/scientific state."""
        self._last_line_test_pos = None
        self.handle_pixel_cache.clear()


def iter_handle_pixel_cache_entries(
    gates, *, get_handles, make_entry=None, make_entries=None
):
    """Yield completed per-gate handle-cache entries in legacy rebuild order.

    The helper only orchestrates deterministic cache construction.  Handle
    discovery and display-space entry construction are callbacks so the UI
    remains authoritative for gate-handle lookup and for the matplotlib
    ``transData`` access/transform timing.  The scalar ``make_entry`` path is
    retained unchanged; ``make_entries`` is an optional per-gate batching seam.
    Yielding each completed gate keeps incremental cache assignment intact.
    """
    if make_entry is None and make_entries is None:
        raise TypeError('make_entry or make_entries is required')

    for gate in gates:
        if not gate.get('applied'):
            continue
        handles = get_handles(gate)
        if make_entries is not None:
            entries = [entry for entry in make_entries(handles) if entry is not None]
        else:
            entries = []
            for handle in handles:
                entry = make_entry(handle)
                if entry is not None:
                    entries.append(entry)
        if entries:
            yield gate, entries


def select_nearest_cached_handle_gate(candidates):
    """Return the gate id whose per-gate cached-handle hit is nearest.

    ``candidates`` is consumed lazily in caller-provided order.  Each item is
    ``(gate_id, nearest_result)`` where ``nearest_result`` is either ``None``
    or the unchanged result of ``vflow.core.gates.nearest_cached_handle``.
    This helper performs only the cross-gate strict-distance reduction; event
    coordinate reads, thresholding, and per-handle distance geometry remain
    outside this module.
    """
    best_gid = None
    best_dist = float('inf')
    for gid, nearest in candidates:
        if nearest is None:
            continue
        _key, dist = nearest
        if dist < best_dist:
            best_dist = dist
            best_gid = gid
    return best_gid


class CachedHandleProjectionError(ValueError):
    """Raised when an already-computed nearest-handle result has invalid shape."""


def resolve_winning_cached_handle_key(nearest_result):
    """Return a validated cached-handle key from one nearest result.

    ``nearest_cached_handle`` returns either ``None`` or a two-item tuple
    ``(handle_key, distance)`` where ``handle_key`` is the three-item tuple
    ``(gate_id, handle_name, index)``.  This projection validates only those
    structural invariants.  Key contents and the distance value are preserved
    without coercion or semantic validation.
    """
    if nearest_result is None:
        return None
    if not isinstance(nearest_result, tuple) or len(nearest_result) != 2:
        raise CachedHandleProjectionError(
            'Nearest cached-handle result must be a 2-item tuple '
            '(handle_key, distance).'
        )
    handle_key = nearest_result[0]
    if not isinstance(handle_key, tuple) or len(handle_key) != 3:
        raise CachedHandleProjectionError(
            'Nearest cached-handle key must be a 3-item tuple '
            '(gate_id, handle_name, index).'
        )
    return handle_key


def run_hover_handle_proximity_execution_sequence(
    *,
    resolve_handle_gate_id,
    resolve_nearest_handle,
    project_handle_key,
):
    """Run frozen handle-gate to winning-handle-key callback sequencing.

    The controller retains handle hit-testing, cache access, event-coordinate
    reads, threshold arithmetic, nearest-handle geometry, and key projection.
    This helper owns only the conditional execution order between those
    controller-owned operations.
    """
    handle_gate_id = resolve_handle_gate_id()
    hover_handle_key = None
    if handle_gate_id is not None:
        nearest_result = resolve_nearest_handle(handle_gate_id)
        hover_handle_key = project_handle_key(nearest_result)
    return handle_gate_id, hover_handle_key


def resolve_cached_handle_hover_cursor(nearest_result) -> str:
    """Return the frozen Tk cursor name for one computed handle hit.

    ``nearest_result`` must be the unchanged output of
    ``vflow.core.gates.nearest_cached_handle``.  This helper performs no event
    reads, cache access, thresholding, distance calculation, or normalization;
    it only preserves the legacy presentation projection.
    """
    if nearest_result is None:
        return "hand2"
    key, _dist = nearest_result
    return "fleur" if key[1] == "center" else "sizing"


def should_resolve_hover_cursor(*, get_handle_drag, get_hover_gate_id, get_pinned_gate_id) -> bool:
    """Return whether hover-cursor resolution should run for this motion.

    Drag-state truth semantics remain unchanged because the drag source is an
    interaction payload, not a gate ID.  Hover and pinned gate IDs use explicit
    ``is not None`` presence checks so gate ID ``0`` is treated as a valid gate
    consistently with pin and line-hit behavior.  Sources remain lazy and retain
    the historical left-to-right access order.
    """
    if get_handle_drag():
        return True
    hover_gate_id = get_hover_gate_id()
    if hover_gate_id is not None:
        return True
    return get_pinned_gate_id() is not None


def resolve_hover_cursor_gate_id(*, get_handle_drag, get_hover_gate_id, get_pinned_gate_id):
    """Resolve the gate whose cached handles drive hover-cursor presentation.

    A truthy drag retains the historical repeated read before ``['gate_id']``.
    Otherwise hover is read before pinned, but gate-ID presence is determined by
    ``is not None`` so ID ``0`` no longer falls through to the pinned source.
    """
    if get_handle_drag():
        return get_handle_drag()['gate_id']
    hover_gate_id = get_hover_gate_id()
    if hover_gate_id is not None:
        return hover_gate_id
    return get_pinned_gate_id()


def resolve_hover_cursor_nearest_result(
    *,
    gate_id,
    get_cached_entries,
    get_event_x,
    get_event_y,
    threshold,
    find_nearest,
):
    """Orchestrate cached-handle lookup while keeping all authorities external.

    The caller supplies callbacks for cache access, event-coordinate reads, and
    the unchanged nearest-handle geometry function.  They are invoked in the
    exact legacy order: cache lookup, X read, Y read, then nearest calculation.
    This helper owns no cache, event object, threshold policy, or geometry.
    """
    entries = get_cached_entries(gate_id)
    x = get_event_x()
    y = get_event_y()
    return find_nearest(entries, x=x, y=y, threshold=threshold)


def resolve_hover_cursor_result_projection(*, get_nearest_result, project_cursor):
    """Sequence nearest-result resolution before cursor presentation projection.

    Both operations remain callbacks so this boundary owns no cache/event access,
    threshold policy, nearest-handle geometry, or cursor projection rules.  The
    nearest result is passed through unchanged and projection runs only after
    result resolution succeeds, preserving legacy failure ordering.
    """
    nearest_result = get_nearest_result()
    return project_cursor(nearest_result)


def resolve_hover_cursor_workflow(
    *,
    should_resolve,
    prepare_resolution,
    resolve_gate_id,
    resolve_cursor_for_gate,
):
    """Sequence the frozen hover-cursor workflow without taking its authorities.

    All concrete decisions remain callbacks owned by the caller.  On the active
    path they run in frozen order: activation, resolution preparation, gate-source
    resolution, then cursor resolution for that gate.  The inactive cursor remains
    the legacy empty string.
    """
    if should_resolve():
        resolution_context = prepare_resolution()
        gate_id = resolve_gate_id()
        return resolve_cursor_for_gate(gate_id, resolution_context)
    return ''


@dataclass(frozen=True)
class PinInteractionPlan:
    """Deterministic presentation changes for one right-click pin decision."""

    pinned_gate_id: int | None
    selected_gate_id: int | None
    update_selection: bool
    redraw: bool


def plan_pin_interaction(*, line_gate_id, pinned_gate_id) -> PinInteractionPlan:
    """Preserve frozen right-click line-pin toggle and empty-space unpin rules."""
    if line_gate_id is not None:
        if pinned_gate_id == line_gate_id:
            return PinInteractionPlan(
                pinned_gate_id=None,
                selected_gate_id=None,
                update_selection=False,
                redraw=True,
            )
        return PinInteractionPlan(
            pinned_gate_id=line_gate_id,
            selected_gate_id=line_gate_id,
            update_selection=True,
            redraw=True,
        )

    if pinned_gate_id is not None:
        return PinInteractionPlan(
            pinned_gate_id=None,
            selected_gate_id=None,
            update_selection=False,
            redraw=True,
        )

    return PinInteractionPlan(
        pinned_gate_id=None,
        selected_gate_id=None,
        update_selection=False,
        redraw=False,
    )


@dataclass(frozen=True)
class HoverHitTestPlan:
    """First-stage hover hit-test orchestration without geometry calculations."""

    hover_gate_id: int | None
    hover_handle_key: tuple | None
    run_line_test: bool
    next_line_test_pos: tuple[float, float] | None


@dataclass(frozen=True)
class HoverHitTestContinuation:
    """Second-stage hover decision after the optional line hit-test completes."""

    hover_gate_id: int | None
    run_interior_test: bool


def plan_hover_hit_testing(
    *,
    handle_gate_id,
    hover_handle_key,
    current_hover_gate_id,
    current_pos,
    last_line_test_pos=None,
    min_delta: float = 10,
) -> HoverHitTestPlan:
    """Plan handle-to-line hover fall-through while leaving geometry outside."""
    run_line_test, next_line_test_pos = line_hover_test_plan(
        new_hover=handle_gate_id,
        current_hover_gate_id=current_hover_gate_id,
        current_pos=current_pos,
        last_line_test_pos=last_line_test_pos,
        min_delta=min_delta,
    )
    return HoverHitTestPlan(
        hover_gate_id=handle_gate_id,
        hover_handle_key=hover_handle_key,
        run_line_test=run_line_test,
        next_line_test_pos=next_line_test_pos,
    )


def continue_hover_hit_testing(
    *,
    plan: HoverHitTestPlan,
    line_gate_id,
    line_test_ran: bool,
    mode,
) -> HoverHitTestContinuation:
    """Plan optional interior hit-testing after the line-test stage."""
    hover_gate_id = line_gate_id if line_test_ran else plan.hover_gate_id
    return HoverHitTestContinuation(
        hover_gate_id=hover_gate_id,
        run_interior_test=(mode == 'draw' and hover_gate_id is None),
    )


def invoke_hover_hit_test_plan(
    *,
    planner,
    handle_gate_id,
    hover_handle_key,
    current_hover_gate_id,
    current_pos,
    last_line_test_pos,
    min_delta,
):
    """Invoke the frozen hover hit-test planner with already-acquired inputs.

    The controller retains ownership and evaluation order for the planner
    symbol, hover state, event coordinates, last-line-test position, and
    ``min_delta`` literal. This helper owns only forwarding those captured
    values into the planner with the historical keyword mapping.
    """
    return planner(
        handle_gate_id=handle_gate_id,
        hover_handle_key=hover_handle_key,
        current_hover_gate_id=current_hover_gate_id,
        current_pos=current_pos,
        last_line_test_pos=last_line_test_pos,
        min_delta=min_delta,
    )


def run_hover_hit_test_execution_sequence(
    *,
    plan,
    mode,
    commit_line_test_pos,
    run_line_test,
    continue_hit_testing,
    run_interior_test,
):
    """Run frozen optional line/interior hover hit-test callback sequencing.

    The controller retains the event, threshold, line/interior hit-test
    implementations, line-test-position storage, mode value, and returned hit
    payloads.  This helper owns only the legacy field-access and callback order
    after ``plan_hover_hit_testing(...)`` has produced its plan.
    """
    line_hover = None
    if plan.run_line_test:
        if plan.next_line_test_pos is not None:
            commit_line_test_pos(plan.next_line_test_pos)
        line_hover = run_line_test()

    continuation = continue_hit_testing(
        plan=plan,
        line_gate_id=line_hover,
        line_test_ran=plan.run_line_test,
        mode=mode,
    )
    new_hover = continuation.hover_gate_id

    new_interior = None
    if continuation.run_interior_test:
        hit = run_interior_test()
        new_interior = hit['id'] if hit else None

    return new_hover, new_interior


@dataclass(frozen=True)
class HoverPresentationPlan:
    """Plain hover-state commit and redraw decision for one motion event."""

    hover_gate_id: int | None
    hover_handle_key: tuple | None
    interior_hover_gate_id: int | None
    changed: bool


def plan_hover_cursor_policy(*, new_hover, pinned_gate_id, new_interior) -> str:
    """Return the cursor-policy branch without resolving a Tk cursor.

    Gate IDs use explicit presence semantics so ID ``0`` is a valid hover/pin
    target.  Interior hover remains a separate ``is not None`` decision.
    """
    if new_hover is not None or pinned_gate_id is not None:
        return "hover"
    if new_interior is not None:
        return "fleur"
    return ""


def invoke_hover_cursor_policy(
    *,
    planner,
    new_hover,
    pinned_gate_id,
    new_interior,
):
    """Invoke a captured hover-cursor policy planner with frozen keyword mapping.

    The controller owns planner-symbol lookup and all concrete hover/pin input
    acquisition.  This helper owns only forwarding already-acquired values to
    the already-captured policy planner.
    """
    return planner(
        new_hover=new_hover,
        pinned_gate_id=pinned_gate_id,
        new_interior=new_interior,
    )


def run_hover_cursor_application_sequence(
    *,
    cursor_policy,
    resolve_hover_cursor,
    apply_cursor,
) -> None:
    """Run the frozen inside-axes hover cursor application sequence.

    The controller retains cursor-policy planning, lazy hover-cursor resolution,
    Tk widget lookup/configuration, and the surrounding broad exception policy.
    This helper owns only the policy-dependent callback order after
    ``plan_hover_cursor_policy(...)`` has produced the legacy policy value.
    """
    if cursor_policy == "hover":
        cursor = resolve_hover_cursor()
    else:
        cursor = cursor_policy
    apply_cursor(cursor)


def plan_hover_presentation(
    *,
    new_hover,
    old_hover,
    new_hover_handle_key,
    old_hover_handle_key,
    new_interior,
    old_interior,
) -> HoverPresentationPlan:
    """Plan the legacy hover-state commit without hit-testing or rendering."""
    changed = (
        new_hover != old_hover
        or new_hover_handle_key != old_hover_handle_key
        or new_interior != old_interior
    )
    return HoverPresentationPlan(
        hover_gate_id=new_hover,
        hover_handle_key=new_hover_handle_key,
        interior_hover_gate_id=new_interior,
        changed=changed,
    )


def run_hover_presentation_sequence(
    *,
    plan: HoverPresentationPlan,
    commit_hover_gate_id,
    commit_hover_handle_key,
    commit_interior_hover_gate_id,
    preview_gate,
    schedule_draw,
) -> bool:
    """Run the frozen hover-state commit and changed-redraw sequence.

    The controller retains hit-testing, cursor policy/application, concrete
    hover-state storage, preview implementation, canvas ownership, and the
    surrounding early-return decision. This helper owns only callback order
    after ``plan_hover_presentation(...)`` has produced the legacy plan.
    """
    commit_hover_gate_id(plan.hover_gate_id)
    commit_hover_handle_key(plan.hover_handle_key)
    commit_interior_hover_gate_id(plan.interior_hover_gate_id)
    if plan.changed:
        preview_gate()
        schedule_draw()
        return True
    return False


def run_outside_axes_hover_clear_sequence(
    *,
    clear_hover_gate_id,
    clear_hover_handle_key,
    clear_interior_hover_gate_id,
    reset_cursor,
    preview_gate,
    schedule_draw,
) -> None:
    """Run the frozen outside-axes hover-clear side-effect sequence.

    The controller retains the activation condition, concrete hover-state
    storage, cursor widget lookup/configuration and its broad exception policy,
    preview implementation, canvas ownership, and surrounding early return.
    This helper owns only callback order after the legacy clear condition has
    already selected the branch.
    """
    clear_hover_gate_id()
    clear_hover_handle_key()
    clear_interior_hover_gate_id()
    reset_cursor()
    preview_gate()
    schedule_draw()


def should_clear_hover_outside_axes(
    *,
    hover_gate_id,
    interior_hover_gate_id,
    resolve_hover_handle_key,
) -> bool:
    """Return whether any hover state remains to clear outside the axes.

    Preserve the historical gate-ID checks first.  Only when both IDs are
    absent is the handle-key resolver consulted, which repairs the stray-handle
    invariant without adding handle-state reads to normal outside-axes clears.
    """
    if hover_gate_id is not None or interior_hover_gate_id is not None:
        return True
    return resolve_hover_handle_key() is not None
