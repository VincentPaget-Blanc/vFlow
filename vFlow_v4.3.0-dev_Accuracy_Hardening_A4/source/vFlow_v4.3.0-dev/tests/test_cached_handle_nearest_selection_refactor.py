from vflow.controllers.gate_interaction_controller import GateInteractionController
from pathlib import Path

import pytest

from vflow.legacy.vflow_app import FlowApp, HANDLE_PX
from vflow.ui.gate_interaction import select_nearest_cached_handle_gate


def test_reducer_selects_strictly_nearest_gate_and_preserves_first_tie():
    candidates = [
        (7, ((7, 'x0', None), 4.0)),
        (8, ((8, 'x1', None), 2.0)),
        (9, ((9, 'center', None), 2.0)),
    ]
    assert select_nearest_cached_handle_gate(candidates) == 8


def test_reducer_skips_none_hits_and_preserves_gate_zero():
    candidates = [
        (5, None),
        (0, ((0, 'center', None), 1.25)),
        (2, None),
    ]
    assert select_nearest_cached_handle_gate(candidates) == 0
    assert select_nearest_cached_handle_gate([(1, None), (2, None)]) is None


def test_reducer_consumes_candidates_lazily_and_propagates_late_failure():
    calls = []

    def candidates():
        calls.append('first')
        yield 1, ((1, 'x0', None), 3.0)
        calls.append('second')
        yield 2, ((2, 'x1', None), 1.0)
        calls.append('boom')
        raise RuntimeError('late candidate failure')

    with pytest.raises(RuntimeError, match='late candidate failure'):
        select_nearest_cached_handle_gate(candidates())
    assert calls == ['first', 'second', 'boom']


def test_reducer_keeps_frozen_nan_and_infinity_comparison_semantics():
    nan = float('nan')
    inf = float('inf')
    assert select_nearest_cached_handle_gate([
        (1, ((1, 'a', None), nan)),
        (2, ((2, 'b', None), 4.0)),
    ]) == 2
    assert select_nearest_cached_handle_gate([
        (1, ((1, 'a', None), inf)),
    ]) is None


class _LoggedEvent:
    def __init__(self, x, y):
        self._x = x
        self._y = y
        self.reads = []

    @property
    def x(self):
        self.reads.append('x')
        return self._x

    @property
    def y(self):
        self.reads.append('y')
        return self._y


def test_flowapp_hover_test_preserves_repeated_event_read_order_and_nearest_gate():
    app = FlowApp.__new__(FlowApp)
    # Two gates with one cached handle each.  Gate 2 is nearer.
    app._handle_px_cache = {
        1: [(0.0, 0.0, 'x0', None)],
        2: [(8.0, 9.0, 'center', None)],
    }
    event = _LoggedEvent(10.0, 10.0)
    assert app._hover_test_handles(event) == 2
    # Frozen implementation reads x then y independently for every gate.
    assert event.reads == ['x', 'y', 'x', 'y']


def test_flowapp_hover_test_keeps_per_gate_geometry_and_threshold_in_controller():
    import inspect
    method = inspect.getsource(GateInteractionController.hover_test_handles)

    assert 'threshold = HANDLE_PX * 2.5' in method
    assert 'nearest_cached_handle(' in method
    assert 'x=event.x' in method
    assert 'y=event.y' in method
    assert 'select_nearest_cached_handle_gate(candidates)' in method
    assert method.index('nearest_cached_handle(') < method.index('select_nearest_cached_handle_gate(candidates)')


def test_reducer_does_not_import_or_call_geometry_helpers():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    start = source.index('def select_nearest_cached_handle_gate(')
    end = source.index('\n\n@dataclass(frozen=True)\nclass PinInteractionPlan', start)
    helper = source[start:end]
    # It may document the legacy per-gate helper, but must not execute it.
    executable = helper.replace('``vflow.core.gates.nearest_cached_handle``', '')
    assert 'nearest_cached_handle(' not in executable
    assert 'point_distance(' not in executable
    assert 'HANDLE_PX' not in executable
