"""Helpers for gated cell export."""

from __future__ import annotations

import numpy as np


def gate_export_order(gates: list[dict]) -> list[dict]:
    """Return shape gates first, then crosshair gates, preserving order within each."""
    shape_gates = [g for g in gates if g.get("type", "crosshair") != "crosshair"]
    xhair_gates = [g for g in gates if g.get("type", "crosshair") == "crosshair"]
    return shape_gates + xhair_gates


def assign_gated_cells(
    gates: list[dict],
    n_cells: int,
    regions_for_gate,
):
    """Assign each cell to its first matching export gate.

    ``regions_for_gate`` is called as ``regions_for_gate(gate)`` and must
    return a region-mask mapping for that gate.
    """
    assigned_gate = np.full(n_cells, "", dtype=object)
    assigned_region = np.full(n_cells, "", dtype=object)
    assigned_type = np.full(n_cells, "", dtype=object)
    in_any = np.zeros(n_cells, bool)

    for gate in gate_export_order(gates):
        regions = regions_for_gate(gate)
        gt = gate.get("type", "crosshair")
        gname = gate.get("name", "")

        for rname, mask in regions.items():
            if gt != "crosshair" and rname == "OUT":
                continue
            new_cells = mask & ~in_any
            if new_cells.any():
                assigned_gate[new_cells] = gname
                assigned_region[new_cells] = rname
                assigned_type[new_cells] = gt
                in_any[new_cells] = True

    return {
        "mask": in_any,
        "gate": assigned_gate,
        "region": assigned_region,
        "type": assigned_type,
    }

