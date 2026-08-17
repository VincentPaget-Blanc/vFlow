"""Composed Matplotlib/Tk gate-event controller.

This module owns the stateful click/motion/release orchestration that was
historically embedded in ``FlowApp``.  The host remains the compatibility/UI
facade and provides geometry, render, cache, and widget operations; keeping
those behind the host boundary avoids changing their frozen behavior while the
event lifecycle itself gains an independently testable owner.
"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox

import numpy as np

from matplotlib.path import Path as MplPath
from matplotlib.patches import Rectangle as MplRect, Ellipse as MplEllipse

from vflow.core.cache_keys import (
    evict_cache_keys,
    gate_mask_cache_keys_for_gate_ids,
    gate_signature as _gate_sig,
    scatter_cache_keys_for_gate_signature,
)
from vflow.core.gates import (
    PolygonGeometrySchemaError,
    gate_by_id,
    gate_snapshot,
    is_degenerate_shape_gate,
    iter_gate_draw_assignments,
    iter_gate_draw_initialization_assignments,
    manual_crosshair_gate,
    nearest_cached_handle,
    plan_polygon_close_entry,
    plan_polygon_vertex,
    require_polygon_vertices,
    update_gate_from_control_points,
    bounded_horizontal_line_distance,
    bounded_vertical_line_distance,
    closed_polygon_points,
    crosshair_preview_boundaries,
    ellipse_area,
    ellipse_center_radii,
    ellipse_perimeter_points,
    ellipse_preview_geometry,
    finite_point_pairs,
    gate_control_points,
    gate_handles,
    gate_preview_style,
    handle_display_mode,
    handle_marker_style,
    is_finite_point,
    iter_handle_drag_assignments,
    point_distance,
    point_in_ellipse,
    point_in_rectangle,
    point_to_polyline_min_distance,
    point_to_segment_distance,
    polygon_area,
    polygon_preview_points,
    polygon_rubber_band_points,
    rectangle_area,
    rectangle_bounds,
    rectangle_line_segments,
    rectangle_preview_geometry,
    should_draw_gate_preview,
    smaller_area_hit,
    visible_handle_gate_ids,
)
from vflow.services.gate_assignment_transaction import (
    rollback_gate_assignments as _rollback_gate_assignments,
    snapshot_gate_assignment as _snapshot_gate_assignment,
)
from vflow.services.gate_geometry_interaction import (
    gate_pixel_delta,
    plan_draw_start,
    plan_gate_move_start,
    plan_handle_drag_start,
    resolve_fresh_draw_finalization_path,
    resolve_fresh_draw_release_guard,
    resolve_release_interaction_path,
    run_crosshair_release_side_effect_sequence,
    run_fresh_draw_discard_side_effect_sequence,
    run_fresh_draw_motion_presentation_sequence,
    run_gate_move_motion_presentation_sequence,
    run_gate_move_release_side_effect_sequence,
    run_handle_drag_motion_presentation_sequence,
    run_handle_drag_release_side_effect_sequence,
    run_polygon_motion_presentation_sequence,
    run_shape_release_side_effect_sequence,
    translate_gate_pixel_points,
)
from vflow.services.gate_threshold_planning import manual_crosshair_threshold_plan
from vflow.ui.gate_interaction import (
    continue_hover_hit_testing,
    invoke_hover_cursor_policy,
    invoke_hover_hit_test_plan,
    plan_hover_cursor_policy,
    plan_hover_hit_testing,
    plan_hover_presentation,
    plan_pin_interaction,
    resolve_winning_cached_handle_key,
    run_hover_cursor_application_sequence,
    run_hover_handle_proximity_execution_sequence,
    run_hover_hit_test_execution_sequence,
    run_hover_presentation_sequence,
    run_outside_axes_hover_clear_sequence,
    should_clear_hover_outside_axes,
    iter_handle_pixel_cache_entries,
    resolve_cached_handle_hover_cursor,
    resolve_hover_cursor_gate_id,
    resolve_hover_cursor_nearest_result,
    resolve_hover_cursor_result_projection,
    resolve_hover_cursor_workflow,
    select_nearest_cached_handle_gate,
    should_resolve_hover_cursor,
)
from vflow.config.constants import GATE_PALETTE, HANDLE_PX


def _host_fwd_axis(host, values, scale, axis):
    """Use explicit per-axis parameters only for standards Logicle.

    Historical host test doubles and compatibility callers expose the original
    two-argument ``_fwd`` surface; keep that surface for every legacy scale.
    """
    if scale == "logicle_gml2":
        return host._fwd(values, scale, axis=axis)
    return host._fwd(values, scale)


def _host_inv_axis(host, values, scale, axis):
    if scale == "logicle_gml2":
        return host._inv(values, scale, axis=axis)
    return host._inv(values, scale)


class GateInteractionController:
    """Own click/motion/release lifecycle while delegating host-specific effects."""

    def __init__(self, host):
        self._host = host

    def on_click(self, event):
        host = self._host
        if event.inaxes != host.ax:
            return

        mode = host.gate_mode_var.get()

        # ── DOUBLE-CLICK: close polygon or sub-gate ──
        if event.dblclick:
            close_entry = plan_polygon_close_entry(
                'double_click', polygon_active=host._poly_active, mode=mode
            )
            if close_entry.should_finish:
                host._poly_finish(); return
            if mode == 'none':
                sel = host._sel_gate()
                if sel and sel.get('applied') and host.manager:
                    host._open_subgate(event.xdata, event.ydata)
            return

        # ── RIGHT-CLICK: grab handle, pin gate outline, or close polygon ──
        if event.button == 3:
            close_entry = plan_polygon_close_entry(
                'right_click', polygon_active=host._poly_active, mode=mode
            )
            if close_entry.should_finish:
                host._poly_finish()
                return
            # Try handle drag first (must be within HANDLE_PX)
            hit = host._hit_test_handles(event)
            if hit:
                # Snapshot axis limits so the view stays frozen during the
                # resize drag (same reason as _gate_move frozen limits).
                _missing_frozen_limit = object()
                _previous_frozen_xlim = hit.get('frozen_xlim', _missing_frozen_limit)
                _previous_frozen_ylim = hit.get('frozen_ylim', _missing_frozen_limit)
                try:
                    hit['frozen_xlim'] = list(host.ax.get_xlim())
                    hit['frozen_ylim'] = list(host.ax.get_ylim())
                except Exception:
                    if _previous_frozen_xlim is _missing_frozen_limit:
                        hit.pop('frozen_xlim', None)
                    else:
                        hit['frozen_xlim'] = _previous_frozen_xlim
                    if _previous_frozen_ylim is _missing_frozen_limit:
                        hit.pop('frozen_ylim', None)
                    else:
                        hit['frozen_ylim'] = _previous_frozen_ylim
                    raise
                host._handle_drag = hit
                handle_plan = plan_handle_drag_start(
                    gate_id=hit['gate_id'],
                    selected_gate_id=host._sel_gate_id,
                )
                host._drag_last_draw = handle_plan.drag_last_draw   # first frame never dropped
                host._start_blit_drag()      # capture scatter background once at press
                if handle_plan.select_gate_id is not None:
                    host._sel_gate_id = handle_plan.select_gate_id
                    host._rebuild_gate_manager()
                    host._rebuild_thresh_panel()
                return
            # Right-drag inside gate body moves the whole gate (any mode).
            # Handle hit-test already returned above, so corner handles always win.
            # Not active during polygon drawing (_poly_active already handled above).
            if not host._poly_active:
                hit_gate = host._hit_test_gate_interior(event)
                if hit_gate is not None:
                    # Record press and original gate geometry in display pixels so
                    # the gate translates rigidly regardless of axis scale (log, biexp…).
                    orig_px = host._gate_pts_to_pixels(hit_gate)
                    # Materialize in frozen v4.1.11 expression order before
                    # handing the plain payload to the Tk-free planner.
                    move_gate_id = hit_gate['id']
                    move_snapshot = gate_snapshot(
                        hit_gate,
                        excluded_types=(tk.BooleanVar, tk.Variable),
                    ) #Replaced copy.deepcopy with a copy method that skips Tkinter objects.
                    move_press_px = np.array([event.x, event.y], dtype=float)
                    move_frozen_xlim = list(host.ax.get_xlim())
                    move_frozen_ylim = list(host.ax.get_ylim())
                    move_plan = plan_gate_move_start(
                        gate_id=move_gate_id,
                        gate=hit_gate,
                        original_gate_snapshot=move_snapshot,
                        press_pixel_point=move_press_px,
                        original_pixel_points=orig_px,   # (N,2) display-pixel coords of original gate
                        # Snapshot current axis limits so the view stays frozen
                        # during the drag.  _preview_gate() calls ax.plot() / add_patch()
                        # which participate in matplotlib autoscale: if gate vertices
                        # reach beyond the current view the axes would zoom out mid-drag.
                        # Restoring these limits each frame keeps the view pixel-stable.
                        frozen_xlim=move_frozen_xlim,
                        frozen_ylim=move_frozen_ylim,
                        selected_gate_id=host._sel_gate_id,
                    )
                    host._gate_move = move_plan.payload
                    host._drag_last_draw = move_plan.drag_last_draw   # reset throttle: first frame never dropped
                    host._start_blit_drag()       # capture scatter background once at press
                    if move_plan.clear_interior_hover:
                        host._interior_hover_gate_id = None
                    if move_plan.select_gate_id is not None:
                        host._sel_gate_id = move_plan.select_gate_id
                        host._rebuild_gate_manager()
                        host._rebuild_thresh_panel()
                    return
            # Try line hit: right-click on a gate line pins/unpins handles
            line_gid = host._hit_test_gate_line(event, threshold_px=10)
            pin_plan = plan_pin_interaction(
                line_gate_id=line_gid,
                pinned_gate_id=host._pinned_gate_id,
            )
            if pin_plan.redraw:
                host._pinned_gate_id = pin_plan.pinned_gate_id
                if pin_plan.update_selection:
                    host._sel_gate_id = pin_plan.selected_gate_id
                    host._rebuild_gate_manager()
                    host._rebuild_thresh_panel()
                host._preview_gate()
                host.canvas.draw_idle()
            return

        # ── LEFT-CLICK: draw mode only ────────────────────────────────────
        if mode != 'draw':
            return

        x, y = event.xdata, event.ydata
        gt   = host.gate_type_var.get()

        draw = host._draw_gate_obj()

        if gt == 'polygon':
            if not host._poly_active or draw is None:
                gate = host._add_gate()
                host._draw_gate_id = gate['id']
                # Milestone 19 source-contract marker retained for regression history:
                # begin_gate_draw(gate, 'polygon', x, y)
                gate['type'] = 'polygon'
                gate['vertices'] = [plan_polygon_vertex('initialize', x, y).vertex]
                host._poly_active = True
                host._drag_last_draw = 0.0   # first rubber-band frame never dropped
                host._start_blit_drag()      # capture scatter background once for polygon session
            else:
                # Milestone 19 source-contract marker retained for regression history:
                # append_polygon_vertex(draw, x, y)
                try:
                    require_polygon_vertices(
                        draw.setdefault('vertices', []), operation='vertex append'
                    ).append(plan_polygon_vertex('append', x, y).vertex)
                except PolygonGeometrySchemaError as exc:
                    try:
                        messagebox.showerror(
                            'Polygon Gate',
                            f"Cannot add a polygon vertex because its geometry is invalid.\n\n{exc}"
                        )
                    except Exception:
                        pass
                    return
            host._update_poly_close_btn()
            host._preview_gate(skip_cache=True)
            host._blit_render()
            return

        if draw is None or draw.get('applied'):
            # ── Crosshair special rule: only one manual crosshair allowed ──
            # If a manual crosshair (auto_method=None) already exists, reuse it
            # in-place rather than stacking up duplicates.  The user can always
            # adjust position by right-drag on the handles.
            if gt == 'crosshair':
                existing = manual_crosshair_gate(host.gates)
                if existing:
                    gate = existing
                    host._draw_gate_id = gate['id']
                    host._sel_gate_id  = gate['id']
                else:
                    gate = host._add_gate()
                    host._draw_gate_id = gate['id']
            else:
                gate = host._add_gate()
                host._draw_gate_id = gate['id']
        else:
            gate = draw

        # BR11 / BR-GEO-001: keep the historical live assignment/evaluation
        # order, but make the geometry update failure-atomic.  Axis snapshot
        # failures below deliberately remain outside this transaction (BR08).
        _geometry_before = {}
        _geometry_order = []
        try:
            _snapshot_gate_assignment(gate, 'type', _geometry_before, _geometry_order)
            gate['type'] = gt
            for key, value in iter_gate_draw_initialization_assignments(gt, x, y):
                _snapshot_gate_assignment(gate, key, _geometry_before, _geometry_order)
                gate[key] = value
        except Exception:
            _rollback_gate_assignments(gate, _geometry_before, _geometry_order)
            raise

        draw_plan = plan_draw_start()
        _previous_moving_gate = host.moving_gate
        _previous_drag_last_draw = host._drag_last_draw
        _previous_draw_frozen_xlim = host._draw_frozen_xlim
        _previous_draw_frozen_ylim = host._draw_frozen_ylim
        try:
            host.moving_gate = draw_plan.moving_gate
            host._drag_last_draw = draw_plan.drag_last_draw   # first frame never dropped
            host._draw_frozen_xlim = list(host.ax.get_xlim())
            host._draw_frozen_ylim = list(host.ax.get_ylim())
        except Exception:
            host.moving_gate = _previous_moving_gate
            host._drag_last_draw = _previous_drag_last_draw
            host._draw_frozen_xlim = _previous_draw_frozen_xlim
            host._draw_frozen_ylim = _previous_draw_frozen_ylim
            raise
        host._start_blit_drag()      # capture scatter background once at press
        host._preview_gate(skip_cache=True)
        host._blit_render()

    def on_motion(self, event):
        host = self._host
        # ── Handle drag: must work even when cursor moves outside axes ──
        if host._handle_drag:
            # event.x/y are mpl display coords (y=0 bottom); invert to data coords
            try:
                x, y = host.ax.transData.inverted().transform((event.x, event.y))
            except Exception:
                return
            # Update geometry on every event (same pattern as _gate_move).
            # Rendering is throttled below; geometry must always be current so
            # the next rendered frame uses the latest cursor position.
            host._drag_handle_update(x, y)

            # Throttle: cap redraws at ~60 fps (16 ms minimum between frames).
            # Clock ownership and arithmetic remain here; the headless helper only
            # sequences post-geometry presentation callbacks.
            def _resolve_handle_drag_redraw_time():
                now = time.monotonic()
                if now - host._drag_last_draw < 0.016:
                    return None
                return now

            def _commit_handle_drag_redraw_time(now):
                host._drag_last_draw = now

            # Restore frozen axis limits to prevent autoscale expansion when
            # a corner handle is dragged near or beyond the current view edge.
            # Keep both payload reads here and after preview, matching v4.1.11.
            def _restore_handle_drag_frozen_axes():
                try:
                    host.ax.set_xlim(host._handle_drag['frozen_xlim'])
                    host.ax.set_ylim(host._handle_drag['frozen_ylim'])
                except Exception:
                    pass

            run_handle_drag_motion_presentation_sequence(
                resolve_redraw_time=_resolve_handle_drag_redraw_time,
                commit_redraw_time=_commit_handle_drag_redraw_time,
                preview_gate=lambda: host._preview_gate(skip_cache=True),
                restore_frozen_axes=_restore_handle_drag_frozen_axes,
                render_frame=lambda: host._blit_render(),
            )
            return

        # ── Gate-body move (right-drag inside gate, any mode) ────────────────
        # Uses display-pixel arithmetic so the gate shape stays visually rigid
        # on any axis scale (linear, log, biexp).  Each motion event applies a
        # pixel delta to the pre-computed original pixel coords and batch-inverts
        # them back to data space — one NumPy call regardless of gate complexity.
        if host._gate_move:
            info = host._gate_move
            gate = info['gate']
            gid  = gate['id']
            # Pixel delta from press point (free 2-D movement, no axis constraint)
            # and rigid translation of the original control points stay as one
            # exception-free, Tk/matplotlib-independent calculation.  Keep this
            # outside the inverse-transform try/except to preserve v4.1.11's
            # arithmetic exception boundary exactly.
            dpx = gate_pixel_delta(
                current_pixel=event.x, press_pixel=info['press_px'][0]
            )
            dpy = gate_pixel_delta(
                current_pixel=event.y, press_pixel=info['press_px'][1]
            )
            shifted_px = translate_gate_pixel_points(
                original_pixel_points=info['orig_px'],
                delta_x=dpx,
                delta_y=dpy,
            )

            # Invert translated pixel coords to data space in one batch.
            try:
                new_data = host.ax.transData.inverted().transform(shifted_px)
            except Exception:
                return
            # Evict stale caches (same pattern as _drag_handle_update)
            stale = gate_mask_cache_keys_for_gate_ids(host._gmc, [gid])
            evict_cache_keys(host._gmc, stale)
            host._analysis_cache_obj().clear_scatter()
            update_gate_from_control_points(gate, new_data)

            # Throttle: cap redraws at ~60 fps (16 ms minimum between frames).
            # Intermediate positions are skipped when the mouse moves faster than
            # the renderer; _drag_last_draw = 0 at press time so frame 1 never drops.
            # Clock ownership and arithmetic remain here; the headless helper only
            # sequences the post-geometry presentation callbacks.
            def _resolve_gate_move_redraw_time():
                now = time.monotonic()
                if now - host._drag_last_draw < 0.016:
                    return None
                return now

            def _commit_gate_move_redraw_time(now):
                host._drag_last_draw = now

            # Correct axis limits: _preview_gate() calls ax.plot()/add_patch() which
            # participate in autoscale and can expand the view if a vertex moves near
            # the axes edge.  Restoring frozen_xlim/ylim keeps the visual context stable
            # and ensures draw_artist() uses the same transform as the render background.
            def _restore_gate_move_frozen_axes():
                try:
                    host.ax.set_xlim(info['frozen_xlim'])
                    host.ax.set_ylim(info['frozen_ylim'])
                except Exception:
                    pass

            run_gate_move_motion_presentation_sequence(
                resolve_redraw_time=_resolve_gate_move_redraw_time,
                commit_redraw_time=_commit_gate_move_redraw_time,
                preview_gate=lambda: host._preview_gate(skip_cache=True),
                restore_frozen_axes=_restore_gate_move_frozen_axes,
                render_frame=lambda: host._blit_render(),
            )
            return

        mode = host.gate_mode_var.get()
        gt   = host.gate_type_var.get()

        # ── FIX BUG 7: Polygon rubber-band update ────────────────────────
        # Check for active polygon drawing BEFORE the `inaxes` guard so the
        # preview line tracks the cursor even when it strays outside the axes.
        # Use event.xdata/ydata when available (cursor is in axes); keep the
        # last known position when the cursor is outside (xdata is None).
        if gt == 'polygon' and host._poly_active and mode == 'draw':
            if event.xdata is not None and event.ydata is not None:
                # Cursor is inside the axes — use the exact data coordinate.
                host._poly_cursor = (event.xdata, event.ydata)
            # else: cursor outside axes — _poly_cursor retains its last value,
            # so the rubber-band line stays connected to the last in-axes point
            # rather than freezing or disappearing.

            # Throttle: cap redraws at ~60 fps.  Cursor-coordinate reads and
            # mutation stay above; the headless helper only sequences the
            # post-cursor presentation callbacks.
            def _resolve_polygon_redraw_time():
                now = time.monotonic()
                if now - host._drag_last_draw < 0.016:
                    return None
                return now

            def _commit_polygon_redraw_time(now):
                host._drag_last_draw = now

            run_polygon_motion_presentation_sequence(
                resolve_redraw_time=_resolve_polygon_redraw_time,
                commit_redraw_time=_commit_polygon_redraw_time,
                preview_gate=lambda: host._preview_gate(skip_cache=True),
                render_frame=lambda: host._blit_render(),
            )
            return

        # ── Hover detection: show/hide handles — skip when actively drawing ──
        if not host.moving_gate and not host._poly_active:
            if event.inaxes == host.ax:
                # Handle-proximity execution remains controller-owned through
                # callbacks; the headless helper preserves only conditional
                # gate-to-nearest-to-winning-key sequencing.
                new_hover, new_hover_handle_key = run_hover_handle_proximity_execution_sequence(
                    resolve_handle_gate_id=lambda: host._hover_test_handles(event),
                    resolve_nearest_handle=lambda gate_id: nearest_cached_handle(
                        host._handle_px_cache.get(gate_id, []),
                        gate_id_value=gate_id,
                        x=event.x,
                        y=event.y,
                        threshold=HANDLE_PX * 2.5,
                    ),
                    project_handle_key=lambda nearest: resolve_winning_cached_handle_key(nearest),
                )

                # If no handle nearby, test line proximity only when hover state needs update
                # (line test calls transData.transform per segment — limit to state changes).
                # Pure orchestration decides only which geometric test runs next; all actual
                # handle/line/interior hit calculations remain in FlowApp.
                hit_test_plan = invoke_hover_hit_test_plan(
                    planner=plan_hover_hit_testing,
                    handle_gate_id=new_hover,
                    hover_handle_key=new_hover_handle_key,
                    current_hover_gate_id=host._hover_gate_id,
                    current_pos=(event.x, event.y),
                    last_line_test_pos=getattr(host, '_last_line_test_pos', None),
                    min_delta=10,
                )
                # Optional line/interior hit-test execution remains controller-owned
                # through callbacks; the headless helper preserves only legacy
                # field-access, commit, continuation, and optional-test ordering.
                new_hover, new_interior = run_hover_hit_test_execution_sequence(
                    plan=hit_test_plan,
                    mode=mode,
                    commit_line_test_pos=lambda value: setattr(host, '_last_line_test_pos', value),
                    run_line_test=lambda: host._hit_test_gate_line(event, threshold_px=8),
                    continue_hit_testing=lambda **kwargs: continue_hover_hit_testing(**kwargs),
                    run_interior_test=lambda: host._hit_test_gate_interior(event),
                )

                # Update Tk cursor
                try:
                    cursor_policy = invoke_hover_cursor_policy(
                        planner=plan_hover_cursor_policy,
                        new_hover=new_hover,
                        pinned_gate_id=host._pinned_gate_id,
                        new_interior=new_interior,
                    )
                    run_hover_cursor_application_sequence(
                        cursor_policy=cursor_policy,
                        resolve_hover_cursor=lambda: host._cursor_for_hover(event),
                        apply_cursor=lambda cursor: host.canvas.get_tk_widget().config(cursor=cursor),
                    )
                except Exception:
                    pass

                # Redraw whenever any hover state changed
                hover_plan = plan_hover_presentation(
                    new_hover=new_hover,
                    old_hover=host._hover_gate_id,
                    new_hover_handle_key=hit_test_plan.hover_handle_key,
                    old_hover_handle_key=host._hover_handle_key,
                    new_interior=new_interior,
                    old_interior=host._interior_hover_gate_id,
                )
                hover_redraw = run_hover_presentation_sequence(
                    plan=hover_plan,
                    commit_hover_gate_id=lambda value: setattr(host, '_hover_gate_id', value),
                    commit_hover_handle_key=lambda value: setattr(host, '_hover_handle_key', value),
                    commit_interior_hover_gate_id=lambda value: setattr(host, '_interior_hover_gate_id', value),
                    preview_gate=lambda: host._preview_gate(),
                    schedule_draw=lambda: host.canvas.draw_idle(),
                )
                if hover_redraw:
                    return
            elif should_clear_hover_outside_axes(
                hover_gate_id=host._hover_gate_id,
                interior_hover_gate_id=host._interior_hover_gate_id,
                resolve_hover_handle_key=lambda: host._hover_handle_key,
            ):
                def _reset_outside_axes_hover_cursor():
                    try:
                        host.canvas.get_tk_widget().config(cursor='')
                    except Exception:
                        pass

                run_outside_axes_hover_clear_sequence(
                    clear_hover_gate_id=lambda: setattr(host, '_hover_gate_id', None),
                    clear_hover_handle_key=lambda: setattr(host, '_hover_handle_key', None),
                    clear_interior_hover_gate_id=lambda: setattr(host, '_interior_hover_gate_id', None),
                    reset_cursor=_reset_outside_axes_hover_cursor,
                    preview_gate=lambda: host._preview_gate(),
                    schedule_draw=lambda: host.canvas.draw_idle(),
                )
                return

        if event.inaxes != host.ax:
            return
        x, y = event.xdata, event.ydata

        if not host.moving_gate:
            return
        gate = host._draw_gate_obj()
        if not gate:
            return

        _geometry_before = {}
        _geometry_order = []
        try:
            for key, value in iter_gate_draw_assignments(gate, x, y):
                _snapshot_gate_assignment(gate, key, _geometry_before, _geometry_order)
                gate[key] = value
        except Exception:
            _rollback_gate_assignments(gate, _geometry_before, _geometry_order)
            raise

        # Throttle: cap redraws at ~60 fps.  Geometry/event/gate ownership
        # remains above; the headless helper only sequences post-geometry
        # presentation callbacks.
        def _resolve_fresh_draw_redraw_time():
            now = time.monotonic()
            if now - host._drag_last_draw < 0.016:
                return None
            return now

        def _commit_fresh_draw_redraw_time(now):
            host._drag_last_draw = now

        # Restore frozen axis limits to prevent autoscale expansion as the
        # gate corner is dragged toward or beyond the current view edge.
        # Keep the guard and broad exception policy controller-owned.
        def _restore_fresh_draw_frozen_axes():
            if host._draw_frozen_xlim is not None:
                try:
                    host.ax.set_xlim(host._draw_frozen_xlim)
                    host.ax.set_ylim(host._draw_frozen_ylim)
                except Exception:
                    pass

        run_fresh_draw_motion_presentation_sequence(
            resolve_redraw_time=_resolve_fresh_draw_redraw_time,
            commit_redraw_time=_commit_fresh_draw_redraw_time,
            preview_gate=lambda: host._preview_gate(skip_cache=True),
            restore_frozen_axes=_restore_fresh_draw_frozen_axes,
            render_frame=lambda: host._blit_render(),
        )

    def on_release(self, event):
        host = self._host
        release_path = resolve_release_interaction_path(
            get_handle_drag=lambda: host._handle_drag,
            get_gate_move=lambda: host._gate_move,
            get_moving_gate=lambda: host.moving_gate,
        )

        # ── Finish handle drag (any button) ──
        if release_path == 'handle_drag':
            def _resolve_handle_drag_gate():
                return gate_by_id(host.gates, host._handle_drag['gate_id'])

            def _clear_handle_drag():
                host._handle_drag = None

            def _clear_handle_hover_gate_id():
                host._hover_gate_id = None   # hide handles after release

            def _clear_handle_frozen_xlim():
                # BUG FIX (B25): release any frozen-axis snapshots
                host._draw_frozen_xlim = None

            def _clear_handle_frozen_ylim():
                host._draw_frozen_ylim = None

            run_handle_drag_release_side_effect_sequence(
                resolve_gate=_resolve_handle_drag_gate,
                clear_handle_drag=_clear_handle_drag,
                clear_hover_gate_id=_clear_handle_hover_gate_id,
                clear_frozen_xlim=_clear_handle_frozen_xlim,
                clear_frozen_ylim=_clear_handle_frozen_ylim,
                end_render_snapshot=host._end_blit_drag,
                finish_gate=lambda gate: host._finish_gate(gate),
            )
            return

        # ── Finish gate-body move ─────────────────────────────────────────────
        if release_path == 'gate_move':
            def _resolve_gate_move_gate():
                return host._gate_move['gate']

            def _clear_gate_move():
                host._gate_move = None

            def _clear_interior_hover_gate_id():
                host._interior_hover_gate_id = None

            def _clear_gate_move_frozen_xlim():
                # BUG FIX (B25): release any frozen-axis snapshots
                host._draw_frozen_xlim = None

            def _clear_gate_move_frozen_ylim():
                host._draw_frozen_ylim = None

            run_gate_move_release_side_effect_sequence(
                resolve_gate=_resolve_gate_move_gate,
                clear_gate_move=_clear_gate_move,
                clear_interior_hover_gate_id=_clear_interior_hover_gate_id,
                clear_frozen_xlim=_clear_gate_move_frozen_xlim,
                clear_frozen_ylim=_clear_gate_move_frozen_ylim,
                end_render_snapshot=host._end_blit_drag,
                finish_gate=lambda gate: host._finish_gate(gate),
            )
            return

        if release_path == 'inactive':
            return
        host.moving_gate = False
        # BUG FIX (B25): release frozen-axis snapshots taken at click time
        # so a later autoscale / fit-axes operation isn't surprised by
        # stale data left over from the previous drag.
        host._draw_frozen_xlim = None
        host._draw_frozen_ylim = None

        release_guard = resolve_fresh_draw_release_guard(
            get_gate=lambda: host._draw_gate_obj(),
            get_x_coord=lambda: event.xdata,
            get_y_coord=lambda: event.ydata,
        )
        gate = release_guard.gate
        # Guard: released outside axes or None coords
        if release_guard.should_discard:
            run_fresh_draw_discard_side_effect_sequence(
                end_render_snapshot=host._end_blit_drag,
                get_gate_for_truth_test=lambda: gate,
                get_applied=lambda: gate.get('applied'),
                get_gate_id=lambda: gate['id'],
                delete_gate=host._del_gate,
            )
            return

        x, y = release_guard.x, release_guard.y
        finalization_path = resolve_fresh_draw_finalization_path(
            get_gate_type=lambda: gate.get('type', 'crosshair'),
        )

        if finalization_path == 'crosshair':
            def _apply_crosshair_geometry():
                _geometry_before = {}
                _geometry_order = []
                try:
                    for key, value in iter_gate_draw_assignments(gate, x, y):
                        _snapshot_gate_assignment(gate, key, _geometry_before, _geometry_order)
                        gate[key] = value
                except Exception:
                    _rollback_gate_assignments(gate, _geometry_before, _geometry_order)
                    raise

            def _crosshair_threshold_plan():
                return manual_crosshair_threshold_plan()

            def _materialize_x_threshold_vars(thresh_plan):
                gate['x_thresh_vars'] = [tk.BooleanVar(value=value)
                                         for value in thresh_plan.x_values]

            def _materialize_y_threshold_var(thresh_plan):
                gate['y_thresh_var']  = tk.BooleanVar(value=thresh_plan.y_value)

            def _mark_crosshair_applied():
                gate['applied']       = True

            def _clear_crosshair_draw_gate_id():
                host._draw_gate_id = None

            run_crosshair_release_side_effect_sequence(
                apply_geometry=_apply_crosshair_geometry,
                get_threshold_plan=_crosshair_threshold_plan,
                materialize_x_threshold_vars=_materialize_x_threshold_vars,
                materialize_y_threshold_var=_materialize_y_threshold_var,
                mark_applied=_mark_crosshair_applied,
                clear_draw_marker=_clear_crosshair_draw_gate_id,
                end_render_snapshot=host._end_blit_drag,
                finish_gate=lambda: host._finish_gate(gate),
            )
            return
        elif finalization_path == 'shape':
            def _apply_shape_geometry():
                _geometry_before = {}
                _geometry_order = []
                try:
                    for key, value in iter_gate_draw_assignments(gate, x, y):
                        _snapshot_gate_assignment(gate, key, _geometry_before, _geometry_order)
                        gate[key] = value
                except Exception:
                    _rollback_gate_assignments(gate, _geometry_before, _geometry_order)
                    raise

            def _shape_is_degenerate():
                return is_degenerate_shape_gate(gate)

            def _shape_gate_id():
                return gate['id']

            def _delete_shape_gate(gate_id):
                host._del_gate(gate_id)

            def _mark_shape_applied():
                gate['applied'] = True

            def _clear_shape_draw_gate_id():
                host._draw_gate_id = None

            run_shape_release_side_effect_sequence(
                apply_geometry=_apply_shape_geometry,
                is_degenerate=_shape_is_degenerate,
                end_render_snapshot=host._end_blit_drag,
                get_gate_id=_shape_gate_id,
                delete_gate=_delete_shape_gate,
                mark_applied=_mark_shape_applied,
                clear_draw_marker=_clear_shape_draw_gate_id,
                finish_gate=lambda: host._finish_gate(gate),
            )
            return
        else:
            return  # polygon finishes via _poly_finish

    def get_handles(self, gate: dict) -> list:
        """
        Return list of handle dicts for editing this gate.
        Each: {'x', 'y', 'handle', 'idx'}  — coordinates in data space.
        """
        host = self._host
        return gate_handles(gate)

    def draw_handles(self):
        """
        Draw handle markers for:
        - The gate being dragged (filled square on the active handle only)
        - Handle-proximity hover: only the nearest handle shown, filled (resize signal)
        - Interior-body hover in draw mode: all handles filled (move-whole-gate signal)
        - Line-proximity hover: all handles as open circles (general hover)
        - The pinned gate (semi-filled circles, persists after right-click)
        """
        host = self._host
        host._handle_artists = []
        drag_gid = host._handle_drag['gate_id'] if host._handle_drag else None
        # Collect all gate ids that need handles drawn
        show_gids = visible_handle_gate_ids(
            drag_gate_id=drag_gid,
            hover_gate_id=host._hover_gate_id,
            pinned_gate_id=host._pinned_gate_id,
            interior_hover_gate_id=host._interior_hover_gate_id,
        )
        if not show_gids:
            return

        for gate in host.gates:
            if not gate.get('applied') or gate['id'] not in show_gids:
                continue
            gid     = gate['id']
            handles = self.get_handles(gate)
            color   = gate.get('color', GATE_PALETTE[0])

            # Classify display mode for this gate's handles:
            #   'drag'         — a handle is actively being right-dragged
            #   'interior'     — cursor is inside gate body (draw mode): all filled
            #   'handle_hover' — cursor is near one specific handle: that handle only
            #   'line_hover'   — cursor is near gate line, not a handle: all open circles
            #   'pinned'       — gate was right-clicked on a line to pin its handles
            disp = handle_display_mode(
                gid,
                drag_gate_id=drag_gid,
                interior_hover_gate_id=host._interior_hover_gate_id,
                hover_gate_id=host._hover_gate_id,
                hover_handle_key=host._hover_handle_key,
            )
            drag_handle_key = (
                drag_gid,
                host._handle_drag.get('handle'),
                host._handle_drag.get('idx'),
            ) if host._handle_drag else None

            for h in handles:
                h_key = (gid, h['handle'], h['idx'])
                style = handle_marker_style(
                    disp,
                    handle_key=h_key,
                    color=color,
                    drag_handle_key=drag_handle_key,
                    hover_handle_key=host._hover_handle_key,
                )
                if style is None:
                    continue

                a, = host.ax.plot(h['x'], h['y'],
                                  marker=style['marker'], ms=style['ms'],
                                  markerfacecolor=style['mfc'],
                                  markeredgecolor=color,
                                  markeredgewidth=style['mew'],
                                  linestyle='none', zorder=20)
                a._flowjo_handle = {'gate_id': gid,
                                    'handle':  h['handle'],
                                    'idx':     h['idx']}
                host._handle_artists.append(a)

    def hit_test_handles(self, event) -> dict:
        """
        Return handle drag info if the click is within HANDLE_PX*2.5 pixels
        of any handle on any applied gate.

        The threshold deliberately matches _hover_test_handles (also HANDLE_PX*2.5)
        so that when the user sees a highlighted handle (hover) and right-clicks on
        it, the click is guaranteed to fall within the hit-test radius.

        Previously used HANDLE_PX (12px) while hover used HANDLE_PX*2.5 (30px),
        creating a dead zone of 13-29px where handles were highlighted but clicks
        silently fell through to the interior-move path — making resize appear broken
        for loaded gates whose on-screen scale could position handles anywhere.

        Computed directly from gate geometry (not from artists) so that
        handles do not need to be visible to be draggable.
        """
        host = self._host
        best, best_dist = None, float('inf')
        threshold = HANDLE_PX * 2.5   # match hover threshold — no dead zone
        for gate in host.gates:
            if not gate.get('applied'):
                continue
            for h in self.get_handles(gate):
                try:
                    px, py = host.ax.transData.transform((h['x'], h['y']))
                except Exception:
                    continue
                dist = point_distance(px, py, event.x, event.y)
                if dist < threshold and dist < best_dist:
                    best_dist = dist
                    best = {'gate_id': gate['id'],
                            'gate':    gate,
                            'handle':  h['handle'],
                            'idx':     h['idx'],
                            # FIX v4.1.3 Bug 1: copy.deepcopy(gate) raises TypeError
                            # on loaded gates whose dict contains tk.BooleanVar /
                            # tk.Variable objects.  This caused _hit_test_handles to
                            # crash silently and return None, making every right-click
                            # on a handle fall through to the body-move path — breaking
                            # resize for all loaded gate types (rectangle, ellipse,
                            # polygon).  Replaced with the same Tkinter-safe shallow
                            # dict comprehension used in the _gate_move block; only
                            # plain float values (x0/x1/y0/y1) are ever read from
                            # 'orig' inside _drag_handle_update, so shallow is correct.
                            'orig':    gate_snapshot(
                                gate,
                                excluded_types=(tk.BooleanVar, tk.Variable),
                            )}
        return best

    def gate_pts_to_pixels(self, gate: dict) -> np.ndarray:
        """Return gate control points as a (N,2) array of display pixels.

        For rectangle/ellipse: rows are [(x0,y0), (x1,y1)] in data space,
        transformed to display pixels.
        For polygon: one row per vertex.

        Used by the pixel-space move to record the original shape at press time
        so motion events apply a pure pixel translation then invert to data space —
        preserving visual shape on any axis scale (linear, log, biexp…).
        """
        host = self._host
        points = gate_control_points(gate)
        pts = np.array(points, dtype=float) if points else np.zeros((0, 2))
        if len(pts) == 0:
            return pts
        try:
            return host.ax.transData.transform(pts)
        except Exception:
            return pts

    def hit_test_gate_interior(self, event) -> dict:
        """Return the smallest applied rect/ellipse/polygon gate whose interior
        contains (event.xdata, event.ydata), or None.

        Crosshair gates are excluded — they span the full axes.
        When gates overlap, the one with the smallest area is returned so that
        nested/inner gates can be targeted independently of outer ones.
        Only meaningful when event.xdata/ydata are valid (cursor inside axes).

        Performance: expensive transform-space area work is deferred until a
        rectangle/ellipse actually contains the pointer.  Polygon candidates
        first use a raw coordinate bounding-box rejection (all supported axis
        transforms are coordinate-wise monotonic), and the transformed event
        coordinate is reused across polygon candidates within this hit test.
        """
        host = self._host
        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return None
        best, best_area = None, float('inf')
        polygon_x_t = None
        polygon_y_t = None
        for gate in host.gates:
            if not gate.get('applied'):
                continue
            gt     = gate.get('type', 'crosshair')
            inside = False
            area   = float('inf')
            if gt == 'rectangle':
                bounds = rectangle_bounds(gate)
                xlo, xhi, ylo, yhi = bounds
                inside = point_in_rectangle(x, y, bounds)
                if inside:
                    # Area in transform space for tiebreak consistency against
                    # polygons.  Outside gates never participate in the area
                    # comparison, so avoid the transforms entirely for them.
                    try:
                        xs_t = _host_fwd_axis(host, np.array([xlo, xhi], float), host.x_scale, "x")
                        ys_t = _host_fwd_axis(host, np.array([ylo, yhi], float), host.y_scale, "y")
                        if np.all(np.isfinite(xs_t)) and np.all(np.isfinite(ys_t)):
                            area = float((xs_t[1] - xs_t[0]) * (ys_t[1] - ys_t[0]))
                        else:
                            area = rectangle_area(bounds)
                    except Exception:
                        area = rectangle_area(bounds)
            elif gt == 'ellipse':
                cx, cy, rx, ry = ellipse_center_radii(gate)
                if rx > 0 and ry > 0:
                    inside = point_in_ellipse(x, y, (cx, cy, rx, ry))
                    if inside:
                        # As above, transform-space area is relevant only for
                        # a containing candidate.
                        try:
                            xs_t = _host_fwd_axis(
                                host, np.array([cx-rx, cx+rx], float), host.x_scale, "x")
                            ys_t = _host_fwd_axis(
                                host, np.array([cy-ry, cy+ry], float), host.y_scale, "y")
                            if np.all(np.isfinite(xs_t)) and np.all(np.isfinite(ys_t)):
                                area = float(np.pi * (xs_t[1] - xs_t[0]) / 2
                                             * (ys_t[1] - ys_t[0]) / 2)
                            else:
                                area = ellipse_area(rx, ry)
                        except Exception:
                            area = ellipse_area(rx, ry)
            elif gt == 'polygon':
                verts = gate.get('vertices', [])
                if len(verts) >= 3:
                    try:
                        vx_values = [v[0] for v in verts]
                        vy_values = [v[1] for v in verts]
                        # Every supported vFlow axis transform is monotonic in
                        # its own coordinate.  Therefore a point outside the raw
                        # axis-aligned vertex bounds cannot be inside the same
                        # polygon after independent X/Y transformation.  Use
                        # scalar min/max before allocating NumPy arrays: most
                        # hover candidates are rejected here.
                        if (x < min(vx_values) or x > max(vx_values) or
                                y < min(vy_values) or y > max(vy_values)):
                            pass
                        else:
                            vx_raw = np.asarray(vx_values, dtype=float)
                            vy_raw = np.asarray(vy_values, dtype=float)
                            vx_t = _host_fwd_axis(host, vx_raw, host.x_scale, "x")
                            vy_t = _host_fwd_axis(host, vy_raw, host.y_scale, "y")
                            if polygon_x_t is None:
                                polygon_x_t = float(_host_fwd_axis(
                                    host, np.asarray([x], dtype=float), host.x_scale, "x")[0])
                            if polygon_y_t is None:
                                polygon_y_t = float(_host_fwd_axis(
                                    host, np.asarray([y], dtype=float), host.y_scale, "y")[0])
                            verts_t = finite_point_pairs(vx_t, vy_t)
                            if (len(verts_t) >= 3 and
                                    is_finite_point(polygon_x_t, polygon_y_t)):
                                path = MplPath(verts_t + [verts_t[0]])
                                inside = path.contains_point((polygon_x_t, polygon_y_t))
                                if inside:
                                    # Shoelace area in transform space — this is
                                    # the area as seen on the canvas, the only
                                    # meaningful tie-break for nested gates.
                                    area = polygon_area(verts_t)
                    except Exception:
                        pass
            best, best_area = smaller_area_hit(
                best,
                best_area,
                gate,
                inside=inside,
                area=area,
            )
        return best

    def rebuild_handle_px_cache(self, event=None):
        """Cache all handle positions in display pixels after a full redraw.
        Avoids calling transData.transform() on every mouse-move event.

        The optional *event* parameter is accepted so this method can be
        registered directly as a draw_event callback (Matplotlib passes the
        DrawEvent object); it is not used internally.
        """
        host = self._host
        host._handle_px_cache = {}
        for gate, entries in iter_handle_pixel_cache_entries(
            host.gates,
            get_handles=lambda gate: self.get_handles(gate),
            make_entries=lambda handles: handle_cache_entries(
                handles, host.ax.transData.transform
            ),
        ):
            host._handle_px_cache[gate['id']] = entries

    def hit_test_gate_line(self, event, threshold_px: int = 8) -> int:
        """
        Return gate_id if the cursor is within threshold_px of any drawn gate
        outline (axvline, axhline, rectangle edge, ellipse perimeter, polygon edge).
        Returns None if no line is close.
        Used for right-click pinning and extended hover detection.

        Shape outlines are transformed in batches and their segment distances
        are evaluated vectorially.  If a custom/failed transform cannot process
        a batch, the historical point-by-point path is used for that gate so
        failure isolation remains conservative.
        """
        host = self._host
        ex, ey = event.x, event.y   # display pixels, y=0 at bottom

        def _data_to_px(dx, dy):
            try:
                return host.ax.transData.transform((dx, dy))
            except Exception:
                return None

        def _batch_points_to_px(points):
            """Return (pixel_points, used_batch) with scalar fallback."""
            try:
                raw = np.asarray(points, dtype=float)
                transformed = np.asarray(host.ax.transData.transform(raw), dtype=float)
                if transformed.shape == raw.shape:
                    return transformed, True
            except Exception:
                pass
            return [_data_to_px(*point) for point in points], False

        def _legacy_segment_min_distance(pixel_points, *, closed=False):
            """Preserve scalar fallback semantics when batch transform fails."""
            if closed:
                pairs = [
                    (pixel_points[i], pixel_points[(i + 1) % len(pixel_points)])
                    for i in range(len(pixel_points))
                ]
            else:
                pairs = list(zip(pixel_points[:-1], pixel_points[1:]))
            best = float('inf')
            for pa, pb in pairs:
                if pa is None or pb is None:
                    continue
                d = point_to_polyline_min_distance(
                    ex, ey, np.asarray([pa, pb], dtype=float), closed=False)
                if d < best:
                    best = d
            return best

        # Get axes bounding box in display pixels for clamping infinite lines
        try:
            axb  = host.ax.get_window_extent()
            x_lo, x_hi = axb.x0, axb.x1
            y_lo, y_hi = axb.y0, axb.y1
        except Exception:
            return None

        best_gid, best_dist = None, float('inf')

        for gate in host.gates:
            if not gate.get('applied'):
                continue
            gid = gate['id']
            gt  = gate.get('type', 'crosshair')

            if gt == 'crosshair':
                # axvlines and axhline span the full axes.  Keep the historical
                # scalar transform path because only one transformed component
                # is consumed for each infinite line.
                for xb in host._active_xbs_for(gate):
                    p = _data_to_px(xb, 0)
                    if p is None: continue
                    vx = p[0]
                    d  = bounded_vertical_line_distance(
                        ex, ey, vx,
                        y_min=y_lo,
                        y_max=y_hi,
                    )
                    if d < threshold_px and d < best_dist:
                        best_dist, best_gid = d, gid
                for yb_val in host._active_ybs_for(gate):
                    p = _data_to_px(0, yb_val)
                    if p is not None:
                        hy = p[1]
                        d  = bounded_horizontal_line_distance(
                            ex, ey, hy,
                            x_min=x_lo,
                            x_max=x_hi,
                        )
                        if d < threshold_px and d < best_dist:
                            best_dist, best_gid = d, gid

            elif gt == 'rectangle':
                segments = rectangle_line_segments(gate)
                # rectangle_line_segments is perimeter-ordered; four unique
                # corners are enough for a closed vectorized polyline.
                points = [segments[0][0]] + [segment[1] for segment in segments[:3]]
                px_points, used_batch = _batch_points_to_px(points)
                if used_batch:
                    # Four rectangle segments are too few for the NumPy distance
                    # kernel to amortize its setup cost.  Batch only the expensive
                    # Matplotlib transform, then keep the four scalar distances.
                    d = min(
                        point_to_segment_distance(
                            ex, ey,
                            px_points[i][0], px_points[i][1],
                            px_points[(i + 1) % 4][0], px_points[(i + 1) % 4][1],
                        )
                        for i in range(4)
                    )
                else:
                    d = _legacy_segment_min_distance(px_points, closed=True)
                if d < threshold_px and d < best_dist:
                    best_dist, best_gid = d, gid

            elif gt == 'ellipse':
                points = ellipse_perimeter_points(gate, n_points=64)
                px_points, used_batch = _batch_points_to_px(points)
                if used_batch:
                    d = point_to_polyline_min_distance(ex, ey, px_points, closed=True)
                else:
                    # Historical ellipse fallback drops failed points before
                    # reconnecting the surviving perimeter samples.
                    surviving = [p for p in px_points if p is not None]
                    d = _legacy_segment_min_distance(surviving, closed=True)
                if d < threshold_px and d < best_dist:
                    best_dist, best_gid = d, gid

            elif gt == 'polygon':
                closed = closed_polygon_points(gate)
                if not closed:
                    continue
                px_points, used_batch = _batch_points_to_px(closed)
                if used_batch:
                    d = point_to_polyline_min_distance(ex, ey, px_points, closed=False)
                else:
                    d = _legacy_segment_min_distance(px_points, closed=False)
                if d < threshold_px and d < best_dist:
                    best_dist, best_gid = d, gid

        return best_gid

    def hover_test_handles(self, event) -> int:
        """Return gate_id if cursor is within HANDLE_PX*2.5 of any handle.

        Uses _handle_px_cache which is rebuilt:
          (a) inside _preview_gate() after every geometry change, and
          (b) in the draw_event callback after every full canvas render.

        Path (b) is the authoritative one: draw_event fires after matplotlib
        has committed all transforms (including non-linear scales such as
        asinh/biexp/logicle), so the cached pixel coords exactly match the
        display positions of the handle markers.

        v4.1.0 tried to replace this with a live transData.transform call.
        That regressed hover detection for loaded gates on non-linear axes:
        after ax.clear() → set_xscale() the composite transData transform is
        in a partially-applied state until the canvas actually renders.
        Live-transform calls made before or between renders returned pixel
        coords that disagreed with what the user saw, so no handle was ever
        detected within the threshold.  Reverting to the cache fixes this.

        Note: _hit_test_handles (click path) uses a live transform and is
        always called after the canvas has rendered (user sees the screen and
        clicks), so it remains correct and is unaffected by this revert.
        """
        host = self._host
        threshold = HANDLE_PX * 2.5
        candidates = (
            (
                gid,
                nearest_cached_handle(
                    entries,
                    gate_id_value=gid,
                    x=event.x,
                    y=event.y,
                    threshold=threshold,
                ),
            )
            for gid, entries in host._handle_px_cache.items()
        )
        return select_nearest_cached_handle_gate(candidates)

    def cursor_for_hover(self, event) -> str:
        """Return Tk cursor name appropriate for the current hover state.
        Uses _handle_px_cache (post-render, reliable) for cursor shape.
        """
        host = self._host
        return resolve_hover_cursor_workflow(
            should_resolve=lambda: should_resolve_hover_cursor(
                get_handle_drag=lambda: host._handle_drag,
                get_hover_gate_id=lambda: host._hover_gate_id,
                get_pinned_gate_id=lambda: host._pinned_gate_id,
            ),
            prepare_resolution=lambda: HANDLE_PX * 2.5,
            resolve_gate_id=lambda: resolve_hover_cursor_gate_id(
                get_handle_drag=lambda: host._handle_drag,
                get_hover_gate_id=lambda: host._hover_gate_id,
                get_pinned_gate_id=lambda: host._pinned_gate_id,
            ),
            resolve_cursor_for_gate=lambda gid, threshold: resolve_hover_cursor_result_projection(
                get_nearest_result=lambda: resolve_hover_cursor_nearest_result(
                    gate_id=gid,
                    get_cached_entries=lambda selected_gid: host._handle_px_cache.get(selected_gid, []),
                    get_event_x=lambda: event.x,
                    get_event_y=lambda: event.y,
                    threshold=threshold,
                    find_nearest=lambda entries, *, x, y, threshold: nearest_cached_handle(
                        entries,
                        gate_id_value=None,
                        x=x,
                        y=y,
                        threshold=threshold,
                    ),
                ),
                project_cursor=lambda nearest: resolve_cached_handle_hover_cursor(nearest),
            ),
        )

    def drag_handle_update(self, x: float, y: float):
        """Update gate geometry as a handle is dragged to (x, y).

        FIX v4.0.14 (Bug 8): Invalidate the gate's persistent mask-cache entry
        at the start of every drag update.  Without this, a sub-pixel drag that
        does not change the float vertex coordinates leaves the stale cached mask
        in host._gmc, so the gate appears not to update after a very small move.
        """
        host = self._host
        info = host._handle_drag
        if not info:
            return
        gate   = info['gate']
        handle = info['handle']
        idx    = info['idx']
        orig   = info['orig']

        # ── FIX BUG 8: Proactively evict THIS gate from the mask cache ────────
        # We do this unconditionally (before changing the geometry) so that even
        # a zero-length drag — where the float coordinates happen to be identical
        # to the previous position — forces a cache miss and fresh computation.
        gid = gate['id']
        stale_keys = gate_mask_cache_keys_for_gate_ids(host._gmc, [gid])
        evict_cache_keys(host._gmc, stale_keys)
        # ── BUG FIX (B17): targeted scatter-cache eviction ────────────────
        # Previous code did a full host._scatter_cache.clear() on every
        # motion frame, wiping all loaded files' caches at ~60 Hz during
        # a drag.  Only entries whose tuple of gate signatures still
        # references this gate are stale; entries for other gate
        # configurations (e.g. a temporarily-hidden gate) remain valid.
        # Identify staleness by checking whether any element of the
        # gate_sigs tuple in the cache key references the current gate's
        # PRE-drag signature, then drop matching entries.
        cur_sig = _gate_sig(gate)
        stale_sc = scatter_cache_keys_for_gate_signature(host._scatter_cache, cur_sig)
        evict_cache_keys(host._scatter_cache, stale_sc)

        _geometry_before = {}
        _geometry_order = []
        try:
            for key, value in iter_handle_drag_assignments(
                gate,
                handle=handle,
                idx=idx,
                orig=orig,
                x=x,
                y=y,
            ):
                _snapshot_gate_assignment(gate, key, _geometry_before, _geometry_order)
                gate[key] = value
        except Exception:
            # Cache eviction above is intentionally not rolled back: an empty
            # cache is conservative and forces recomputation of restored geometry.
            _rollback_gate_assignments(gate, _geometry_before, _geometry_order)
            raise

    def clear_handles(self):
        host = self._host
        for art in host._handle_artists:
            try: art.remove()
            except Exception: pass
        host._handle_artists = []

    def clear_preview(self):
        host = self._host
        for art in host._preview_artists:
            try: art.remove()
            except Exception: pass
        host._preview_artists = []
        self.clear_handles()

    def start_blit_drag(self):
        """Capture the scatter-only pixel background once at drag press.

        Clears all gate preview artists from the axes so the background
        contains only scatter + axes decorations (no gate outlines), performs
        one synchronous canvas.draw() to commit that state, then snapshots
        the pixel buffer with copy_from_bbox.

        This full render happens exactly once per drag (at press time).
        The momentary press latency is imperceptible compared with per-frame
        lag during the motion.  All subsequent frames use restore_region +
        draw_artist + blit, which only touches gate-outline pixels.

        Sets host._drag_bg to None on failure so the motion handler falls
        back to the standard draw_idle() path without crashing.
        """
        host = self._host
        self.clear_preview()           # strip gate outlines from axes
        try:
            host.canvas.draw()          # one full synchronous render
            host._drag_bg = host.canvas.copy_from_bbox(host.fig.bbox)
        except Exception:
            host._drag_bg = None        # blit unavailable; draw_idle fallback

    def end_blit_drag(self):
        """Release the blit background snapshot after drag ends.

        Called in _on_release before _finish_gate() triggers refresh_plot(),
        which performs a normal full render reconciling the final gate position.
        """
        host = self._host
        host._drag_bg = None

    def blit_render(self):
        """Composite current preview artists onto the blit background and flush.

        Restores the pixel snapshot captured by _start_blit_drag(), composites
        all current preview and handle artists on top with draw_artist(), then
        flushes only those changed pixels with canvas.blit().

        Falls back to canvas.draw_idle() if _drag_bg is None (background was
        not captured — canvas not yet fully initialised at press time, or blit
        was never started for this interaction).
        """
        host = self._host
        if host._drag_bg is not None:
            host.canvas.restore_region(host._drag_bg)
            for art in host._preview_artists + host._handle_artists:
                try:
                    host.ax.draw_artist(art)
                except Exception:
                    pass
            host.canvas.blit(host.fig.bbox)
        else:
            host.canvas.draw_idle()

    def preview_gate(self, skip_cache: bool = False):
        """
        Redraw ALL gate outlines (applied + in-progress) and handle dots.
        Called both during drag preview and after ax.clear() in refresh_plot.

        skip_cache : if True, skip _rebuild_handle_px_cache().  Set during
                     gate-body drag — the hover hit-test block is unreachable
                     while _gate_move is active, so rebuilding pixel coords
                     each frame is pure overhead.  The cache is rebuilt on
                     the next full refresh_plot() call (on mouse-release).
        """
        host = self._host
        self.clear_preview()

        for gate in host.gates:
            if not should_draw_gate_preview(gate):
                continue
            if gate.get('applied') and not host._gate_context_matches(gate):
                continue
            style = gate_preview_style(
                gate,
                selected_gate_id=host._sel_gate_id,
                default_color=GATE_PALETTE[0],
            )
            c    = style['color']
            ls   = style['linestyle']
            lw   = style['linewidth']
            gt   = gate.get('type', 'crosshair')

            if gt == 'crosshair':
                xbs, ybs = crosshair_preview_boundaries(gate)
                for xb in xbs:
                    a = host.ax.axvline(xb, color=c, ls=ls, lw=lw, zorder=10)
                    host._preview_artists.append(a)
                for yb_val in ybs:
                    a = host.ax.axhline(yb_val, color=c, ls=ls, lw=lw, zorder=10)
                    host._preview_artists.append(a)

            elif gt in ('rectangle', 'ellipse'):
                if gt == 'rectangle':
                    rx, ry, rw, rh = rectangle_preview_geometry(gate)
                    patch = MplRect((rx, ry), rw, rh,
                                    lw=lw, ls=ls, edgecolor=c, facecolor='none', zorder=10)
                else:
                    # Matplotlib's Ellipse patch applies nonlinear axis
                    # transforms to its Bezier control points, so on log/asinh/
                    # biexp/logicle axes the visible outline can diverge from
                    # vFlow's established raw-data ellipse membership equation.
                    # Preserve the exact legacy patch on linear/linear axes, but
                    # sample the same raw ellipse densely whenever either axis is
                    # nonlinear so the displayed boundary follows the population
                    # that gate statistics actually select.
                    if host.x_scale == 'linear' and host.y_scale == 'linear':
                        cx, cy, w, h = ellipse_preview_geometry(gate)
                        patch = MplEllipse((cx, cy), w, h,
                                           lw=lw, ls=ls, edgecolor=c,
                                           facecolor='none', zorder=10)
                    else:
                        points = ellipse_perimeter_points(gate, n_points=256)
                        if not points:
                            continue
                        xs = [point[0] for point in points] + [points[0][0]]
                        ys = [point[1] for point in points] + [points[0][1]]
                        line, = host.ax.plot(
                            xs, ys, color=c, ls=ls, lw=lw, zorder=10)
                        host._preview_artists.append(line)
                        continue
                host.ax.add_patch(patch)
                host._preview_artists.append(patch)

            elif gt == 'polygon':
                xs, ys = polygon_preview_points(gate)
                if xs:
                    ln, = host.ax.plot(xs, ys, color=c, ls=ls, lw=lw,
                                       marker='o' if not gate.get('applied') else 'none',
                                       markersize=3, zorder=10)
                    host._preview_artists.append(ln)
                    # Rubber-band line to cursor while drawing
                    rb_points = polygon_rubber_band_points(
                        gate,
                        xs,
                        ys,
                        polygon_active=host._poly_active,
                        polygon_cursor=host._poly_cursor,
                        draw_gate_id=host._draw_gate_id,
                    )
                    if rb_points is not None:
                        rb_xs, rb_ys = rb_points
                        rb, = host.ax.plot(
                            rb_xs,
                            rb_ys,
                            color=c, ls=':', lw=1.0, zorder=10)
                        host._preview_artists.append(rb)

        # Draw handles
        self.draw_handles()
        # Rebuild pixel-coord cache so hover hit-testing avoids per-event transforms.
        # Skipped during gate-body drag (skip_cache=True): the hover block is
        # unreachable while _gate_move is active; the cache is rebuilt correctly
        # on mouse-release via the normal refresh_plot() → _preview_gate() path.
        if not skip_cache:
            self.rebuild_handle_px_cache()
