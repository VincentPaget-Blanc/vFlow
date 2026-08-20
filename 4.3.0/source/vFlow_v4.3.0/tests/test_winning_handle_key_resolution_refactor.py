from pathlib import Path

import pytest

from vflow.core.gates import nearest_cached_handle
from vflow.ui.gate_interaction import (
    CachedHandleProjectionError,
    resolve_winning_cached_handle_key,
)


def test_resolution_preserves_none_and_returns_valid_handle_key_exactly():
    key = (0, 'center', None)
    assert resolve_winning_cached_handle_key(None) is None
    assert resolve_winning_cached_handle_key((key, 1.25)) is key


@pytest.mark.parametrize(
    'nearest_result',
    [
        [],
        [('gate', 'center', None), 1.25],
        ((1, 'center', None),),
        ((1, 'center', None), 1.25, 'extra'),
        'raw-result',
    ],
)
def test_resolution_rejects_noncanonical_nearest_result_shape(nearest_result):
    with pytest.raises(
        CachedHandleProjectionError,
        match=r'Nearest cached-handle result must be a 2-item tuple',
    ):
        resolve_winning_cached_handle_key(nearest_result)


@pytest.mark.parametrize(
    'handle_key',
    [
        None,
        'raw-key',
        [1, 'center', None],
        (1, 'center'),
        (1, 'center', None, 'extra'),
    ],
)
def test_resolution_rejects_noncanonical_handle_key_shape(handle_key):
    with pytest.raises(
        CachedHandleProjectionError,
        match=r'Nearest cached-handle key must be a 3-item tuple',
    ):
        resolve_winning_cached_handle_key((handle_key, 1.25))



def test_projection_accepts_real_nearest_cached_handle_output_without_normalization():
    nearest = nearest_cached_handle(
        [(10.0, 20.0, 'center', None)],
        gate_id_value=0,
        x=10.0,
        y=20.0,
        threshold=1.0,
    )
    assert nearest is not None
    assert resolve_winning_cached_handle_key(nearest) == (0, 'center', None)

def test_resolution_does_not_coerce_or_validate_valid_key_contents_or_distance():
    handle_name = object()
    index = object()
    distance = object()
    key = (0, handle_name, index)

    result = resolve_winning_cached_handle_key((key, distance))

    assert result is key
    assert result[0] == 0
    assert result[1] is handle_name
    assert result[2] is index


def test_resolution_does_not_execute_custom_getitem_on_invalid_result_object():
    calls = []

    class Result:
        def __getitem__(self, index):
            calls.append(index)
            raise RuntimeError(f'getitem-{index}')

    with pytest.raises(CachedHandleProjectionError):
        resolve_winning_cached_handle_key(Result())
    assert calls == []


def test_flowapp_keeps_cache_event_threshold_and_nearest_geometry_in_controller():
    source = Path('vflow/controllers/gate_interaction_controller.py').read_text()
    start = source.index('    def on_motion(')
    end = source.index('\n    def on_release(', start)
    method = source[start:end]

    nearest_call = method.index('resolve_nearest_handle=lambda gate_id: nearest_cached_handle(')
    projection_call = method.index('project_handle_key=lambda nearest: resolve_winning_cached_handle_key(nearest)')
    assert nearest_call < projection_call
    segment = method[nearest_call:projection_call]
    assert 'host._handle_px_cache.get(gate_id, [])' in segment
    assert 'gate_id_value=gate_id' in segment
    assert 'x=event.x' in segment
    assert 'y=event.y' in segment
    assert 'threshold=HANDLE_PX * 2.5' in segment
    assert 'nearest[0] if nearest is not None else None' not in method


def test_projection_helper_contains_validation_but_no_cache_event_threshold_or_geometry_logic():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    start = source.index('def resolve_winning_cached_handle_key(')
    end = source.index('\n\ndef run_hover_handle_proximity_execution_sequence(', start)
    helper = source[start:end]

    assert 'nearest_cached_handle(' not in helper
    assert '_handle_px_cache' not in helper
    assert 'event.' not in helper
    assert 'HANDLE_PX' not in helper
    assert 'point_distance(' not in helper
    assert 'isinstance(nearest_result, tuple)' in helper
    assert 'len(nearest_result) != 2' in helper
    assert 'isinstance(handle_key, tuple)' in helper
    assert 'len(handle_key) != 3' in helper
    assert 'CachedHandleProjectionError' in helper
