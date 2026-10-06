"""Tk-free planning helpers for the live-gate lifecycle.

This module preserves the frozen v4.1.11 gate-list semantics while keeping
all Tk variables, geometry editing, context binding, cache invalidation,
statistics, and rendering inside ``FlowApp``.  The helpers here only make
plain-Python decisions about gate construction, selector labels/resolution,
and deletion/neighbor selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vflow.core.gates import new_gate_dict, remove_gate_and_select_neighbor


@dataclass(frozen=True)
class NewGatePlan:
    """Plain gate payload plus the legacy draw-gate selection decision."""

    gate: dict
    draw_gate_id: int | None


def build_new_gate_plan(
    *,
    gate_id: int,
    gate_type: str,
    color: str,
    auto_apply: dict | None = None,
    auto_method: str | None = None,
) -> NewGatePlan:
    """Build a new legacy gate without touching Tk or application state.

    Frozen v4.1.11 intentionally distinguishes ``auto_apply is None`` from
    truthiness when deciding whether Draw mode is enabled in ``FlowApp``, but
    uses truthiness here for geometry injection / ``applied`` and for whether
    the new gate remains the draw target.  That slightly unusual behavior is
    preserved exactly, including the empty-dict case.
    """
    gate = new_gate_dict(
        gate_id_value=gate_id,
        gate_type_value=gate_type,
        color=color,
        auto_method=auto_method,
    )
    if auto_apply:
        gate.update(auto_apply)
        gate["applied"] = True
    return NewGatePlan(
        gate=gate,
        draw_gate_id=gate_id if not auto_apply else None,
    )


@dataclass(frozen=True)
class DeleteGatePlan:
    """Plain state decisions for deleting one gate."""

    gates: list[dict]
    selected_gate_id: int | None
    clear_hover: bool
    clear_pinned: bool
    clear_draw: bool
    remove_stats: bool


def plan_gate_delete(
    gates: list[dict],
    *,
    gate_id: int,
    selected_gate_id: int | None,
    hover_gate_id: int | None,
    pinned_gate_id: int | None,
    draw_gate_id: int | None,
    stats_gate_ids: Any = (),
) -> DeleteGatePlan:
    """Return the exact v4.1.11 gate-list/transient cleanup decisions."""
    remaining, selected = remove_gate_and_select_neighbor(
        gates,
        gate_id_value=gate_id,
        selected_gate_id=selected_gate_id,
    )
    return DeleteGatePlan(
        gates=remaining,
        selected_gate_id=selected,
        clear_hover=hover_gate_id == gate_id,
        clear_pinned=pinned_gate_id == gate_id,
        clear_draw=draw_gate_id == gate_id,
        remove_stats=gate_id in stats_gate_ids,
    )


def gate_selector_labels(gates: list[dict]) -> list[str]:
    """Return frozen duplicate-safe selector labels for applied gates."""
    applied = [gate for gate in gates if gate.get("applied")]
    counts: dict[str, int] = {}
    for gate in applied:
        name = str(gate.get("name") or f"Gate {gate.get('id', '?')}")
        counts[name] = counts.get(name, 0) + 1

    labels = ["All cells"]
    for gate in applied:
        name = str(gate.get("name") or f"Gate {gate.get('id', '?')}")
        labels.append(
            name if counts[name] == 1 else f"{name} [#{gate.get('id')}]"
        )
    return labels


def resolve_gate_selector(gates: list[dict], choice: str):
    """Resolve a selector label to exactly one applied gate, or ``None``."""
    if not choice or choice == "All cells":
        return None

    applied = [gate for gate in gates if gate.get("applied")]
    counts: dict[str, int] = {}
    for gate in applied:
        name = str(gate.get("name") or f"Gate {gate.get('id', '?')}")
        counts[name] = counts.get(name, 0) + 1

    matches = []
    for gate in applied:
        name = str(gate.get("name") or f"Gate {gate.get('id', '?')}")
        label = name if counts[name] == 1 else f"{name} [#{gate.get('id')}]"
        if label == choice:
            matches.append(gate)
    return matches[0] if len(matches) == 1 else None
