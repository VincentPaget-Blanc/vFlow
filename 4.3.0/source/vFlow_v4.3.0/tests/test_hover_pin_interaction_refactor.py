import ast
from pathlib import Path

from vflow.ui.gate_interaction import (
    GateInteractionState,
    plan_hover_cursor_policy,
    plan_hover_presentation,
    plan_pin_interaction,
    should_clear_hover_outside_axes,
)


def test_gate_interaction_state_owns_hover_handle_key_and_clears_it():
    state = GateInteractionState(
        selected_gate_id=1,
        draw_gate_id=2,
        hover_gate_id=3,
        hover_handle_key=(3, 'corner', 1),
        interior_hover_gate_id=4,
        pinned_gate_id=5,
    )
    state.clear_gate_references()
    assert state == GateInteractionState()


def test_flowapp_hover_handle_key_property_is_bidirectional():
    from vflow.legacy.vflow_app import FlowApp

    app = FlowApp.__new__(FlowApp)
    app._hover_handle_key = (7, 'center', None)
    state = app._gate_interaction_state_obj()
    assert state.hover_handle_key == (7, 'center', None)
    state.hover_handle_key = (8, 'vertex', 2)
    assert app._hover_handle_key == (8, 'vertex', 2)


def test_pin_plan_preserves_toggle_select_and_empty_space_rules():
    assert plan_pin_interaction(line_gate_id=4, pinned_gate_id=None) == (
        type(plan_pin_interaction(line_gate_id=4, pinned_gate_id=None))(
            pinned_gate_id=4,
            selected_gate_id=4,
            update_selection=True,
            redraw=True,
        )
    )
    toggled_off = plan_pin_interaction(line_gate_id=4, pinned_gate_id=4)
    assert toggled_off.pinned_gate_id is None
    assert toggled_off.update_selection is False
    assert toggled_off.redraw is True

    empty_unpin = plan_pin_interaction(line_gate_id=None, pinned_gate_id=4)
    assert empty_unpin.pinned_gate_id is None
    assert empty_unpin.update_selection is False
    assert empty_unpin.redraw is True

    empty_noop = plan_pin_interaction(line_gate_id=None, pinned_gate_id=None)
    assert empty_noop.redraw is False


def test_pin_plan_treats_gate_id_zero_as_a_real_line_hit():
    plan = plan_pin_interaction(line_gate_id=0, pinned_gate_id=None)
    assert plan.pinned_gate_id == 0
    assert plan.selected_gate_id == 0
    assert plan.update_selection is True
    assert plan.redraw is True


def test_hover_cursor_policy_treats_gate_zero_as_present():
    assert plan_hover_cursor_policy(
        new_hover=3, pinned_gate_id=None, new_interior=None
    ) == 'hover'
    assert plan_hover_cursor_policy(
        new_hover=None, pinned_gate_id=3, new_interior=None
    ) == 'hover'
    assert plan_hover_cursor_policy(
        new_hover=0, pinned_gate_id=0, new_interior=None
    ) == 'hover'
    assert plan_hover_cursor_policy(
        new_hover=0, pinned_gate_id=0, new_interior=9
    ) == 'hover'


def test_hover_presentation_plan_preserves_state_and_changed_semantics():
    same = plan_hover_presentation(
        new_hover=2,
        old_hover=2,
        new_hover_handle_key=(2, 'center', None),
        old_hover_handle_key=(2, 'center', None),
        new_interior=None,
        old_interior=None,
    )
    assert same.changed is False
    assert same.hover_gate_id == 2
    assert same.hover_handle_key == (2, 'center', None)

    changed = plan_hover_presentation(
        new_hover=2,
        old_hover=2,
        new_hover_handle_key=(2, 'corner', 1),
        old_hover_handle_key=(2, 'center', None),
        new_interior=4,
        old_interior=None,
    )
    assert changed.changed is True
    assert changed.interior_hover_gate_id == 4


def test_outside_axes_clear_condition_includes_stray_handle_state_lazily():
    calls = []

    def handle(value):
        def resolve():
            calls.append(value)
            return value
        return resolve

    assert should_clear_hover_outside_axes(
        hover_gate_id=None,
        interior_hover_gate_id=None,
        resolve_hover_handle_key=handle(None),
    ) is False
    assert calls == [None]

    assert should_clear_hover_outside_axes(
        hover_gate_id=None,
        interior_hover_gate_id=None,
        resolve_hover_handle_key=handle((3, 'edge', 0)),
    ) is True
    assert calls[-1] == (3, 'edge', 0)

    before = list(calls)
    assert should_clear_hover_outside_axes(
        hover_gate_id=0,
        interior_hover_gate_id=None,
        resolve_hover_handle_key=handle(('must', 'not', 'read')),
    ) is True
    assert should_clear_hover_outside_axes(
        hover_gate_id=None,
        interior_hover_gate_id=0,
        resolve_hover_handle_key=handle(('must', 'not', 'read')),
    ) is True
    assert calls == before


def test_gate_interaction_planning_module_stays_tk_and_matplotlib_free():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any(name == 'tkinter' or name.startswith('tkinter.') for name in imports)
    assert not any(name == 'matplotlib' or name.startswith('matplotlib.') for name in imports)


def test_flowapp_keeps_hit_testing_cursor_and_rendering_side_effects():
    source = Path('vflow/controllers/gate_interaction_controller.py').read_text()
    assert 'host._hit_test_gate_line(event, threshold_px=10)' in source
    assert 'host._hover_test_handles(event)' in source
    assert 'host._hit_test_gate_interior(event)' in source
    assert 'host._cursor_for_hover(event)' in source
    assert 'host._preview_gate()' in source
    assert 'host.canvas.draw_idle()' in source
