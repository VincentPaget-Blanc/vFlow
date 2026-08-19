import ast
import inspect

import pytest

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.legacy.vflow_app import FlowApp
from vflow.services import gate_geometry_interaction as service
from vflow.services.gate_geometry_interaction import resolve_release_interaction_path


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


def _getter(label, value, log):
    def get():
        log.append(("get", label))
        if isinstance(value, BaseException):
            raise value
        return value
    return get


def test_release_path_service_is_tk_and_matplotlib_free():
    src = inspect.getsource(service)
    tree = ast.parse(src)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert not any(name.startswith("tkinter") for name in imports)
    assert not any(name.startswith("matplotlib") for name in imports)


def test_handle_drag_has_first_priority_and_short_circuits_later_sources():
    log = []
    out = resolve_release_interaction_path(
        get_handle_drag=_getter("drag", TruthValue("drag", True, log), log),
        get_gate_move=_getter("move", AssertionError("move should not run"), log),
        get_moving_gate=_getter("moving", AssertionError("moving should not run"), log),
    )
    assert out == "handle_drag"
    assert log == [("get", "drag"), ("bool", "drag")]


def test_gate_move_runs_only_after_falsey_handle_drag():
    log = []
    out = resolve_release_interaction_path(
        get_handle_drag=_getter("drag", TruthValue("drag", False, log), log),
        get_gate_move=_getter("move", TruthValue("move", True, log), log),
        get_moving_gate=_getter("moving", AssertionError("moving should not run"), log),
    )
    assert out == "gate_move"
    assert log == [
        ("get", "drag"), ("bool", "drag"),
        ("get", "move"), ("bool", "move"),
    ]


@pytest.mark.parametrize("moving, expected", [(False, "inactive"), (True, "fresh_draw")])
def test_final_moving_gate_truth_test_preserves_release_path(moving, expected):
    log = []
    out = resolve_release_interaction_path(
        get_handle_drag=_getter("drag", None, log),
        get_gate_move=_getter("move", None, log),
        get_moving_gate=_getter("moving", TruthValue("moving", moving, log), log),
    )
    assert out == expected
    assert log == [
        ("get", "drag"),
        ("get", "move"),
        ("get", "moving"), ("bool", "moving"),
    ]


@pytest.mark.parametrize("failing", ["drag", "move", "moving"])
def test_source_and_truthiness_failures_cut_off_later_release_reads(failing):
    log = []
    boom = RuntimeError(f"{failing}-fail")
    drag = boom if failing == "drag" else None
    move = boom if failing == "move" else None
    moving = boom if failing == "moving" else True
    with pytest.raises(RuntimeError, match=f"{failing}-fail"):
        resolve_release_interaction_path(
            get_handle_drag=_getter("drag", drag, log),
            get_gate_move=_getter("move", move, log),
            get_moving_gate=_getter("moving", moving, log),
        )
    labels = [item[1] for item in log if item[0] == "get"]
    expected = {
        "drag": ["drag"],
        "move": ["drag", "move"],
        "moving": ["drag", "move", "moving"],
    }[failing]
    assert labels == expected


def test_truth_test_exception_propagates_without_normalization():
    log = []
    boom = RuntimeError("bool-fail")
    with pytest.raises(RuntimeError, match="bool-fail"):
        resolve_release_interaction_path(
            get_handle_drag=_getter("drag", TruthValue("drag", boom, log), log),
            get_gate_move=_getter("move", None, log),
            get_moving_gate=_getter("moving", True, log),
        )
    assert log == [("get", "drag"), ("bool", "drag")]


def test_flowapp_release_keeps_all_concrete_authorities_in_controller():
    source = inspect.getsource(GateInteractionController.on_release)
    assert "resolve_release_interaction_path" in source
    assert "gate_by_id" in source
    assert "iter_gate_draw_assignments" in source
    assert "manual_crosshair_threshold_plan" in source
    assert "tk.BooleanVar" in source
    assert "is_degenerate_shape_gate" in source
    assert "_end_blit_drag" in source
    assert "_del_gate" in source
    assert "_finish_gate" in source
    assert "event.xdata" in source and "event.ydata" in source


def test_release_path_helper_does_not_absorb_release_side_effects():
    source = inspect.getsource(resolve_release_interaction_path)
    forbidden = [
        "gate_by_id", "BooleanVar", "iter_gate_draw_assignments",
        "is_degenerate_shape_gate", "_end_blit_drag", "_finish_gate",
        "_del_gate", "xdata", "ydata", "gate[",
    ]
    for token in forbidden:
        assert token not in source
