#!/usr/bin/env python3
"""Independent deterministic evidence for the v4.3 A2 scientific-method changes."""
from __future__ import annotations

import json
import math
import numpy as np
import pandas as pd
from scipy.optimize import brentq

from vflow.core.circular_stats import (
    Y_ORIENTATION_CARTESIAN, Y_ORIENTATION_IMAGE,
    vector_direction_stats, vectors_from_coordinate_columns,
)
from vflow.core.gate_masks import compute_gate_regions
from vflow.core.logicle import LogicleParameters, logicle_forward, logicle_inverse
from vflow.core.transforms import forward_transform, inverse_transform
from vflow.services.gate_session import prepare_gate_session_load


def main():
    result = {}

    p = LogicleParameters()
    zero_position = (p.A + p.W) / (p.M + p.A)
    landmarks = logicle_inverse(np.array([zero_position, 1.0]), p)
    result["gml2_default_zero_display_coordinate"] = zero_position
    result["gml2_inverse_at_zero_coordinate"] = float(landmarks[0])
    result["gml2_inverse_at_one"] = float(landmarks[1])
    result["gml2_default_T"] = p.T

    rng = np.random.default_rng(4302001)
    root_checks = 0
    max_root_abs_error = 0.0
    for _ in range(40):
        M = rng.uniform(2.0, 6.0)
        W = rng.uniform(0.0, M / 2.0)
        A = rng.uniform(-W, M - 2.0 * W)
        pp = LogicleParameters(T=10 ** rng.uniform(3.0, 7.0), W=W, M=M, A=A)
        xs = rng.uniform(-3.0 * pp.T, 3.0 * pp.T, 12)
        actual = logicle_forward(xs, pp)
        for x, y_actual in zip(xs, actual):
            fn = lambda y: float(logicle_inverse(np.array([y]), pp)[0] - x)
            lo, hi = -1.0, 2.0
            while fn(lo) > 0.0:
                lo *= 2.0
            while fn(hi) < 0.0:
                hi *= 2.0
            expected = brentq(fn, lo, hi, xtol=1e-14, rtol=1e-14)
            max_root_abs_error = max(max_root_abs_error, abs(float(y_actual) - expected))
            root_checks += 1
    result["gml2_independent_root_checks"] = root_checks
    result["gml2_max_forward_coordinate_abs_error"] = max_root_abs_error

    values = np.array([-1e6, -100.0, -1.0, 0.0, 1.0, 100.0, 1e6])
    alias_equal = {}
    for old, explicit in (("biexp", "legacy_biexp"), ("logicle", "legacy_logicle")):
        old_fwd = forward_transform(values, old, 150.0)
        new_fwd = forward_transform(values, explicit, 150.0)
        alias_equal[old] = bool(
            np.array_equal(old_fwd, new_fwd)
            and np.array_equal(
                inverse_transform(old_fwd, old, 150.0),
                inverse_transform(new_fwd, explicit, 150.0),
            )
        )
    result["legacy_alias_bit_identical"] = alias_equal

    payload = {
        "version": 2,
        "gates": [{
            "id": 8, "name": "P", "type": "polygon", "applied": True,
            "vertices": [(-500, -300), (200, -800), (1500, 100),
                         (600, 1200), (-700, 700)],
        }],
        "gate_contexts": {"8": {
            "x_channel": "X", "y_channel": "Y",
            "x_scale": "logicle", "y_scale": "biexp", "cofactor": 73.0,
        }},
    }
    prep = prepare_gate_session_load(payload, gate_file_version=2, current_next_id=0)
    migrated = prep.saved_contexts["8"]
    result["v2_migrated_x_scale"] = migrated["x_scale"]
    result["v2_migrated_y_scale"] = migrated["y_scale"]

    rng = np.random.default_rng(4303)
    x = rng.normal(0.0, 900.0, 3000)
    y = rng.normal(0.0, 900.0, 3000)
    gate = payload["gates"][0]
    old, _ = compute_gate_regions(
        gate, x, y, x_scale="logicle", y_scale="biexp", cofactor=73.0)
    explicit, _ = compute_gate_regions(
        gate, x, y, x_scale="legacy_logicle", y_scale="legacy_biexp", cofactor=73.0)
    result["v2_migration_membership_events"] = int(len(x))
    result["v2_migration_membership_bit_identical"] = bool(
        np.array_equal(old["IN"], explicit["IN"])
        and np.array_equal(old["OUT"], explicit["OUT"])
    )

    df = pd.DataFrame({
        "x1": [0.0, 0.0, 0.0], "y1": [0.0, 0.0, 0.0],
        "x2": [0.0, 1.0, -1.0], "y2": [1.0, 1.0, 1.0],
    })
    mask = np.ones(len(df), dtype=bool)
    cart, mag_cart = vectors_from_coordinate_columns(
        df, mask, "x1", "y1", "x2", "y2",
        y_coordinate_orientation=Y_ORIENTATION_CARTESIAN)
    image, mag_image = vectors_from_coordinate_columns(
        df, mask, "x1", "y1", "x2", "y2",
        y_coordinate_orientation=Y_ORIENTATION_IMAGE)
    sc = vector_direction_stats(cart, mrl_threshold=0.0)
    si = vector_direction_stats(image, mrl_threshold=0.0)
    result["polar_image_angles_are_cartesian_reflection"] = bool(np.allclose(image, -cart))
    result["polar_magnitudes_identical"] = bool(np.array_equal(mag_cart, mag_image))
    result["polar_mrl_abs_difference"] = abs(float(sc["mrl"]) - float(si["mrl"]))
    result["polar_rayleigh_abs_difference"] = abs(float(sc["rayleigh_p"]) - float(si["rayleigh_p"]))
    result["polar_cartesian_mean_deg"] = float(sc["mean_dir_deg"])
    result["polar_image_mean_deg"] = float(si["mean_dir_deg"])

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
