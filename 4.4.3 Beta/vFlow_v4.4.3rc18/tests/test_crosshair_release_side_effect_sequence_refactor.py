import inspect

import pytest

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.legacy.vflow_app import FlowApp
from vflow.services.gate_geometry_interaction import (
    run_crosshair_release_side_effect_sequence,
)


class Plan:
    pass


def _callbacks(*, fail=None):
    log = []
    plan = Plan()

    def step(name, result=None):
        def call(*args):
            log.append((name, *args))
            if fail == name:
                raise RuntimeError(f"{name}-fail")
            return result
        return call

    callbacks = {
        "apply_geometry": step("geometry"),
        "get_threshold_plan": step("plan", plan),
        "materialize_x_threshold_vars": step("xvars"),
        "materialize_y_threshold_var": step("yvar"),
        "mark_applied": step("applied"),
        "clear_draw_marker": step("clear_id"),
        "end_render_snapshot": step("end_render"),
        "finish_gate": step("finish"),
    }
    return log, plan, callbacks


def test_crosshair_sequence_matches_frozen_success_order_and_plan_identity():
    log, plan, callbacks = _callbacks()
    run_crosshair_release_side_effect_sequence(**callbacks)
    assert log == [
        ("geometry",),
        ("plan",),
        ("xvars", plan),
        ("yvar", plan),
        ("applied",),
        ("clear_id",),
        ("end_render",),
        ("finish",),
    ]


@pytest.mark.parametrize(
    "fail,expected_names",
    [
        ("geometry", ["geometry"]),
        ("plan", ["geometry", "plan"]),
        ("xvars", ["geometry", "plan", "xvars"]),
        ("yvar", ["geometry", "plan", "xvars", "yvar"]),
        ("applied", ["geometry", "plan", "xvars", "yvar", "applied"]),
        ("clear_id", ["geometry", "plan", "xvars", "yvar", "applied", "clear_id"]),
        ("end_render", ["geometry", "plan", "xvars", "yvar", "applied", "clear_id", "end_render"]),
        ("finish", ["geometry", "plan", "xvars", "yvar", "applied", "clear_id", "end_render", "finish"]),
    ],
)
def test_crosshair_sequence_preserves_each_failure_cutoff(fail, expected_names):
    log, _plan, callbacks = _callbacks(fail=fail)
    with pytest.raises(RuntimeError, match=rf"^{fail}-fail$"):
        run_crosshair_release_side_effect_sequence(**callbacks)
    assert [entry[0] for entry in log] == expected_names


def test_flowapp_keeps_crosshair_materialization_and_mutation_controller_owned():
    source = inspect.getsource(GateInteractionController.on_release)
    assert "run_crosshair_release_side_effect_sequence" in source
    assert "iter_gate_draw_assignments(gate, x, y)" in source
    assert "gate[key] = value" in source
    assert "manual_crosshair_threshold_plan()" in source
    assert "gate['x_thresh_vars'] = [tk.BooleanVar" in source
    assert "gate['y_thresh_var']  = tk.BooleanVar" in source
    assert "gate['applied']       = True" in source
    assert "host._draw_gate_id = None" in source
    assert "end_render_snapshot=host._end_blit_drag" in source
    assert "finish_gate=lambda: host._finish_gate(gate)" in source


def test_shape_degeneracy_path_remains_separate_and_controller_owned():
    source = inspect.getsource(GateInteractionController.on_release)
    shape = source[source.index("elif finalization_path == 'shape':"):]
    assert "run_shape_release_side_effect_sequence" in shape
    assert "iter_gate_draw_assignments(gate, x, y)" in shape
    assert "is_degenerate_shape_gate(gate)" in shape
    assert "return gate['id']" in shape
    assert "host._del_gate(gate_id)" in shape
    assert "gate['applied'] = True" in shape
    assert "host._draw_gate_id = None" in shape
    assert "end_render_snapshot=host._end_blit_drag" in shape
    assert "finish_gate=lambda: host._finish_gate(gate)" in shape


def test_sequence_helper_does_not_absorb_concrete_controller_authority():
    source = inspect.getsource(run_crosshair_release_side_effect_sequence)
    forbidden = [
        "gate[", "gate.get", "BooleanVar", "iter_gate_draw_assignments",
        "manual_crosshair_threshold_plan", "_draw_gate_id", "_finish_gate",
        "event.", "is_degenerate_shape_gate", "_del_gate",
    ]
    for token in forbidden:
        assert token not in source
