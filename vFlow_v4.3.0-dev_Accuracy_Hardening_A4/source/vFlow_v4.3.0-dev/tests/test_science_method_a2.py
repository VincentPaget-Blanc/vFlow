from pathlib import Path
import math

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import brentq

from vflow.app.state import AnalysisState
from vflow.core.circular_stats import (
    ANGLE_CONVENTION,
    Y_ORIENTATION_CARTESIAN,
    Y_ORIENTATION_IMAGE,
    build_polar_stats_export_row,
    vector_direction_stats,
    vectors_from_coordinate_columns,
)
from vflow.core.gate_masks import compute_gate_regions
from vflow.core.logicle import (
    LogicleParameters,
    logicle_forward,
    logicle_inverse,
)
from vflow.core.transforms import forward_transform, inverse_transform
from vflow.services.gate_session import (
    build_gate_session_payload,
    prepare_gate_session_load,
    validate_gate_context_payload,
)


def test_gatingml_logicle_default_landmarks_and_monotonicity():
    p = LogicleParameters()
    zero_position = (p.A + p.W) / (p.M + p.A)
    raw = logicle_inverse(np.array([zero_position, 1.0]), p)
    assert raw[0] == pytest.approx(0.0, abs=1e-12)
    assert raw[1] == pytest.approx(p.T, rel=2e-13, abs=2e-10)

    values = np.linspace(-2 * p.T, 2 * p.T, 4001)
    transformed = logicle_forward(values, p)
    assert np.all(np.diff(transformed) > 0.0)


def test_gatingml_logicle_forward_matches_independent_bracketed_roots_randomized():
    rng = np.random.default_rng(4302)
    for _ in range(40):
        M = rng.uniform(2.0, 6.0)
        W = rng.uniform(0.0, M / 2.0)
        A = rng.uniform(-W, M - 2.0 * W)
        p = LogicleParameters(T=10 ** rng.uniform(3.0, 7.0), W=W, M=M, A=A)
        xs = rng.uniform(-3.0 * p.T, 3.0 * p.T, 12)
        actual = logicle_forward(xs, p)
        expected = []
        for x in xs:
            fn = lambda y: float(logicle_inverse(np.array([y]), p)[0] - x)
            lo, hi = -1.0, 2.0
            while fn(lo) > 0:
                lo *= 2.0
            while fn(hi) < 0:
                hi *= 2.0
            expected.append(brentq(fn, lo, hi, xtol=1e-14, rtol=1e-14))
        assert np.allclose(actual, expected, rtol=0.0, atol=2e-11)


def test_gatingml_logicle_parameter_constraints_fail_closed():
    with pytest.raises(ValueError):
        LogicleParameters(T=0)
    with pytest.raises(ValueError):
        LogicleParameters(W=3.0, M=4.5)
    with pytest.raises(ValueError):
        LogicleParameters(W=0.5, M=4.5, A=-0.6)
    with pytest.raises(ValueError):
        LogicleParameters(W=0.5, M=4.5, A=3.6)


def test_historical_transform_aliases_are_bit_identical_to_explicit_legacy_names():
    values = np.array([-1e6, -100.0, -1.0, 0.0, 1.0, 100.0, 1e6])
    for old, explicit in (("biexp", "legacy_biexp"), ("logicle", "legacy_logicle")):
        old_fwd = forward_transform(values, old, 150.0)
        explicit_fwd = forward_transform(values, explicit, 150.0)
        assert np.array_equal(old_fwd, explicit_fwd)
        assert np.array_equal(
            inverse_transform(old_fwd, old, 150.0),
            inverse_transform(explicit_fwd, explicit, 150.0),
        )


def test_v2_gate_context_migrates_names_only_and_preserves_membership():
    payload = {
        "version": 2,
        "gates": [{
            "id": 4, "name": "P", "type": "polygon", "applied": True,
            "vertices": [(-100, -100), (100, -100), (100, 100), (-100, 100)],
        }],
        "gate_contexts": {"4": {
            "x_channel": "X", "y_channel": "Y",
            "x_scale": "logicle", "y_scale": "biexp", "cofactor": 150.0,
        }},
    }
    prep = prepare_gate_session_load(payload, gate_file_version=2, current_next_id=0)
    ctx = prep.saved_contexts["4"]
    assert ctx["x_scale"] == "legacy_logicle"
    assert ctx["y_scale"] == "legacy_biexp"

    x = np.array([-200.0, -50.0, 0.0, 50.0, 200.0])
    y = np.array([0.0, -50.0, 0.0, 50.0, 0.0])
    old_regions, _ = compute_gate_regions(
        payload["gates"][0], x, y,
        x_scale="logicle", y_scale="biexp", cofactor=150.0)
    new_regions, _ = compute_gate_regions(
        payload["gates"][0], x, y,
        x_scale=ctx["x_scale"], y_scale=ctx["y_scale"], cofactor=150.0)
    assert np.array_equal(old_regions["IN"], new_regions["IN"])
    assert np.array_equal(old_regions["OUT"], new_regions["OUT"])


def test_v3_standard_logicle_context_requires_and_serializes_per_axis_parameters():
    state = AnalysisState(x_channel="X", y_channel="Y", x_scale="logicle_gml2", y_scale="linear")
    state.x_transform_params = {"T": 100000.0, "W": 0.35, "M": 4.2, "A": 0.1}
    gate = {
        "id": 1, "name": "R", "type": "rectangle", "applied": True,
        "x0": -5, "y0": -5, "x1": 5, "y1": 5,
    }
    state.bind_gate_context(gate)
    payload = build_gate_session_payload([gate], analysis_state=state, population_lineage=[])
    assert payload["version"] == 3
    assert payload["x_transform_params"] == state.x_transform_params
    assert payload["gate_contexts"]["1"]["x_transform_params"] == state.x_transform_params

    bad = dict(payload["gate_contexts"]["1"])
    bad.pop("x_transform_params")
    ok, why = validate_gate_context_payload(bad)
    assert not ok
    assert why == "missing X Logicle parameters"


def test_gate_context_compatibility_includes_per_axis_logicle_parameters():
    state = AnalysisState(x_channel="X", y_channel="Y", x_scale="logicle_gml2", y_scale="linear")
    gate = {"id": 1}
    state.bind_gate_context(gate)
    assert state.gate_context_matches(gate)
    state.x_transform_params = dict(state.x_transform_params, W=0.6)
    assert not state.gate_context_matches(gate)


def _coordinate_df():
    return pd.DataFrame({
        "x1": [0.0, 0.0, 0.0],
        "y1": [0.0, 0.0, 0.0],
        "x2": [0.0, 1.0, -1.0],
        "y2": [1.0, 1.0, 1.0],
    })


def test_polar_y_orientation_reflects_angles_but_preserves_magnitude_and_rayleigh_strength():
    df = _coordinate_df()
    mask = np.ones(len(df), bool)
    cart, mag_cart = vectors_from_coordinate_columns(
        df, mask, "x1", "y1", "x2", "y2",
        y_coordinate_orientation=Y_ORIENTATION_CARTESIAN)
    image, mag_image = vectors_from_coordinate_columns(
        df, mask, "x1", "y1", "x2", "y2",
        y_coordinate_orientation=Y_ORIENTATION_IMAGE)
    assert np.allclose(image, -cart)
    assert np.array_equal(mag_cart, mag_image)
    stats_cart = vector_direction_stats(cart, mrl_threshold=0.0)
    stats_image = vector_direction_stats(image, mrl_threshold=0.0)
    assert stats_image["mrl"] == pytest.approx(stats_cart["mrl"])
    assert stats_image["rayleigh_p"] == pytest.approx(stats_cart["rayleigh_p"])
    assert stats_image["mean_dir_deg"] == pytest.approx(-stats_cart["mean_dir_deg"])


def test_polar_export_records_orientation_and_angle_convention():
    row = build_polar_stats_export_row(
        file_name="a.csv", gate="All cells", region="All regions",
        angles=np.array([math.pi / 2]), mrl_threshold=0.5,
        x_ch1="x1", y_ch1="y1", x_ch2="x2", y_ch2="y2",
        y_coordinate_orientation=Y_ORIENTATION_IMAGE,
    )
    assert row["Y_Coordinate_Orientation"] == Y_ORIENTATION_IMAGE
    assert row["Angle_Convention"] == ANGLE_CONVENTION
    assert row["Mean_dir_deg"] == 90.0  # row records already-normalized angles


def test_polar_invalid_orientation_is_rejected_not_guessed():
    df = _coordinate_df()
    with pytest.raises(ValueError, match="Unsupported Y-coordinate orientation"):
        vectors_from_coordinate_columns(
            df, np.ones(len(df), bool), "x1", "y1", "x2", "y2",
            y_coordinate_orientation="auto_guess")


def test_scatter_cache_eviction_accepts_a2_parameterized_key():
    from vflow.core.cache_keys import scatter_cache_keys_for_gate_signature

    sig = 12345
    key = (
        1, "sample.csv", "X", "Y", "logicle_gml2", "linear", 5.0,
        (sig,), 3.0, 0.6, "#abcdef", False,
        (("A", 0.0), ("M", 4.5), ("T", 262144.0), ("W", 0.5)), (),
    )
    cache = {key: object()}
    assert scatter_cache_keys_for_gate_signature(cache, sig) == [key]


def test_render_cache_keys_encode_gml2_axis_parameters():
    source = Path("vflow/rendering/flow_renderer.py").read_text()
    assert "tuple(sorted(host.x_transform_params.items()))" in source
    assert "tuple(sorted(host.y_transform_params.items()))" in source
    # Scatter cache keeps the historical gate-signature slot and appends params.
    scatter_block = source[source.index("sc_key    ="):source.index("cached_scatter =", source.index("sc_key    ="))]
    assert scatter_block.index("gate_sigs") < scatter_block.index("host.x_transform_params")
    # Cold KDE precompute must query exactly the same parameterized context family.
    pre = source[source.index("def precompute_cold_kde_payloads"):source.index("def draw_region_labels")]
    assert pre.count("host.x_transform_params.items()") >= 2
    assert pre.count("host.y_transform_params.items()") >= 2


def test_matplotlib_gml2_scale_matches_core_transform_and_inverse():
    from vflow.core.scales import GatingMLLogicleScale

    params = {"T": 1_000_000.0, "W": 0.35, "M": 5.0, "A": 0.2}
    values = np.array([-500_000.0, -1000.0, -1.0, 0.0, 1.0, 1000.0, 500_000.0])
    scale = GatingMLLogicleScale(None, **params)
    mpl = scale.get_transform()
    expected = forward_transform(values, "logicle_gml2", transform_params=params)
    actual = mpl.transform_non_affine(values)
    assert np.allclose(actual, expected, rtol=0.0, atol=2e-12)
    restored = mpl.inverted().transform_non_affine(actual)
    assert np.allclose(restored, values, rtol=2e-11, atol=2e-8)


def test_gml2_gate_evaluation_uses_independent_x_and_y_parameters():
    x_params = {"T": 262144.0, "W": 0.3, "M": 4.5, "A": 0.0}
    y_params = {"T": 1_000_000.0, "W": 0.8, "M": 5.5, "A": 0.2}
    gate = {
        "id": 7, "name": "poly", "type": "polygon", "applied": True,
        "vertices": [(-5000.0, -8000.0), (100000.0, -5000.0),
                     (120000.0, 200000.0), (-3000.0, 170000.0)],
    }
    # Include events close to mapped polygon edges where swapping the axis-specific
    # parameter sets changes membership; these are deterministic stress points.
    x = np.array([70945.32506293792, 116191.87360689181, 101437.29196620878,
                  50000.0, 150000.0])
    y = np.array([198974.57937940545, 7313.405493366965, -2681.3803597149636,
                  100000.0, 300000.0])
    regions, _ = compute_gate_regions(
        gate, x, y,
        x_scale="logicle_gml2", y_scale="logicle_gml2", cofactor=150.0,
        x_transform_params=x_params, y_transform_params=y_params,
    )
    assert regions["IN"].dtype == bool
    assert len(regions["IN"]) == len(x)
    # Swapping parameter provenance is scientifically a different 2-D mapping;
    # the implementation must not collapse X/Y parameter sets to one global set.
    swapped, _ = compute_gate_regions(
        gate, x, y,
        x_scale="logicle_gml2", y_scale="logicle_gml2", cofactor=150.0,
        x_transform_params=y_params, y_transform_params=x_params,
    )
    # The exact test geometry was selected to cross at least one curved mapped edge.
    assert not np.array_equal(regions["IN"], swapped["IN"])


def test_v2_legacy_alias_migration_is_bit_identical_over_randomized_polygon_membership():
    rng = np.random.default_rng(4303)
    gate = {
        "id": 8, "name": "P", "type": "polygon", "applied": True,
        "vertices": [(-500, -300), (200, -800), (1500, 100),
                     (600, 1200), (-700, 700)],
    }
    x = rng.normal(0.0, 900.0, 3000)
    y = rng.normal(0.0, 900.0, 3000)
    old, _ = compute_gate_regions(
        gate, x, y, x_scale="logicle", y_scale="biexp", cofactor=73.0)
    explicit, _ = compute_gate_regions(
        gate, x, y, x_scale="legacy_logicle", y_scale="legacy_biexp", cofactor=73.0)
    assert np.array_equal(old["IN"], explicit["IN"])
    assert np.array_equal(old["OUT"], explicit["OUT"])
