import pytest

from vflow.legacy.vflow_app import FlowApp


class _App:
    pass


def _make_app(gate, *, update=None, end=None, finish=None):
    app = _App()
    app._poly_active = True
    app._poly_cursor = (9.0, 8.0)
    app._draw_gate_id = 77
    app._draw_gate_obj = lambda: gate
    app._update_poly_close_btn = update or (lambda: None)
    app._end_blit_drag = end or (lambda: None)
    app._finish_gate = finish or (lambda _gate: None)
    return app


def _assert_open_state(app, gate, *, applied_present=True, applied_value=False):
    assert app._poly_active is True
    assert app._poly_cursor == (9.0, 8.0)
    assert app._draw_gate_id == 77
    assert ('applied' in gate) is applied_present
    if applied_present:
        assert gate['applied'] is applied_value


def test_successful_polygon_close_keeps_historical_callback_order_and_closed_state():
    gate = {'id': 10, 'type': 'polygon', 'vertices': [(0, 0), (1, 0), (1, 1)], 'applied': False}
    calls = []
    app = _make_app(gate)

    def snapshot(label):
        calls.append((label, gate['applied'], app._poly_active, app._poly_cursor, app._draw_gate_id))

    app._update_poly_close_btn = lambda: snapshot('update')
    app._end_blit_drag = lambda: snapshot('end')
    app._finish_gate = lambda g: (snapshot('finish'), calls.append(('same_gate', g is gate)))

    FlowApp._poly_finish(app)

    assert calls == [
        ('update', True, False, None, None),
        ('end', True, False, None, None),
        ('finish', True, False, None, None),
        ('same_gate', True),
    ]
    assert gate['applied'] is True
    assert app._poly_active is False
    assert app._poly_cursor is None
    assert app._draw_gate_id is None


def test_update_failure_restores_close_state_and_preserves_original_exception():
    gate = {'id': 10, 'type': 'polygon', 'vertices': [(0, 0), (1, 0), (1, 1)], 'applied': False}
    calls = []

    def update():
        calls.append('update')
        raise RuntimeError('update boom')

    app = _make_app(gate, update=update, end=lambda: calls.append('end'), finish=lambda g: calls.append('finish'))

    with pytest.raises(RuntimeError, match='update boom'):
        FlowApp._poly_finish(app)

    assert calls == ['update']
    _assert_open_state(app, gate)


def test_end_blit_failure_restores_state_then_resyncs_close_button_once():
    gate = {'id': 10, 'type': 'polygon', 'vertices': [(0, 0), (1, 0), (1, 1)], 'applied': False}
    calls = []
    app = _make_app(gate)

    def update():
        calls.append(('update', app._poly_active, gate['applied']))

    def end():
        calls.append(('end', app._poly_active, gate['applied']))
        raise RuntimeError('end boom')

    app._update_poly_close_btn = update
    app._end_blit_drag = end
    app._finish_gate = lambda g: calls.append(('finish',))

    with pytest.raises(RuntimeError, match='end boom'):
        FlowApp._poly_finish(app)

    assert calls == [
        ('update', False, True),
        ('end', False, True),
        ('update', True, False),
    ]
    _assert_open_state(app, gate)


def test_finish_failure_restores_state_and_resyncs_close_button_after_finish():
    gate = {'id': 10, 'type': 'polygon', 'vertices': [(0, 0), (1, 0), (1, 1)], 'applied': False}
    calls = []
    app = _make_app(gate)

    def update():
        calls.append(('update', app._poly_active, gate['applied']))

    def end():
        calls.append(('end', app._poly_active, gate['applied']))

    def finish(g):
        calls.append(('finish', g is gate, app._poly_active, gate['applied']))
        raise RuntimeError('finish boom')

    app._update_poly_close_btn = update
    app._end_blit_drag = end
    app._finish_gate = finish

    with pytest.raises(RuntimeError, match='finish boom'):
        FlowApp._poly_finish(app)

    assert calls == [
        ('update', False, True),
        ('end', False, True),
        ('finish', True, False, True),
        ('update', True, False),
    ]
    _assert_open_state(app, gate)


def test_failure_restores_absent_applied_key_to_absent():
    gate = {'id': 10, 'type': 'polygon', 'vertices': [(0, 0), (1, 0), (1, 1)]}
    app = _make_app(gate, finish=lambda g: (_ for _ in ()).throw(RuntimeError('finish boom')))

    with pytest.raises(RuntimeError, match='finish boom'):
        FlowApp._poly_finish(app)

    _assert_open_state(app, gate, applied_present=False)


def test_resync_failure_does_not_mask_original_post_close_exception():
    gate = {'id': 10, 'type': 'polygon', 'vertices': [(0, 0), (1, 0), (1, 1)], 'applied': False}
    count = {'update': 0}

    def update():
        count['update'] += 1
        if count['update'] == 2:
            raise ValueError('resync boom')

    def end():
        raise RuntimeError('end boom')

    app = _make_app(gate, update=update, end=end)

    with pytest.raises(RuntimeError, match='end boom'):
        FlowApp._poly_finish(app)

    assert count['update'] == 2
    _assert_open_state(app, gate)


def test_ineligible_polygon_finish_remains_noop():
    gate = {'id': 10, 'type': 'polygon', 'vertices': [(0, 0), (1, 0)], 'applied': False}
    calls = []
    app = _make_app(
        gate,
        update=lambda: calls.append('update'),
        end=lambda: calls.append('end'),
        finish=lambda g: calls.append('finish'),
    )

    FlowApp._poly_finish(app)

    assert calls == []
    _assert_open_state(app, gate)
