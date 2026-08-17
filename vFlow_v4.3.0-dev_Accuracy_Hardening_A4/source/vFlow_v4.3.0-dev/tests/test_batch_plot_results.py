import numpy as np
import pytest

pd = pytest.importorskip("pandas")

from vflow.core.gate_stats import binomial_percentage_sem
from vflow.services.batch_plot_results import compute_batch_plot_results


def _crosshair_regions(xa, ya):
    return {
        'Ch1+Ch2+': (xa >= 0) & (ya >= 0),
        'Ch1-Ch2+': (xa < 0) & (ya >= 0),
        'Ch1-Ch2-': (xa < 0) & (ya < 0),
        'Ch1+Ch2-': (xa >= 0) & (ya < 0),
    }


def test_batch_results_all_cells_filters_only_nonfinite_distribution_values():
    df = pd.DataFrame({'D': [1.0, np.nan, 3.0]})

    result = compute_batch_plot_results(
        [('s', df, 'red')],
        dist_col='D', gate=None, region_name='All regions',
        x_channel=None, y_channel=None, use_gate=False,
        transform_xy=lambda x, y: (_ for _ in ()).throw(AssertionError()),
        gate_mask_for=lambda *a: (_ for _ in ()).throw(AssertionError()),
    )

    assert not result.failed
    assert result.sample_labels == ('s',)
    assert result.dist_cache['s'][0].tolist() == [1.0, 3.0]
    assert result.dist_cache['s'][1] == 'red'
    assert result.pop_cache == {'s': {}}
    assert result.pop_sem_cache == {}


def test_batch_results_uses_finite_xy_denominator_for_percentages_and_sem():
    df = pd.DataFrame({
        'X': [1.0, -1.0, np.nan, 1.0],
        'Y': [1.0, 1.0, 2.0, -1.0],
        'D': [10.0, 20.0, 30.0, 40.0],
    })
    seen = []

    def transform_xy(xa, ya):
        valid = np.isfinite(xa) & np.isfinite(ya)
        seen.append(('transform', int(valid.sum())))
        return xa.copy(), ya.copy(), valid

    def gate_mask_for(gate, xa, ya):
        seen.append(('gate', len(xa)))
        valid = np.isfinite(xa) & np.isfinite(ya)
        regions = {k: v & valid for k, v in _crosshair_regions(xa, ya).items()}
        return regions, None

    result = compute_batch_plot_results(
        [('s', df, 'blue')],
        dist_col='D', gate={'type': 'crosshair'}, region_name='All regions',
        x_channel='X', y_channel='Y', use_gate=True,
        transform_xy=transform_xy, gate_mask_for=gate_mask_for,
    )

    assert not result.failed
    assert seen == [('transform', 3), ('gate', 4)]
    assert result.pop_cache['s'] == {
        'Ch1+Ch2+': pytest.approx(100 / 3),
        'Ch1-Ch2+': pytest.approx(100 / 3),
        'Ch1-Ch2-': pytest.approx(0.0),
        'Ch1+Ch2-': pytest.approx(100 / 3),
    }
    expected_sem = binomial_percentage_sem(100 / 3, 3)
    assert result.pop_sem_cache[('s', 'Ch1+Ch2+')] == pytest.approx(expected_sem)
    # All-regions selection is the union of valid region masks, so the row with
    # non-finite X is excluded from the distribution.
    assert result.dist_cache['s'][0].tolist() == [10.0, 20.0, 40.0]


def test_batch_results_selected_region_filters_distribution_but_not_gate_denominator():
    df = pd.DataFrame({
        'X': [1.0, -1.0, 2.0, np.nan],
        'Y': [1.0, 1.0, -1.0, 1.0],
        'D': [10.0, 20.0, 30.0, 99.0],
    })

    def transform_xy(xa, ya):
        return xa, ya, np.isfinite(xa) & np.isfinite(ya)

    def gate_mask_for(gate, xa, ya):
        valid = np.isfinite(xa) & np.isfinite(ya)
        return {k: v & valid for k, v in _crosshair_regions(xa, ya).items()}, None

    result = compute_batch_plot_results(
        [('s', df, 'blue')],
        dist_col='D', gate={'type': 'crosshair'}, region_name='Ch1+Ch2+',
        x_channel='X', y_channel='Y', use_gate=True,
        transform_xy=transform_xy, gate_mask_for=gate_mask_for,
    )

    assert result.dist_cache['s'][0].tolist() == [10.0]
    assert result.pop_cache['s']['Ch1+Ch2+'] == pytest.approx(100 / 3)


def test_batch_results_collects_all_failed_samples_and_discards_partial_caches():
    good = pd.DataFrame({'X': [1.0], 'Y': [1.0], 'D': [5.0]})
    missing_y = pd.DataFrame({'X': [1.0], 'D': [6.0]})
    gate_fail = pd.DataFrame({'X': [2.0], 'Y': [2.0], 'D': [7.0]})
    calls = []

    def transform_xy(xa, ya):
        calls.append(float(xa[0]))
        return xa, ya, np.ones(len(xa), bool)

    def gate_mask_for(gate, xa, ya):
        if xa[0] == 2.0:
            raise RuntimeError('gate failed')
        return {'IN': np.ones(len(xa), bool)}, None

    result = compute_batch_plot_results(
        [('good', good, 'a'), ('missing', missing_y, 'b'), ('badgate', gate_fail, 'c')],
        dist_col='D', gate={'type': 'rectangle'}, region_name='IN',
        x_channel='X', y_channel='Y', use_gate=True,
        transform_xy=transform_xy, gate_mask_for=gate_mask_for,
    )

    assert result.failed
    assert result.failed_samples == ('missing', 'badgate')
    assert result.dist_cache == {}
    assert result.pop_cache == {}
    assert result.pop_sem_cache == {}
    assert result.sample_labels == ()
    # The loop still reaches later requested samples, matching the legacy code.
    assert calls == [1.0, 2.0]


def test_batch_results_zero_finite_denominator_keeps_distribution_but_no_percentages():
    df = pd.DataFrame({'X': [np.nan], 'Y': [1.0], 'D': [5.0]})

    def transform_xy(xa, ya):
        return xa, ya, np.zeros(len(xa), bool)

    def gate_mask_for(gate, xa, ya):
        # A non-empty mapping is truthy even when every membership mask is false.
        return {'IN': np.zeros(len(xa), bool), 'OUT': np.zeros(len(xa), bool)}, None

    result = compute_batch_plot_results(
        [('s', df, 'a')],
        dist_col='D', gate={'type': 'rectangle'}, region_name='All regions',
        x_channel='X', y_channel='Y', use_gate=True,
        transform_xy=transform_xy, gate_mask_for=gate_mask_for,
    )

    assert not result.failed
    assert result.dist_cache['s'][0].size == 0
    assert result.pop_cache == {'s': {}}
    assert result.pop_sem_cache == {}


def test_batch_results_does_not_swallow_distribution_conversion_errors():
    df = pd.DataFrame({'D': ['not-a-number']})

    with pytest.raises((TypeError, ValueError)):
        compute_batch_plot_results(
            [('s', df, 'a')],
            dist_col='D', gate=None, region_name='All regions',
            x_channel=None, y_channel=None, use_gate=False,
            transform_xy=lambda x, y: (x, y, np.ones(len(x), bool)),
            gate_mask_for=lambda *a: ({}, None),
        )


def test_legacy_batch_compute_delegates_to_tk_free_result_service():
    import ast
    import inspect
    import textwrap
    from vflow.legacy.vflow_app import BatchPlotWindow

    tree = ast.parse(textwrap.dedent(inspect.getsource(BatchPlotWindow._compute_and_plot)))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert any(
        isinstance(call.func, ast.Name) and call.func.id == 'compute_batch_plot_results'
        for call in calls
    )
