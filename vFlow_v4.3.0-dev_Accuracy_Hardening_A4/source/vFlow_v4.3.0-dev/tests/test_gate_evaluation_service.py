import numpy as np
import pytest

from vflow.app.cache import AnalysisCache
from vflow.app.state import AnalysisState
from vflow.services.gate_evaluation import evaluate_gate_regions


def rectangle_gate(**overrides):
    gate = {
        'id': 7,
        'name': 'Rect',
        'type': 'rectangle',
        'applied': True,
        'color': '#f00',
        'x0': -1.0, 'y0': -1.0, 'x1': 1.0, 'y1': 1.0,
    }
    gate.update(overrides)
    return gate


def linear_state():
    return AnalysisState(
        x_channel='X', y_channel='Y',
        x_scale='linear', y_scale='linear', cofactor=150.0)


def test_gate_evaluation_preserves_finite_event_universe():
    state = linear_state()
    gate = rectangle_gate()
    x = np.array([0.0, 2.0, np.nan, np.inf], dtype=np.float64)
    y = np.array([0.0, 2.0, 0.0, 0.0], dtype=np.float64)
    regions, _ = evaluate_gate_regions(
        gate, x, y, analysis_state=state, analysis_cache=AnalysisCache())
    assert regions['IN'].tolist() == [True, False, False, False]
    assert regions['OUT'].tolist() == [False, True, False, False]


def test_gate_evaluation_binds_context_once_and_fails_closed_after_change():
    state = linear_state()
    gate = rectangle_gate()
    cache = AnalysisCache()
    regions, _ = evaluate_gate_regions(
        gate, [0.0], [0.0], analysis_state=state, analysis_cache=cache)
    assert regions['IN'].tolist() == [True]
    assert gate['_analysis_context']['x_channel'] == 'X'
    state.x_scale = 'asinh'
    regions2, colors2 = evaluate_gate_regions(
        gate, [0.0], [0.0], analysis_state=state, analysis_cache=cache)
    assert regions2 == {}
    assert colors2 == []


def test_gate_evaluation_cache_key_separates_generation_and_reuses_payload():
    state = linear_state()
    gate = rectangle_gate()
    cache = AnalysisCache()
    x = np.array([0.0, 2.0], dtype=np.float64)
    y = np.array([0.0, 2.0], dtype=np.float64)
    first = evaluate_gate_regions(
        gate, x, y, analysis_state=state, analysis_cache=cache,
        cache_path='same.csv')
    assert len(cache.gate_masks) == 1
    second = evaluate_gate_regions(
        gate, x, y, analysis_state=state, analysis_cache=cache,
        cache_path='same.csv')
    assert second is not first
    assert second[0] is first[0]
    state.advance_data_generation()
    evaluate_gate_regions(
        gate, x, y, analysis_state=state, analysis_cache=cache,
        cache_path='same.csv')
    assert len(cache.gate_masks) == 2


def test_gate_evaluation_stale_cached_length_is_recomputed():
    state = linear_state()
    gate = rectangle_gate()
    cache = AnalysisCache()
    evaluate_gate_regions(
        gate, [0.0, 2.0], [0.0, 2.0], analysis_state=state,
        analysis_cache=cache, cache_path='same.csv')
    regions, _ = evaluate_gate_regions(
        gate, [0.0], [0.0], analysis_state=state,
        analysis_cache=cache, cache_path='same.csv')
    assert len(regions['IN']) == 1


def test_gate_evaluation_rejects_mismatched_arrays():
    with pytest.raises(ValueError, match='one-dimensional and equal length'):
        evaluate_gate_regions(
            rectangle_gate(), [0.0, 1.0], [0.0],
            analysis_state=linear_state(), analysis_cache=AnalysisCache())


def test_gate_evaluation_nonapplied_gate_does_not_bind_context():
    state = linear_state()
    gate = rectangle_gate(applied=False)
    assert evaluate_gate_regions(
        gate, [0.0], [0.0], analysis_state=state,
        analysis_cache=AnalysisCache()) == ({}, [])
    assert '_analysis_context' not in gate
