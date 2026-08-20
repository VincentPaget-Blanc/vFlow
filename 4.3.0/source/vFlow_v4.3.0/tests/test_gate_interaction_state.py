import ast
from pathlib import Path

from vflow.ui.gate_interaction import GateInteractionState


def test_gate_interaction_state_defaults_and_clear():
    state = GateInteractionState(
        selected_gate_id=1,
        draw_gate_id=2,
        hover_gate_id=3,
        interior_hover_gate_id=4,
        pinned_gate_id=5,
    )
    state.clear_gate_references()
    assert state == GateInteractionState()


def test_gate_interaction_state_is_plain_and_tk_free():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any(name == 'tkinter' or name.startswith('tkinter.') for name in imports)


def test_flowapp_legacy_gate_id_properties_share_one_interaction_owner():
    from vflow.legacy.vflow_app import FlowApp

    app = FlowApp.__new__(FlowApp)
    app._sel_gate_id = 11
    app._draw_gate_id = 12
    app._hover_gate_id = 13
    app._interior_hover_gate_id = 14
    app._pinned_gate_id = 15

    state = app._gate_interaction_state_obj()
    assert state.selected_gate_id == 11
    assert state.draw_gate_id == 12
    assert state.hover_gate_id == 13
    assert state.interior_hover_gate_id == 14
    assert state.pinned_gate_id == 15
    assert app.__dict__['_gate_interaction_state'] is state


def test_flowapp_property_writes_and_state_writes_are_bidirectional():
    from vflow.legacy.vflow_app import FlowApp

    app = FlowApp.__new__(FlowApp)
    state = app._gate_interaction_state_obj()
    state.selected_gate_id = 21
    state.draw_gate_id = 22
    state.hover_gate_id = 23
    state.interior_hover_gate_id = 24
    state.pinned_gate_id = 25

    assert app._sel_gate_id == 21
    assert app._draw_gate_id == 22
    assert app._hover_gate_id == 23
    assert app._interior_hover_gate_id == 24
    assert app._pinned_gate_id == 25
