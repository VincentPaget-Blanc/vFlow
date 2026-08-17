#!/usr/bin/env python3
"""Rebuild the frozen v4.2 scientific fingerprint from the current source tree."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from vflow.app.lineage import PopulationLineage
from vflow.app.state import AnalysisState
from vflow.core.fcs_reader import read_fcs
from vflow.core.gate_masks import compute_gate_regions, selected_region_mask
from vflow.core.gate_serialization import gate_to_json_dict
from vflow.legacy.vflow_app import FlowApp


def _sha_bool(mask) -> str:
    return hashlib.sha256(np.asarray(mask, dtype=bool).tobytes()).hexdigest()


def _gate_record(gate, x, y):
    regions, colors = compute_gate_regions(
        gate, x, y, x_scale="linear", y_scale="linear", cofactor=150.0,
        x_channel="X", y_channel="Y")
    all_mask = selected_region_mask(
        regions, total=len(x), gate_type=gate.get("type", "crosshair"),
        region_name="All regions")
    return {
        "all_mask": _sha_bool(all_mask),
        "colors": list(colors),
        "regions": {name: _sha_bool(mask) for name, mask in regions.items()},
    }


def build(reference_fcs: Path) -> dict:
    x = np.array([-2, -1, 0, 1, 2, np.nan, np.inf], dtype=np.float64)
    y = x.copy()
    gates = [
        {"id": 1, "name": "C", "type": "crosshair", "applied": True,
         "color": "#1", "x_boundaries": [0.0], "x_thresh_active": [True],
         "y_boundary": 0.0, "y_thresh_active": True},
        {"id": 2, "name": "R", "type": "rectangle", "applied": True,
         "color": "#2", "x0": -1.0, "x1": 1.0, "y0": -1.0, "y1": 1.0},
        {"id": 3, "name": "E", "type": "ellipse", "applied": True,
         "color": "#3", "x0": -1.5, "x1": 1.5, "y0": -1.5, "y1": 1.5},
        {"id": 4, "name": "P", "type": "polygon", "applied": True,
         "color": "#4", "vertices": [(-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0)]},
    ]

    explicit_regions, _ = compute_gate_regions(
        gates[1], x, y, x_scale="linear", y_scale="linear", cofactor=150.0,
        x_channel="X", y_channel="Y")

    same_a = {"x_channel": "X", "y_channel": "Y", "x_scale": "linear",
              "y_scale": "linear", "cofactor": None}
    same_b = dict(same_a)
    other = dict(same_a, x_channel="Other")

    df, _ = read_fcs(str(reference_fcs))
    fcs_values = df.to_numpy(dtype=np.float64, copy=False)

    app = FlowApp.__new__(FlowApp)
    app.x_channel = "X"
    app.y_channel = "Y"
    app.x_scale = "linear"
    app.y_scale = "linear"
    app.cofactor = 150.0
    app._data_generation = 1
    app._tc = {}
    app._gmc = {}
    app._scatter_cache = {}
    app._minor_loc_cache = {}
    cache_gate = dict(gates[1])
    app._bind_gate_context(cache_gate)
    r1, c1 = app._gate_mask_for(cache_gate, x, y, _cache_path="reference.csv")
    r2, c2 = app._gate_mask_for(cache_gate, x, y, _cache_path="reference.csv")
    cached_same = (
        r1.keys() == r2.keys()
        and all(r1[k] is r2[k] for k in r1)
        and c1 is c2
    )

    serial_gate = {
        "id": 8, "name": "Ser", "type": "crosshair", "auto_method": None,
        "applied": True, "color": "#abc", "linestyle": "--", "linewidth": 1.5,
        "x_boundaries": [-1.0, 1.0], "y_boundary": 0.25,
        "x_thresh_vars": [True, False], "y_thresh_var": True,
        "y_boundaries": None, "y_thresh_vars": [],
        "x0": 0.0, "y0": 0.0, "x1": 0.0, "y1": 0.0, "vertices": [],
    }

    lineage_context = dict(same_a)
    lineage_gate = {
        "id": 2, "name": "R", "type": "rectangle", "applied": True,
        "color": "#2", "x0": -1.0, "x1": 1.0, "y0": -1.0, "y1": 1.0,
        "_analysis_context": dict(lineage_context),
    }
    lineage = [{"gate": lineage_gate, "region": "IN", "context": dict(lineage_context)}]

    return {
        "context_equal_other": AnalysisState.contexts_equal(same_a, other),
        "context_equal_same": AnalysisState.contexts_equal(same_a, same_b),
        "explicit_regions": {k: _sha_bool(v) for k, v in explicit_regions.items()},
        "fcs_cols": list(df.columns),
        "fcs_compat_count": len(df.attrs.get("fcs_compatibility_fixes", ())),
        "fcs_finite": bool(np.isfinite(fcs_values).all()),
        "fcs_shape": list(fcs_values.shape),
        "fcs_values_sha256": hashlib.sha256(fcs_values.tobytes()).hexdigest(),
        "flow_gate_cache_size": len(app._gmc),
        "flow_gate_cached_same_arrays": bool(cached_same),
        "flow_gate_colors": list(c1),
        "flow_gate_regions": {k: _sha_bool(v) for k, v in r1.items()},
        "gate_json": gate_to_json_dict(serial_gate),
        "gates": {str(g["id"]): _gate_record(g, x, y) for g in gates},
        "lineage_signature": PopulationLineage.legacy_signature(lineage),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("reference_fcs", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    payload = build(args.reference_fcs)
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False) + "\n").encode("utf-8")
    if args.output:
        args.output.write_bytes(raw)
    sha = hashlib.sha256(raw).hexdigest()
    print(f"scientific_fingerprint_sha256={sha}")
    if args.compare:
        expected = args.compare.read_bytes()
        print(f"byte_identical={raw == expected}")
        if raw != expected:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
