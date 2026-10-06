from pathlib import Path

import pytest

from vflow.ui.gate_interaction import run_hover_handle_proximity_execution_sequence


def test_none_handle_gate_skips_nearest_and_projection():
    log = []

    result = run_hover_handle_proximity_execution_sequence(
        resolve_handle_gate_id=lambda: log.append('handle_gate') or None,
        resolve_nearest_handle=lambda gate_id: log.append(('nearest', gate_id)),
        project_handle_key=lambda nearest: log.append(('project', nearest)),
    )

    assert result == (None, None)
    assert log == ['handle_gate']


def test_gate_id_zero_is_not_none_and_runs_nearest_and_projection():
    log = []

    result = run_hover_handle_proximity_execution_sequence(
        resolve_handle_gate_id=lambda: log.append('handle_gate') or 0,
        resolve_nearest_handle=lambda gate_id: log.append(('nearest', gate_id)) or (('g', 'h'), 2.0),
        project_handle_key=lambda nearest: log.append(('project', nearest)) or nearest[0],
    )

    assert result == (0, ('g', 'h'))
    assert log == [
        'handle_gate',
        ('nearest', 0),
        ('project', (('g', 'h'), 2.0)),
    ]


def test_nearest_none_is_still_forwarded_to_projection():
    log = []

    result = run_hover_handle_proximity_execution_sequence(
        resolve_handle_gate_id=lambda: 7,
        resolve_nearest_handle=lambda gate_id: log.append(('nearest', gate_id)) or None,
        project_handle_key=lambda nearest: log.append(('project', nearest)) or 'sentinel',
    )

    assert result == (7, 'sentinel')
    assert log == [('nearest', 7), ('project', None)]


def test_handle_gate_failure_stops_before_nearest():
    log = []

    def fail_gate():
        log.append('handle_gate')
        raise RuntimeError('gate-fail')

    with pytest.raises(RuntimeError, match='gate-fail'):
        run_hover_handle_proximity_execution_sequence(
            resolve_handle_gate_id=fail_gate,
            resolve_nearest_handle=lambda gate_id: log.append('nearest'),
            project_handle_key=lambda nearest: log.append('project'),
        )

    assert log == ['handle_gate']


def test_nearest_failure_stops_before_projection():
    log = []

    def fail_nearest(gate_id):
        log.append(('nearest', gate_id))
        raise RuntimeError('nearest-fail')

    with pytest.raises(RuntimeError, match='nearest-fail'):
        run_hover_handle_proximity_execution_sequence(
            resolve_handle_gate_id=lambda: 9,
            resolve_nearest_handle=fail_nearest,
            project_handle_key=lambda nearest: log.append('project'),
        )

    assert log == [('nearest', 9)]


def test_projection_failure_occurs_only_after_nearest_success():
    log = []

    def fail_projection(nearest):
        log.append(('project', nearest))
        raise RuntimeError('project-fail')

    nearest = (('key', 'edge'), 1.5)
    with pytest.raises(RuntimeError, match='project-fail'):
        run_hover_handle_proximity_execution_sequence(
            resolve_handle_gate_id=lambda: 3,
            resolve_nearest_handle=lambda gate_id: log.append(('nearest', gate_id)) or nearest,
            project_handle_key=fail_projection,
        )

    assert log == [('nearest', 3), ('project', nearest)]


def test_flowapp_retains_concrete_handle_cache_event_threshold_and_geometry_authority():
    source = Path('vflow/controllers/gate_interaction_controller.py').read_text()
    start = source.index('new_hover, new_hover_handle_key = run_hover_handle_proximity_execution_sequence(')
    end = source.index('\n\n                # If no handle nearby', start)
    block = source[start:end]

    assert 'host._hover_test_handles(event)' in block
    assert 'nearest_cached_handle(' in block
    assert 'host._handle_px_cache.get(gate_id, [])' in block
    assert 'gate_id_value=gate_id' in block
    assert 'x=event.x' in block
    assert 'y=event.y' in block
    assert 'threshold=HANDLE_PX * 2.5' in block
    assert 'resolve_winning_cached_handle_key(nearest)' in block


def test_controller_keeps_cache_x_y_threshold_order_inside_lazy_nearest_callback():
    source = Path('vflow/controllers/gate_interaction_controller.py').read_text()
    start = source.index('resolve_nearest_handle=lambda gate_id: nearest_cached_handle(')
    end = source.index('\n                    ),', start)
    block = source[start:end]

    assert block.index('host._handle_px_cache.get(gate_id, [])') < block.index('x=event.x')
    assert block.index('x=event.x') < block.index('y=event.y')
    assert block.index('y=event.y') < block.index('threshold=HANDLE_PX * 2.5')


def test_helper_has_no_concrete_controller_cache_event_threshold_or_geometry_authority():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    start = source.index('def run_hover_handle_proximity_execution_sequence(')
    end = source.index('\n\ndef resolve_cached_handle_hover_cursor', start)
    helper = source[start:end]

    assert 'self.' not in helper
    assert 'event.' not in helper
    assert '_handle_px_cache' not in helper
    assert 'HANDLE_PX' not in helper
    assert 'nearest_cached_handle' not in helper
    assert 'resolve_winning_cached_handle_key' not in helper
    assert 'canvas' not in helper


def test_helper_uses_is_not_none_not_truthiness_for_handle_gate():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    start = source.index('def run_hover_handle_proximity_execution_sequence(')
    end = source.index('\n\ndef resolve_cached_handle_hover_cursor', start)
    helper = source[start:end]

    assert 'if handle_gate_id is not None:' in helper
    assert 'if handle_gate_id:' not in helper
