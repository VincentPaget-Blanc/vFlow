import inspect

import pytest

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.legacy.vflow_app import FlowApp
from vflow.services.gate_geometry_interaction import (
    resolve_fresh_draw_release_guard,
    run_fresh_draw_discard_side_effect_sequence,
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


class GateId:
    pass


def _callbacks(*, gate_truth=True, applied_truth=False, fail=None,
               gate_bool_fail=None, applied_bool_fail=None):
    log = []
    gate = TruthValue(
        "gate",
        gate_bool_fail if gate_bool_fail is not None else gate_truth,
        log,
    )
    applied = TruthValue(
        "applied",
        applied_bool_fail if applied_bool_fail is not None else applied_truth,
        log,
    )
    gate_id = GateId()

    def step(name, result=None):
        def call(*args):
            log.append((name, *args))
            if fail == name:
                raise RuntimeError(f"{name}-fail")
            return result
        return call

    callbacks = {
        "end_render_snapshot": step("end_render"),
        "get_gate_for_truth_test": step("gate", gate),
        "get_applied": step("applied", applied),
        "get_gate_id": step("gate_id", gate_id),
        "delete_gate": step("delete"),
    }
    return log, gate_id, callbacks


def test_discard_sequence_falsey_gate_stops_after_second_gate_truth_test():
    log, _gate_id, callbacks = _callbacks(gate_truth=False)
    run_fresh_draw_discard_side_effect_sequence(**callbacks)
    assert log == [
        ("end_render",),
        ("gate",),
        ("bool", "gate"),
    ]


def test_discard_sequence_truthy_applied_gate_is_not_deleted():
    log, _gate_id, callbacks = _callbacks(gate_truth=True, applied_truth=True)
    run_fresh_draw_discard_side_effect_sequence(**callbacks)
    assert log == [
        ("end_render",),
        ("gate",),
        ("bool", "gate"),
        ("applied",),
        ("bool", "applied"),
    ]


def test_discard_sequence_unapplied_gate_resolves_id_then_deletes_with_identity():
    log, gate_id, callbacks = _callbacks(gate_truth=True, applied_truth=False)
    run_fresh_draw_discard_side_effect_sequence(**callbacks)
    assert log == [
        ("end_render",),
        ("gate",),
        ("bool", "gate"),
        ("applied",),
        ("bool", "applied"),
        ("gate_id",),
        ("delete", gate_id),
    ]


@pytest.mark.parametrize(
    "fail,expected_names",
    [
        ("end_render", ["end_render"]),
        ("gate", ["end_render", "gate"]),
        ("applied", ["end_render", "gate", "applied"]),
        ("gate_id", ["end_render", "gate", "applied", "gate_id"]),
        ("delete", ["end_render", "gate", "applied", "gate_id", "delete"]),
    ],
)
def test_discard_sequence_callback_failures_preserve_exact_cutoff(fail, expected_names):
    log, _gate_id, callbacks = _callbacks(
        gate_truth=True,
        applied_truth=False,
        fail=fail,
    )
    with pytest.raises(RuntimeError, match=rf"^{fail}-fail$"):
        run_fresh_draw_discard_side_effect_sequence(**callbacks)
    assert [entry[0] for entry in log if entry[0] != "bool"] == expected_names


def test_discard_sequence_gate_truth_failure_occurs_after_render_teardown():
    log, _gate_id, callbacks = _callbacks(
        gate_bool_fail=RuntimeError("gate-bool-fail")
    )
    with pytest.raises(RuntimeError, match="^gate-bool-fail$"):
        run_fresh_draw_discard_side_effect_sequence(**callbacks)
    assert log == [
        ("end_render",),
        ("gate",),
        ("bool", "gate"),
    ]


def test_discard_sequence_applied_truth_failure_occurs_before_id_lookup():
    log, _gate_id, callbacks = _callbacks(
        gate_truth=True,
        applied_bool_fail=RuntimeError("applied-bool-fail"),
    )
    with pytest.raises(RuntimeError, match="^applied-bool-fail$"):
        run_fresh_draw_discard_side_effect_sequence(**callbacks)
    assert log == [
        ("end_render",),
        ("gate",),
        ("bool", "gate"),
        ("applied",),
        ("bool", "applied"),
    ]


def test_flowapp_keeps_concrete_discard_gate_access_and_deletion_controller_owned():
    source = inspect.getsource(GateInteractionController.on_release)
    discard = source[source.index("if release_guard.should_discard:"):source.index("x, y = release_guard.x")]
    assert "run_fresh_draw_discard_side_effect_sequence" in discard
    assert "end_render_snapshot=host._end_blit_drag" in discard
    assert "get_gate_for_truth_test=lambda: gate" in discard
    assert "get_applied=lambda: gate.get('applied')" in discard
    assert "get_gate_id=lambda: gate['id']" in discard
    assert "delete_gate=host._del_gate" in discard


def test_discard_sequence_remains_separate_from_release_guard():
    guard_source = inspect.getsource(resolve_fresh_draw_release_guard)
    discard_source = inspect.getsource(run_fresh_draw_discard_side_effect_sequence)
    assert "should_discard" in guard_source
    assert "end_render_snapshot" not in guard_source
    assert "end_render_snapshot" in discard_source
    assert "get_x_coord" not in discard_source
    assert "get_y_coord" not in discard_source


def test_discard_helper_does_not_absorb_concrete_controller_authority():
    source = inspect.getsource(run_fresh_draw_discard_side_effect_sequence)
    forbidden = [
        "self.", "gate.get", "gate[", "_end_blit_drag", "_del_gate",
        "_finish_gate", "event.", "BooleanVar", "iter_gate_draw_assignments",
        "is_degenerate_shape_gate", "_draw_gate_id",
    ]
    for token in forbidden:
        assert token not in source
