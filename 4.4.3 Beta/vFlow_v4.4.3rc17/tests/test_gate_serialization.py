import pytest

from vflow.core.gate_serialization import (
    gate_channel_mismatch_message,
    gate_from_json_dict,
    gate_load_message,
    gate_load_status,
    gate_save_message,
    gate_save_status,
    gates_to_json_payload,
    next_free_gate_id,
    sanitize_raw_gates,
    safe_vertices,
    validate_raw_gate,
    gate_to_json_dict,
)


class Flag:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def test_gate_to_json_preserves_zero_y_boundary():
    raw = gate_to_json_dict(
        {
            "type": "crosshair",
            "y_boundary": 0.0,
            "y_thresh_var": Flag(True),
        }
    )

    assert raw["y_boundary"] == 0.0
    assert raw["y_thresh_active"] is True


def test_gates_to_json_payload_preserves_channels_and_schema():
    payload = gates_to_json_payload(
        [{"name": "Gate A", "type": "crosshair"}],
        "FSC A",
        "SSC A",
    )

    assert payload["version"] == 1
    assert payload["x_channel"] == "FSC A"
    assert payload["y_channel"] == "SSC A"
    assert payload["gates"][0]["name"] == "Gate A"


def test_gate_save_and_load_messages():
    assert gate_save_status("/tmp/gates.json", 2) == (
        "\u2713 2 gate(s) saved \u2192 gates.json"
    )
    assert gate_save_message("/tmp/gates.json", 2, "X", "Y") == (
        "2 gate(s) saved to:\n/tmp/gates.json\n\n"
        "Channels at save time:\n  X: X\n  Y: Y"
    )
    assert gate_load_status("/tmp/gates.json", 2, 1) == (
        "\u2713 2 gate(s) loaded from gates.json  "
        "(1 malformed gate(s) skipped)"
    )
    assert gate_load_message("/tmp/gates.json", 2, 1) == (
        "2 gate(s) loaded from:\n/tmp/gates.json\n\n"
        "\u26a0 1 malformed gate(s) skipped."
    )


def test_gate_channel_mismatch_message():
    msg = gate_channel_mismatch_message(
        saved_x="A",
        saved_y="B",
        current_x="C",
        current_y="D",
    )

    assert "Saved with:   X='A'  Y='B'" in msg
    assert "Current axes: X='C'  Y='D'" in msg
    assert msg.endswith("Load anyway? (Gate positions will be wrong if channels differ.)")


def test_safe_vertices_drops_malformed_entries():
    assert safe_vertices([["a", "b"], [1, 2], [3, float("inf")], [4]]) == [
        (1.0, 2.0)
    ]


def test_applied_polygon_without_valid_vertices_is_rejected():
    assert validate_raw_gate(
        {"type": "polygon", "applied": True, "vertices": [["x", "y"]]}
    ) is False


def test_missing_gate_ids_get_unique_ids():
    raw_gates = [{"id": 7}, {"name": "A"}, {"name": "B"}]
    next_id = next_free_gate_id(raw_gates, current_next_id=3)

    gate_a, next_id = gate_from_json_dict(raw_gates[1], next_id)
    gate_b, next_id = gate_from_json_dict(raw_gates[2], next_id)

    assert gate_a["id"] == 8
    assert gate_b["id"] == 9
    assert next_id == 10


def test_sanitize_raw_gates_assigns_ids_and_counts_skipped():
    gates, next_id, skipped = sanitize_raw_gates(
        [
            {"id": 5, "name": "Existing"},
            {"name": "Missing"},
            {"type": "polygon", "applied": True, "vertices": [["bad", "bad"]]},
            "not a gate",
        ],
        current_next_id=3,
    )

    assert [gate["id"] for gate in gates] == [5, 6]
    assert [gate["name"] for gate in gates] == ["Existing", "Missing"]
    assert next_id == 7
    assert skipped == 2


def test_inactive_gate_with_malformed_geometry_is_rejected_not_sanitized():
    raw = {
        "name": "Loaded",
        "type": "crosshair",
        "applied": False,
        "x_boundaries": ["1", "bad", 2],
        "y_boundary": "0",
        "x_thresh_active": [True, True, False],
    }
    assert validate_raw_gate(raw) is False
    gate, next_id = gate_from_json_dict(raw, 4)
    assert gate is None
    assert next_id == 4


def test_inactive_partial_finite_polygon_round_trips_without_geometry_loss():
    raw = {
        "name": "Draft", "type": "polygon", "applied": False,
        "vertices": [[1, 2], [3, 4]],
    }
    assert validate_raw_gate(raw) is True
    gate, _ = gate_from_json_dict(raw, 0)
    assert gate["vertices"] == [(1.0, 2.0), (3.0, 4.0)]


def test_inactive_rectangle_rejects_nonfinite_or_partial_serialized_geometry():
    assert validate_raw_gate({
        "type": "rectangle", "applied": False,
        "x0": 0, "y0": 0, "x1": "nan", "y1": 1,
    }) is False
    assert validate_raw_gate({
        "type": "rectangle", "applied": False, "x0": 0,
    }) is False
    # Historical entirely-blank inactive placeholder remains supported.
    assert validate_raw_gate({"type": "rectangle", "applied": False}) is True


def test_gate_from_json_dict_parses_string_booleans_without_truthiness_inversion():
    gate, _ = gate_from_json_dict(
        {
            "type": "crosshair",
            "applied": "true",
            "x_boundaries": [1.0],
            "x_thresh_active": ["false"],
            "y_boundary": 2.0,
            "y_thresh_active": "false",
            "y_thresh_actives": ["true", "0"],
        },
        0,
    )
    assert gate is not None
    assert gate["applied"] is True
    assert gate["x_thresh_active"] == [False]
    assert gate["y_thresh_active"] is False
    assert gate["y_thresh_actives"] == [True, False]


def test_validate_raw_gate_treats_serialized_false_as_not_applied():
    assert validate_raw_gate({"type": "polygon", "applied": "false", "vertices": []}) is True


def test_sanitize_repairs_duplicate_explicit_gate_ids():
    gates, next_id, skipped = sanitize_raw_gates([
        {"id": 2, "name": "A"}, {"id": 2, "name": "B"}
    ])
    assert skipped == 0
    assert len({g["id"] for g in gates}) == 2
    assert gates[0]["id"] == 2
    assert gates[1]["id"] >= 3

def test_applied_degenerate_shapes_and_unknown_types_are_rejected():
    assert validate_raw_gate({"type": "rectangle", "applied": True, "x0": 1, "x1": 1, "y0": 0, "y1": 2}) is False
    assert validate_raw_gate({"type": "mystery", "applied": True}) is False
    assert validate_raw_gate({"type": "crosshair", "applied": True}) is False


def test_applied_polygon_with_malformed_vertex_is_rejected_not_reshaped():
    raw = {
        "type": "polygon",
        "applied": True,
        "vertices": [[0, 0], [1, 0], ["bad", 1], [0, 1]],
    }
    assert validate_raw_gate(raw) is False
    gate, _ = gate_from_json_dict(raw, 0)
    assert gate is None


def test_applied_crosshair_with_malformed_threshold_is_rejected_not_shrunk():
    raw = {
        "type": "crosshair",
        "applied": True,
        "x_boundaries": [1.0, "bad", 3.0],
        "x_thresh_active": [True, True, True],
    }
    assert validate_raw_gate(raw) is False
    gate, _ = gate_from_json_dict(raw, 0)
    assert gate is None


def test_applied_crosshair_rejects_threshold_flag_length_mismatch():
    raw = {
        "type": "crosshair",
        "applied": True,
        "x_boundaries": [1.0, 3.0],
        "x_thresh_active": [False],
    }
    assert validate_raw_gate(raw) is False


def test_gate_to_json_rejects_nonfinite_inactive_geometry_instead_of_writing_nan():
    gate = {
        "id": 7, "name": "Bad draft", "type": "rectangle", "applied": False,
        "x0": 0.0, "y0": 0.0, "x1": float("nan"), "y1": 1.0,
        "x_thresh_vars": [], "y_thresh_var": None, "y_thresh_vars": [],
    }
    with pytest.raises(ValueError, match="cannot be serialized losslessly"):
        gate_to_json_dict(gate)
