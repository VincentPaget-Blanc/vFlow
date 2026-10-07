import inspect

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.core.gates import iter_gate_draw_assignments, update_gate_draw
from vflow.legacy.vflow_app import FlowApp


def test_crosshair_draw_assignments_are_ordered_and_pure():
    gate = {"type": "crosshair", "x_boundaries": [1.0], "y_boundary": 2.0}
    before = dict(gate)
    assert list(iter_gate_draw_assignments(gate, 3.0, 4.0)) == [
        ("x_boundaries", [3.0]),
        ("y_boundary", 4.0),
    ]
    assert gate == before


def test_shape_draw_assignments_are_ordered_and_pure():
    for gate_type in ("rectangle", "ellipse"):
        gate = {"type": gate_type, "x0": 1.0, "y0": 2.0, "x1": 1.0, "y1": 2.0}
        before = dict(gate)
        assert list(iter_gate_draw_assignments(gate, 5.0, 6.0)) == [
            ("x1", 5.0),
            ("y1", 6.0),
        ]
        assert gate == before


def test_polygon_draw_assignments_are_intentionally_empty():
    gate = {"type": "polygon", "vertices": [(1.0, 2.0)]}
    assert list(iter_gate_draw_assignments(gate, 3.0, 4.0)) == []
    assert gate == {"type": "polygon", "vertices": [(1.0, 2.0)]}


def test_legacy_update_gate_draw_delegates_to_ordered_assignments():
    gate = {"type": "rectangle", "x0": 0.0, "y0": 0.0, "x1": 0.0, "y1": 0.0}
    update_gate_draw(gate, 7.0, 8.0)
    assert gate["x1"] == 7.0
    assert gate["y1"] == 8.0
    source = inspect.getsource(update_gate_draw)
    assert "iter_gate_draw_assignments" in source


def test_flowapp_uses_ordered_draw_assignments_for_motion_and_release():
    motion = inspect.getsource(GateInteractionController.on_motion)
    release = inspect.getsource(GateInteractionController.on_release)
    assert "iter_gate_draw_assignments" in motion
    assert "iter_gate_draw_assignments" in release
    assert "update_gate_draw(gate" not in motion
    assert "update_gate_draw(gate" not in release
    assert "gate[key] = value" in motion
    assert "gate[key] = value" in release


def test_polygon_lifecycle_remains_separate_from_fresh_draw_assignment_helper():
    release = inspect.getsource(GateInteractionController.on_release)
    poly_finish = inspect.getsource(FlowApp._poly_finish)
    assert "polygon finishes via _poly_finish" in release
    assert "polygon_gate_can_finish" in poly_finish
