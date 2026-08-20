import copy

import numpy as np

from vflow.app.state import AnalysisState
from vflow.core.gate_masks import compute_gate_regions
from vflow.legacy import vflow_app as legacy
from vflow.legacy.vflow_app import FlowApp
from vflow.services.axis_input_planning import plan_axis_apply
from vflow.services.gate_axis_swap import (
    is_pure_axis_swap,
    plan_gate_axis_swap,
    swap_analysis_context_axes,
)


class Var:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class BoolVar(Var):
    pass


def _mask_set(regions):
    return {np.asarray(mask, bool).tobytes() for mask in regions.values()}


def _regions(gate, x, y, context):
    return compute_gate_regions(
        gate, x, y,
        x_scale=context['x_scale'], y_scale=context['y_scale'],
        cofactor=context.get('cofactor') or 150.0,
        x_transform_params=context.get('x_transform_params'),
        y_transform_params=context.get('y_transform_params'),
        x_channel=context['x_channel'], y_channel=context['y_channel'],
    )[0]


def test_axis_plan_distinguishes_true_swap_from_new_channel_change():
    swap = plan_axis_apply('B', 'A', 'A', 'B')
    assert swap.swap_axes is True
    assert swap.context_changed is True
    assert is_pure_axis_swap('B', 'A', 'A', 'B') is True

    changed = plan_axis_apply('C', 'A', 'A', 'B')
    assert changed.swap_axes is False
    assert changed.context_changed is True
    assert is_pure_axis_swap('C', 'A', 'A', 'B') is False


def test_analysis_context_swap_moves_every_axis_affine_field_only():
    ctx = {
        'x_channel': 'A', 'y_channel': 'B',
        'x_scale': 'logicle_gml2', 'y_scale': 'asinh',
        'cofactor': 150.0,
        'x_transform_params': {'T': 1.0, 'W': 0.1, 'M': 4.5, 'A': 0.0},
        'custom_shared': {'keep': True},
    }
    swapped = swap_analysis_context_axes(ctx)
    assert swapped['x_channel'] == 'B'
    assert swapped['y_channel'] == 'A'
    assert swapped['x_scale'] == 'asinh'
    assert swapped['y_scale'] == 'logicle_gml2'
    assert 'x_transform_params' not in swapped
    assert swapped['y_transform_params'] == ctx['x_transform_params']
    assert swapped['cofactor'] == 150.0
    assert swapped['custom_shared'] == {'keep': True}


def test_crosshair_swap_preserves_threshold_activity_and_gmm_axis_metadata():
    gate = {
        'type': 'crosshair', 'applied': True,
        'x_boundaries': [1.0, 2.0],
        'x_thresh_vars': [BoolVar(True), BoolVar(False)],
        'y_boundary': 10.0,
        'y_boundaries': None,
        'y_thresh_var': BoolVar(False),
        'y_thresh_vars': [],
        'gmm_x_params': {'axis': 'A'},
        'gmm_y_params': {'axis': 'B'},
    }
    plan = plan_gate_axis_swap(gate)
    assert plan.crosshair.x_boundaries == (10.0,)
    assert plan.crosshair.x_active == (False,)
    assert plan.crosshair.y_boundary is None
    assert plan.crosshair.y_boundaries == (1.0, 2.0)
    assert plan.crosshair.y_actives == (True, False)
    assert plan.geometry['gmm_x_params'] == {'axis': 'B'}
    assert plan.geometry['gmm_y_params'] == {'axis': 'A'}


def test_shape_swap_plans_transpose_raw_geometry():
    rect = plan_gate_axis_swap({
        'type': 'rectangle', 'x0': 1.0, 'y0': 10.0, 'x1': 3.0, 'y1': 20.0
    })
    assert rect.geometry == {'x0': 10.0, 'y0': 1.0, 'x1': 20.0, 'y1': 3.0}

    poly = plan_gate_axis_swap({
        'type': 'polygon', 'vertices': [(1.0, 10.0), (2.0, 30.0), (4.0, 20.0)]
    })
    assert poly.geometry['vertices'] == [(10.0, 1.0), (30.0, 2.0), (20.0, 4.0)]


def _make_app(monkeypatch, gates):
    monkeypatch.setattr(legacy.tk, 'BooleanVar', BoolVar)
    app = FlowApp.__new__(FlowApp)
    state = AnalysisState(
        x_channel='A', y_channel='B',
        x_scale='logicle_gml2', y_scale='asinh', cofactor=150.0,
        x_transform_params={'T': 262144.0, 'W': 0.5, 'M': 4.5, 'A': 0.0},
    )
    app.__dict__['_analysis_state'] = state
    app.gates = gates
    for gate in gates:
        if gate.get('_analysis_context') is None:
            app._bind_gate_context(gate)
    app.x_var = Var('B')
    app.y_var = Var('A')
    app.x_scale_var = Var(app.x_scale)
    app.y_scale_var = Var(app.y_scale)
    app._locked_xlim = (-100.0, 5000.0)
    app._locked_ylim = (-5.0, 80.0)
    app.status_var = Var('')
    app._rebuild_thresh_panel = lambda: None
    calls = []
    app._analysis_context_changed = lambda: calls.append('changed')
    app.refresh_plot = lambda: calls.append('refresh')
    return app, calls


def test_flowapp_true_axis_swap_preserves_gate_membership_and_swaps_channel_state(monkeypatch):
    gates = [
        {
            'id': 1, 'name': 'R', 'type': 'rectangle', 'applied': True,
            'x0': 10.0, 'y0': 1.0, 'x1': 1000.0, 'y1': 20.0,
        },
        {
            'id': 2, 'name': 'E', 'type': 'ellipse', 'applied': True,
            'x0': 20.0, 'y0': 2.0, 'x1': 2000.0, 'y1': 30.0,
        },
        {
            'id': 3, 'name': 'P', 'type': 'polygon', 'applied': True,
            'vertices': [(10.0, 1.0), (1000.0, 2.0), (2000.0, 20.0), (20.0, 30.0)],
        },
        {
            'id': 4, 'name': 'C', 'type': 'crosshair', 'applied': True,
            'x_boundaries': [50.0, 500.0],
            'x_thresh_vars': [BoolVar(True), BoolVar(False)],
            'y_boundary': 10.0, 'y_boundaries': None,
            'y_thresh_var': BoolVar(True), 'y_thresh_vars': [],
        },
    ]
    app, calls = _make_app(monkeypatch, gates)
    old_ctx = app._current_analysis_context()
    original = copy.deepcopy([
        {k: v for k, v in gate.items() if k not in ('x_thresh_vars', 'y_thresh_var', 'y_thresh_vars')}
        for gate in gates
    ])

    x = np.array([-20.0, 0.0, 10.0, 20.0, 50.0, 100.0, 500.0, 1000.0, 2000.0, 4000.0])
    y = np.array([-2.0, 0.0, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, 60.0])
    before = [_mask_set(_regions(g, x, y, old_ctx)) for g in gates]

    app.apply_axes()

    assert calls == ['changed']
    assert (app.x_channel, app.y_channel) == ('B', 'A')
    assert (app.x_scale, app.y_scale) == ('asinh', 'logicle_gml2')
    assert app.x_scale_var.get() == 'asinh'
    assert app.y_scale_var.get() == 'logicle_gml2'
    assert app.x_transform_params == AnalysisState().x_transform_params
    assert app.y_transform_params == old_ctx['x_transform_params']
    assert app._locked_xlim == (-5.0, 80.0)
    assert app._locked_ylim == (-100.0, 5000.0)

    new_ctx = app._current_analysis_context()
    after = [_mask_set(_regions(g, y, x, new_ctx)) for g in gates]
    assert after == before
    assert all(app._gate_context_matches(g) for g in gates)
    assert '4 gate(s) transposed and recomputed' in app.status_var.get()

    # Swap back and verify raw geometry/provenance recover exactly.
    app.x_var.set('A')
    app.y_var.set('B')
    calls.clear()
    app.apply_axes()
    assert calls == ['changed']
    assert (app.x_channel, app.y_channel) == ('A', 'B')
    assert app._current_analysis_context() == old_ctx

    restored = [
        {k: v for k, v in gate.items() if k not in ('x_thresh_vars', 'y_thresh_var', 'y_thresh_vars')}
        for gate in gates
    ]
    assert restored == original
    roundtrip = [_mask_set(_regions(g, x, y, old_ctx)) for g in gates]
    assert roundtrip == before


def test_new_channel_change_still_leaves_old_gate_incompatible_and_unmodified(monkeypatch):
    gate = {
        'id': 1, 'name': 'P', 'type': 'polygon', 'applied': True,
        'vertices': [(1.0, 10.0), (2.0, 20.0), (3.0, 10.0)],
    }
    app, calls = _make_app(monkeypatch, [gate])
    old_gate = copy.deepcopy(gate)
    app.x_var.set('C')
    app.y_var.set('B')

    app.apply_axes()

    assert calls == ['changed']
    assert (app.x_channel, app.y_channel) == ('C', 'B')
    assert gate == old_gate
    assert app._gate_context_matches(gate) is False


def test_serialized_crosshair_swap_preserves_plain_threshold_flags():
    from vflow.services.gate_axis_swap import apply_serialized_gate_axis_swap_plan
    gate = {
        'type': 'crosshair', 'applied': True,
        'x_boundaries': [1.0, 2.0], 'x_thresh_active': [True, False],
        'y_boundary': 10.0, 'y_boundaries': None,
        'y_thresh_active': False, 'y_thresh_actives': [],
    }
    plan = plan_gate_axis_swap(gate)
    apply_serialized_gate_axis_swap_plan(gate, plan)
    assert gate['x_boundaries'] == [10.0]
    assert gate['x_thresh_active'] == [False]
    assert gate['y_boundary'] is None
    assert gate['y_boundaries'] == [1.0, 2.0]
    assert gate['y_thresh_actives'] == [True, False]
