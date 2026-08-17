from vflow.controllers.gate_interaction_controller import GateInteractionController
from pathlib import Path

import pytest

from vflow.ui.gate_interaction import resolve_hover_cursor_result_projection


def test_result_projection_orchestration_resolves_before_projecting():
    calls = []
    nearest_result = object()
    cursor_result = object()

    def get_nearest_result():
        calls.append('nearest')
        return nearest_result

    def project_cursor(value):
        calls.append(('project', value is nearest_result))
        return cursor_result

    result = resolve_hover_cursor_result_projection(
        get_nearest_result=get_nearest_result,
        project_cursor=project_cursor,
    )

    assert result is cursor_result
    assert calls == ['nearest', ('project', True)]


def test_nearest_resolution_failure_prevents_projection():
    calls = []

    def get_nearest_result():
        calls.append('nearest')
        raise RuntimeError('nearest-resolution-fail')

    def project_cursor(_value):
        calls.append('project')
        return 'unused'

    with pytest.raises(RuntimeError, match='nearest-resolution-fail'):
        resolve_hover_cursor_result_projection(
            get_nearest_result=get_nearest_result,
            project_cursor=project_cursor,
        )

    assert calls == ['nearest']


def test_projection_failure_propagates_after_result_resolution():
    calls = []
    nearest_result = object()

    def get_nearest_result():
        calls.append('nearest')
        return nearest_result

    def project_cursor(value):
        calls.append(('project', value is nearest_result))
        raise RuntimeError('projection-fail')

    with pytest.raises(RuntimeError, match='projection-fail'):
        resolve_hover_cursor_result_projection(
            get_nearest_result=get_nearest_result,
            project_cursor=project_cursor,
        )

    assert calls == ['nearest', ('project', True)]


@pytest.mark.parametrize('nearest_result', [None, 0, '', [], 'result', (('key',), 1.0)])
def test_nearest_result_is_forwarded_without_normalization(nearest_result):
    seen = []

    result = resolve_hover_cursor_result_projection(
        get_nearest_result=lambda: nearest_result,
        project_cursor=lambda value: seen.append(value) or 'cursor',
    )

    assert result == 'cursor'
    assert len(seen) == 1
    assert seen[0] is nearest_result


def test_projection_workflow_is_presentation_orchestration_only():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    start = source.index('def resolve_hover_cursor_result_projection(')
    end = source.index('\n\n@dataclass(frozen=True)\nclass PinInteractionPlan', start)
    helper = source[start:end]

    assert '_handle_px_cache' not in helper
    assert 'event.' not in helper
    assert 'HANDLE_PX' not in helper
    assert 'nearest_cached_handle(' not in helper
    assert 'resolve_cached_handle_hover_cursor(' not in helper
    assert 'nearest_result = get_nearest_result()' in helper
    assert 'return project_cursor(nearest_result)' in helper


def test_flowapp_keeps_cursor_authorities_outside_projection_workflow():
    import inspect
    method = inspect.getsource(GateInteractionController.cursor_for_hover)

    assert 'should_resolve_hover_cursor(' in method
    assert 'get_handle_drag=lambda: host._handle_drag' in method
    assert 'get_hover_gate_id=lambda: host._hover_gate_id' in method
    assert 'get_pinned_gate_id=lambda: host._pinned_gate_id' in method
    assert 'prepare_resolution=lambda: HANDLE_PX * 2.5' in method
    assert 'resolve_hover_cursor_gate_id(' in method
    assert 'resolve_hover_cursor_result_projection(' in method
    assert 'get_nearest_result=lambda: resolve_hover_cursor_nearest_result(' in method
    assert 'get_cached_entries=lambda selected_gid: host._handle_px_cache.get(selected_gid, [])' in method
    assert 'get_event_x=lambda: event.x' in method
    assert 'get_event_y=lambda: event.y' in method
    assert 'find_nearest=lambda entries, *, x, y, threshold: nearest_cached_handle(' in method
    assert 'gate_id_value=None' in method
    assert 'project_cursor=lambda nearest: resolve_cached_handle_hover_cursor(nearest)' in method
