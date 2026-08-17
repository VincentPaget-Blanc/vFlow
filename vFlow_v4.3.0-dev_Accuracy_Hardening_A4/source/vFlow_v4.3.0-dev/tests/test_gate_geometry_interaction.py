import numpy as np

from vflow.services.gate_geometry_interaction import (
    DrawInteractionPlan,
    GateMoveStartPlan,
    HandleDragStartPlan,
    plan_draw_start,
    plan_gate_move_start,
    plan_handle_drag_start,
)


def test_draw_start_preserves_frozen_moving_and_throttle_decisions():
    assert plan_draw_start() == DrawInteractionPlan(moving_gate=True, drag_last_draw=0.0)


def test_handle_drag_start_preserves_selection_and_first_frame_rules():
    assert plan_handle_drag_start(gate_id=7, selected_gate_id=1) == HandleDragStartPlan(0.0, 7)
    assert plan_handle_drag_start(gate_id=7, selected_gate_id=7) == HandleDragStartPlan(0.0, None)


def test_gate_move_start_preserves_payload_references_and_selection():
    gate = {"id": 9, "type": "polygon"}
    snap = {"id": 9, "vertices": [(1.0, 2.0)]}
    px = np.array([[10.0, 20.0], [30.0, 40.0]])
    press = np.array([12.0, 34.0])
    fx = [1.0, 5.0]
    fy = [2.0, 8.0]
    plan = plan_gate_move_start(
        gate_id=9,
        gate=gate,
        original_gate_snapshot=snap,
        original_pixel_points=px,
        press_pixel_point=press,
        frozen_xlim=fx,
        frozen_ylim=fy,
        selected_gate_id=1,
    )
    assert isinstance(plan, GateMoveStartPlan)
    assert plan.payload["gate_id"] == 9
    assert plan.payload["gate"] is gate
    assert plan.payload["orig"] is snap
    assert plan.payload["orig_px"] is px
    assert plan.payload["press_px"] is press
    assert plan.payload["frozen_xlim"] is fx
    assert plan.payload["frozen_ylim"] is fy
    assert plan.drag_last_draw == 0.0
    assert plan.clear_interior_hover is True
    assert plan.select_gate_id == 9


def test_gate_move_start_preserves_already_selected_gate():
    gate = {"id": 9}
    plan = plan_gate_move_start(
        gate_id=9, gate=gate, original_gate_snapshot={},
        original_pixel_points=[], press_pixel_point=[],
        frozen_xlim=[0, 1], frozen_ylim=[0, 1], selected_gate_id=9,
    )
    assert plan.select_gate_id is None



def test_gate_pixel_delta_preserves_orderable_legacy_subtraction():
    from vflow.services.gate_geometry_interaction import gate_pixel_delta

    assert gate_pixel_delta(current_pixel=112.5, press_pixel=100.0) == 12.5
    assert gate_pixel_delta(current_pixel=193.0, press_pixel=200.0) == -7.0


def test_translate_gate_pixel_points_preserves_rigid_numpy_translation():
    from vflow.services.gate_geometry_interaction import translate_gate_pixel_points

    original = np.array([[10.0, 20.0], [30.0, 40.0], [-5.0, 8.0]])
    shifted = translate_gate_pixel_points(
        original_pixel_points=original,
        delta_x=12.5,
        delta_y=-7.0,
    )
    np.testing.assert_array_equal(
        shifted,
        np.array([[22.5, 13.0], [42.5, 33.0], [7.5, 1.0]]),
    )
    assert shifted.dtype == original.dtype


def test_translate_gate_pixel_points_preserves_empty_shape_and_float_dtype():
    from vflow.services.gate_geometry_interaction import translate_gate_pixel_points

    original = np.zeros((0, 2), dtype=float)
    shifted = translate_gate_pixel_points(
        original_pixel_points=original,
        delta_x=3.0,
        delta_y=4.0,
    )
    assert shifted.shape == (0, 2)
    assert shifted.dtype == np.dtype(float)


def test_gate_pixel_delta_preserves_legacy_arithmetic_exception_boundary():
    from vflow.services.gate_geometry_interaction import gate_pixel_delta

    class BadCurrent:
        def __sub__(self, other):
            raise RuntimeError("delta failed")

    with __import__('pytest').raises(RuntimeError, match='delta failed'):
        gate_pixel_delta(current_pixel=BadCurrent(), press_pixel=0.0)


def test_handle_drag_assignment_planner_is_pure_for_shape_and_polygon():
    from vflow.core.gates import iter_handle_drag_assignments

    rect = {"type": "rectangle", "x0": 0.0, "y0": 1.0, "x1": 4.0, "y1": 5.0}
    orig = dict(rect)
    before = dict(rect)
    assert list(iter_handle_drag_assignments(
        rect, handle="ne", idx=1, orig=orig, x=6.0, y=-2.0
    )) == [("x1", 6.0), ("y0", -2.0)]
    assert rect == before

    assert list(iter_handle_drag_assignments(
        rect, handle="center", idx=4, orig=orig, x=3.0, y=5.0
    )) == [
        ("x0", 1.0), ("x1", 5.0), ("y0", 3.0), ("y1", 7.0)
    ]
    assert rect == before

    poly = {"type": "polygon", "vertices": [(0.0, 0.0), (1.0, 1.0)]}
    poly_before = {"type": "polygon", "vertices": list(poly["vertices"])}
    assert list(iter_handle_drag_assignments(
        poly, handle="vertex", idx=1, orig={}, x=2.0, y=3.0
    )) == [("vertices", [(0.0, 0.0), (2.0, 3.0)])]
    assert poly == poly_before


def test_handle_drag_assignment_planner_preserves_noop_cases():
    from vflow.core.gates import iter_handle_drag_assignments

    assert list(iter_handle_drag_assignments(
        {"type": "rectangle"}, handle="unknown", idx=0, orig={}, x=1, y=2
    )) == []
    assert list(iter_handle_drag_assignments(
        {"type": "polygon", "vertices": [(0, 0)]},
        handle="vertex", idx=5, orig={}, x=1, y=2
    )) == []
    assert list(iter_handle_drag_assignments(
        {"type": "crosshair"}, handle="center", idx=0, orig={}, x=1, y=2
    )) == []


def test_center_handle_assignment_planner_is_lazy_in_legacy_order():
    from vflow.core.gates import iter_handle_drag_assignments

    class Orig(dict):
        def __init__(self):
            super().__init__(x0=0.0, x1=4.0, y0=1.0, y1=5.0)
            self.calls = []
        def __getitem__(self, key):
            self.calls.append(key)
            # Frozen center logic reads x0/x1 for dx, y0/y1 for dy, then x0 again.
            if self.calls == ["x0", "x1", "y0", "y1", "x0", "x1"]:
                raise RuntimeError("late x1 failure")
            return super().__getitem__(key)

    orig = Orig()
    it = iter_handle_drag_assignments(
        {"type": "rectangle"}, handle="center", idx=4, orig=orig, x=3.0, y=5.0
    )
    assert next(it) == ("x0", 1.0)
    import pytest
    with pytest.raises(RuntimeError, match="late x1 failure"):
        next(it)
    assert orig.calls == ["x0", "x1", "y0", "y1", "x0", "x1"]
