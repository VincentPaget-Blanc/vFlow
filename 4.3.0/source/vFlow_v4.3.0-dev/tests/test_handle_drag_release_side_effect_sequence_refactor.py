import inspect

import pytest

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.legacy.vflow_app import FlowApp
from vflow.services.gate_geometry_interaction import (
    resolve_release_interaction_path,
    run_handle_drag_release_side_effect_sequence,
)


class TruthGate:
    def __init__(self, truth, log):
        self.truth = truth
        self.log = log

    def __bool__(self):
        self.log.append(("bool", "gate"))
        if isinstance(self.truth, BaseException):
            raise self.truth
        return self.truth


def _callbacks(*, gate_truth=True, fail=None):
    log = []
    gate = TruthGate(gate_truth, log)

    def step(name, result=None):
        def call(*args):
            log.append((name, *args))
            if fail == name:
                raise RuntimeError(f"{name}-fail")
            return result
        return call

    callbacks = {
        "resolve_gate": step("resolve_gate", gate),
        "clear_handle_drag": step("clear_handle_drag"),
        "clear_hover_gate_id": step("clear_hover_gate_id"),
        "clear_frozen_xlim": step("clear_frozen_xlim"),
        "clear_frozen_ylim": step("clear_frozen_ylim"),
        "end_render_snapshot": step("end_render"),
        "finish_gate": step("finish_gate"),
    }
    return log, gate, callbacks


def test_handle_drag_sequence_truthy_gate_preserves_exact_order_and_identity():
    log, gate, callbacks = _callbacks(gate_truth=True)
    run_handle_drag_release_side_effect_sequence(**callbacks)
    assert log == [
        ("resolve_gate",),
        ("clear_handle_drag",),
        ("clear_hover_gate_id",),
        ("clear_frozen_xlim",),
        ("clear_frozen_ylim",),
        ("end_render",),
        ("bool", "gate"),
        ("finish_gate", gate),
    ]


def test_handle_drag_sequence_falsey_gate_tears_down_but_skips_finish():
    log, _gate, callbacks = _callbacks(gate_truth=False)
    run_handle_drag_release_side_effect_sequence(**callbacks)
    assert log == [
        ("resolve_gate",),
        ("clear_handle_drag",),
        ("clear_hover_gate_id",),
        ("clear_frozen_xlim",),
        ("clear_frozen_ylim",),
        ("end_render",),
        ("bool", "gate"),
    ]


@pytest.mark.parametrize(
    "fail,expected",
    [
        ("resolve_gate", ["resolve_gate"]),
        ("clear_handle_drag", ["resolve_gate", "clear_handle_drag"]),
        (
            "clear_hover_gate_id",
            ["resolve_gate", "clear_handle_drag", "clear_hover_gate_id"],
        ),
        (
            "clear_frozen_xlim",
            [
                "resolve_gate",
                "clear_handle_drag",
                "clear_hover_gate_id",
                "clear_frozen_xlim",
            ],
        ),
        (
            "clear_frozen_ylim",
            [
                "resolve_gate",
                "clear_handle_drag",
                "clear_hover_gate_id",
                "clear_frozen_xlim",
                "clear_frozen_ylim",
            ],
        ),
        (
            "end_render",
            [
                "resolve_gate",
                "clear_handle_drag",
                "clear_hover_gate_id",
                "clear_frozen_xlim",
                "clear_frozen_ylim",
                "end_render",
            ],
        ),
    ],
)
def test_handle_drag_callback_failures_preserve_partial_state_cutoff(fail, expected):
    log, _gate, callbacks = _callbacks(gate_truth=True, fail=fail)
    with pytest.raises(RuntimeError, match=rf"^{fail}-fail$"):
        run_handle_drag_release_side_effect_sequence(**callbacks)
    assert [entry[0] for entry in log if entry[0] != "bool"] == expected


def test_handle_drag_gate_truth_failure_occurs_only_after_render_teardown():
    log, _gate, callbacks = _callbacks(gate_truth=RuntimeError("gate-bool-fail"))
    with pytest.raises(RuntimeError, match="^gate-bool-fail$"):
        run_handle_drag_release_side_effect_sequence(**callbacks)
    assert log == [
        ("resolve_gate",),
        ("clear_handle_drag",),
        ("clear_hover_gate_id",),
        ("clear_frozen_xlim",),
        ("clear_frozen_ylim",),
        ("end_render",),
        ("bool", "gate"),
    ]


def test_handle_drag_finish_failure_occurs_after_truth_test():
    log, _gate, callbacks = _callbacks(gate_truth=True, fail="finish_gate")
    with pytest.raises(RuntimeError, match="^finish_gate-fail$"):
        run_handle_drag_release_side_effect_sequence(**callbacks)
    assert [entry[0] for entry in log] == [
        "resolve_gate",
        "clear_handle_drag",
        "clear_hover_gate_id",
        "clear_frozen_xlim",
        "clear_frozen_ylim",
        "end_render",
        "bool",
        "finish_gate",
    ]


def test_flowapp_keeps_handle_drag_gate_lookup_and_mutations_controller_owned():
    source = inspect.getsource(GateInteractionController.on_release)
    branch = source[
        source.index("if release_path == 'handle_drag':"):
        source.index("# ── Finish gate-body move")
    ]
    assert "run_handle_drag_release_side_effect_sequence" in branch
    assert "gate_by_id(host.gates, host._handle_drag['gate_id'])" in branch
    assert "host._handle_drag = None" in branch
    assert "host._hover_gate_id = None" in branch
    assert "host._draw_frozen_xlim = None" in branch
    assert "host._draw_frozen_ylim = None" in branch
    assert "end_render_snapshot=host._end_blit_drag" in branch
    assert "host._finish_gate(gate)" in branch


def test_handle_drag_sequence_remains_separate_from_top_level_path_selection():
    selector_source = inspect.getsource(resolve_release_interaction_path)
    sequence_source = inspect.getsource(run_handle_drag_release_side_effect_sequence)
    assert "get_handle_drag" in selector_source
    assert "resolve_gate" not in selector_source
    assert "resolve_gate" in sequence_source
    assert "get_gate_move" not in sequence_source
    assert "get_moving_gate" not in sequence_source


def test_handle_drag_helper_does_not_absorb_concrete_controller_authority():
    source = inspect.getsource(run_handle_drag_release_side_effect_sequence)
    forbidden = [
        "self.", "gate_by_id", "self._handle_drag", "self._hover_gate_id",
        "self._draw_frozen_xlim", "self._draw_frozen_ylim", "_end_blit_drag",
        "_finish_gate", "event.", "BooleanVar", "gate[", "gate.get",
        "_del_gate", "iter_gate_draw_assignments", "is_degenerate_shape_gate",
    ]
    for token in forbidden:
        assert token not in source
