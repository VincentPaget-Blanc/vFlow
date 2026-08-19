from vflow.controllers.gate_interaction_controller import GateInteractionController
import ast
from pathlib import Path

import pytest

from vflow.ui.gate_interaction import iter_handle_pixel_cache_entries


def test_builder_skips_unapplied_and_preserves_gate_identity_and_order():
    g0 = {'id': 0, 'applied': False}
    g1 = {'id': 1, 'applied': True}
    g2 = {'id': 2, 'applied': True}
    calls = []

    def get_handles(gate):
        calls.append(('handles', gate['id']))
        return [{'name': f"h{gate['id']}"}]

    def make_entry(handle):
        calls.append(('entry', handle['name']))
        return ('px', handle['name'])

    rows = list(iter_handle_pixel_cache_entries(
        [g0, g1, g2], get_handles=get_handles, make_entry=make_entry
    ))
    assert rows == [
        (g1, [('px', 'h1')]),
        (g2, [('px', 'h2')]),
    ]
    assert rows[0][0] is g1
    assert rows[1][0] is g2
    assert calls == [
        ('handles', 1), ('entry', 'h1'),
        ('handles', 2), ('entry', 'h2'),
    ]


def test_builder_filters_none_entries_but_keeps_handle_callback_order():
    gate = {'id': 4, 'applied': True}
    handles = ['a', 'b', 'c']
    calls = []

    def get_handles(_gate):
        calls.append('get_handles')
        return handles

    def make_entry(handle):
        calls.append(handle)
        return None if handle == 'b' else handle.upper()

    assert list(iter_handle_pixel_cache_entries(
        [gate], get_handles=get_handles, make_entry=make_entry
    )) == [(gate, ['A', 'C'])]
    assert calls == ['get_handles', 'a', 'b', 'c']


def test_builder_does_not_yield_gate_when_every_entry_fails_closed():
    gate = {'id': 5, 'applied': True}
    assert list(iter_handle_pixel_cache_entries(
        [gate], get_handles=lambda _g: [1, 2], make_entry=lambda _h: None
    )) == []


def test_builder_is_lazy_and_preserves_completed_gate_before_later_failure():
    first = {'id': 1, 'applied': True}
    second = {'id': 2, 'applied': True}
    calls = []

    def get_handles(gate):
        calls.append(('handles', gate['id']))
        if gate is second:
            raise RuntimeError('later gate failed')
        return ['ok']

    gen = iter_handle_pixel_cache_entries(
        [first, second],
        get_handles=get_handles,
        make_entry=lambda h: ('entry', h),
    )
    assert next(gen) == (first, [('entry', 'ok')])
    assert calls == [('handles', 1)]
    with pytest.raises(RuntimeError, match='later gate failed'):
        next(gen)
    assert calls == [('handles', 1), ('handles', 2)]


def test_builder_propagates_get_handles_and_make_entry_failures():
    gate = {'id': 1, 'applied': True}
    with pytest.raises(ValueError, match='handles'):
        list(iter_handle_pixel_cache_entries(
            [gate],
            get_handles=lambda _g: (_ for _ in ()).throw(ValueError('handles')),
            make_entry=lambda h: h,
        ))

    with pytest.raises(ValueError, match='entry'):
        list(iter_handle_pixel_cache_entries(
            [gate],
            get_handles=lambda _g: ['h'],
            make_entry=lambda _h: (_ for _ in ()).throw(ValueError('entry')),
        ))


def test_flowapp_rebuild_retains_authoritative_transform_and_incremental_assignment():
    import inspect
    method = inspect.getsource(GateInteractionController.rebuild_handle_px_cache)

    assert 'host._handle_px_cache = {}' in method
    assert 'iter_handle_pixel_cache_entries(' in method
    assert 'get_handles=lambda gate: self.get_handles(gate)' in method
    assert 'make_entries=lambda handles: handle_cache_entries(' in method
    assert 'handles, host.ax.transData.transform' in method
    assert "host._handle_px_cache[gate['id']] = entries" in method

    # Clear must still happen before the helper, and live assignment after it.
    assert method.index('host._handle_px_cache = {}') < method.index('iter_handle_pixel_cache_entries(')
    assert method.index('iter_handle_pixel_cache_entries(') < method.index("host._handle_px_cache[gate['id']] = entries")


def test_builder_module_remains_tk_and_matplotlib_free_and_does_not_transform_itself():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any(name == 'tkinter' or name.startswith('tkinter.') for name in imports)
    assert not any(name == 'matplotlib' or name.startswith('matplotlib.') for name in imports)

    start = source.index('def iter_handle_pixel_cache_entries(')
    end = source.index('\n\n@dataclass(frozen=True)\nclass PinInteractionPlan', start)
    helper = source[start:end]
    assert 'transData' not in helper.replace('``transData``', '')
    assert 'make_entry(handle)' in helper


def test_builder_optional_batch_callback_preserves_per_gate_order_and_filtering():
    gates = [
        {'id': 0, 'applied': False},
        {'id': 1, 'applied': True},
        {'id': 2, 'applied': True},
    ]
    calls = []

    def get_handles(gate):
        calls.append(('handles', gate['id']))
        return [gate['id'], gate['id'] + 10]

    def make_entries(handles):
        handles = list(handles)
        calls.append(('entries', tuple(handles)))
        if handles[0] == 2:
            return [None, None]
        return [('batch', value) for value in handles]

    rows = list(iter_handle_pixel_cache_entries(
        gates, get_handles=get_handles, make_entries=make_entries
    ))
    assert rows == [(gates[1], [('batch', 1), ('batch', 11)])]
    assert calls == [
        ('handles', 1), ('entries', (1, 11)),
        ('handles', 2), ('entries', (2, 12)),
    ]


def test_builder_batch_callback_failure_propagates_after_completed_gate():
    first = {'id': 1, 'applied': True}
    second = {'id': 2, 'applied': True}

    def make_entries(handles):
        handles = list(handles)
        if handles == ['second']:
            raise RuntimeError('batch failed')
        return [('ok', handles[0])]

    gen = iter_handle_pixel_cache_entries(
        [first, second],
        get_handles=lambda gate: ['first' if gate is first else 'second'],
        make_entries=make_entries,
    )
    assert next(gen) == (first, [('ok', 'first')])
    with pytest.raises(RuntimeError, match='batch failed'):
        next(gen)


def test_builder_requires_an_entry_callback():
    with pytest.raises(TypeError, match='make_entry or make_entries is required'):
        list(iter_handle_pixel_cache_entries(
            [{'id': 1, 'applied': True}], get_handles=lambda _gate: []
        ))
