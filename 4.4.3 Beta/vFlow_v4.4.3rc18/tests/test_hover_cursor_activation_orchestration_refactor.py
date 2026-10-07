from vflow.controllers.gate_interaction_controller import GateInteractionController
from pathlib import Path

import pytest

from vflow.ui.gate_interaction import should_resolve_hover_cursor


def test_truthy_drag_activates_without_reading_hover_or_pin():
    calls = []

    def drag():
        calls.append('drag')
        return {'gate_id': 7}

    def hover():
        calls.append('hover')
        raise AssertionError('hover must remain lazy after truthy drag')

    def pinned():
        calls.append('pinned')
        raise AssertionError('pinned must remain lazy after truthy drag')

    assert should_resolve_hover_cursor(
        get_handle_drag=drag,
        get_hover_gate_id=hover,
        get_pinned_gate_id=pinned,
    ) is True
    assert calls == ['drag']


def test_truthy_hover_activates_after_falsey_drag_without_reading_pin():
    calls = []

    def drag():
        calls.append('drag')
        return None

    def hover():
        calls.append('hover')
        return 9

    def pinned():
        calls.append('pinned')
        raise AssertionError('pinned must remain lazy after truthy hover')

    assert should_resolve_hover_cursor(
        get_handle_drag=drag,
        get_hover_gate_id=hover,
        get_pinned_gate_id=pinned,
    ) is True
    assert calls == ['drag', 'hover']


def test_gate_id_zero_activates_after_falsey_drag_without_reading_pin():
    calls = []

    def getter(name, value):
        def get():
            calls.append(name)
            return value
        return get

    assert should_resolve_hover_cursor(
        get_handle_drag=getter('drag', {}),
        get_hover_gate_id=getter('hover', 0),
        get_pinned_gate_id=getter('pinned', 12),
    ) is True
    assert calls == ['drag', 'hover']


def test_none_hover_and_none_pin_return_false():
    calls = []

    def getter(name, value):
        def get():
            calls.append((name, value))
            return value
        return get

    assert should_resolve_hover_cursor(
        get_handle_drag=getter('drag', None),
        get_hover_gate_id=getter('hover', None),
        get_pinned_gate_id=getter('pinned', None),
    ) is False
    assert calls == [('drag', None), ('hover', None), ('pinned', None)]


def test_gate_id_zero_is_present_and_does_not_fall_through_to_pin():
    calls = []

    def hover():
        calls.append('hover')
        return 0

    def pinned():
        calls.append('pinned')
        return 5

    assert should_resolve_hover_cursor(
        get_handle_drag=lambda: None,
        get_hover_gate_id=hover,
        get_pinned_gate_id=pinned,
    ) is True
    assert calls == ['hover']


def test_gate_id_sources_use_presence_not_truth_testing():
    calls = []

    class Value:
        def __bool__(self):
            calls.append('unexpected-bool')
            raise AssertionError('gate IDs must use presence checks, not truth testing')

    assert should_resolve_hover_cursor(
        get_handle_drag=lambda: None,
        get_hover_gate_id=lambda: calls.append('hover-get') or Value(),
        get_pinned_gate_id=lambda: calls.append('pinned-get') or 3,
    ) is True
    assert calls == ['hover-get']


@pytest.mark.parametrize('failure_source', ['drag', 'hover', 'pinned'])
def test_getter_failures_propagate_at_the_same_short_circuit_position(failure_source):
    calls = []

    def getter(name):
        def get():
            calls.append(name)
            if name == failure_source:
                raise RuntimeError(f'{name}-fail')
            return None
        return get

    with pytest.raises(RuntimeError, match=f'{failure_source}-fail'):
        should_resolve_hover_cursor(
            get_handle_drag=getter('drag'),
            get_hover_gate_id=getter('hover'),
            get_pinned_gate_id=getter('pinned'),
        )

    expected = {
        'drag': ['drag'],
        'hover': ['drag', 'hover'],
        'pinned': ['drag', 'hover', 'pinned'],
    }[failure_source]
    assert calls == expected


def test_truthiness_failure_propagates_without_reading_later_sources():
    calls = []

    class BadBool:
        def __bool__(self):
            calls.append('bool-drag')
            raise RuntimeError('drag-bool-fail')

    def hover():
        calls.append('hover')
        return 1

    with pytest.raises(RuntimeError, match='drag-bool-fail'):
        should_resolve_hover_cursor(
            get_handle_drag=lambda: BadBool(),
            get_hover_gate_id=hover,
            get_pinned_gate_id=lambda: 2,
        )
    assert calls == ['bool-drag']


def test_activation_helper_owns_no_selection_cache_event_geometry_or_projection_logic():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    start = source.index('def should_resolve_hover_cursor(')
    end = source.index('\n\ndef resolve_hover_cursor_gate_id(', start)
    helper = source[start:end]

    assert "if get_handle_drag():" in helper
    assert "hover_gate_id = get_hover_gate_id()" in helper
    assert "if hover_gate_id is not None:" in helper
    assert "return get_pinned_gate_id() is not None" in helper
    assert "['gate_id']" not in helper
    assert '_handle_px_cache' not in helper
    assert 'event.x' not in helper
    assert 'event.y' not in helper
    assert 'HANDLE_PX' not in helper
    assert 'nearest_cached_handle(' not in helper
    assert 'resolve_cached_handle_hover_cursor(' not in helper


def test_flowapp_delegates_only_activation_decision_and_keeps_cursor_authorities_local():
    import inspect
    method = inspect.getsource(GateInteractionController.cursor_for_hover)

    assert 'should_resolve_hover_cursor(' in method
    assert 'get_handle_drag=lambda: host._handle_drag' in method
    assert 'get_hover_gate_id=lambda: host._hover_gate_id' in method
    assert 'get_pinned_gate_id=lambda: host._pinned_gate_id' in method
    assert 'prepare_resolution=lambda: HANDLE_PX * 2.5' in method
    assert 'resolve_hover_cursor_gate_id(' in method
    assert 'get_cached_entries=lambda selected_gid: host._handle_px_cache.get(selected_gid, [])' in method
    assert 'get_event_x=lambda: event.x' in method
    assert 'get_event_y=lambda: event.y' in method
    assert 'nearest_cached_handle(' in method
    assert 'gate_id_value=None' in method
    assert 'resolve_cached_handle_hover_cursor(nearest)' in method
    assert 'return resolve_hover_cursor_workflow(' in method
