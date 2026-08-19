from vflow.controllers.gate_interaction_controller import GateInteractionController
from pathlib import Path

import pytest

from vflow.ui.gate_interaction import resolve_hover_cursor_workflow


def test_inactive_workflow_returns_legacy_empty_cursor_and_stops_after_activation():
    calls = []

    result = resolve_hover_cursor_workflow(
        should_resolve=lambda: calls.append('activation') or False,
        prepare_resolution=lambda: calls.append('prepare'),
        resolve_gate_id=lambda: calls.append('gate'),
        resolve_cursor_for_gate=lambda *_args: calls.append('cursor'),
    )

    assert result == ''
    assert calls == ['activation']


def test_active_workflow_preserves_activation_prepare_gate_cursor_order():
    calls = []
    context = object()
    gate_id = object()
    cursor = object()

    def resolve_cursor(gid, prepared):
        calls.append(('cursor', gid is gate_id, prepared is context))
        return cursor

    result = resolve_hover_cursor_workflow(
        should_resolve=lambda: calls.append('activation') or True,
        prepare_resolution=lambda: calls.append('prepare') or context,
        resolve_gate_id=lambda: calls.append('gate') or gate_id,
        resolve_cursor_for_gate=resolve_cursor,
    )

    assert result is cursor
    assert calls == ['activation', 'prepare', 'gate', ('cursor', True, True)]


def test_activation_failure_prevents_all_later_work():
    calls = []

    def activation():
        calls.append('activation')
        raise RuntimeError('activation-fail')

    with pytest.raises(RuntimeError, match='activation-fail'):
        resolve_hover_cursor_workflow(
            should_resolve=activation,
            prepare_resolution=lambda: calls.append('prepare'),
            resolve_gate_id=lambda: calls.append('gate'),
            resolve_cursor_for_gate=lambda *_args: calls.append('cursor'),
        )

    assert calls == ['activation']


def test_prepare_failure_happens_before_gate_source_resolution():
    calls = []

    def prepare():
        calls.append('prepare')
        raise RuntimeError('prepare-fail')

    with pytest.raises(RuntimeError, match='prepare-fail'):
        resolve_hover_cursor_workflow(
            should_resolve=lambda: calls.append('activation') or True,
            prepare_resolution=prepare,
            resolve_gate_id=lambda: calls.append('gate'),
            resolve_cursor_for_gate=lambda *_args: calls.append('cursor'),
        )

    assert calls == ['activation', 'prepare']


def test_gate_source_failure_happens_after_prepare_and_before_cursor_resolution():
    calls = []

    def gate():
        calls.append('gate')
        raise RuntimeError('gate-fail')

    with pytest.raises(RuntimeError, match='gate-fail'):
        resolve_hover_cursor_workflow(
            should_resolve=lambda: calls.append('activation') or True,
            prepare_resolution=lambda: calls.append('prepare') or 25.0,
            resolve_gate_id=gate,
            resolve_cursor_for_gate=lambda *_args: calls.append('cursor'),
        )

    assert calls == ['activation', 'prepare', 'gate']


def test_cursor_failure_propagates_after_gate_and_preparation():
    calls = []

    def cursor(gid, context):
        calls.append(('cursor', gid, context))
        raise RuntimeError('cursor-fail')

    with pytest.raises(RuntimeError, match='cursor-fail'):
        resolve_hover_cursor_workflow(
            should_resolve=lambda: calls.append('activation') or True,
            prepare_resolution=lambda: calls.append('prepare') or 12.5,
            resolve_gate_id=lambda: calls.append('gate') or 7,
            resolve_cursor_for_gate=cursor,
        )

    assert calls == ['activation', 'prepare', 'gate', ('cursor', 7, 12.5)]


def test_activation_result_is_truth_tested_once():
    calls = []

    class Activation:
        def __bool__(self):
            calls.append('bool')
            return False

    result = resolve_hover_cursor_workflow(
        should_resolve=lambda: calls.append('activation') or Activation(),
        prepare_resolution=lambda: calls.append('prepare'),
        resolve_gate_id=lambda: calls.append('gate'),
        resolve_cursor_for_gate=lambda *_args: calls.append('cursor'),
    )

    assert result == ''
    assert calls == ['activation', 'bool']


def test_context_and_gate_id_are_forwarded_without_normalization():
    context = []
    gate_id = 0
    seen = []

    result = resolve_hover_cursor_workflow(
        should_resolve=lambda: True,
        prepare_resolution=lambda: context,
        resolve_gate_id=lambda: gate_id,
        resolve_cursor_for_gate=lambda gid, prepared: seen.append((gid, prepared)) or 'hand2',
    )

    assert result == 'hand2'
    assert seen == [(0, context)]
    assert seen[0][1] is context


def test_workflow_helper_owns_only_sequence_not_cursor_authorities():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    start = source.index('def resolve_hover_cursor_workflow(')
    end = source.index('\n\n@dataclass(frozen=True)\nclass PinInteractionPlan', start)
    helper = source[start:end]

    assert 'if should_resolve():' in helper
    assert 'resolution_context = prepare_resolution()' in helper
    assert 'gate_id = resolve_gate_id()' in helper
    assert 'return resolve_cursor_for_gate(gate_id, resolution_context)' in helper
    assert "return ''" in helper
    assert 'HANDLE_PX' not in helper
    assert '_handle_px_cache' not in helper
    assert 'event.x' not in helper
    assert 'event.y' not in helper
    assert 'nearest_cached_handle(' not in helper
    assert 'resolve_cached_handle_hover_cursor(' not in helper


def test_flowapp_keeps_all_concrete_cursor_authorities_in_callbacks():
    import inspect
    method = inspect.getsource(GateInteractionController.cursor_for_hover)

    assert 'return resolve_hover_cursor_workflow(' in method
    assert 'should_resolve=lambda: should_resolve_hover_cursor(' in method
    assert 'prepare_resolution=lambda: HANDLE_PX * 2.5' in method
    assert 'resolve_gate_id=lambda: resolve_hover_cursor_gate_id(' in method
    assert 'resolve_cursor_for_gate=lambda gid, threshold: resolve_hover_cursor_result_projection(' in method
    assert 'get_cached_entries=lambda selected_gid: host._handle_px_cache.get(selected_gid, [])' in method
    assert 'get_event_x=lambda: event.x' in method
    assert 'get_event_y=lambda: event.y' in method
    assert 'find_nearest=lambda entries, *, x, y, threshold: nearest_cached_handle(' in method
    assert 'project_cursor=lambda nearest: resolve_cached_handle_hover_cursor(nearest)' in method


def test_controller_callback_source_order_matches_frozen_workflow_order():
    import inspect
    method = inspect.getsource(GateInteractionController.cursor_for_hover)

    activation = method.index('should_resolve=lambda: should_resolve_hover_cursor(')
    prepare = method.index('prepare_resolution=lambda: HANDLE_PX * 2.5')
    gate = method.index('resolve_gate_id=lambda: resolve_hover_cursor_gate_id(')
    cursor = method.index('resolve_cursor_for_gate=lambda gid, threshold: resolve_hover_cursor_result_projection(')
    assert activation < prepare < gate < cursor
