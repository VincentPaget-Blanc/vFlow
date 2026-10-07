from vflow.controllers.gate_interaction_controller import GateInteractionController
from pathlib import Path

import pytest

from vflow.ui.gate_interaction import resolve_cached_handle_hover_cursor


def test_cursor_resolution_preserves_miss_center_and_other_handle_rules():
    assert resolve_cached_handle_hover_cursor(None) == 'hand2'
    assert resolve_cached_handle_hover_cursor(((7, 'center', None), 0.25)) == 'fleur'
    assert resolve_cached_handle_hover_cursor(((7, 'ne', 1), 0.25)) == 'sizing'
    assert resolve_cached_handle_hover_cursor(((0, 'vertex', 3), 0.0)) == 'sizing'


def test_cursor_resolution_preserves_exact_two_item_unpack_contract():
    with pytest.raises(ValueError):
        resolve_cached_handle_hover_cursor([('key',)])
    with pytest.raises(ValueError):
        resolve_cached_handle_hover_cursor([('key',), 1.0, 'extra'])


def test_cursor_resolution_uses_handle_name_at_key_position_one_without_normalizing():
    calls = []

    class Key:
        def __getitem__(self, index):
            calls.append(index)
            if index == 1:
                return 'center'
            raise AssertionError(f'unexpected key index {index}')

    assert resolve_cached_handle_hover_cursor((Key(), object())) == 'fleur'
    assert calls == [1]


def test_cursor_resolution_propagates_legacy_key_index_failure():
    class Key:
        def __getitem__(self, index):
            raise RuntimeError(f'key-index-{index}')

    with pytest.raises(RuntimeError, match='key-index-1'):
        resolve_cached_handle_hover_cursor((Key(), 1.0))


def test_flowapp_keeps_cache_event_threshold_and_nearest_geometry_in_cursor_controller():
    import inspect
    method = inspect.getsource(GateInteractionController.cursor_for_hover)

    workflow_call = method.index('resolve_hover_cursor_result_projection(')
    lookup_call = method.index('get_nearest_result=lambda: resolve_hover_cursor_nearest_result(')
    project_call = method.index('project_cursor=lambda nearest: resolve_cached_handle_hover_cursor(nearest)')
    assert workflow_call < lookup_call < project_call
    segment = method[workflow_call:project_call]
    assert 'get_cached_entries=lambda selected_gid: host._handle_px_cache.get(selected_gid, [])' in segment
    assert 'get_event_x=lambda: event.x' in segment
    assert 'get_event_y=lambda: event.y' in segment
    assert 'find_nearest=lambda entries, *, x, y, threshold: nearest_cached_handle(' in segment
    assert 'gate_id_value=None' in segment
    assert 'x=x' in segment
    assert 'y=y' in segment
    assert 'threshold=threshold' in segment
    assert 'prepare_resolution=lambda: HANDLE_PX * 2.5' in method
    assert 'hover_cursor_for_cached_handles(' not in method


def test_cursor_projection_helper_contains_no_cache_event_threshold_or_geometry_logic():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    start = source.index('def resolve_cached_handle_hover_cursor(')
    end = source.index('\n\ndef should_resolve_hover_cursor(', start)
    helper = source[start:end]

    assert 'nearest_cached_handle(' not in helper
    assert '_handle_px_cache' not in helper
    assert 'event.' not in helper
    assert 'HANDLE_PX' not in helper
    assert 'point_distance(' not in helper
    assert 'return "hand2"' in helper
    assert 'return "fleur" if key[1] == "center" else "sizing"' in helper
