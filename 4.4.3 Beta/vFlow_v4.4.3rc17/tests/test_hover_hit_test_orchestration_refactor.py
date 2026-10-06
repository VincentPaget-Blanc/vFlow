from pathlib import Path

from vflow.ui.gate_interaction import (
    continue_hover_hit_testing,
    plan_hover_hit_testing,
)


def test_handle_hit_suppresses_line_test_and_preserves_handle_key():
    plan = plan_hover_hit_testing(
        handle_gate_id=7,
        hover_handle_key=(7, 'center', None),
        current_hover_gate_id=None,
        current_pos=(100, 200),
        last_line_test_pos=(0, 0),
    )
    assert plan.hover_gate_id == 7
    assert plan.hover_handle_key == (7, 'center', None)
    assert plan.run_line_test is False
    assert plan.next_line_test_pos == (0, 0)

    continuation = continue_hover_hit_testing(
        plan=plan, line_gate_id=None, line_test_ran=False, mode='draw'
    )
    assert continuation.hover_gate_id == 7
    assert continuation.run_interior_test is False


def test_existing_hover_gate_forces_line_retest_even_for_gate_zero():
    for current in (0, 4):
        plan = plan_hover_hit_testing(
            handle_gate_id=None,
            hover_handle_key=None,
            current_hover_gate_id=current,
            current_pos=(12, 18),
            last_line_test_pos=(11, 18),
        )
        assert plan.run_line_test is True
        # Frozen line-hover helper preserves the cached cursor position here.
        assert plan.next_line_test_pos == (11, 18)


def test_cursor_distance_throttles_line_test_but_still_allows_draw_interior():
    plan = plan_hover_hit_testing(
        handle_gate_id=None,
        hover_handle_key=None,
        current_hover_gate_id=None,
        current_pos=(15, 15),
        last_line_test_pos=(10, 11),
        min_delta=10,
    )
    assert plan.run_line_test is False
    assert plan.next_line_test_pos == (10, 11)

    continuation = continue_hover_hit_testing(
        plan=plan, line_gate_id=None, line_test_ran=False, mode='draw'
    )
    assert continuation.hover_gate_id is None
    assert continuation.run_interior_test is True


def test_cursor_distance_schedules_line_test_and_next_position():
    plan = plan_hover_hit_testing(
        handle_gate_id=None,
        hover_handle_key=None,
        current_hover_gate_id=None,
        current_pos=(30, 50),
        last_line_test_pos=(5, 7),
        min_delta=10,
    )
    assert plan.run_line_test is True
    assert plan.next_line_test_pos == (30, 50)


def test_line_result_becomes_hover_and_suppresses_interior():
    plan = plan_hover_hit_testing(
        handle_gate_id=None,
        hover_handle_key=None,
        current_hover_gate_id=None,
        current_pos=(30, 50),
        last_line_test_pos=None,
    )
    assert plan.run_line_test is True

    continuation = continue_hover_hit_testing(
        plan=plan, line_gate_id=9, line_test_ran=True, mode='draw'
    )
    assert continuation.hover_gate_id == 9
    assert continuation.run_interior_test is False


def test_failed_line_hit_allows_interior_only_in_draw_mode():
    plan = plan_hover_hit_testing(
        handle_gate_id=None,
        hover_handle_key=None,
        current_hover_gate_id=3,
        current_pos=(1, 2),
        last_line_test_pos=(1, 2),
    )
    assert plan.run_line_test is True

    draw = continue_hover_hit_testing(
        plan=plan, line_gate_id=None, line_test_ran=True, mode='draw'
    )
    select = continue_hover_hit_testing(
        plan=plan, line_gate_id=None, line_test_ran=True, mode='select'
    )
    assert draw.run_interior_test is True
    assert select.run_interior_test is False


def test_flowapp_keeps_actual_hover_geometry_and_transform_calls():
    source = Path('vflow/controllers/gate_interaction_controller.py').read_text()
    assert 'host._hover_test_handles(event)' in source
    assert 'nearest_cached_handle(' in source
    assert 'host._hit_test_gate_line(event, threshold_px=8)' in source
    assert 'host._hit_test_gate_interior(event)' in source
    assert 'invoke_hover_hit_test_plan(' in source
    assert 'planner=plan_hover_hit_testing' in source
    assert 'continue_hover_hit_testing(' in source
