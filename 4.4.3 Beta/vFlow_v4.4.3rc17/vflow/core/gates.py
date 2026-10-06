"""Dict-compatible gate helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .threshold_state import (
    multi_y_threshold_flags,
    single_y_threshold_flag,
    x_threshold_flags,
)


def gate_type(gate: dict) -> str:
    return gate.get("type", "crosshair") if gate else "crosshair"


def gate_id(gate: dict):
    return gate.get("id") if gate else None


def gate_by_id(gates: list[dict], gate_id_value):
    """Return the first gate with the requested id, or None."""
    return next((gate for gate in gates if gate.get("id") == gate_id_value), None)


def manual_crosshair_gate(gates: list[dict]):
    """Return the reusable manual crosshair gate, if one exists."""
    return next(
        (
            gate
            for gate in gates
            if gate.get("type") == "crosshair" and gate.get("auto_method") is None
        ),
        None,
    )


def subgate_candidate_order(gates: list[dict], selected_gate: dict | None) -> list[dict]:
    """Return candidate gates for sub-gate hit-testing, selected gate first."""
    return ([selected_gate] if selected_gate else []) + [
        gate for gate in gates if gate.get("applied") and gate is not selected_gate
    ]


def _mask_any(mask) -> bool:
    try:
        return bool(mask.any())
    except AttributeError:
        return any(mask)


def clicked_subgate_region(gate: dict, regions: dict):
    """Return the first clicked region name allowed for sub-gating."""
    for region_name, mask in regions.items():
        if not _mask_any(mask):
            continue
        if gate_type(gate) != "crosshair" and region_name == "OUT":
            continue
        return region_name
    return None


def remove_gate_and_select_neighbor(
    gates: list[dict],
    *,
    gate_id_value,
    selected_gate_id,
) -> tuple[list[dict], int | None]:
    """Remove a gate and return the remaining gates plus updated selected id."""
    idx_before = next(
        (idx for idx, gate in enumerate(gates) if gate.get("id") == gate_id_value),
        None,
    )
    remaining = [gate for gate in gates if gate.get("id") != gate_id_value]
    if selected_gate_id != gate_id_value:
        return remaining, selected_gate_id
    if not remaining:
        return remaining, None
    sel_idx = min(idx_before, len(remaining) - 1) if idx_before is not None else -1
    return remaining, remaining[sel_idx].get("id")


def is_crosshair(gate: dict) -> bool:
    return gate_type(gate) == "crosshair"


def is_shape_gate(gate: dict) -> bool:
    return gate_type(gate) in ("rectangle", "ellipse", "polygon")


def gate_snapshot(gate: dict, *, excluded_types: tuple = ()) -> dict:
    """Return a shallow gate copy, omitting values whose types cannot be copied safely."""
    return {
        key: value
        for key, value in gate.items()
        if not isinstance(value, excluded_types)
    }


def new_gate_dict(
    *,
    gate_id_value: int,
    gate_type_value: str,
    color: str,
    auto_method: str | None = None,
) -> dict:
    """Return the legacy default gate dictionary for a new gate."""
    return {
        "id": gate_id_value,
        "name": f"Gate {gate_id_value + 1}",
        "type": gate_type_value,
        "applied": False,
        "auto_method": auto_method,
        "color": color,
        "linestyle": "-",
        "linewidth": 0.5,
        "x_boundaries": [],
        "y_boundary": None,
        "x_thresh_vars": [],
        "y_thresh_var": None,
        "y_boundaries": None,
        "y_thresh_vars": [],
        "x0": 0.0,
        "y0": 0.0,
        "x1": 0.0,
        "y1": 0.0,
        "vertices": [],
    }


def active_x_boundaries(gate: dict) -> list:
    """Return enabled X boundaries for a crosshair gate dict."""
    if not gate or not is_crosshair(gate):
        return []
    xbs = gate.get("x_boundaries", [])
    flags = x_threshold_flags(gate)
    if len(flags) != len(xbs):
        return list(xbs)
    return [xb for xb, active in zip(xbs, flags) if active]


def active_y_boundary(gate: dict):
    """Return the first active Y boundary for compatibility callers."""
    ybs = active_y_boundaries(gate)
    return ybs[0] if ybs else None


def active_y_boundaries(gate: dict) -> list:
    """Return all enabled Y boundaries for a crosshair gate dict."""
    if not gate or not is_crosshair(gate):
        return []

    ybs_list = gate.get("y_boundaries")
    if ybs_list:
        flags = multi_y_threshold_flags(gate)
        if len(flags) != len(ybs_list):
            return list(ybs_list)
        return [yb for yb, active in zip(ybs_list, flags) if active]

    yb = gate.get("y_boundary")
    if yb is None:
        return []
    return [yb] if single_y_threshold_flag(gate) else []


def gate_handles(gate: dict) -> list[dict]:
    """Return edit handles for a shape/polygon gate dict."""
    handles = []
    gt = gate_type(gate)
    if gt in ("rectangle", "ellipse"):
        x0, y0 = gate["x0"], gate["y0"]
        x1, y1 = gate["x1"], gate["y1"]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for idx, (x, y, name) in enumerate(
            [
                (x0, y0, "nw"),
                (x1, y0, "ne"),
                (x1, y1, "se"),
                (x0, y1, "sw"),
                (cx, cy, "center"),
            ]
        ):
            handles.append({"x": x, "y": y, "handle": name, "idx": idx})
    elif gt == "polygon":
        for idx, (x, y) in enumerate(gate.get("vertices", [])):
            handles.append({"x": x, "y": y, "handle": "vertex", "idx": idx})
    return handles


def handle_cache_entry(handle: dict, transform_point):
    """Return a cached pixel handle entry, or None when transform fails."""
    try:
        px, py = transform_point((handle["x"], handle["y"]))
    except Exception:
        return None
    return (px, py, handle["handle"], handle["idx"])


def handle_cache_entries(handles, transform_points):
    """Return pixel-cache entries for one gate, batching the transform when possible.

    Matplotlib transforms accept an ``N x 2`` array, so a gate's handles can be
    projected in one call instead of one call per handle.  Any failure or
    malformed batch result falls back to the historical scalar helper for each
    handle, preserving its per-handle fail-closed behavior.
    """
    handles = list(handles)
    if not handles:
        return []

    try:
        points = np.asarray(
            [(handle["x"], handle["y"]) for handle in handles],
            dtype=float,
        )
        transformed = np.asarray(transform_points(points))
        if transformed.shape == points.shape:
            return [
                (px, py, handle["handle"], handle["idx"])
                for handle, (px, py) in zip(handles, transformed)
            ]
    except Exception:
        pass

    return [
        entry
        for handle in handles
        if (entry := handle_cache_entry(handle, transform_points)) is not None
    ]


def gate_control_points(gate: dict) -> list[tuple[float, float]]:
    """Return data-space control points that define a movable shape gate."""
    gt = gate_type(gate)
    if gt in ("rectangle", "ellipse"):
        return [
            (gate["x0"], gate["y0"]),
            (gate["x1"], gate["y1"]),
        ]
    if gt == "polygon":
        return list(gate.get("vertices", []))
    return []


def iter_handle_drag_assignments(
    gate: dict,
    *,
    handle: str,
    idx: int,
    orig: dict,
    x: float,
    y: float,
):
    """Yield ordered key/value assignments for one handle drag.

    This is the pure geometry-calculation boundary used by the interactive
    controller.  It deliberately yields assignments lazily instead of
    materialising a final gate dictionary: the caller can apply each yielded
    assignment immediately, preserving v4.1.11's center-drag evaluation and
    partial-mutation order even if a pathological ``orig`` mapping raises
    while a later coordinate is being calculated.

    The function never mutates ``gate`` or ``orig``.
    """
    gt = gate_type(gate)
    if gt in ("rectangle", "ellipse"):
        if handle == "nw":
            yield "x0", x
            yield "y0", y
        elif handle == "ne":
            yield "x1", x
            yield "y0", y
        elif handle == "se":
            yield "x1", x
            yield "y1", y
        elif handle == "sw":
            yield "x0", x
            yield "y1", y
        elif handle == "center":
            dx = x - (orig["x0"] + orig["x1"]) / 2
            dy = y - (orig["y0"] + orig["y1"]) / 2
            yield "x0", orig["x0"] + dx
            yield "x1", orig["x1"] + dx
            yield "y0", orig["y0"] + dy
            yield "y1", orig["y1"] + dy
    elif gt == "polygon" and handle == "vertex":
        verts = list(gate.get("vertices", []))
        if 0 <= idx < len(verts):
            verts[idx] = (x, y)
            yield "vertices", verts


def update_gate_from_handle_drag(
    gate: dict,
    *,
    handle: str,
    idx: int,
    orig: dict,
    x: float,
    y: float,
) -> None:
    """Mutate a shape gate for a handle drag in data coordinates.

    Compatibility wrapper around :func:`iter_handle_drag_assignments`.
    Interactive ``FlowApp`` applies the same ordered assignments itself so
    live gate mutation remains at the controller boundary.
    """
    for key, value in iter_handle_drag_assignments(
        gate, handle=handle, idx=idx, orig=orig, x=x, y=y
    ):
        gate[key] = value


def update_gate_from_control_points(gate: dict, points) -> None:
    """Mutate a shape gate from transformed-back data-space control points."""
    gt = gate_type(gate)
    if gt in ("rectangle", "ellipse"):
        gate["x0"], gate["y0"] = float(points[0][0]), float(points[0][1])
        gate["x1"], gate["y1"] = float(points[1][0]), float(points[1][1])
    elif gt == "polygon":
        gate["vertices"] = [
            (float(points[i][0]), float(points[i][1]))
            for i in range(len(points))
        ]


def iter_gate_draw_initialization_assignments(gate_type_value: str, x: float, y: float):
    """Yield ordered geometry assignments for starting a non-polygon draw.

    The helper intentionally excludes polygon initialization because polygon
    drawing has a separate append/double-click/finalization lifecycle.  It is
    lazy so the interactive controller can preserve the legacy assignment
    order and any partial state if an exceptional mapping fails mid-update.
    """
    if gate_type_value == "crosshair":
        yield "x_boundaries", [x]
        yield "y_boundary", y
    elif gate_type_value in ("rectangle", "ellipse"):
        yield "x0", x
        yield "y0", y
        yield "x1", x
        yield "y1", y


class PolygonGeometrySchemaError(ValueError):
    """Raised when live polygon geometry has an invalid vertex container.

    Missing ``vertices`` remains valid legacy state and is interpreted by the
    caller's existing default.  An explicitly stored ``None`` is invalid and
    must not fail later through an accidental ``append``/``len`` exception.
    """



def require_polygon_vertices(vertices, *, operation: str):
    """Return ``vertices`` unless the live polygon container is explicitly None.

    The helper intentionally validates only the BR-POLY-003/004 case.  Other
    custom containers retain their historical append/length semantics.
    """
    if vertices is None:
        raise PolygonGeometrySchemaError(
            "Polygon geometry is malformed: 'vertices' is None during "
            f"{operation}. Expected a vertex container; recreate the polygon gate."
        )
    return vertices


@dataclass(frozen=True)
class PolygonVertexPlan:
    """Pure description of one polygon vertex lifecycle mutation."""

    operation: str
    vertex: tuple[float, float]


def plan_polygon_vertex(operation: str, x: float, y: float) -> PolygonVertexPlan:
    """Plan one polygon initial-vertex or append mutation without side effects.

    Polygon click/double-click/finalization semantics intentionally remain in
    the interactive controller.  The planner only materializes the requested
    lifecycle operation and data-space vertex payload so the controller can
    retain authoritative mutation ownership.
    """
    if operation not in ("initialize", "append"):
        raise ValueError(f"unsupported polygon vertex operation: {operation}")
    return PolygonVertexPlan(operation=operation, vertex=(x, y))


def begin_gate_draw(gate: dict, gate_type_value: str, x: float, y: float) -> None:
    """Initialise draw geometry for a gate at a data-space point."""
    gate["type"] = gate_type_value
    if gate_type_value == "polygon":
        gate["vertices"] = [plan_polygon_vertex("initialize", x, y).vertex]
        return
    for key, value in iter_gate_draw_initialization_assignments(
        gate_type_value, x, y
    ):
        gate[key] = value


def append_polygon_vertex(gate: dict, x: float, y: float) -> None:
    """Append one data-space vertex to a polygon gate."""
    require_polygon_vertices(
        gate.setdefault("vertices", []), operation="vertex append"
    ).append(plan_polygon_vertex("append", x, y).vertex)


@dataclass(frozen=True)
class PolygonFinishPlan:
    """Pure decision/state payload for closing one in-progress polygon gate."""

    can_finish: bool
    applied_value: bool = True
    poly_active_value: bool = False
    poly_cursor_value: object = None
    draw_gate_id_value: object = None


def plan_polygon_finish(gate: dict, *, min_vertices: int = 3) -> PolygonFinishPlan:
    """Plan polygon close eligibility and successful-close transient state.

    The eligibility expression intentionally matches the frozen v4.1.11
    ``polygon_gate_can_finish`` rule exactly, including its short-circuiting and
    exception behavior for unusual mapping/``vertices`` values.  The returned
    plan is read-only; the interactive controller remains responsible for every
    live gate/UI mutation and callback.
    """
    if gate_type(gate) != "polygon":
        return PolygonFinishPlan(can_finish=False)
    vertices = require_polygon_vertices(
        gate.get("vertices", []), operation="finish eligibility"
    )
    return PolygonFinishPlan(can_finish=len(vertices) >= min_vertices)


def polygon_gate_can_finish(gate: dict, *, min_vertices: int = 3) -> bool:
    """Return True when a polygon gate has enough vertices to be applied."""
    return plan_polygon_finish(gate, min_vertices=min_vertices).can_finish


@dataclass(frozen=True)
class PolygonCloseEntryPlan:
    """Pure decision payload for polygon close-entry intent."""

    should_finish: bool


def plan_polygon_close_entry(
    trigger: str,
    *,
    polygon_active: bool,
    mode: str,
) -> PolygonCloseEntryPlan:
    """Plan whether a click-entry path should invoke polygon finalization.

    This intentionally covers only entry intent.  Minimum-vertex eligibility,
    live gate mutation, blit teardown, and finalization callbacks remain in
    their existing controller/finalization layers.
    """
    if trigger == "double_click":
        return PolygonCloseEntryPlan(
            should_finish=bool(polygon_active and mode == "draw")
        )
    if trigger == "right_click":
        return PolygonCloseEntryPlan(should_finish=bool(polygon_active))
    raise ValueError(f"unsupported polygon close trigger: {trigger}")


def iter_gate_draw_assignments(gate: dict, x: float, y: float):
    """Yield ordered live-gate assignments for in-progress draw geometry.

    The helper is intentionally lazy so callers can preserve the legacy
    mutation order (X before Y) and any partial state if a later assignment
    fails. Polygon drawing has a separate append/finalization lifecycle and
    therefore yields no assignments here.
    """
    gt = gate_type(gate)
    if gt == "crosshair":
        yield "x_boundaries", [x]
        yield "y_boundary", y
    elif gt in ("rectangle", "ellipse"):
        yield "x1", x
        yield "y1", y


def update_gate_draw(gate: dict, x: float, y: float) -> None:
    """Update in-progress draw geometry at a data-space point."""
    for key, value in iter_gate_draw_assignments(gate, x, y):
        gate[key] = value


def is_degenerate_shape_gate(gate: dict, *, min_span: float = 1e-10) -> bool:
    """Return True when a rectangle/ellipse has no meaningful width or height."""
    if gate_type(gate) not in ("rectangle", "ellipse"):
        return False
    return (
        abs(gate["x1"] - gate["x0"]) < min_span
        or abs(gate["y1"] - gate["y0"]) < min_span
    )


def should_draw_gate_preview(gate: dict) -> bool:
    """Return whether a gate should be considered for preview drawing."""
    if not gate:
        return False
    gt = gate_type(gate)
    if not gate.get("vertices", []) and not gate.get("applied", False) and gt not in (
        "crosshair",
        "rectangle",
        "ellipse",
    ):
        return False
    if gt in ("rectangle", "ellipse"):
        x0, x1 = gate.get("x0", 0), gate.get("x1", 0)
        y0, y1 = gate.get("y0", 0), gate.get("y1", 0)
        if x0 == x1 and y0 == y1 and not gate.get("applied", False):
            return False
    return True


def gate_preview_style(
    gate: dict,
    *,
    selected_gate_id=None,
    default_color: str,
) -> dict:
    """Return color, line style, and line width for preview drawing."""
    color = gate.get("color", default_color)
    line_style = gate.get("linestyle", "-") if gate.get("applied") else "--"
    base_line_width = gate.get("linewidth", 0.5)
    line_width = base_line_width + 0.8 if gate.get("id") == selected_gate_id else base_line_width
    return {"color": color, "linestyle": line_style, "linewidth": line_width}


def crosshair_preview_boundaries(gate: dict) -> tuple[list, list]:
    """Return X and Y boundaries to draw for a crosshair preview."""
    if gate.get("applied"):
        return active_x_boundaries(gate), active_y_boundaries(gate)
    x_boundaries = gate.get("x_boundaries", [])
    y_boundary = gate.get("y_boundary")
    y_boundaries = gate.get("y_boundaries") or (
        [y_boundary] if y_boundary is not None else []
    )
    return x_boundaries, y_boundaries


def rectangle_preview_geometry(gate: dict) -> tuple[float, float, float, float]:
    """Return lower-left x/y plus width/height for a rectangle preview."""
    x0, y0 = gate.get("x0", 0), gate.get("y0", 0)
    x1, y1 = gate.get("x1", 0), gate.get("y1", 0)
    return min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)


def ellipse_preview_geometry(gate: dict) -> tuple[float, float, float, float]:
    """Return center x/y plus width/height for an ellipse preview."""
    x0, y0 = gate.get("x0", 0), gate.get("y0", 0)
    x1, y1 = gate.get("x1", 0), gate.get("y1", 0)
    return (x0 + x1) / 2, (y0 + y1) / 2, abs(x1 - x0), abs(y1 - y0)


def rectangle_bounds(gate: dict) -> tuple[float, float, float, float]:
    """Return rectangle x/y bounds as xlo, xhi, ylo, yhi."""
    x0, y0 = gate.get("x0", 0), gate.get("y0", 0)
    x1, y1 = gate.get("x1", 0), gate.get("y1", 0)
    return min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)


def point_in_rectangle(x: float, y: float, bounds: tuple[float, float, float, float]) -> bool:
    """Return whether a point is inside inclusive rectangle bounds."""
    xlo, xhi, ylo, yhi = bounds
    return xlo <= x <= xhi and ylo <= y <= yhi


def rectangle_area(bounds: tuple[float, float, float, float]) -> float:
    """Return rectangle area from xlo, xhi, ylo, yhi bounds."""
    xlo, xhi, ylo, yhi = bounds
    return (xhi - xlo) * (yhi - ylo)


def ellipse_center_radii(gate: dict) -> tuple[float, float, float, float]:
    """Return ellipse center x/y plus x/y radii."""
    cx, cy, width, height = ellipse_preview_geometry(gate)
    return cx, cy, width / 2, height / 2


def point_in_ellipse(x: float, y: float, center_radii: tuple[float, float, float, float]) -> bool:
    """Return whether a point is inside an ellipse."""
    cx, cy, rx, ry = center_radii
    if rx <= 0 or ry <= 0:
        return False
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0


def ellipse_area(rx: float, ry: float) -> float:
    """Return ellipse area from x/y radii."""
    return math.pi * rx * ry


def polygon_area(points: list[tuple[float, float]]) -> float:
    """Return absolute polygon area using the shoelace formula."""
    if len(points) < 3:
        return 0.0
    return abs(
        sum(
            points[i][0] * points[i - 1][1] - points[i - 1][0] * points[i][1]
            for i in range(len(points))
        )
    ) / 2


def is_finite_point(x, y) -> bool:
    """Return whether a point has finite numeric coordinates."""
    try:
        return math.isfinite(float(x)) and math.isfinite(float(y))
    except (TypeError, ValueError):
        return False


def finite_point_pairs(xs, ys) -> list[tuple[float, float]]:
    """Return finite float point pairs from parallel x/y iterables."""
    pairs = []
    for x, y in zip(xs, ys):
        if is_finite_point(x, y):
            pairs.append((float(x), float(y)))
    return pairs


def smaller_area_hit(best_gate, best_area: float, gate: dict, *, inside: bool, area: float):
    """Return updated best gate/area when a containing candidate is smaller."""
    if inside and area < best_area:
        return gate, area
    return best_gate, best_area


def rectangle_line_segments(gate: dict) -> list[tuple[tuple, tuple]]:
    """Return data-space rectangle edge segments."""
    x0, y0 = gate.get("x0", 0), gate.get("y0", 0)
    x1, y1 = gate.get("x1", 0), gate.get("y1", 0)
    return [
        ((x0, y0), (x1, y0)),
        ((x1, y0), (x1, y1)),
        ((x1, y1), (x0, y1)),
        ((x0, y1), (x0, y0)),
    ]


def ellipse_perimeter_points(gate: dict, *, n_points: int = 64) -> list[tuple[float, float]]:
    """Return data-space sample points around an ellipse perimeter."""
    if n_points <= 0:
        return []
    cx, cy, width, height = ellipse_preview_geometry(gate)
    rx, ry = width / 2, height / 2
    return [
        (
            cx + rx * math.cos(2 * math.pi * i / n_points),
            cy + ry * math.sin(2 * math.pi * i / n_points),
        )
        for i in range(n_points)
    ]


def polygon_preview_points(gate: dict) -> tuple[list, list]:
    """Return x/y point lists for polygon preview drawing."""
    verts = gate.get("vertices", [])
    if not verts:
        return [], []
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    if gate.get("applied"):
        xs = xs + [xs[0]]
        ys = ys + [ys[0]]
    return xs, ys


def closed_polygon_points(gate: dict) -> list:
    """Return data-space polygon vertices closed back to the first point."""
    verts = list(gate.get("vertices", []))
    if len(verts) < 2:
        return []
    return verts + [verts[0]]


def polygon_rubber_band_points(
    gate: dict,
    xs: list,
    ys: list,
    *,
    polygon_active: bool,
    polygon_cursor,
    draw_gate_id,
):
    """Return x/y points for a polygon rubber-band segment, or None."""
    if (
        polygon_active
        and polygon_cursor is not None
        and gate.get("id") == draw_gate_id
        and xs
        and ys
    ):
        return [xs[-1], polygon_cursor[0]], [ys[-1], polygon_cursor[1]]
    return None


def gate_geometry_summary_lines(
    gate: dict,
    *,
    polygon_active: bool = False,
) -> tuple[list[str], list[str]]:
    """Return monospace and dim summary lines for shape gate info panels."""
    gt = gate_type(gate)
    mono_lines: list[str] = []
    dim_lines: list[str] = []

    if gt == "rectangle":
        x0, y0 = gate.get("x0", 0), gate.get("y0", 0)
        x1, y1 = gate.get("x1", 0), gate.get("y1", 0)
        mono_lines.extend(
            [
                f"  X: {min(x0, x1):,.1f} → {max(x0, x1):,.1f}",
                f"  Y: {min(y0, y1):,.1f} → {max(y0, y1):,.1f}",
            ]
        )
    elif gt == "ellipse":
        x0, y0 = gate.get("x0", 0), gate.get("y0", 0)
        x1, y1 = gate.get("x1", 0), gate.get("y1", 0)
        mono_lines.extend(
            [
                f"  Centre: ({(x0 + x1) / 2:,.1f}, {(y0 + y1) / 2:,.1f})",
                f"  a={abs(x1 - x0) / 2:,.1f}  b={abs(y1 - y0) / 2:,.1f}",
            ]
        )
    elif gt == "polygon":
        n_vertices = len(gate.get("vertices", []))
        status = "drawing…" if polygon_active else "closed"
        mono_lines.append(f"  {n_vertices} vertices  ({status})")
        if polygon_active:
            dim_lines.append("  Click ✓ Close Polygon or dbl-click")

    if gate and gate.get("applied") and gt in ("rectangle", "ellipse", "polygon"):
        dim_lines.append("  Drag ◼ handles to reshape")

    return mono_lines, dim_lines


def handle_display_mode(
    gate_id_value,
    *,
    drag_gate_id=None,
    interior_hover_gate_id=None,
    hover_gate_id=None,
    hover_handle_key=None,
) -> str:
    """Classify how a gate's edit handles should be drawn."""
    if gate_id_value == drag_gate_id:
        return "drag"
    if gate_id_value == interior_hover_gate_id:
        return "interior"
    if (
        gate_id_value == hover_gate_id
        and hover_handle_key is not None
        and hover_handle_key[0] == gate_id_value
    ):
        return "handle_hover"
    if gate_id_value == hover_gate_id:
        return "line_hover"
    return "pinned"


def visible_handle_gate_ids(
    *,
    drag_gate_id=None,
    hover_gate_id=None,
    pinned_gate_id=None,
    interior_hover_gate_id=None,
) -> set:
    """Return gate ids whose handles should be drawn."""
    gate_ids = set()
    if drag_gate_id:
        gate_ids.add(drag_gate_id)
    if hover_gate_id:
        gate_ids.add(hover_gate_id)
    if pinned_gate_id:
        gate_ids.add(pinned_gate_id)
    if interior_hover_gate_id:
        gate_ids.add(interior_hover_gate_id)
    return gate_ids


def handle_marker_style(
    display_mode: str,
    *,
    handle_key: tuple,
    color: str,
    drag_handle_key: tuple | None = None,
    hover_handle_key: tuple | None = None,
) -> dict | None:
    """Return marker styling for one handle, or None when it should be hidden."""
    if display_mode == "drag":
        active = handle_key == drag_handle_key
        return {
            "marker": "s" if active else "o",
            "ms": 9 if active else 7,
            "mfc": color if active else "none",
            "mew": 1.5 if active else 0.5,
        }
    if display_mode == "interior":
        return {"marker": "o", "ms": 8, "mfc": color, "mew": 1.5}
    if display_mode == "handle_hover":
        if handle_key != hover_handle_key:
            return None
        return {"marker": "s", "ms": 9, "mfc": color, "mew": 1.5}
    if display_mode == "line_hover":
        return {"marker": "o", "ms": 7, "mfc": "none", "mew": 0.5}
    return {"marker": "o", "ms": 8, "mfc": color + "55", "mew": 2.0}


def nearest_cached_handle(
    entries,
    *,
    gate_id_value,
    x: float,
    y: float,
    threshold: float,
):
    """Return nearest cached handle key and distance within a pixel threshold."""
    best_key = None
    best_dist = float("inf")
    for px, py, handle, idx in entries:
        dist = point_distance(px, py, x, y)
        if dist < threshold and dist < best_dist:
            best_dist = dist
            best_key = (gate_id_value, handle, idx)
    if best_key is None:
        return None
    return best_key, best_dist


def hover_cursor_for_cached_handles(entries, *, x: float, y: float, threshold: float) -> str:
    """Return cursor name for cached handles near a display-space point."""
    nearest = nearest_cached_handle(
        entries,
        gate_id_value=None,
        x=x,
        y=y,
        threshold=threshold,
    )
    if nearest is None:
        return "hand2"
    key, _dist = nearest
    return "fleur" if key[1] == "center" else "sizing"


def line_hover_test_plan(
    *,
    new_hover,
    current_hover_gate_id,
    current_pos: tuple[float, float],
    last_line_test_pos=None,
    min_delta: float = 10,
) -> tuple[bool, tuple[float, float] | None]:
    """Return whether to run line-hover hit-testing and the next cached cursor position."""
    if new_hover is not None:
        return False, last_line_test_pos
    if current_hover_gate_id is not None:
        return True, last_line_test_pos

    ex, ey = current_pos
    lx, ly = last_line_test_pos if last_line_test_pos is not None else (ex - 99, ey)
    if abs(ex - lx) + abs(ey - ly) > min_delta:
        return True, (ex, ey)
    return False, last_line_test_pos


def hover_state_changed(
    *,
    new_hover,
    old_hover,
    new_hover_handle_key,
    old_hover_handle_key,
    new_interior,
    old_interior,
) -> bool:
    """Return whether any hover-related state changed."""
    return (
        new_hover != old_hover
        or new_hover_handle_key != old_hover_handle_key
        or new_interior != old_interior
    )


def crosshair_corner_label_position(region_name: str):
    """Return axes-space corner label placement for simple crosshair quadrants."""
    if "/" not in region_name:
        return None
    y_part, x_part = region_name.split("/", 1)
    y_plus = y_part.endswith("+")
    y_minus = y_part.endswith("-")
    x_plus = x_part.endswith("+")
    x_minus = x_part.endswith("-")
    if not ((y_plus or y_minus) and (x_plus or x_minus)):
        return None
    x_ax = 0.98 if x_plus else 0.02
    y_ax = 0.97 if y_plus else 0.03
    ha = "right" if x_plus else "left"
    va = "top" if y_plus else "bottom"
    return x_ax, y_ax, ha, va


def point_distance(ax, ay, bx, by) -> float:
    """Return Euclidean distance between two display-space points."""
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def point_to_segment_distance(px, py, ax, ay, bx, by) -> float:
    """Return pixel distance from point P to segment AB."""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return point_distance(px, py, ax, ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    nearest_x = ax + t * dx
    nearest_y = ay + t * dy
    return point_distance(px, py, nearest_x, nearest_y)


def point_to_polyline_min_distance(
    px: float,
    py: float,
    points,
    *,
    closed: bool = False,
) -> float:
    """Return the nearest display-space distance to a polyline.

    The segment projection is vectorized so hover hit-testing can process an
    entire rectangle, ellipse perimeter, or polygon with one NumPy operation
    after Matplotlib has batch-transformed the points.  Non-finite segment
    distances are ignored, matching the legacy scalar caller where ``nan``
    distances never won the strict threshold comparison.
    """
    pts = np.asarray(points, dtype=float)
    if pts.ndim != 2 or pts.shape[1:] != (2,) or len(pts) < 2:
        return float("inf")

    if closed:
        starts = pts
        ends = np.roll(pts, -1, axis=0)
    else:
        starts = pts[:-1]
        ends = pts[1:]

    delta = ends - starts
    denom = np.sum(delta * delta, axis=1)
    rel = np.asarray([px, py], dtype=float) - starts
    numer = np.sum(rel * delta, axis=1)
    projection = np.zeros_like(denom, dtype=float)
    nonzero = denom != 0
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        projection[nonzero] = numer[nonzero] / denom[nonzero]
    np.clip(projection, 0.0, 1.0, out=projection)

    nearest = starts + projection[:, None] * delta
    with np.errstate(invalid="ignore", over="ignore"):
        distances = np.sqrt(
            (px - nearest[:, 0]) ** 2 + (py - nearest[:, 1]) ** 2
        )
    finite = np.isfinite(distances)
    if not np.any(finite):
        return float("inf")
    return float(np.min(distances[finite]))


def bounded_vertical_line_distance(
    px: float,
    py: float,
    line_x: float,
    *,
    y_min: float,
    y_max: float,
) -> float:
    """Return display-space distance to a vertical line segment spanning y bounds."""
    return abs(px - line_x) if y_min <= py <= y_max else float("inf")


def bounded_horizontal_line_distance(
    px: float,
    py: float,
    line_y: float,
    *,
    x_min: float,
    x_max: float,
) -> float:
    """Return display-space distance to a horizontal line segment spanning x bounds."""
    return abs(py - line_y) if x_min <= px <= x_max else float("inf")
