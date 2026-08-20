import ast
from pathlib import Path

from vflow.services.gate_lifecycle import (
    build_new_gate_plan,
    gate_selector_labels,
    plan_gate_delete,
    resolve_gate_selector,
)


def _gate(gid, name=None, applied=True):
    return {
        'id': gid,
        'name': name if name is not None else f'Gate {gid + 1}',
        'applied': applied,
    }


def test_new_gate_plan_preserves_manual_defaults_and_draw_target():
    plan = build_new_gate_plan(
        gate_id=3, gate_type='rectangle', color='#abc', auto_method=None,
    )
    assert plan.draw_gate_id == 3
    assert plan.gate['id'] == 3
    assert plan.gate['name'] == 'Gate 4'
    assert plan.gate['type'] == 'rectangle'
    assert plan.gate['color'] == '#abc'
    assert plan.gate['applied'] is False
    assert plan.gate['auto_method'] is None


def test_new_gate_plan_preserves_truthy_auto_apply_semantics():
    auto = {'x0': 1.0, 'x1': 2.0, 'y0': 3.0, 'y1': 4.0}
    plan = build_new_gate_plan(
        gate_id=7, gate_type='ellipse', color='red',
        auto_apply=auto, auto_method='gmm',
    )
    assert plan.draw_gate_id is None
    assert plan.gate['applied'] is True
    assert plan.gate['auto_method'] == 'gmm'
    for key, value in auto.items():
        assert plan.gate[key] == value


def test_new_gate_plan_preserves_frozen_empty_auto_apply_edge_case():
    plan = build_new_gate_plan(
        gate_id=5, gate_type='polygon', color='blue', auto_apply={},
    )
    assert plan.draw_gate_id == 5
    assert plan.gate['applied'] is False


def test_gate_delete_selects_nearest_neighbor_and_reports_transient_cleanup():
    gates = [_gate(0), _gate(1), _gate(2)]
    plan = plan_gate_delete(
        gates,
        gate_id=1,
        selected_gate_id=1,
        hover_gate_id=1,
        pinned_gate_id=0,
        draw_gate_id=1,
        stats_gate_ids={1: {}, 2: {}},
    )
    assert [g['id'] for g in plan.gates] == [0, 2]
    assert plan.selected_gate_id == 2
    assert plan.clear_hover is True
    assert plan.clear_pinned is False
    assert plan.clear_draw is True
    assert plan.remove_stats is True


def test_gate_delete_keeps_other_selection_and_does_not_overclear():
    gates = [_gate(0), _gate(1), _gate(2)]
    plan = plan_gate_delete(
        gates,
        gate_id=0,
        selected_gate_id=2,
        hover_gate_id=2,
        pinned_gate_id=2,
        draw_gate_id=None,
        stats_gate_ids={2: {}},
    )
    assert [g['id'] for g in plan.gates] == [1, 2]
    assert plan.selected_gate_id == 2
    assert plan.clear_hover is False
    assert plan.clear_pinned is False
    assert plan.clear_draw is False
    assert plan.remove_stats is False


def test_gate_delete_last_selected_gate_yields_none_selection():
    plan = plan_gate_delete(
        [_gate(9)],
        gate_id=9,
        selected_gate_id=9,
        hover_gate_id=None,
        pinned_gate_id=None,
        draw_gate_id=None,
        stats_gate_ids=(),
    )
    assert plan.gates == []
    assert plan.selected_gate_id is None


def test_selector_labels_ignore_unapplied_and_disambiguate_duplicates_by_id():
    gates = [
        _gate(1, 'A', True),
        _gate(2, 'A', True),
        _gate(3, 'B', True),
        _gate(4, 'A', False),
    ]
    assert gate_selector_labels(gates) == [
        'All cells', 'A [#1]', 'A [#2]', 'B'
    ]


def test_selector_fallback_name_and_resolution_are_frozen():
    gates = [
        {'id': 6, 'name': '', 'applied': True},
        {'id': 7, 'name': None, 'applied': True},
    ]
    assert gate_selector_labels(gates) == ['All cells', 'Gate 6', 'Gate 7']
    assert resolve_gate_selector(gates, 'Gate 6') is gates[0]
    assert resolve_gate_selector(gates, 'Gate 7') is gates[1]
    assert resolve_gate_selector(gates, 'All cells') is None
    assert resolve_gate_selector(gates, '') is None
    assert resolve_gate_selector(gates, 'missing') is None


def test_selector_never_returns_first_by_name_for_duplicate_applied_gates():
    gates = [_gate(1, 'dup'), _gate(2, 'dup')]
    assert resolve_gate_selector(gates, 'dup') is None
    assert resolve_gate_selector(gates, 'dup [#1]') is gates[0]
    assert resolve_gate_selector(gates, 'dup [#2]') is gates[1]


def test_gate_lifecycle_service_is_tk_free_and_legacy_methods_delegate():
    service = Path('vflow/services/gate_lifecycle.py').read_text()
    tree = ast.parse(service)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any(name == 'tkinter' or name.startswith('tkinter.') for name in imports)

    legacy = Path('vflow/legacy/vflow_app.py').read_text()
    assert 'return gate_selector_labels(self.gates)' in legacy
    assert 'return resolve_gate_selector(self.gates, choice)' in legacy
    assert 'plan  = build_new_gate_plan(' in legacy
    assert 'plan = plan_gate_delete(' in legacy
