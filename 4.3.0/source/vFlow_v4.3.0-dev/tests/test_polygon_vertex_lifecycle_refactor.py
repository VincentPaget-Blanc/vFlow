import inspect

import pytest

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.core.gates import (
    PolygonGeometrySchemaError,
    PolygonVertexPlan,
    append_polygon_vertex,
    begin_gate_draw,
    plan_polygon_vertex,
)
from vflow.legacy.vflow_app import FlowApp


def test_polygon_vertex_plan_is_frozen_pure_payload():
    plan = plan_polygon_vertex("initialize", 1.25, -2.5)
    assert plan == PolygonVertexPlan("initialize", (1.25, -2.5))
    with pytest.raises(Exception):
        plan.operation = "append"


def test_polygon_vertex_plan_distinguishes_initialize_and_append():
    assert plan_polygon_vertex("initialize", 1.0, 2.0).operation == "initialize"
    assert plan_polygon_vertex("append", 1.0, 2.0).operation == "append"
    with pytest.raises(ValueError):
        plan_polygon_vertex("finish", 1.0, 2.0)


def test_polygon_planner_does_not_read_or_mutate_gate_state():
    gate = {"vertices": [(9.0, 9.0)], "sentinel": object()}
    before = dict(gate)
    plan = plan_polygon_vertex("append", 3.0, 4.0)
    assert plan.vertex == (3.0, 4.0)
    assert gate == before
    assert gate["vertices"] is before["vertices"]


def test_compatibility_wrappers_preserve_initialize_and_append_semantics():
    gate = {"vertices": [(99.0, 99.0)], "sentinel": 7}
    begin_gate_draw(gate, "polygon", 1.0, 2.0)
    assert gate == {
        "vertices": [(1.0, 2.0)],
        "sentinel": 7,
        "type": "polygon",
    }
    vertices = gate["vertices"]
    append_polygon_vertex(gate, 3.0, 4.0)
    assert gate["vertices"] is vertices
    assert gate["vertices"] == [(1.0, 2.0), (3.0, 4.0)]


def test_append_wrapper_preserves_setdefault_behavior():
    gate = {"sentinel": 7}
    append_polygon_vertex(gate, 3.0, 4.0)
    assert gate == {"sentinel": 7, "vertices": [(3.0, 4.0)]}

    gate_with_none = {"vertices": None}
    with pytest.raises(PolygonGeometrySchemaError, match="vertices.*None.*vertex append"):
        append_polygon_vertex(gate_with_none, 3.0, 4.0)
    assert gate_with_none == {"vertices": None}


def test_flowapp_owns_polygon_live_mutation_and_keeps_finalize_separate():
    click_source = inspect.getsource(GateInteractionController.on_click)
    finish_source = inspect.getsource(FlowApp._poly_finish)

    assert "plan_polygon_vertex('initialize', x, y).vertex" in click_source
    assert "plan_polygon_vertex('append', x, y).vertex" in click_source
    assert "gate['vertices'] =" in click_source
    assert "draw.setdefault('vertices', [])" in click_source
    assert "require_polygon_vertices" in click_source
    assert "polygon_gate_can_finish(draw)" in finish_source
    assert "draw['applied']" in finish_source
    assert "plan_polygon_vertex" not in finish_source
