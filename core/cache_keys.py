"""Cache key helpers for gate-dependent computations."""

from __future__ import annotations


def _flag_tuple(values) -> tuple:
    out = []
    for value in values or []:
        try:
            out.append(bool(value.get()))
        except AttributeError:
            out.append(bool(value))
    return tuple(out)


def _flag_value(value, default=True) -> bool:
    if value is None:
        return bool(default)
    try:
        return bool(value.get())
    except AttributeError:
        return bool(value)


def gate_signature(gate: dict) -> int:
    """Return a stable integer hash of a gate's geometry and active flags."""
    vertex_prec = 8

    gt = gate.get("type", "crosshair")
    if gt == "crosshair":
        x_tvs = gate.get("x_thresh_vars") or gate.get("x_thresh_active") or []
        y_tvs = gate.get("y_thresh_vars") or gate.get("y_thresh_actives") or []
        y_boundaries = gate.get("y_boundaries") or []
        key = (
            gt,
            tuple(gate.get("x_boundaries") or []),
            gate.get("y_boundary"),
            _flag_tuple(x_tvs),
            _flag_value(gate.get("y_thresh_var"), gate.get("y_thresh_active", True)),
            tuple(y_boundaries),
            _flag_tuple(y_tvs),
        )
    elif gt in ("rectangle", "ellipse"):
        key = (
            gt,
            gate.get("x0"),
            gate.get("y0"),
            gate.get("x1"),
            gate.get("y1"),
        )
    elif gt == "polygon":
        raw_verts = gate.get("vertices") or []
        rounded = tuple(
            (round(float(x), vertex_prec), round(float(y), vertex_prec))
            for x, y in raw_verts
        )
        key = (gt, rounded)
    else:
        key = (gt,)
    return hash(key)

