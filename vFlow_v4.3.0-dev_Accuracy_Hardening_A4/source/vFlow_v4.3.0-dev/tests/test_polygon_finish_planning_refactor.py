import inspect

import pytest

from vflow.core.gates import (
    PolygonFinishPlan,
    PolygonGeometrySchemaError,
    plan_polygon_finish,
    polygon_gate_can_finish,
)
from vflow.legacy.vflow_app import FlowApp


def test_polygon_finish_plan_is_frozen_and_contains_only_close_decisions():
    plan = plan_polygon_finish({"type": "polygon", "vertices": [(0, 0)] * 3})
    assert plan == PolygonFinishPlan(
        can_finish=True,
        applied_value=True,
        poly_active_value=False,
        poly_cursor_value=None,
        draw_gate_id_value=None,
    )
    with pytest.raises(Exception):
        plan.can_finish = False


def test_polygon_finish_eligibility_matches_legacy_minimum_vertex_rule():
    for n in range(5):
        gate = {"type": "polygon", "vertices": [(float(i), 0.0) for i in range(n)]}
        assert plan_polygon_finish(gate).can_finish is (n >= 3)
    assert not plan_polygon_finish(None).can_finish
    assert not plan_polygon_finish({"type": "rectangle", "vertices": [(0, 0)] * 99}).can_finish


def test_polygon_finish_preserves_short_circuit_and_rejects_vertices_none_deliberately():
    # Non-polygons never inspect polygon vertices, preserving the legacy short-circuit.
    assert not plan_polygon_finish({"type": "rectangle", "vertices": None}).can_finish

    with pytest.raises(PolygonGeometrySchemaError, match="vertices.*None.*finish eligibility"):
        plan_polygon_finish({"type": "polygon", "vertices": None})


def test_polygon_finish_preserves_custom_min_vertices_semantics():
    gate = {"type": "polygon", "vertices": [(0, 0), (1, 1)]}
    assert plan_polygon_finish(gate, min_vertices=2).can_finish
    assert plan_polygon_finish(gate, min_vertices=0).can_finish
    assert plan_polygon_finish(gate, min_vertices=-1).can_finish
    with pytest.raises(TypeError):
        plan_polygon_finish(gate, min_vertices=None)


def test_polygon_gate_can_finish_remains_compatibility_wrapper():
    gate = {"type": "polygon", "vertices": [(0, 0)] * 3}
    assert polygon_gate_can_finish(gate)
    source = inspect.getsource(polygon_gate_can_finish)
    assert "plan_polygon_finish" in source
    assert ".can_finish" in source


def test_flowapp_keeps_authoritative_polygon_finish_mutations_and_callbacks():
    source = inspect.getsource(FlowApp._poly_finish)
    assert "plan_polygon_finish(draw)" in source
    assert "draw['applied']" in source
    assert "self._poly_active" in source
    assert "self._poly_cursor" in source
    assert "self._draw_gate_id" in source
    assert "self._update_poly_close_btn()" in source
    assert "self._end_blit_drag()" in source
    assert "self._finish_gate(draw)" in source
    # Frozen older source-level contracts continue to see the historical marker.
    assert "polygon_gate_can_finish(draw)" in source


def test_core_finish_planner_has_no_tk_or_flowapp_side_effect_dependencies():
    source = inspect.getsource(plan_polygon_finish)
    assert "tk." not in source
    assert "_finish_gate" not in source
    assert "_end_blit_drag" not in source
    assert "_update_poly_close_btn" not in source
