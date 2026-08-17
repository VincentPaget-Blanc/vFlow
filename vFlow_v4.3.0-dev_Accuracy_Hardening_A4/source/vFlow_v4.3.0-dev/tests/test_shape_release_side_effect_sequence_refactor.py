import inspect

import pytest

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.legacy.vflow_app import FlowApp
from vflow.services.gate_geometry_interaction import (
    run_crosshair_release_side_effect_sequence,
    run_shape_release_side_effect_sequence,
)


class GateId:
    pass


def _callbacks(*, degenerate=False, fail=None):
    log = []
    gate_id = GateId()

    def step(name, result=None):
        def call(*args):
            log.append((name, *args))
            if fail == name:
                raise RuntimeError(f"{name}-fail")
            return result
        return call

    callbacks = {
        "apply_geometry": step("geometry"),
        "is_degenerate": step("degenerate", degenerate),
        "end_render_snapshot": step("end_render"),
        "get_gate_id": step("gate_id", gate_id),
        "delete_gate": step("delete"),
        "mark_applied": step("applied"),
        "clear_draw_marker": step("clear_id"),
        "finish_gate": step("finish"),
    }
    return log, gate_id, callbacks


def test_shape_sequence_matches_frozen_non_degenerate_success_order():
    log, _gate_id, callbacks = _callbacks(degenerate=False)
    run_shape_release_side_effect_sequence(**callbacks)
    assert log == [
        ("geometry",),
        ("degenerate",),
        ("applied",),
        ("clear_id",),
        ("end_render",),
        ("finish",),
    ]


def test_shape_sequence_matches_frozen_degenerate_success_order_and_id_identity():
    log, gate_id, callbacks = _callbacks(degenerate=True)
    run_shape_release_side_effect_sequence(**callbacks)
    assert log == [
        ("geometry",),
        ("degenerate",),
        ("end_render",),
        ("gate_id",),
        ("delete", gate_id),
    ]


@pytest.mark.parametrize(
    "degenerate,fail,expected_names",
    [
        (False, "geometry", ["geometry"]),
        (False, "degenerate", ["geometry", "degenerate"]),
        (True, "end_render", ["geometry", "degenerate", "end_render"]),
        (True, "gate_id", ["geometry", "degenerate", "end_render", "gate_id"]),
        (True, "delete", ["geometry", "degenerate", "end_render", "gate_id", "delete"]),
        (False, "applied", ["geometry", "degenerate", "applied"]),
        (False, "clear_id", ["geometry", "degenerate", "applied", "clear_id"]),
        (False, "end_render", ["geometry", "degenerate", "applied", "clear_id", "end_render"]),
        (False, "finish", ["geometry", "degenerate", "applied", "clear_id", "end_render", "finish"]),
    ],
)
def test_shape_sequence_preserves_each_branch_failure_cutoff(
    degenerate, fail, expected_names
):
    log, _gate_id, callbacks = _callbacks(degenerate=degenerate, fail=fail)
    with pytest.raises(RuntimeError, match=rf"^{fail}-fail$"):
        run_shape_release_side_effect_sequence(**callbacks)
    assert [entry[0] for entry in log] == expected_names


def test_flowapp_keeps_shape_mutation_degeneracy_and_deletion_controller_owned():
    source = inspect.getsource(GateInteractionController.on_release)
    shape = source[source.index("elif finalization_path == 'shape':"):]
    assert "run_shape_release_side_effect_sequence" in shape
    assert "iter_gate_draw_assignments(gate, x, y)" in shape
    assert "gate[key] = value" in shape
    assert "is_degenerate_shape_gate(gate)" in shape
    assert "return gate['id']" in shape
    assert "host._del_gate(gate_id)" in shape
    assert "gate['applied'] = True" in shape
    assert "host._draw_gate_id = None" in shape
    assert "end_render_snapshot=host._end_blit_drag" in shape
    assert "finish_gate=lambda: host._finish_gate(gate)" in shape


def test_shape_and_crosshair_sequences_remain_distinct_boundaries():
    source = inspect.getsource(GateInteractionController.on_release)
    assert "run_crosshair_release_side_effect_sequence" in source
    assert "run_shape_release_side_effect_sequence" in source
    crosshair = inspect.getsource(run_crosshair_release_side_effect_sequence)
    shape = inspect.getsource(run_shape_release_side_effect_sequence)
    assert "get_threshold_plan" in crosshair
    assert "is_degenerate" not in crosshair
    assert "is_degenerate" in shape
    assert "get_threshold_plan" not in shape


def test_shape_sequence_helper_does_not_absorb_concrete_controller_authority():
    source = inspect.getsource(run_shape_release_side_effect_sequence)
    forbidden = [
        "gate[", "gate.get", "iter_gate_draw_assignments",
        "is_degenerate_shape_gate", "_draw_gate_id", "_finish_gate",
        "_del_gate", "event.", "BooleanVar", "self.",
    ]
    for token in forbidden:
        assert token not in source
