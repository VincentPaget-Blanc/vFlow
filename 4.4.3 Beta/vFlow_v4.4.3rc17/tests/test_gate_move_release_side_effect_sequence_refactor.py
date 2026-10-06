import inspect

import pytest

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.legacy.vflow_app import FlowApp
from vflow.services.gate_geometry_interaction import (
    resolve_release_interaction_path,
    run_gate_move_release_side_effect_sequence,
)


def _callbacks(*, gate=None, fail=None):
    log = []
    if gate is None:
        gate = object()

    def step(name, result=None):
        def call(*args):
            log.append((name, *args))
            if fail == name:
                raise RuntimeError(f"{name}-fail")
            return result
        return call

    callbacks = {
        "resolve_gate": step("resolve_gate", gate),
        "clear_gate_move": step("clear_gate_move"),
        "clear_interior_hover_gate_id": step("clear_interior_hover_gate_id"),
        "clear_frozen_xlim": step("clear_frozen_xlim"),
        "clear_frozen_ylim": step("clear_frozen_ylim"),
        "end_render_snapshot": step("end_render"),
        "finish_gate": step("finish_gate"),
    }
    return log, gate, callbacks


def test_gate_move_sequence_preserves_exact_order_and_gate_identity():
    log, gate, callbacks = _callbacks()
    run_gate_move_release_side_effect_sequence(**callbacks)
    assert log == [
        ("resolve_gate",),
        ("clear_gate_move",),
        ("clear_interior_hover_gate_id",),
        ("clear_frozen_xlim",),
        ("clear_frozen_ylim",),
        ("end_render",),
        ("finish_gate", gate),
    ]


def test_gate_move_sequence_finalizes_none_unconditionally_without_truth_test():
    log, _gate, callbacks = _callbacks(gate=None)
    callbacks["resolve_gate"] = (lambda: log.append(("resolve_gate",)) or None)
    run_gate_move_release_side_effect_sequence(**callbacks)
    assert log == [
        ("resolve_gate",),
        ("clear_gate_move",),
        ("clear_interior_hover_gate_id",),
        ("clear_frozen_xlim",),
        ("clear_frozen_ylim",),
        ("end_render",),
        ("finish_gate", None),
    ]


@pytest.mark.parametrize(
    "fail,expected",
    [
        ("resolve_gate", ["resolve_gate"]),
        ("clear_gate_move", ["resolve_gate", "clear_gate_move"]),
        (
            "clear_interior_hover_gate_id",
            ["resolve_gate", "clear_gate_move", "clear_interior_hover_gate_id"],
        ),
        (
            "clear_frozen_xlim",
            [
                "resolve_gate",
                "clear_gate_move",
                "clear_interior_hover_gate_id",
                "clear_frozen_xlim",
            ],
        ),
        (
            "clear_frozen_ylim",
            [
                "resolve_gate",
                "clear_gate_move",
                "clear_interior_hover_gate_id",
                "clear_frozen_xlim",
                "clear_frozen_ylim",
            ],
        ),
        (
            "end_render",
            [
                "resolve_gate",
                "clear_gate_move",
                "clear_interior_hover_gate_id",
                "clear_frozen_xlim",
                "clear_frozen_ylim",
                "end_render",
            ],
        ),
        (
            "finish_gate",
            [
                "resolve_gate",
                "clear_gate_move",
                "clear_interior_hover_gate_id",
                "clear_frozen_xlim",
                "clear_frozen_ylim",
                "end_render",
                "finish_gate",
            ],
        ),
    ],
)
def test_gate_move_callback_failures_preserve_partial_state_cutoff(fail, expected):
    log, _gate, callbacks = _callbacks(fail=fail)
    with pytest.raises(RuntimeError, match=rf"^{fail}-fail$"):
        run_gate_move_release_side_effect_sequence(**callbacks)
    assert [entry[0] for entry in log] == expected


def test_gate_move_sequence_never_truth_tests_gate_before_unconditional_finish():
    log = []

    class ExplodingTruthGate:
        def __bool__(self):
            log.append(("bool", "gate"))
            raise AssertionError("gate truth test must not occur")

    gate = ExplodingTruthGate()
    _, _, callbacks = _callbacks(gate=gate)
    # Replace callbacks so all operations share this test's log.
    def step(name, result=None):
        def call(*args):
            log.append((name, *args))
            return result
        return call
    callbacks = {
        "resolve_gate": step("resolve_gate", gate),
        "clear_gate_move": step("clear_gate_move"),
        "clear_interior_hover_gate_id": step("clear_interior_hover_gate_id"),
        "clear_frozen_xlim": step("clear_frozen_xlim"),
        "clear_frozen_ylim": step("clear_frozen_ylim"),
        "end_render_snapshot": step("end_render"),
        "finish_gate": step("finish_gate"),
    }
    run_gate_move_release_side_effect_sequence(**callbacks)
    assert ("bool", "gate") not in log
    assert log[-1] == ("finish_gate", gate)


def test_flowapp_keeps_gate_move_payload_read_and_mutations_controller_owned():
    source = inspect.getsource(GateInteractionController.on_release)
    branch = source[
        source.index("if release_path == 'gate_move':"):
        source.index("if release_path == 'inactive':")
    ]
    assert "run_gate_move_release_side_effect_sequence" in branch
    assert "host._gate_move['gate']" in branch
    assert "host._gate_move = None" in branch
    assert "host._interior_hover_gate_id = None" in branch
    assert "host._draw_frozen_xlim = None" in branch
    assert "host._draw_frozen_ylim = None" in branch
    assert "end_render_snapshot=host._end_blit_drag" in branch
    assert "host._finish_gate(gate)" in branch


def test_gate_move_sequence_remains_separate_from_top_level_path_selection():
    selector_source = inspect.getsource(resolve_release_interaction_path)
    sequence_source = inspect.getsource(run_gate_move_release_side_effect_sequence)
    assert "get_gate_move" in selector_source
    assert "resolve_gate" not in selector_source
    assert "resolve_gate" in sequence_source
    assert "get_handle_drag" not in sequence_source
    assert "get_moving_gate" not in sequence_source


def test_gate_move_helper_does_not_absorb_concrete_controller_authority():
    source = inspect.getsource(run_gate_move_release_side_effect_sequence)
    forbidden = [
        "self.", "self._gate_move", "self._interior_hover_gate_id",
        "self._draw_frozen_xlim", "self._draw_frozen_ylim", "_end_blit_drag",
        "_finish_gate", "event.", "BooleanVar", "gate[", "gate.get",
        "gate_by_id", "_del_gate", "iter_gate_draw_assignments",
        "is_degenerate_shape_gate",
    ]
    for token in forbidden:
        assert token not in source
