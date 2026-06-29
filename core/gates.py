"""Dict-compatible gate helpers."""

from __future__ import annotations


def gate_type(gate: dict) -> str:
    return gate.get("type", "crosshair") if gate else "crosshair"


def gate_id(gate: dict):
    return gate.get("id") if gate else None


def is_crosshair(gate: dict) -> bool:
    return gate_type(gate) == "crosshair"


def is_shape_gate(gate: dict) -> bool:
    return gate_type(gate) in ("rectangle", "ellipse", "polygon")


def _flag_value(value) -> bool:
    try:
        return bool(value.get())
    except AttributeError:
        return bool(value)


def active_x_boundaries(gate: dict) -> list:
    """Return enabled X boundaries for a crosshair gate dict."""
    if not gate or not is_crosshair(gate):
        return []
    xbs = gate.get("x_boundaries", [])
    tvs = gate.get("x_thresh_vars") or gate.get("x_thresh_active") or []
    if len(tvs) != len(xbs):
        return list(xbs)
    return [xb for xb, flag in zip(xbs, tvs) if _flag_value(flag)]


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
        tvs = gate.get("y_thresh_vars") or gate.get("y_thresh_actives") or []
        if len(tvs) != len(ybs_list):
            return list(ybs_list)
        return [yb for yb, flag in zip(ybs_list, tvs) if _flag_value(flag)]

    yb = gate.get("y_boundary")
    if yb is None:
        return []
    flag = gate.get("y_thresh_var")
    if flag is None:
        flag = gate.get("y_thresh_active", True)
    return [yb] if _flag_value(flag) else []

