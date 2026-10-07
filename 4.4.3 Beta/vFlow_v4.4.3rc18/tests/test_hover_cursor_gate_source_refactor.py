from vflow.controllers.gate_interaction_controller import GateInteractionController
from pathlib import Path

import pytest

from vflow.ui.gate_interaction import resolve_hover_cursor_gate_id


def test_drag_source_wins_without_reading_hover_or_pin_getters():
    calls = []

    def hover():
        calls.append('hover')
        raise AssertionError('hover getter must stay lazy during drag')

    def pinned():
        calls.append('pinned')
        raise AssertionError('pinned getter must stay lazy during drag')

    drag = {'gate_id': 7}

    def get_drag():
        calls.append('drag')
        return drag

    assert resolve_hover_cursor_gate_id(
        get_handle_drag=get_drag,
        get_hover_gate_id=hover,
        get_pinned_gate_id=pinned,
    ) == 7
    assert calls == ['drag', 'drag']


def test_hover_source_wins_and_pinned_getter_remains_lazy():
    calls = []

    def hover():
        calls.append('hover')
        return 9

    def pinned():
        calls.append('pinned')
        raise AssertionError('pinned getter must stay lazy after truthy hover')

    assert resolve_hover_cursor_gate_id(
        get_handle_drag=lambda: None,
        get_hover_gate_id=hover,
        get_pinned_gate_id=pinned,
    ) == 9
    assert calls == ['hover']


def test_gate_id_zero_hover_wins_without_reading_pinned():
    calls = []

    def hover():
        calls.append('hover')
        return 0

    def pinned():
        calls.append('pinned')
        return 12

    assert resolve_hover_cursor_gate_id(
        get_handle_drag=lambda: {},
        get_hover_gate_id=hover,
        get_pinned_gate_id=pinned,
    ) == 0
    assert calls == ['hover']


def test_falsey_pinned_value_is_returned_without_normalization():
    assert resolve_hover_cursor_gate_id(
        get_handle_drag=lambda: None,
        get_hover_gate_id=lambda: None,
        get_pinned_gate_id=lambda: 0,
    ) == 0


def test_drag_gate_id_lookup_preserves_mapping_exception():
    class Drag(dict):
        def __getitem__(self, key):
            raise RuntimeError(f'drag-key-{key}')

    with pytest.raises(RuntimeError, match='drag-key-gate_id'):
        resolve_hover_cursor_gate_id(
            get_handle_drag=lambda: Drag(x=1),
            get_hover_gate_id=lambda: 2,
            get_pinned_gate_id=lambda: 3,
        )


def test_flowapp_keeps_outer_truthiness_and_all_cache_geometry_work_in_controller():
    import inspect
    method = inspect.getsource(GateInteractionController.cursor_for_hover)

    assert 'should_resolve_hover_cursor(' in method
    assert 'get_handle_drag=lambda: host._handle_drag' in method
    assert 'get_hover_gate_id=lambda: host._hover_gate_id' in method
    assert 'get_pinned_gate_id=lambda: host._pinned_gate_id' in method
    assert 'resolve_hover_cursor_gate_id(' in method
    assert 'get_handle_drag=lambda: host._handle_drag' in method
    assert 'get_hover_gate_id=lambda: host._hover_gate_id' in method
    assert 'get_pinned_gate_id=lambda: host._pinned_gate_id' in method
    activation_call = method.index('should_resolve_hover_cursor(')
    resolve_call = method.index('resolve_hover_cursor_gate_id(')
    workflow_call = method.index('resolve_hover_cursor_result_projection(')
    lookup_call = method.index('get_nearest_result=lambda: resolve_hover_cursor_nearest_result(')
    assert activation_call < resolve_call < workflow_call < lookup_call
    assert 'get_cached_entries=lambda selected_gid: host._handle_px_cache.get(selected_gid, [])' in method
    assert 'get_event_x=lambda: event.x' in method
    assert 'get_event_y=lambda: event.y' in method
    assert 'find_nearest=lambda entries, *, x, y, threshold: nearest_cached_handle(' in method
    assert 'gate_id_value=None' in method
    assert 'prepare_resolution=lambda: HANDLE_PX * 2.5' in method


def test_gate_source_helper_contains_no_cache_event_threshold_or_geometry_logic():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    start = source.index('def resolve_hover_cursor_gate_id(')
    end = source.index('\n\ndef resolve_hover_cursor_nearest_result(', start)
    helper = source[start:end]

    assert '_handle_px_cache' not in helper
    assert 'event.' not in helper
    assert 'HANDLE_PX' not in helper
    assert 'nearest_cached_handle(' not in helper
    assert 'return get_handle_drag()[\'gate_id\']' in helper
    assert 'hover_gate_id = get_hover_gate_id()' in helper
    assert 'if hover_gate_id is not None:' in helper
    assert 'return hover_gate_id' in helper
    assert 'return get_pinned_gate_id()' in helper
