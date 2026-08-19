#!/usr/bin/env python3
"""Deterministic adversarial checks for v4.3 Accuracy Hardening A4."""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from vflow.core.circular_stats import circular_mean_direction, vector_direction_stats
from vflow.core.gate_serialization import validate_raw_gate
from vflow.services.batch_stats_export import region_universe_total
from vflow.services.channel_selection import plan_channel_menu


def _assert_raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return
    raise AssertionError(f"expected {exc.__name__}")


def main():
    rng = np.random.default_rng(4304001)

    # 1. Batch partitions must be disjoint and exhaustive over the established
    # transform-valid universe.  Valid randomized partitions pass; overlap/gap
    # variants must fail rather than change the denominator.
    valid_partitions = 0
    rejected_bad_partitions = 0
    for _ in range(300):
        n = int(rng.integers(1, 250))
        labels = rng.integers(0, 4, size=n)
        regions = {f"R{i}": labels == i for i in range(4)}
        assert region_universe_total(regions, n) == n
        valid_partitions += 1

        overlap = {k: v.copy() for k, v in regions.items()}
        overlap["R0"][0] = True
        overlap["R1"][0] = True
        _assert_raises(lambda o=overlap, n=n: region_universe_total(o, n))
        rejected_bad_partitions += 1

        gap = {k: v.copy() for k, v in regions.items()}
        for mask in gap.values():
            mask[0] = False
        _assert_raises(lambda g=gap, n=n: region_universe_total(g, n))
        rejected_bad_partitions += 1

    # 2. Multi-file channel planning may expose only numeric, non-provenance
    # channels that are actually analyzable in every active source.  A pooled
    # channel absent from one constituent source must be withheld.
    channel_checks = 0
    for _ in range(300):
        n1 = int(rng.integers(2, 20))
        n2 = int(rng.integers(2, 20))
        a = pd.DataFrame({"A": rng.normal(size=n1), "B": rng.normal(size=n1)})
        b = pd.DataFrame({"A": rng.normal(size=n2), "B": rng.normal(size=n2)})
        a["Source_Path"] = "/tmp/a.csv"
        b["Source_Path"] = "/tmp/b.csv"
        plan = plan_channel_menu({"a": a, "b": b}, None, None)
        assert plan.values == ("A", "B")
        assert "Source_Path" not in plan.values
        channel_checks += 1

    pooled = pd.DataFrame({
        "A": [1.0, 2.0, 3.0, 4.0],
        "Partial": [10.0, 11.0, np.nan, np.nan],
        "Source_Path": ["/tmp/a.csv", "/tmp/a.csv", "/tmp/b.csv", "/tmp/b.csv"],
    })
    pooled_plan = plan_channel_menu({"pool": pooled}, None, None)
    assert "A" in pooled_plan.values
    assert "Partial" not in pooled_plan.values
    assert "Source_Path" not in pooled_plan.values
    channel_checks += 1

    no_common = plan_channel_menu(
        {"a": pd.DataFrame({"A": [1.0]}), "b": pd.DataFrame({"B": [2.0]})},
        "A", "B",
    )
    assert no_common.values == ()
    assert ("x_channel", None) in no_common.operations
    assert ("y_channel", None) in no_common.operations
    channel_checks += 1

    # Ambiguous auto-suffixed identities remain single-file usable but are not
    # silently assumed to match across files.
    f1 = pd.DataFrame({"CD3": [1.0], "CD3_1": [2.0]})
    f2 = pd.DataFrame({"CD3": [3.0], "CD3_1": [4.0]})
    f1.attrs["fcs_ambiguous_channel_names"] = ("CD3", "CD3_1")
    f2.attrs["fcs_ambiguous_channel_names"] = ("CD3", "CD3_1")
    single = plan_channel_menu({"f1": f1}, None, None)
    multi = plan_channel_menu({"f1": f1, "f2": f2}, None, None)
    assert "CD3" in single.values and "CD3_1" in single.values
    assert "CD3" not in multi.values and "CD3_1" not in multi.values
    channel_checks += 1

    # 3. Circular mean direction is undefined for an exactly antipodal pair at
    # every rotation; no floating-point artifact may manufacture an angle.
    circular_checks = 0
    for phi in np.linspace(-math.pi, math.pi, 361):
        angles = np.array([phi, phi + math.pi])
        assert np.isnan(circular_mean_direction(angles))
        stats = vector_direction_stats(angles, mrl_threshold=0.5)
        assert stats["mean_dir_deg"] is None
        assert stats["significant"] is False
        circular_checks += 1

    # 4. Inactive malformed geometry must fail validation just like applied
    # malformed geometry; it must not be sanitized into a different future gate.
    malformed = [
        {"type": "polygon", "applied": False, "vertices": [[0, 0], [1, float("nan")], [1, 1]]},
        {"type": "rectangle", "applied": False, "x0": 0, "y0": 0, "x1": float("inf"), "y1": 1},
        {"type": "ellipse", "applied": False, "x0": 0, "y0": 0, "x1": "bad", "y1": 1},
        {"type": "crosshair", "applied": False, "x_boundaries": [0, float("nan")]},
    ]
    for gate in malformed:
        assert validate_raw_gate(gate) is False

    result = {
        "valid_batch_partition_checks": valid_partitions,
        "rejected_bad_batch_partitions": rejected_bad_partitions,
        "channel_integrity_checks": channel_checks,
        "undefined_circular_mean_checks": circular_checks,
        "malformed_inactive_gate_checks": len(malformed),
        "status": "PASS",
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
