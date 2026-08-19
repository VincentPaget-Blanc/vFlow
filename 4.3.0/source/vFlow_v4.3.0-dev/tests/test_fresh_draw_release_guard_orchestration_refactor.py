import inspect

import pytest

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.legacy.vflow_app import FlowApp
from vflow.services.gate_geometry_interaction import (
    FreshDrawReleaseGuard,
    resolve_fresh_draw_release_guard,
)


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


class SequenceGetter:
    def __init__(self, label, values, log):
        self.label = label
        self.values = list(values)
        self.log = log
        self.index = 0

    def __call__(self):
        idx = self.index
        self.index += 1
        self.log.append(("get", self.label, idx))
        value = self.values[idx] if idx < len(self.values) else self.values[-1]
        if isinstance(value, BaseException):
            raise value
        return value


def _guard(gate_values, x_values, y_values, log):
    return resolve_fresh_draw_release_guard(
        get_gate=SequenceGetter("gate", gate_values, log),
        get_x_coord=SequenceGetter("x", x_values, log),
        get_y_coord=SequenceGetter("y", y_values, log),
    )


def test_falsey_gate_short_circuits_all_coordinate_reads():
    log = []
    gate = TruthValue("gate", False, log)
    result = _guard([gate], [AssertionError("x should not run")], [AssertionError("y should not run")], log)
    assert result == FreshDrawReleaseGuard(gate=gate, should_discard=True)
    assert log == [("get", "gate", 0), ("bool", "gate")]


def test_missing_first_x_short_circuits_y_and_marks_discard():
    log = []
    gate = TruthValue("gate", True, log)
    result = _guard([gate], [None], [AssertionError("y should not run")], log)
    assert result == FreshDrawReleaseGuard(gate=gate, should_discard=True)
    assert log == [
        ("get", "gate", 0), ("bool", "gate"),
        ("get", "x", 0),
    ]


def test_missing_first_y_reads_x_then_y_once_and_marks_discard():
    log = []
    gate = TruthValue("gate", True, log)
    result = _guard([gate], [1.25], [None], log)
    assert result == FreshDrawReleaseGuard(gate=gate, should_discard=True)
    assert log == [
        ("get", "gate", 0), ("bool", "gate"),
        ("get", "x", 0), ("get", "y", 0),
    ]


def test_success_repeats_x_then_y_and_returns_second_reads():
    log = []
    gate = TruthValue("gate", True, log)
    result = _guard([gate], [1.0, 10.0], [2.0, 20.0], log)
    assert result == FreshDrawReleaseGuard(
        gate=gate,
        should_discard=False,
        x=10.0,
        y=20.0,
    )
    assert log == [
        ("get", "gate", 0), ("bool", "gate"),
        ("get", "x", 0), ("get", "y", 0),
        ("get", "x", 1), ("get", "y", 1),
    ]


def test_gate_getter_failure_propagates_before_truth_test_or_coordinates():
    log = []
    with pytest.raises(RuntimeError, match="gate-fail"):
        _guard([RuntimeError("gate-fail")], [1.0], [2.0], log)
    assert log == [("get", "gate", 0)]


def test_gate_truthiness_failure_propagates_before_coordinates():
    log = []
    gate = TruthValue("gate", RuntimeError("gate-bool-fail"), log)
    with pytest.raises(RuntimeError, match="gate-bool-fail"):
        _guard([gate], [1.0], [2.0], log)
    assert log == [("get", "gate", 0), ("bool", "gate")]


@pytest.mark.parametrize(
    "x_values,y_values,message,expected",
    [
        ([RuntimeError("x0-fail")], [2.0], "x0-fail", [("get", "x", 0)]),
        ([1.0], [RuntimeError("y0-fail")], "y0-fail", [("get", "x", 0), ("get", "y", 0)]),
        ([1.0, RuntimeError("x1-fail")], [2.0, 20.0], "x1-fail", [("get", "x", 0), ("get", "y", 0), ("get", "x", 1)]),
        ([1.0, 10.0], [2.0, RuntimeError("y1-fail")], "y1-fail", [("get", "x", 0), ("get", "y", 0), ("get", "x", 1), ("get", "y", 1)]),
    ],
)
def test_coordinate_failures_preserve_exact_cutoff_order(x_values, y_values, message, expected):
    log = []
    gate = TruthValue("gate", True, log)
    with pytest.raises(RuntimeError, match=message):
        _guard([gate], x_values, y_values, log)
    assert log == [("get", "gate", 0), ("bool", "gate"), *expected]


def test_flowapp_retains_discard_type_geometry_tk_and_finalization_authority():
    source = inspect.getsource(GateInteractionController.on_release)
    assert "resolve_fresh_draw_release_guard" in source
    assert "event.xdata" in source and "event.ydata" in source
    assert "run_fresh_draw_discard_side_effect_sequence" in source
    assert "gate.get('applied')" in source
    assert "gate['id']" in source
    assert "_del_gate" in source
    assert "gate.get('type', 'crosshair')" in source
    assert "iter_gate_draw_assignments" in source
    assert "manual_crosshair_threshold_plan" in source
    assert "tk.BooleanVar" in source
    assert "is_degenerate_shape_gate" in source
    assert "gate['applied']" in source
    assert "_draw_gate_id" in source
    assert "_end_blit_drag" in source
    assert "_finish_gate" in source


def test_guard_helper_does_not_absorb_release_side_effects_or_gate_type_dispatch():
    source = inspect.getsource(resolve_fresh_draw_release_guard)
    forbidden = [
        "_end_blit_drag", "_del_gate", "_finish_gate", "BooleanVar",
        "iter_gate_draw_assignments", "is_degenerate_shape_gate", "applied",
        "get('type'", "_draw_gate_id", "event.", "gate[",
    ]
    for token in forbidden:
        assert token not in source
