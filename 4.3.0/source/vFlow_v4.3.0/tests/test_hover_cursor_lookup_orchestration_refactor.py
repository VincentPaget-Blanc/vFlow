from vflow.controllers.gate_interaction_controller import GateInteractionController
from pathlib import Path

import pytest

from vflow.ui.gate_interaction import resolve_hover_cursor_nearest_result


def test_lookup_orchestration_preserves_cache_x_y_nearest_order():
    calls = []

    def get_entries(gid):
        calls.append(('cache', gid))
        return [('h', gid)]

    def get_x():
        calls.append(('x',))
        return 10

    def get_y():
        calls.append(('y',))
        return 20

    def find_nearest(entries, *, x, y, threshold):
        calls.append(('nearest', entries, x, y, threshold))
        return (('key',), 1.5)

    result = resolve_hover_cursor_nearest_result(
        gate_id=7,
        get_cached_entries=get_entries,
        get_event_x=get_x,
        get_event_y=get_y,
        threshold=25.0,
        find_nearest=find_nearest,
    )
    assert result == (('key',), 1.5)
    assert calls == [
        ('cache', 7),
        ('x',),
        ('y',),
        ('nearest', [('h', 7)], 10, 20, 25.0),
    ]


def test_cache_failure_prevents_event_reads_and_nearest_call():
    calls = []

    def get_entries(_gid):
        calls.append('cache')
        raise RuntimeError('cache-fail')

    with pytest.raises(RuntimeError, match='cache-fail'):
        resolve_hover_cursor_nearest_result(
            gate_id=7,
            get_cached_entries=get_entries,
            get_event_x=lambda: calls.append('x'),
            get_event_y=lambda: calls.append('y'),
            threshold=1,
            find_nearest=lambda *_args, **_kwargs: calls.append('nearest'),
        )
    assert calls == ['cache']


def test_x_failure_happens_after_cache_and_before_y():
    calls = []

    def get_x():
        calls.append('x')
        raise RuntimeError('x-fail')

    with pytest.raises(RuntimeError, match='x-fail'):
        resolve_hover_cursor_nearest_result(
            gate_id=3,
            get_cached_entries=lambda gid: calls.append(('cache', gid)) or [],
            get_event_x=get_x,
            get_event_y=lambda: calls.append('y'),
            threshold=1,
            find_nearest=lambda *_args, **_kwargs: calls.append('nearest'),
        )
    assert calls == [('cache', 3), 'x']


def test_y_failure_happens_after_cache_and_x_and_before_nearest():
    calls = []

    def get_y():
        calls.append('y')
        raise RuntimeError('y-fail')

    with pytest.raises(RuntimeError, match='y-fail'):
        resolve_hover_cursor_nearest_result(
            gate_id=3,
            get_cached_entries=lambda gid: calls.append(('cache', gid)) or [],
            get_event_x=lambda: calls.append('x') or 1,
            get_event_y=get_y,
            threshold=1,
            find_nearest=lambda *_args, **_kwargs: calls.append('nearest'),
        )
    assert calls == [('cache', 3), 'x', 'y']


def test_nearest_exception_propagates_after_all_lookup_inputs():
    calls = []

    def nearest(entries, *, x, y, threshold):
        calls.append(('nearest', entries, x, y, threshold))
        raise RuntimeError('nearest-fail')

    with pytest.raises(RuntimeError, match='nearest-fail'):
        resolve_hover_cursor_nearest_result(
            gate_id=0,
            get_cached_entries=lambda gid: calls.append(('cache', gid)) or ['entry'],
            get_event_x=lambda: calls.append('x') or 4,
            get_event_y=lambda: calls.append('y') or 5,
            threshold=6,
            find_nearest=nearest,
        )
    assert calls == [('cache', 0), 'x', 'y', ('nearest', ['entry'], 4, 5, 6)]


def test_lookup_helper_is_geometry_and_ui_independent():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    start = source.index('def resolve_hover_cursor_nearest_result(')
    end = source.index('\n\ndef resolve_hover_cursor_result_projection(', start)
    helper = source[start:end]

    assert '_handle_px_cache' not in helper
    assert 'event.' not in helper
    assert 'HANDLE_PX' not in helper
    assert 'nearest_cached_handle(' not in helper
    assert 'get_cached_entries(gate_id)' in helper
    assert 'get_event_x()' in helper
    assert 'get_event_y()' in helper
    assert 'find_nearest(entries, x=x, y=y, threshold=threshold)' in helper


def test_flowapp_retains_cache_event_threshold_and_nearest_authority():
    import inspect
    method = inspect.getsource(GateInteractionController.cursor_for_hover)

    assert 'prepare_resolution=lambda: HANDLE_PX * 2.5' in method
    assert 'get_cached_entries=lambda selected_gid: host._handle_px_cache.get(selected_gid, [])' in method
    assert 'get_event_x=lambda: event.x' in method
    assert 'get_event_y=lambda: event.y' in method
    assert 'find_nearest=lambda entries, *, x, y, threshold: nearest_cached_handle(' in method
    assert 'gate_id_value=None' in method
    assert 'x=x' in method
    assert 'y=y' in method
    assert 'threshold=threshold' in method
