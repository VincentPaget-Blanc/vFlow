import inspect

import pytest

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.core.gates import (
    PolygonCloseEntryPlan,
    plan_polygon_close_entry,
)
from vflow.legacy.vflow_app import FlowApp


def test_polygon_close_entry_plan_is_frozen_and_minimal():
    plan = plan_polygon_close_entry(
        "double_click", polygon_active=True, mode="draw"
    )
    assert plan == PolygonCloseEntryPlan(should_finish=True)
    with pytest.raises(Exception):
        plan.should_finish = False


def test_double_click_only_finishes_active_polygon_in_draw_mode():
    for active in (False, True):
        for mode in ("draw", "none", "other"):
            plan = plan_polygon_close_entry(
                "double_click", polygon_active=active, mode=mode
            )
            assert plan.should_finish is (active and mode == "draw")


def test_right_click_finish_intent_depends_only_on_polygon_active():
    for active in (False, True):
        for mode in ("draw", "none", "other"):
            plan = plan_polygon_close_entry(
                "right_click", polygon_active=active, mode=mode
            )
            assert plan.should_finish is active


def test_unknown_close_entry_trigger_is_rejected():
    with pytest.raises(ValueError, match="unsupported polygon close trigger"):
        plan_polygon_close_entry("middle_click", polygon_active=True, mode="draw")


def test_close_entry_planner_has_no_gate_or_ui_side_effects():
    source = inspect.getsource(plan_polygon_close_entry)
    assert "tk." not in source
    assert "event." not in source
    assert "_poly_finish" not in source
    assert "plan_polygon_finish" not in source
    assert "vertices" not in source


def test_flowapp_keeps_event_access_subgate_and_finish_ownership():
    source = inspect.getsource(GateInteractionController.on_click)
    assert "if event.dblclick:" in source
    assert "if event.button == 3:" in source
    assert "plan_polygon_close_entry(" in source
    assert "'double_click'" in source
    assert "'right_click'" in source
    assert "host._poly_finish()" in source
    assert "host._open_subgate(event.xdata, event.ydata)" in source
    assert "event.dblclick" not in inspect.getsource(plan_polygon_close_entry)
    assert "event.button" not in inspect.getsource(plan_polygon_close_entry)
