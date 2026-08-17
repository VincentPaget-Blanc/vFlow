import numpy as np
import pandas as pd

import vflow.legacy.vflow_app as legacy
from vflow.core.gate_masks import compute_gate_regions
from vflow.core.gate_serialization import gate_to_json_dict
from vflow.core.gate_stats import stats_from_regions
from vflow.core.gates import new_gate_dict


class FakeBooleanVar:
    def __init__(self, value=False):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class Event:
    xdata = 0.0
    ydata = 0.0


class Cache:
    def clear_gate_dependent(self):
        pass


def _science_snapshot(gate):
    x = np.array([-2.0, -0.5, 0.5, 2.0], dtype=float)
    y = np.array([-2.0, 0.5, -0.5, 2.0], dtype=float)
    regions, _ = compute_gate_regions(
        gate, x, y,
        x_scale='linear', y_scale='linear', cofactor=150.0,
        x_channel='X', y_channel='Y',
    )
    stats = stats_from_regions(regions, total=len(x))
    return gate_to_json_dict(gate), stats


def test_manual_release_materializes_legacy_vars_and_downstream_science(monkeypatch):
    monkeypatch.setattr(legacy.tk, 'BooleanVar', FakeBooleanVar)
    gate = new_gate_dict(gate_id_value=1, gate_type_value='crosshair', color='#abc')
    app = object.__new__(legacy.FlowApp)
    app._handle_drag = None
    app._gate_move = None
    app.moving_gate = True
    app._draw_frozen_xlim = None
    app._draw_frozen_ylim = None
    app._draw_gate_id = 1
    app._draw_gate_obj = lambda: gate
    app._end_blit_drag = lambda: None
    app._finish_gate = lambda g: None
    app._del_gate = lambda gid: None

    legacy.FlowApp._on_release(app, Event())

    payload, stats = _science_snapshot(gate)
    assert payload['x_thresh_active'] == [True]
    assert payload['y_thresh_active'] is True
    assert stats['total'] == 4
    assert sum(item['count'] for item in stats['stats'].values()) == 4


def test_single_y_auto_materialization_preserves_serialization_masks_and_stats(monkeypatch):
    monkeypatch.setattr(legacy.tk, 'BooleanVar', FakeBooleanVar)
    app = object.__new__(legacy.FlowApp)
    app.gates = []
    app._sel_gate_id = None
    app._sel_gate = lambda: None
    def add_gate(auto_type=None, auto_apply=None, auto_method=None):
        gate = new_gate_dict(gate_id_value=2, gate_type_value=auto_type or 'crosshair', color='#def')
        gate['auto_method'] = auto_method
        app.gates.append(gate)
        return gate
    app._add_gate = add_gate
    app._bind_gate_context = lambda gate: None
    app._analysis_cache_obj = lambda: Cache()
    app._gate_hint_var = type('V', (), {'set': lambda self, value: None})()
    app._compute_gate_stats_for = lambda gate: None
    app._rebuild_gate_manager = lambda: None
    app._rebuild_thresh_panel = lambda: None
    app.refresh_plot = lambda: None
    app._update_stats_display = lambda: None

    legacy.FlowApp._apply_gate_and_refresh(app, [0.0], 0.0, 'kde')

    gate = app.gates[0]
    payload, stats = _science_snapshot(gate)
    assert payload['x_thresh_active'] == [True]
    assert payload['y_thresh_active'] is True
    assert payload['y_thresh_actives'] == []
    assert stats['total'] == 4
    assert sum(item['count'] for item in stats['stats'].values()) == 4


def test_gmm_multi_materialization_preserves_multi_y_serialization_masks_and_stats(monkeypatch):
    monkeypatch.setattr(legacy.tk, 'BooleanVar', FakeBooleanVar)
    monkeypatch.setattr(legacy, 'HAS_SKLEARN', True)
    monkeypatch.setattr(legacy, 'gmm_component_count', lambda value: int(value))
    results = iter([
        ([0.0], 'x-summary', {'axis': 'x'}),
        ([-1.0, 1.0], 'y-summary', {'axis': 'y'}),
    ])
    monkeypatch.setattr(legacy, 'fit_gmm_crossings', lambda *args, **kwargs: next(results))
    monkeypatch.setattr(legacy, 'gmm_multi_status', lambda **kwargs: 'ok')

    app = object.__new__(legacy.FlowApp)
    app.gates = []
    app._sel_gate_id = None
    app.x_channel = 'X'
    app.y_channel = 'Y'
    app._active = lambda: {'file': pd.DataFrame({'X': [1.0, 2.0], 'Y': [3.0, 4.0]})}
    app.gmm_max_x_var = type('V', (), {'get': lambda self: '2'})()
    app.gmm_max_y_var = type('V', (), {'get': lambda self: '3'})()
    app._collect_x_transform = lambda: np.array([1.0, 2.0])
    app._collect_y_transform = lambda: np.array([3.0, 4.0])
    app._inv = lambda *args: None
    app._last_auto_gate_fn = None
    app.status_var = type('V', (), {'set': lambda self, value: None})()
    def add_gate(auto_type=None, auto_apply=None, auto_method=None):
        gate = new_gate_dict(gate_id_value=3, gate_type_value=auto_type or 'crosshair', color='#fed')
        gate['auto_method'] = auto_method
        app.gates.append(gate)
        return gate
    app._add_gate = add_gate
    app._bind_gate_context = lambda gate: None
    app._analysis_cache_obj = lambda: Cache()
    app._compute_gate_stats_for = lambda gate: None
    app._rebuild_gate_manager = lambda: None
    app._rebuild_thresh_panel = lambda: None
    app.refresh_plot = lambda: None
    app._update_stats_display = lambda: None
    app._gate_hint_var = type('V', (), {'set': lambda self, value: None})()

    legacy.FlowApp.auto_gate_gmm_multi(app)

    gate = app.gates[0]
    payload, stats = _science_snapshot(gate)
    assert payload['x_thresh_active'] == [True]
    assert payload['y_thresh_active'] is True  # legacy serializer default for None scalar var
    assert payload['y_thresh_actives'] == [True, True]
    assert payload['y_boundaries'] == [-1.0, 1.0]
    assert stats['total'] == 4
    assert sum(item['count'] for item in stats['stats'].values()) == 4
