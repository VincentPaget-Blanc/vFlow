import numpy as np
import pytest

from vflow.services.population_evaluation import (
    regions_in_explicit_context,
    restrict_regions_to_valid,
)


def test_restrict_regions_to_valid_preserves_shared_event_universe():
    regions = {
        'IN': np.array([True, True, False, False]),
        'OUT': np.array([False, False, True, True]),
    }
    valid = np.array([True, False, True, False])
    out = restrict_regions_to_valid(regions, valid)
    assert out['IN'].tolist() == [True, False, False, False]
    assert out['OUT'].tolist() == [False, False, True, False]


def test_restrict_regions_to_valid_fails_on_length_mismatch():
    with pytest.raises(ValueError, match='expected 3'):
        restrict_regions_to_valid({'IN': np.array([True, False])}, [True, True, True])


def test_explicit_context_rectangle_membership_and_invalid_values_match_v411_rules():
    gate = {
        'id': 1, 'type': 'rectangle', 'applied': True, 'color': '#f00',
        'x0': -1.0, 'y0': -1.0, 'x1': 1.0, 'y1': 1.0,
    }
    context = {
        'x_channel': 'X', 'y_channel': 'Y',
        'x_scale': 'linear', 'y_scale': 'linear', 'cofactor': None,
    }
    x = np.array([0.0, 2.0, np.nan, np.inf])
    y = np.array([0.0, 2.0, 0.0, 0.0])
    regions, _ = regions_in_explicit_context(
        gate, x, y, context, fallback_cofactor=150.0)
    assert regions['IN'].tolist() == [True, False, False, False]
    assert regions['OUT'].tolist() == [False, True, False, False]


def test_explicit_context_uses_serialized_context_not_child_context():
    gate = {
        'id': 1, 'type': 'rectangle', 'applied': True, 'color': '#f00',
        'x0': -1.0, 'y0': -1.0, 'x1': 1.0, 'y1': 1.0,
    }
    context = {
        'x_channel': 'AncestorX', 'y_channel': 'AncestorY',
        'x_scale': 'linear', 'y_scale': 'linear', 'cofactor': None,
    }
    regions, _ = regions_in_explicit_context(
        gate, np.array([0.0, 2.0]), np.array([0.0, 2.0]), context,
        fallback_cofactor=999.0)
    assert regions['IN'].tolist() == [True, False]


def test_explicit_context_rejects_mismatched_arrays():
    gate = {'type': 'rectangle', 'applied': True, 'x0': 0, 'y0': 0, 'x1': 1, 'y1': 1}
    with pytest.raises(ValueError, match='one-dimensional and equal length'):
        regions_in_explicit_context(
            gate, [0.0, 1.0], [0.0],
            {'x_scale': 'linear', 'y_scale': 'linear'},
            fallback_cofactor=150.0)


def test_secondary_population_service_matches_gate_region_semantics():
    import pandas as pd
    from vflow.app.state import AnalysisState
    from vflow.services.population_evaluation import selected_population_mask_for_dataframe

    state = AnalysisState(
        x_channel='X', y_channel='Y', x_scale='linear', y_scale='linear', cofactor=150.0)
    gate = {
        'id': 1, 'type': 'rectangle', 'applied': True, 'color': '#f00',
        'x0': -1.0, 'y0': -1.0, 'x1': 1.0, 'y1': 1.0,
    }
    df = pd.DataFrame({'X': [0.0, 2.0, np.nan], 'Y': [0.0, 2.0, 0.0]})
    mask_in = selected_population_mask_for_dataframe(
        df, gate, region_name='IN', analysis_state=state)
    assert mask_in.tolist() == [True, False, False]
    mask_all = selected_population_mask_for_dataframe(
        df, gate, region_name='All regions', analysis_state=state)
    # For shape gates, All regions means the biologically selected IN population,
    # not IN+OUT, matching selected_region_mask's frozen behavior.
    assert mask_all.tolist() == [True, False, False]


def test_secondary_population_service_fails_closed_on_context_or_channel_mismatch():
    import pandas as pd
    from vflow.app.state import AnalysisState
    from vflow.services.population_evaluation import selected_population_mask_for_dataframe

    state = AnalysisState(
        x_channel='X', y_channel='Y', x_scale='linear', y_scale='linear', cofactor=150.0)
    gate = {
        'id': 1, 'type': 'rectangle', 'applied': True,
        'x0': -1.0, 'y0': -1.0, 'x1': 1.0, 'y1': 1.0,
        '_analysis_context': {
            'x_channel': 'Other', 'y_channel': 'Y',
            'x_scale': 'linear', 'y_scale': 'linear', 'cofactor': None,
        },
    }
    df = pd.DataFrame({'X': [0.0], 'Y': [0.0]})
    assert selected_population_mask_for_dataframe(
        df, gate, region_name='IN', analysis_state=state) is None
    state2 = AnalysisState(
        x_channel='Missing', y_channel='Y', x_scale='linear', y_scale='linear')
    gate2 = dict(gate)
    gate2.pop('_analysis_context', None)
    assert selected_population_mask_for_dataframe(
        df, gate2, region_name='IN', analysis_state=state2) is None
