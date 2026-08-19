from vflow.core.cache_keys import (
    evict_cache_keys,
    gate_mask_cache_keys_for_gate_ids,
    gate_signature,
    scatter_cache_keys_for_gate_signature,
)


class Flag:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def test_gate_signature_includes_threshold_toggles():
    gate = {
        "type": "crosshair",
        "x_boundaries": [1.0, 2.0],
        "x_thresh_vars": [Flag(True), Flag(True)],
        "y_boundary": None,
        "y_boundaries": None,
    }

    before = gate_signature(gate)
    gate["x_thresh_vars"][1].value = False

    assert gate_signature(gate) != before


def test_gate_signature_handles_none_y_boundaries():
    gate = {
        "type": "crosshair",
        "x_boundaries": [1.0],
        "x_thresh_active": [True],
        "y_boundary": None,
        "y_boundaries": None,
    }

    assert isinstance(gate_signature(gate), int)


def test_polygon_signature_rounds_vertices():
    gate_a = {"type": "polygon", "vertices": [(1.000000001, 2.0)]}
    gate_b = {"type": "polygon", "vertices": [(1.000000002, 2.0)]}

    assert gate_signature(gate_a) == gate_signature(gate_b)


def test_gate_mask_cache_keys_for_gate_ids():
    cache = {
        ("path-a", "x", "y", 1, "sig"): "a",
        ("path-b", "x", "y", 2, "sig"): "b",
        ("short", 1, 2): "ignored",
    }

    assert gate_mask_cache_keys_for_gate_ids(cache, {2, 3}) == [
        ("path-b", "x", "y", 2, "sig")
    ]



def test_gate_mask_cache_keys_for_gate_ids_current_generation_key_shape():
    current = (17, "sample.fcs", "X", "Y", "linear", "linear", 150.0, 42, 999)
    other = (17, "sample.fcs", "X", 42, "linear", "linear", 150.0, 7, 888)
    cache = {current: "target", other: "other"}

    assert gate_mask_cache_keys_for_gate_ids(cache, {42}) == [current]


def test_gate_mask_cache_keys_for_gate_ids_does_not_treat_y_channel_as_gate_id():
    key = (17, "sample.fcs", "X", 42, "linear", "linear", 150.0, 7, 888)
    assert gate_mask_cache_keys_for_gate_ids({key: "payload"}, {42}) == []

def test_scatter_cache_keys_for_gate_signature():
    cache = {
        ("path-a", "x", "y", (10, 20), 4, 0.5, "c", "overlay"): "a",
        ("path-b", "x", "y", (30,), 4, 0.5, "c", "overlay"): "b",
        ("short", 1, 2): "ignored",
    }

    assert scatter_cache_keys_for_gate_signature(cache, 20) == [
        ("path-a", "x", "y", (10, 20), 4, 0.5, "c", "overlay")
    ]



def test_scatter_cache_keys_for_gate_signature_current_generation_key_shape():
    current = (17, "sample.fcs", "X", "Y", "linear", "linear", 150.0, (10, 20), 4, 0.5, "c", False)
    other = (17, "sample.fcs", "X", "Y", "linear", "linear", 150.0, (30,), 4, 0.5, "c", False)
    cache = {current: "target", other: "other"}

    assert scatter_cache_keys_for_gate_signature(cache, 20) == [current]


def test_scatter_cache_keys_for_gate_signature_does_not_treat_y_channel_as_signature_tuple():
    key = (17, "sample.fcs", "X", (10, 20), "linear", "linear", 150.0, (30,), 4, 0.5, "c", False)
    assert scatter_cache_keys_for_gate_signature({key: "payload"}, 20) == []

def test_evict_cache_keys_returns_removed_count():
    cache = {"a": 1, "b": 2}

    assert evict_cache_keys(cache, ["a", "missing", "a"]) == 1
    assert cache == {"b": 2}
