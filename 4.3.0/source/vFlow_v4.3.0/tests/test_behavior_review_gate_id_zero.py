from types import SimpleNamespace

from vflow.ui.gate_interaction import (
    plan_hover_cursor_policy,
    resolve_hover_cursor_gate_id,
    should_resolve_hover_cursor,
)


def test_br_hover_001_gate_zero_is_a_real_cursor_source_end_to_end_helpers():
    calls = []

    assert should_resolve_hover_cursor(
        get_handle_drag=lambda: None,
        get_hover_gate_id=lambda: calls.append('hover') or 0,
        get_pinned_gate_id=lambda: calls.append('pinned') or 9,
    ) is True
    assert calls == ['hover']

    calls.clear()
    assert resolve_hover_cursor_gate_id(
        get_handle_drag=lambda: None,
        get_hover_gate_id=lambda: calls.append('hover') or 0,
        get_pinned_gate_id=lambda: calls.append('pinned') or 9,
    ) == 0
    assert calls == ['hover']

    assert plan_hover_cursor_policy(
        new_hover=0,
        pinned_gate_id=None,
        new_interior=None,
    ) == 'hover'


def test_br_hover_001_pinned_gate_zero_is_a_real_cursor_source():
    assert should_resolve_hover_cursor(
        get_handle_drag=lambda: None,
        get_hover_gate_id=lambda: None,
        get_pinned_gate_id=lambda: 0,
    ) is True
    assert resolve_hover_cursor_gate_id(
        get_handle_drag=lambda: None,
        get_hover_gate_id=lambda: None,
        get_pinned_gate_id=lambda: 0,
    ) == 0
    assert plan_hover_cursor_policy(
        new_hover=None,
        pinned_gate_id=0,
        new_interior=None,
    ) == 'hover'


def test_br_hover_001_flowapp_cursor_uses_hover_gate_zero_cache():
    from vflow.legacy.vflow_app import FlowApp

    app = FlowApp.__new__(FlowApp)
    app._handle_drag = None
    app._hover_gate_id = 0
    app._pinned_gate_id = 9
    app._handle_px_cache = {
        0: [(10.0, 20.0, 'center', None)],
        9: [(1000.0, 1000.0, 'center', None)],
    }

    event = SimpleNamespace(x=10.0, y=20.0)
    assert app._cursor_for_hover(event) == 'fleur'
