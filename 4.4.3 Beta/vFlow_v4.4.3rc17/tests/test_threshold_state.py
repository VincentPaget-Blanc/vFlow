import pytest

np = pytest.importorskip("numpy")

from vflow.core.cache_keys import gate_signature
from vflow.core.gate_masks import compute_gate_regions
from vflow.core.gate_serialization import gate_to_json_dict
from vflow.core.gate_stats import stats_from_regions
from vflow.core.gates import active_x_boundaries, active_y_boundaries
from vflow.core.threshold_state import (
    ThresholdSchemaError,
    ThresholdState,
    flag_value,
    multi_y_threshold_flags,
    serialized_threshold_flags,
    single_y_threshold_flag,
    x_threshold_flags,
)


class Flag:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class ExplodingFlag:
    def get(self):
        raise RuntimeError("flag read failed")


def _live_gate():
    return {
        "id": 7,
        "name": "Threshold gate",
        "type": "crosshair",
        "applied": True,
        "color": "#123456",
        "x_boundaries": [1.0, 3.0],
        "x_thresh_vars": [Flag(True), Flag(False)],
        "y_boundary": None,
        "y_thresh_var": None,
        "y_boundaries": [2.0, 4.0],
        "y_thresh_vars": [Flag(False), Flag(True)],
    }


def _plain_equivalent_gate():
    return {
        "id": 7,
        "name": "Threshold gate",
        "type": "crosshair",
        "applied": True,
        "color": "#123456",
        "x_boundaries": [1.0, 3.0],
        "x_thresh_active": [True, False],
        "y_boundary": None,
        "y_thresh_active": True,
        "y_boundaries": [2.0, 4.0],
        "y_thresh_actives": [False, True],
    }


def test_threshold_state_snapshots_live_flags_without_tk_dependency():
    state = ThresholdState.from_gate(_live_gate())

    assert state.x_flags == (True, False)
    assert state.y_flag is True
    assert state.y_flags == (False, True)
    assert state.active_x([1.0, 3.0]) == [1.0]
    assert state.active_y(None, [2.0, 4.0]) == [4.0]


def test_activity_projection_matches_serialized_aliases():
    live = _live_gate()
    plain = _plain_equivalent_gate()

    assert x_threshold_flags(live) == x_threshold_flags(plain) == (True, False)
    assert multi_y_threshold_flags(live) == multi_y_threshold_flags(plain) == (False, True)
    assert active_x_boundaries(live) == active_x_boundaries(plain) == [1.0]
    assert active_y_boundaries(live) == active_y_boundaries(plain) == [4.0]


def test_live_threshold_lists_take_precedence_when_nonempty():
    gate = _plain_equivalent_gate()
    gate["x_thresh_vars"] = [Flag(False), Flag(True)]
    gate["y_thresh_vars"] = [Flag(True), Flag(False)]

    assert x_threshold_flags(gate) == (False, True)
    assert multi_y_threshold_flags(gate) == (True, False)
    assert active_x_boundaries(gate) == [3.0]
    assert active_y_boundaries(gate) == [2.0]


def test_empty_live_lists_preserve_legacy_alias_fallback():
    gate = _plain_equivalent_gate()
    gate["x_thresh_vars"] = []
    gate["y_thresh_vars"] = []

    assert x_threshold_flags(gate) == (True, False)
    assert multi_y_threshold_flags(gate) == (False, True)


def test_activity_length_mismatch_enables_all_boundaries():
    gate = _live_gate()
    gate["x_thresh_vars"] = [Flag(False)]
    gate["y_thresh_vars"] = [Flag(False)]

    assert active_x_boundaries(gate) == [1.0, 3.0]
    assert active_y_boundaries(gate) == [2.0, 4.0]


def test_scalar_y_alias_default_and_false_are_preserved():
    default_gate = {
        "type": "crosshair",
        "y_boundary": 0.0,
        "y_boundaries": None,
    }
    false_gate = dict(default_gate, y_thresh_active=False)

    assert single_y_threshold_flag(default_gate) is True
    assert active_y_boundaries(default_gate) == [0.0]
    assert single_y_threshold_flag(false_gate) is False
    assert active_y_boundaries(false_gate) == []


def test_serialization_projection_intentionally_does_not_use_alias_fallbacks():
    gate = {
        "type": "crosshair",
        "x_thresh_active": [True, False],
        "y_thresh_active": False,
        "y_thresh_actives": [False, True],
    }

    flags = serialized_threshold_flags(gate)
    raw = gate_to_json_dict(gate)

    assert flags.x_active == ()
    assert flags.y_active is True
    assert flags.y_actives == ()
    assert raw["x_thresh_active"] == []
    assert raw["y_thresh_active"] is True
    assert raw["y_thresh_actives"] == []


def test_serialization_projection_reports_explicit_none_list_as_schema_error():
    with pytest.raises(ThresholdSchemaError, match="x_thresh_vars.*got None"):
        serialized_threshold_flags({"x_thresh_vars": None})
    with pytest.raises(ThresholdSchemaError, match="Gate '<unnamed>'.*x_thresh_vars.*got None"):
        gate_to_json_dict({"x_thresh_vars": None})


def test_flag_getter_exceptions_are_wrapped_with_threshold_context():
    with pytest.raises(ThresholdSchemaError, match=r"threshold flag.*get\(\).*flag read failed"):
        flag_value(ExplodingFlag())
    with pytest.raises(ThresholdSchemaError, match=r"x_thresh_vars/x_thresh_active\[0\].*flag read failed"):
        active_x_boundaries({
            "type": "crosshair",
            "x_boundaries": [1.0],
            "x_thresh_vars": [ExplodingFlag()],
        })


def test_live_and_plain_thresholds_have_same_gate_signature_masks_and_stats():
    live = _live_gate()
    plain = _plain_equivalent_gate()
    x = np.array([0.0, 1.5, 2.5, 3.5, 5.0, np.nan], dtype=float)
    y = np.array([1.0, 3.0, 5.0, 1.0, 5.0, 2.0], dtype=float)

    assert gate_signature(live) == gate_signature(plain)

    live_regions, live_colors = compute_gate_regions(
        live, x, y,
        x_scale="linear", y_scale="linear", cofactor=150.0,
        x_channel="X", y_channel="Y",
    )
    plain_regions, plain_colors = compute_gate_regions(
        plain, x, y,
        x_scale="linear", y_scale="linear", cofactor=150.0,
        x_channel="X", y_channel="Y",
    )

    assert live_colors == plain_colors
    assert list(live_regions) == list(plain_regions)
    for name in live_regions:
        assert np.array_equal(live_regions[name], plain_regions[name])

    total = int(np.isfinite(x).sum())
    assert stats_from_regions(live_regions, total) == stats_from_regions(plain_regions, total)
