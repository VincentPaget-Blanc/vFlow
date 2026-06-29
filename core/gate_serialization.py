"""JSON-safe gate serialization helpers."""

from __future__ import annotations

import math


def _var_bool(value, default=False) -> bool:
    if value is None:
        return bool(default)
    try:
        return bool(value.get())
    except AttributeError:
        return bool(value)


def safe_float(value, default=0.0):
    try:
        out = float(value)
        if not math.isfinite(out):
            return default
        return out
    except (TypeError, ValueError):
        return default


def safe_optional_float(value):
    if value is None:
        return None
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def safe_float_list(seq) -> list:
    if not isinstance(seq, (list, tuple)):
        return []
    out = []
    for value in seq:
        maybe = safe_optional_float(value)
        if maybe is not None:
            out.append(maybe)
    return out


def safe_vertices(seq) -> list:
    if not isinstance(seq, (list, tuple)):
        return []
    out = []
    for value in seq:
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            continue
        x = safe_optional_float(value[0])
        y = safe_optional_float(value[1])
        if x is not None and y is not None:
            out.append((x, y))
    return out


def gate_to_json_dict(gate: dict) -> dict:
    """Convert a live gate dict into the legacy JSON-compatible schema."""
    return {
        "id": gate.get("id"),
        "name": gate.get("name", ""),
        "type": gate.get("type", "crosshair"),
        "auto_method": gate.get("auto_method"),
        "applied": gate.get("applied", False),
        "color": gate.get("color", "#e74c3c"),
        "linestyle": gate.get("linestyle", "-"),
        "linewidth": gate.get("linewidth", 0.5),
        "x_boundaries": gate.get("x_boundaries", []),
        "y_boundary": gate.get("y_boundary"),
        "x_thresh_active": [
            _var_bool(value) for value in gate.get("x_thresh_vars", [])
        ],
        "y_thresh_active": _var_bool(gate.get("y_thresh_var"), True),
        "y_boundaries": gate.get("y_boundaries"),
        "y_thresh_actives": [
            _var_bool(value) for value in gate.get("y_thresh_vars", [])
        ],
        "x0": gate.get("x0", 0.0),
        "y0": gate.get("y0", 0.0),
        "x1": gate.get("x1", 0.0),
        "y1": gate.get("y1", 0.0),
        "vertices": list(gate.get("vertices", [])),
    }


def validate_raw_gate(raw) -> bool:
    if not isinstance(raw, dict):
        return False
    gt = raw.get("type", "crosshair")
    if gt == "polygon":
        verts = safe_vertices(raw.get("vertices", []))
        if len(verts) == 0 and raw.get("applied"):
            return False
    return True


def gate_from_json_dict(raw: dict, next_id: int):
    """Build a sanitized, Tk-free gate dict from legacy JSON data."""
    if not validate_raw_gate(raw):
        return None, next_id

    raw_id = raw.get("id")
    if isinstance(raw_id, (int, float)):
        gid = int(raw_id)
    else:
        gid = next_id
        next_id += 1

    ybs_raw = raw.get("y_boundaries")
    ybs = safe_float_list(ybs_raw) if isinstance(ybs_raw, (list, tuple)) else None

    return {
        "id": gid,
        "name": str(raw.get("name", "Gate")),
        "type": str(raw.get("type", "crosshair")),
        "auto_method": raw.get("auto_method"),
        "applied": bool(raw.get("applied", False)),
        "color": str(raw.get("color", "#e74c3c")),
        "linestyle": str(raw.get("linestyle", "-")),
        "linewidth": safe_float(raw.get("linewidth", 0.5), 0.5),
        "x_boundaries": safe_float_list(raw.get("x_boundaries", [])),
        "y_boundary": safe_optional_float(raw.get("y_boundary")),
        "x_thresh_active": [
            bool(value)
            for value in (
                raw.get("x_thresh_active", [])
                if isinstance(raw.get("x_thresh_active", []), (list, tuple))
                else []
            )
        ],
        "y_thresh_active": bool(raw.get("y_thresh_active", True)),
        "y_boundaries": ybs,
        "y_thresh_actives": [
            bool(value)
            for value in (
                raw.get("y_thresh_actives", [])
                if isinstance(raw.get("y_thresh_actives", []), (list, tuple))
                else []
            )
        ],
        "x0": safe_float(raw.get("x0", 0.0)),
        "y0": safe_float(raw.get("y0", 0.0)),
        "x1": safe_float(raw.get("x1", 0.0)),
        "y1": safe_float(raw.get("y1", 0.0)),
        "vertices": safe_vertices(raw.get("vertices", [])),
    }, next_id


def next_free_gate_id(raw_gates, current_next_id=0) -> int:
    existing_ids = {
        int(raw["id"])
        for raw in raw_gates
        if isinstance(raw, dict) and isinstance(raw.get("id"), (int, float))
    }
    return max(max(existing_ids, default=-1) + 1, current_next_id)
