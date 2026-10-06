import numpy as np
import pandas as pd
import pytest

from vflow.app.cache import AnalysisCache
from vflow.app.state import AnalysisState
from vflow.services.subgate_population import (
    SubgateChannelMismatchError, resolve_subgate_selection)


def state():
    return AnalysisState(
        x_channel='X', y_channel='Y',
        x_scale='linear', y_scale='linear', cofactor=150.0)


def rect(gid, x0, y0, x1, y1, *, applied=True):
    return {
        'id': gid, 'name': f'Gate {gid}', 'type': 'rectangle',
        'applied': applied, 'color': '#f00',
        'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
    }


def test_subgate_resolver_prefers_selected_gate_when_gates_overlap():
    a = rect(1, -2, -2, 2, 2)
    b = rect(2, -1, -1, 1, 1)
    selection = resolve_subgate_selection(
        gates=[a, b], selected_gate=b, click_x=0.0, click_y=0.0,
        active_files={'s.csv': pd.DataFrame({'X': [0.0, 1.5], 'Y': [0.0, 1.5]})},
        analysis_state=state(), analysis_cache=AnalysisCache())
    assert selection is not None
    assert selection.target_gate is b
    assert selection.region == 'IN'
    assert selection.total_cells == 1
    assert selection.filtered_data['s.csv']['X'].tolist() == [0.0]


def test_subgate_resolver_uses_other_applied_gate_when_selected_does_not_contain_click():
    a = rect(1, 10, 10, 20, 20)
    b = rect(2, -1, -1, 1, 1)
    selection = resolve_subgate_selection(
        gates=[a, b], selected_gate=a, click_x=0.0, click_y=0.0,
        active_files={'s.csv': pd.DataFrame({'X': [0.0], 'Y': [0.0]})},
        analysis_state=state(), analysis_cache=AnalysisCache())
    assert selection is not None
    assert selection.target_gate is b


def test_subgate_resolver_shape_click_outside_does_not_open_out_population():
    gate = rect(1, -1, -1, 1, 1)
    selection = resolve_subgate_selection(
        gates=[gate], selected_gate=gate, click_x=5.0, click_y=5.0,
        active_files={'s.csv': pd.DataFrame({'X': [0.0], 'Y': [0.0]})},
        analysis_state=state(), analysis_cache=AnalysisCache())
    assert selection is None


def test_subgate_resolver_crosshair_returns_clicked_quadrant_and_filters_all_files():
    gate = {
        'id': 3, 'name': 'Cross', 'type': 'crosshair', 'applied': True,
        'color': '#f00', 'x_boundaries': [0.0], 'y_boundary': 0.0,
        'x_thresh_vars': [True], 'y_thresh_var': True,
        'y_boundaries': None, 'y_thresh_vars': [],
    }
    files = {
        'a.csv': pd.DataFrame({'X': [1.0, -1.0], 'Y': [1.0, 1.0]}),
        'b.csv': pd.DataFrame({'X': [2.0, -2.0], 'Y': [2.0, -2.0]}),
    }
    selection = resolve_subgate_selection(
        gates=[gate], selected_gate=gate, click_x=1.0, click_y=1.0,
        active_files=files, analysis_state=state(), analysis_cache=AnalysisCache())
    assert selection is not None
    assert selection.region in selection.filtered_data['a.csv'].columns or selection.region
    assert selection.total_cells == 2
    assert selection.filtered_data['a.csv']['X'].tolist() == [1.0]
    assert selection.filtered_data['b.csv']['X'].tolist() == [2.0]


def test_subgate_resolver_rejects_partial_population_when_any_active_file_lacks_axes():
    gate = rect(1, -1, -1, 1, 1)
    files = {
        'missing.csv': pd.DataFrame({'X': [0.0]}),
        'inside.csv': pd.DataFrame({'X': [0.0], 'Y': [0.0]}),
    }
    with pytest.raises(SubgateChannelMismatchError) as exc:
        resolve_subgate_selection(
            gates=[gate], selected_gate=gate, click_x=0.0, click_y=0.0,
            active_files=files, analysis_state=state(), analysis_cache=AnalysisCache())
    assert exc.value.missing_files == ('missing.csv',)
    assert exc.value.x_channel == 'X'
    assert exc.value.y_channel == 'Y'


def test_subgate_resolver_reuses_same_per_file_gate_cache_contract():
    gate = rect(1, -1, -1, 1, 1)
    cache = AnalysisCache()
    files = {'s.csv': pd.DataFrame({'X': [0.0, 2.0], 'Y': [0.0, 2.0]})}
    st = state()
    resolve_subgate_selection(
        gates=[gate], selected_gate=gate, click_x=0.0, click_y=0.0,
        active_files=files, analysis_state=st, analysis_cache=cache)
    assert len(cache.gate_masks) == 1
    key = next(iter(cache.gate_masks))
    assert key[1] == 's.csv'
    assert key[0] == st.data_generation
