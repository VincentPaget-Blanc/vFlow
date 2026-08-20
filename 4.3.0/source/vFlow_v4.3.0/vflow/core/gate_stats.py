"""Gate statistics aggregation helpers."""

from __future__ import annotations

import json
import math
import os

import numpy as np

from vflow.core.sample_labels import unique_source_labels


def _validated_region_counts(regions: dict, total: int) -> dict[str, int]:
    """Validate that region masks form one disjoint partition of ``total`` events."""
    total = int(total)
    if total < 0:
        raise ValueError("Gate-stat denominator cannot be negative.")
    if not isinstance(regions, dict):
        raise TypeError("Gate regions must be a dict of boolean masks.")
    if not regions:
        if total == 0:
            return {}
        raise ValueError("A non-empty gate population has no region masks.")

    expected_len = None
    occupied = None
    counts = {}
    for name, raw_mask in regions.items():
        mask = np.asarray(raw_mask, dtype=bool)
        if mask.ndim != 1:
            raise ValueError(f"Gate region {name!r} mask must be one-dimensional.")
        if expected_len is None:
            expected_len = len(mask)
            occupied = np.zeros(expected_len, dtype=bool)
        elif len(mask) != expected_len:
            raise ValueError("Gate region masks do not have a common row length.")
        if np.any(occupied & mask):
            raise ValueError(f"Gate region {name!r} overlaps another region.")
        occupied |= mask
        counts[name] = int(mask.sum())

    union_total = int(occupied.sum()) if occupied is not None else 0
    if union_total != total:
        raise ValueError(
            f"Gate regions cover {union_total} events but the denominator is {total}; "
            "refusing to report inconsistent percentages."
        )
    return counts


def stats_from_regions(regions: dict, total: int) -> dict:
    counts = _validated_region_counts(regions, total)
    return {
        "stats": {
            rname: {
                "count": count,
                "pct": count / total * 100 if total else 0.0,
            }
            for rname, count in counts.items()
        },
        "total": int(total),
    }


def region_percentages(regions: dict, total: int) -> dict:
    if int(total) == 0 and not regions:
        return {}
    counts = _validated_region_counts(regions, total)
    if int(total) == 0:
        return {name: 0.0 for name in counts}
    return {name: count / int(total) * 100.0 for name, count in counts.items()}


def region_percentages_with_total(regions: dict, total: int) -> dict:
    return {rname: (pct, total) for rname, pct in region_percentages(regions, total).items()}


def binomial_percentage_sem(pct: float, total: int) -> float:
    total = int(total)
    pct = float(pct)
    if total <= 0:
        return 0.0
    if not math.isfinite(pct) or not (0.0 <= pct <= 100.0):
        raise ValueError("Percentage must be finite and between 0 and 100.")
    p = pct / 100.0
    return float(math.sqrt(p * (1.0 - p) / total) * 100.0)


def _gate_export_provenance(gate: dict | None, y_boundaries) -> dict:
    """Return additive audit fields for single-gate CSV exports."""
    if gate is None:
        return {}
    gate_type = str(gate.get("type", "crosshair"))
    context = gate.get("_analysis_context") or {}
    geometry = {}
    if gate_type in {"rectangle", "ellipse"}:
        geometry = {key: gate.get(key) for key in ("x0", "y0", "x1", "y1")}
    elif gate_type == "polygon":
        geometry = {"vertices": list(gate.get("vertices") or [])}

    y_values = list(y_boundaries or [])
    return {
        "Gate ID": gate.get("id", ""),
        "Gate Name": gate.get("name", ""),
        "Gate Type": gate_type,
        "Y Gates": "; ".join(f"{float(value):.4f}" for value in y_values),
        "Gate Geometry": (
            json.dumps(geometry, sort_keys=True, separators=(",", ":")) if geometry else ""
        ),
        "X Scale": context.get("x_scale", ""),
        "Y Scale": context.get("y_scale", ""),
        "Cofactor": context.get("cofactor", ""),
        "X Transform Params": (
            json.dumps(context.get("x_transform_params"), sort_keys=True, separators=(",", ":"))
            if context.get("x_transform_params") is not None else ""
        ),
        "Y Transform Params": (
            json.dumps(context.get("y_transform_params"), sort_keys=True, separators=(",", ":"))
            if context.get("y_transform_params") is not None else ""
        ),
    }


def build_gate_stats_export_rows(
    *, mode: str, gate_stats_for: dict, merged_stats: dict,
    x_channel: str, y_channel: str, x_boundaries: list, y_boundary,
    y_boundaries=None, gate: dict | None = None,
) -> list[dict]:
    """Build single-gate stats CSV rows with auditable per-file provenance."""
    rows = []
    x_gates = "; ".join(f"{value:.4f}" for value in x_boundaries)
    y_gate = round(y_boundary, 4) if y_boundary is not None else ""
    provenance = _gate_export_provenance(gate, y_boundaries)

    if mode == "merged":
        if not merged_stats:
            return rows
        for population, data in merged_stats["stats"].items():
            rows.append({
                **provenance,
                "File": "MERGED", "Source_Path": "",
                "X Channel": x_channel, "Y Channel": y_channel,
                "X Gates": x_gates, "Y Gate": y_gate,
                "Population": population, "Count": data["count"],
                "Total": merged_stats["total"],
                "Input Total": merged_stats.get("raw_total", merged_stats["total"]),
                "Transform Excluded": merged_stats.get("transform_excluded", 0),
                "FCS Compensation Metadata": "; ".join(
                    merged_stats.get("compensation_metadata_keys", ())),
                "Compensation State": (
                    "VERIFY" if merged_stats.get("compensation_metadata_keys") else ""),
                "Percentage": round(data["pct"], 3),
            })
        return rows

    labels = unique_source_labels(list(gate_stats_for.keys()))
    for file_path, info in gate_stats_for.items():
        for population, data in info["stats"].items():
            rows.append({
                **provenance,
                "File": labels[str(file_path)],
                "Source_Path": os.path.abspath(os.path.normpath(str(file_path))),
                "X Channel": x_channel, "Y Channel": y_channel,
                "X Gates": x_gates, "Y Gate": y_gate,
                "Population": population, "Count": data["count"],
                "Total": info["total"],
                "Input Total": info.get("raw_total", info["total"]),
                "Transform Excluded": info.get("transform_excluded", 0),
                "FCS Compensation Metadata": "; ".join(
                    info.get("compensation_metadata_keys", ())),
                "Compensation State": (
                    "VERIFY" if info.get("compensation_metadata_keys") else ""),
                "Percentage": round(data["pct"], 3),
            })
    return rows


def merge_gate_stats(gate_data: dict) -> dict:
    """Merge compatible per-file gate stats; reject region-schema drift."""
    if not gate_data:
        return {}
    first_info = next(iter(gate_data.values()))
    region_names = list(first_info["stats"].keys())
    expected = set(region_names)
    counts = {region: 0 for region in region_names}
    total = 0
    raw_total = 0
    transform_excluded = 0
    compensation_metadata_keys = set()
    for file_path, info in gate_data.items():
        actual = set(info.get("stats", {}).keys())
        if actual != expected:
            raise ValueError(
                f"Gate region schema differs for {file_path!r}: "
                f"expected {sorted(expected)}, got {sorted(actual)}."
            )
        file_total = int(info.get("total", 0))
        if file_total < 0:
            raise ValueError("Gate-stat denominator cannot be negative.")
        file_count_sum = sum(int(info["stats"][region].get("count", 0)) for region in region_names)
        if file_count_sum != file_total:
            raise ValueError(
                f"Gate counts for {file_path!r} sum to {file_count_sum}, "
                f"but total is {file_total}."
            )
        total += file_total
        file_raw_total = int(info.get("raw_total", file_total))
        file_excluded = int(info.get("transform_excluded", file_raw_total - file_total))
        if file_raw_total < file_total or file_excluded != file_raw_total - file_total:
            raise ValueError(
                f"Gate provenance for {file_path!r} is inconsistent: input={file_raw_total}, "
                f"valid={file_total}, excluded={file_excluded}."
            )
        raw_total += file_raw_total
        transform_excluded += file_excluded
        compensation_metadata_keys.update(
            str(key) for key in info.get("compensation_metadata_keys", ()) or ())
        for region in region_names:
            counts[region] += int(info["stats"][region].get("count", 0))
    return {
        "stats": {
            region: {
                "count": counts[region],
                "pct": counts[region] / total * 100 if total else 0.0,
            }
            for region in region_names
        },
        "total": total,
        "raw_total": raw_total,
        "transform_excluded": transform_excluded,
        "compensation_metadata_keys": tuple(sorted(compensation_metadata_keys)),
    }

def binary_gate_partition_counts(
    gate_names: list[str],
    in_masks: list[np.ndarray],
) -> dict[str, int]:
    """Return the exact v4.2 Venn-like partition for multiple shape gates.

    Combinations are enumerated in the historical little-endian gate order
    (gate 0 is the least-significant bit). Duplicate display names intentionally
    aggregate into the same textual region key, matching the legacy controller.
    """
    if len(gate_names) != len(in_masks):
        raise ValueError("gate_names and in_masks must have equal length.")
    if not gate_names:
        return {}

    masks = [np.asarray(mask, dtype=bool) for mask in in_masks]
    n = len(masks[0])
    if any(mask.ndim != 1 or len(mask) != n for mask in masks):
        raise ValueError("All binary gate masks must be one-dimensional and equal length.")

    parts: dict[str, int] = {}
    for combo_index in range(2 ** len(gate_names)):
        combo_mask = np.ones(n, bool)
        labels = []
        for gate_index, gate_name in enumerate(gate_names):
            flag = bool((combo_index >> gate_index) & 1)
            if flag:
                combo_mask &= masks[gate_index]
                labels.append(gate_name)
            else:
                combo_mask &= ~masks[gate_index]
        count = int(combo_mask.sum())
        if count == 0:
            continue
        region_name = " ∩ ".join(labels) if labels else "Outside all"
        parts[region_name] = parts.get(region_name, 0) + count
    return parts


def binary_gate_partition_sort_key(region_name: str) -> tuple[int, str]:
    """Return the legacy display ordering for multi-shape partition regions."""
    if region_name == "Outside all":
        return (2, region_name)
    if "∩" in region_name:
        return (1, region_name)
    return (0, region_name)

