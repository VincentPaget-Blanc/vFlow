"""JSON-safe gate serialization helpers."""

from __future__ import annotations

import math
import os

from .threshold_state import ThresholdSchemaError, serialized_threshold_flags


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


def safe_bool(value, default=False) -> bool:
    """Parse legacy JSON booleans without treating the string ``"false"`` as True."""
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            if math.isfinite(float(value)):
                return bool(value)
        except (TypeError, ValueError, OverflowError):
            pass
        return bool(default)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False
        return bool(default)
    return bool(default)


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
    try:
        threshold_flags = serialized_threshold_flags(gate)
    except ThresholdSchemaError as exc:
        name = gate.get("name")
        gate_id = gate.get("id")
        label = name if name else (gate_id if gate_id is not None else "<unnamed>")
        raise ThresholdSchemaError(f"Gate {label!r}: {exc}") from exc
    raw = {
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
        "x_thresh_active": list(threshold_flags.x_active),
        "y_thresh_active": threshold_flags.y_active,
        "y_boundaries": gate.get("y_boundaries"),
        "y_thresh_actives": list(threshold_flags.y_actives),
        "x0": gate.get("x0", 0.0),
        "y0": gate.get("y0", 0.0),
        "x1": gate.get("x1", 0.0),
        "y1": gate.get("y1", 0.0),
        "vertices": list(gate.get("vertices", [])),
    }
    if not validate_raw_gate(raw):
        label = raw.get("name") or raw.get("id") or "<unnamed>"
        raise ValueError(
            f"Gate {label!r} contains malformed/non-finite geometry or threshold "
            "state and cannot be serialized losslessly."
        )
    return raw


def gates_to_json_payload(gates: list[dict], x_channel: str | None, y_channel: str | None) -> dict:
    """Build the legacy JSON payload for saved gates."""
    return {
        "version": 1,
        "x_channel": x_channel or "",
        "y_channel": y_channel or "",
        "gates": [gate_to_json_dict(gate) for gate in gates],
    }


def gate_save_status(path: str, count: int) -> str:
    """Return the legacy status line after saving gates."""
    return f"\u2713 {count} gate(s) saved \u2192 {os.path.basename(path)}"


def gate_save_message(path: str, count: int, x_channel: str | None, y_channel: str | None) -> str:
    """Return the legacy save-gates completion dialog text."""
    return (
        f"{count} gate(s) saved to:\n{path}\n\n"
        "Channels at save time:\n"
        f"  X: {x_channel}\n  Y: {y_channel}"
    )


def gate_channel_mismatch_message(
    *,
    saved_x: str,
    saved_y: str,
    current_x: str | None,
    current_y: str | None,
) -> str:
    """Return the legacy warning when gate-file channels differ."""
    return (
        "Channel mismatch!\n\n"
        f"Saved with:   X={saved_x!r}  Y={saved_y!r}\n"
        f"Current axes: X={current_x!r}  Y={current_y!r}\n\n"
        "Load anyway? (Gate positions will be wrong if channels differ.)"
    )


def gate_load_status(path: str, count: int, skipped: int = 0) -> str:
    """Return the legacy status line after loading gates."""
    skip_msg = f"  ({skipped} malformed gate(s) skipped)" if skipped else ""
    return f"\u2713 {count} gate(s) loaded from {os.path.basename(path)}{skip_msg}"


def gate_load_message(path: str, count: int, skipped: int = 0) -> str:
    """Return the legacy load-gates completion dialog text."""
    return (
        f"{count} gate(s) loaded from:\n{path}"
        + (f"\n\n\u26a0 {skipped} malformed gate(s) skipped." if skipped else "")
    )


def validate_raw_gate(raw) -> bool:
    """Return whether serialized gate state can be loaded without changing it.

    Inactive gates are validated too: silently dropping a malformed vertex or
    replacing a non-finite coordinate with 0 would create a different gate that
    could later be applied.  Empty/partial *finite* inactive geometry remains
    allowed because it can represent an unfinished gate.
    """
    if not isinstance(raw, dict):
        return False
    gt = raw.get("type", "crosshair")
    if gt not in {"crosshair", "rectangle", "ellipse", "polygon"}:
        return False
    applied = safe_bool(raw.get("applied", False), default=False)

    if gt == "polygon":
        raw_verts = raw.get("vertices", [])
        if not isinstance(raw_verts, (list, tuple)):
            return False
        verts = safe_vertices(raw_verts)
        # Geometry must round-trip losslessly even when inactive.
        if len(verts) != len(raw_verts):
            return False
        return len(verts) >= 3 if applied else True

    if gt in {"rectangle", "ellipse"}:
        keys = ("x0", "y0", "x1", "y1")
        present = [key in raw for key in keys]
        # A completely absent inactive geometry is the historical blank-gate
        # placeholder and will become the all-zero default. Partial presence is
        # ambiguous and must not be synthesized.
        if not any(present):
            return not applied
        if not all(present):
            return False
        coords = [safe_optional_float(raw.get(k)) for k in keys]
        if any(value is None for value in coords):
            return False
        x0, y0, x1, y1 = coords
        return (x0 != x1 and y0 != y1) if applied else True

    # Crosshair thresholds and activity arrays must also round-trip losslessly.
    raw_xbs = raw.get("x_boundaries", [])
    if not isinstance(raw_xbs, (list, tuple)):
        return False
    xbs = safe_float_list(raw_xbs)
    if len(xbs) != len(raw_xbs):
        return False

    raw_yb = raw.get("y_boundary")
    yb = safe_optional_float(raw_yb)
    if raw_yb is not None and yb is None:
        return False

    raw_ybs = raw.get("y_boundaries", [])
    if raw_ybs is None:
        raw_ybs = []
    if not isinstance(raw_ybs, (list, tuple)):
        return False
    ybs = safe_float_list(raw_ybs)
    if len(ybs) != len(raw_ybs):
        return False

    raw_x_flags = raw.get("x_thresh_active")
    if raw_x_flags is not None:
        if not isinstance(raw_x_flags, (list, tuple)) or len(raw_x_flags) != len(xbs):
            return False
    raw_y_flags = raw.get("y_thresh_actives")
    if raw_y_flags is not None:
        if not isinstance(raw_y_flags, (list, tuple)):
            return False
        # Dormant legacy multi-Y flags may be present while only scalar Y is
        # active; preserve them rather than deleting them.  Once multi-Y
        # boundaries exist, lengths must match losslessly.
        if ybs and len(raw_y_flags) != len(ybs):
            return False

    return bool(xbs or yb is not None or ybs) if applied else True


def gate_from_json_dict(raw: dict, next_id: int):
    """Build a sanitized, Tk-free gate dict from legacy JSON data."""
    if not validate_raw_gate(raw):
        return None, next_id

    raw_id = raw.get("id")
    if (isinstance(raw_id, int) and not isinstance(raw_id, bool) and raw_id >= 0):
        gid = raw_id
    elif isinstance(raw_id, float) and math.isfinite(raw_id) and raw_id.is_integer() and raw_id >= 0:
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
        "applied": safe_bool(raw.get("applied", False), default=False),
        "color": str(raw.get("color", "#e74c3c")),
        "linestyle": str(raw.get("linestyle", "-")),
        "linewidth": safe_float(raw.get("linewidth", 0.5), 0.5),
        "x_boundaries": safe_float_list(raw.get("x_boundaries", [])),
        "y_boundary": safe_optional_float(raw.get("y_boundary")),
        "x_thresh_active": [
            safe_bool(value, default=False)
            for value in (
                raw.get("x_thresh_active", [])
                if isinstance(raw.get("x_thresh_active", []), (list, tuple))
                else []
            )
        ],
        "y_thresh_active": safe_bool(raw.get("y_thresh_active", True), default=False),
        "y_boundaries": ybs,
        "y_thresh_actives": [
            safe_bool(value, default=False)
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
    existing_ids = set()
    for raw in raw_gates:
        if not isinstance(raw, dict):
            continue
        value = raw.get("id")
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            existing_ids.add(value)
        elif isinstance(value, float) and math.isfinite(value) and value.is_integer() and value >= 0:
            existing_ids.add(int(value))
    return max(max(existing_ids, default=-1) + 1, current_next_id)


def sanitize_raw_gates(raw_gates: list, current_next_id: int = 0) -> tuple[list[dict], int, int]:
    """Return sanitized gate dicts, next gate id, and skipped count."""
    next_id = next_free_gate_id(raw_gates, current_next_id)
    clean_gates = []
    skipped = 0
    used_ids = set()

    for raw in raw_gates:
        if not validate_raw_gate(raw):
            skipped += 1
            continue
        try:
            clean, next_id = gate_from_json_dict(raw, next_id)
        except Exception:
            skipped += 1
            continue
        if clean is None:
            skipped += 1
            continue
        if clean["id"] in used_ids:
            while next_id in used_ids:
                next_id += 1
            clean["id"] = next_id
            next_id += 1
        used_ids.add(clean["id"])
        clean_gates.append(clean)

    return clean_gates, next_id, skipped
