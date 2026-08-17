import inspect

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.core.gates import (
    begin_gate_draw,
    iter_gate_draw_initialization_assignments,
)
from vflow.legacy.vflow_app import FlowApp


def test_crosshair_initialization_assignments_are_ordered_and_pure():
    assert list(iter_gate_draw_initialization_assignments("crosshair", 1.0, 2.0)) == [
        ("x_boundaries", [1.0]),
        ("y_boundary", 2.0),
    ]


def test_shape_initialization_assignments_are_ordered_and_pure():
    expected = [("x0", 3.0), ("y0", 4.0), ("x1", 3.0), ("y1", 4.0)]
    assert list(iter_gate_draw_initialization_assignments("rectangle", 3.0, 4.0)) == expected
    assert list(iter_gate_draw_initialization_assignments("ellipse", 3.0, 4.0)) == expected


def test_polygon_and_unknown_initialization_stay_outside_helper():
    assert list(iter_gate_draw_initialization_assignments("polygon", 1.0, 2.0)) == []
    assert list(iter_gate_draw_initialization_assignments("unknown", 1.0, 2.0)) == []


def test_begin_gate_draw_compatibility_wrapper_preserves_all_legacy_shapes():
    cases = [
        ("crosshair", {"type": "crosshair", "x_boundaries": [1.0], "y_boundary": 2.0}),
        ("rectangle", {"type": "rectangle", "x0": 1.0, "y0": 2.0, "x1": 1.0, "y1": 2.0}),
        ("ellipse", {"type": "ellipse", "x0": 1.0, "y0": 2.0, "x1": 1.0, "y1": 2.0}),
        ("polygon", {"type": "polygon", "vertices": [(1.0, 2.0)]}),
        ("unknown", {"type": "unknown"}),
    ]
    for gate_type, expected in cases:
        gate = {"sentinel": 7}
        begin_gate_draw(gate, gate_type, 1.0, 2.0)
        assert gate == {"sentinel": 7, **expected}


def test_flowapp_nonpolygon_click_uses_ordered_initialization_helper():
    source = inspect.getsource(GateInteractionController.on_click)
    assert "iter_gate_draw_initialization_assignments(gt, x, y)" in source
    assert "gate['type'] = gt" in source
    assert "gate[key] = value" in source


def test_polygon_click_still_uses_legacy_begin_gate_draw_path():
    source = inspect.getsource(GateInteractionController.on_click)
    assert "begin_gate_draw(gate, 'polygon', x, y)" in source
    assert "append_polygon_vertex(draw, x, y)" in source


def test_begin_gate_draw_delegates_only_nonpolygon_geometry_to_helper():
    source = inspect.getsource(begin_gate_draw)
    assert "gate[\"type\"] = gate_type_value" in source
    assert "gate_type_value == \"polygon\"" in source
    assert "iter_gate_draw_initialization_assignments" in source
