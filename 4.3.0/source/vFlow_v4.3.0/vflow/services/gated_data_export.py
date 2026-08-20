"""Helpers for gated cell export."""

from __future__ import annotations

import os

import numpy as np

from vflow.core.sample_labels import unique_source_labels


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
    assigned_id = np.full(n_cells, -1, dtype=np.int64)
    in_any = np.zeros(n_cells, bool)

    for gate in gate_export_order(gates):
        regions = regions_for_gate(gate)
        gt = gate.get("type", "crosshair")
        gname = gate.get("name", "")
        gid = gate.get("id", -1)

        for rname, mask in regions.items():
            mask = np.asarray(mask, dtype=bool)
            if mask.ndim != 1 or len(mask) != n_cells:
                raise ValueError(
                    f"Gate {gname!r} region {rname!r} mask length does not match "
                    f"the {n_cells} input rows."
                )
            if gt != "crosshair" and rname == "OUT":
                continue
            new_cells = mask & ~in_any
            if new_cells.any():
                assigned_gate[new_cells] = gname
                assigned_region[new_cells] = rname
                assigned_type[new_cells] = gt
                try:
                    assigned_id[new_cells] = int(gid)
                except (TypeError, ValueError):
                    assigned_id[new_cells] = -1
                in_any[new_cells] = True

    return {
        "mask": in_any,
        "gate": assigned_gate,
        "region": assigned_region,
        "type": assigned_type,
        "id": assigned_id,
    }


def build_gated_export_frames(
    *,
    active_files: dict,
    applied_gates: list[dict],
    x_channel: str | None,
    y_channel: str | None,
    regions_for_gate,
) -> list:
    """Build per-file DataFrames for the legacy gated-cell CSV export."""
    frames = []
    source_labels = unique_source_labels(list(active_files.keys()))

    for file_path, df in active_files.items():
        file_base = source_labels[str(file_path)]
        source_path = os.path.abspath(os.path.normpath(str(file_path)))

        if not applied_gates:
            out = df.copy()
            out.insert(0, "Source_Path", source_path)
            out.insert(0, "Source_File", file_base)
            frames.append(out)
            continue

        xa = (
            df[x_channel].to_numpy(dtype=float, copy=False)
            if x_channel and x_channel in df.columns
            else None
        )
        ya = (
            df[y_channel].to_numpy(dtype=float, copy=False)
            if y_channel and y_channel in df.columns
            else None
        )

        if xa is None or ya is None:
            raise ValueError(
                f"Cannot export gated data for {file_base!r}: required gate axes "
                f"X={x_channel!r}, Y={y_channel!r} are not both present."
            )

        assignment = assign_gated_cells(
            applied_gates,
            len(df),
            lambda gate: regions_for_gate(file_path, gate, xa, ya),
        )
        gated_mask = assignment["mask"]
        if not gated_mask.any():
            continue

        out = df[gated_mask].copy().reset_index(drop=True)
        out.insert(0, "Source_Path", [source_path] * int(gated_mask.sum()))
        out.insert(0, "Source_File", [file_base] * int(gated_mask.sum()))
        out["Gate_ID"] = assignment["id"][gated_mask]
        out["Gate_Name"] = assignment["gate"][gated_mask]
        out["Gate_Region"] = assignment["region"][gated_mask]
        out["Gate_Type"] = assignment["type"][gated_mask]
        frames.append(out)

    return frames
