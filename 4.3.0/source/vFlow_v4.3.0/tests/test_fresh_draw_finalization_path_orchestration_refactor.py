import inspect

import pytest

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.legacy.vflow_app import FlowApp
from vflow.services.gate_geometry_interaction import resolve_fresh_draw_finalization_path


class TruthValue:
    def __init__(self, label, result, log):
        self.label = label
        self.result = result
        self.log = log

    def __bool__(self):
        self.log.append(("bool", self.label))
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class TypeProbe:
    def __init__(self, outcomes, log):
        self.outcomes = dict(outcomes)
        self.log = log

    def __eq__(self, other):
        self.log.append(("eq", other))
        outcome = self.outcomes.get(other, False)
        if isinstance(outcome, BaseException):
            raise outcome
        if isinstance(outcome, tuple) and outcome[0] == "truth":
            return TruthValue(f"eq-{other}", outcome[1], self.log)
        return outcome


class Getter:
    def __init__(self, value, log):
        self.value = value
        self.log = log
        self.calls = 0

    def __call__(self):
        self.log.append(("get_type", self.calls))
        self.calls += 1
        if isinstance(self.value, BaseException):
            raise self.value
        return self.value


@pytest.mark.parametrize(
    "gate_type, expected",
    [
        ("crosshair", "crosshair"),
        ("rectangle", "shape"),
        ("ellipse", "shape"),
        ("polygon", "deferred"),
        ("mystery", "deferred"),
        (None, "deferred"),
        (0, "deferred"),
    ],
)
def test_plain_gate_types_preserve_frozen_branch_selection(gate_type, expected):
    log = []
    getter = Getter(gate_type, log)
    assert resolve_fresh_draw_finalization_path(get_gate_type=getter) == expected
    assert log == [("get_type", 0)]
    assert getter.calls == 1


def test_custom_equality_preserves_crosshair_then_rectangle_order():
    log = []
    value = TypeProbe(
        {"crosshair": ("truth", False), "rectangle": ("truth", True)},
        log,
    )
    assert resolve_fresh_draw_finalization_path(get_gate_type=Getter(value, log)) == "shape"
    assert log == [
        ("get_type", 0),
        ("eq", "crosshair"),
        ("bool", "eq-crosshair"),
        ("eq", "rectangle"),
        ("bool", "eq-rectangle"),
    ]


def test_custom_equality_reaches_ellipse_only_after_rectangle_is_false():
    log = []
    value = TypeProbe(
        {"crosshair": False, "rectangle": False, "ellipse": True},
        log,
    )
    assert resolve_fresh_draw_finalization_path(get_gate_type=Getter(value, log)) == "shape"
    assert log == [
        ("get_type", 0),
        ("eq", "crosshair"),
        ("eq", "rectangle"),
        ("eq", "ellipse"),
    ]


def test_type_getter_failure_propagates_before_any_comparison():
    log = []
    with pytest.raises(RuntimeError, match="type-get-fail"):
        resolve_fresh_draw_finalization_path(
            get_gate_type=Getter(RuntimeError("type-get-fail"), log)
        )
    assert log == [("get_type", 0)]


def test_crosshair_comparison_failure_preserves_cutoff():
    log = []
    value = TypeProbe({"crosshair": RuntimeError("cross-eq-fail")}, log)
    with pytest.raises(RuntimeError, match="cross-eq-fail"):
        resolve_fresh_draw_finalization_path(get_gate_type=Getter(value, log))
    assert log == [("get_type", 0), ("eq", "crosshair")]


def test_comparison_truth_test_failure_preserves_cutoff():
    log = []
    value = TypeProbe(
        {"crosshair": ("truth", RuntimeError("cross-bool-fail"))},
        log,
    )
    with pytest.raises(RuntimeError, match="cross-bool-fail"):
        resolve_fresh_draw_finalization_path(get_gate_type=Getter(value, log))
    assert log == [
        ("get_type", 0),
        ("eq", "crosshair"),
        ("bool", "eq-crosshair"),
    ]


def test_flowapp_retains_concrete_type_lookup_and_all_finalization_side_effects():
    source = inspect.getsource(GateInteractionController.on_release)
    assert "resolve_fresh_draw_finalization_path" in source
    assert "gate.get('type', 'crosshair')" in source
    assert "iter_gate_draw_assignments" in source
    assert "manual_crosshair_threshold_plan" in source
    assert "tk.BooleanVar" in source
    assert "is_degenerate_shape_gate" in source
    assert "gate['applied']" in source
    assert "_del_gate" in source
    assert "_draw_gate_id" in source
    assert "_end_blit_drag" in source
    assert "_finish_gate" in source
    assert "return  # polygon finishes via _poly_finish" in source


def test_finalization_path_helper_does_not_absorb_gate_mutation_or_controller_state():
    source = inspect.getsource(resolve_fresh_draw_finalization_path)
    forbidden = [
        "gate.get", "gate[", "BooleanVar", "iter_gate_draw_assignments",
        "is_degenerate_shape_gate", "_del_gate", "_draw_gate_id",
        "_end_blit_drag", "_finish_gate", "event.", "applied",
    ]
    for token in forbidden:
        assert token not in source
