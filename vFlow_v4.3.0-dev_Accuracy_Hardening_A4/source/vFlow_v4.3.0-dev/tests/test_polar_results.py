import numpy as np

from vflow.config.constants import FILE_COLORS
from vflow.services.polar_results import collect_polar_datasets


def test_collect_polar_datasets_preserves_sorted_order_labels_and_colors():
    active = {'/z/b.csv': object(), '/a/a.csv': object()}
    seen = []

    def mask_for(df, path):
        seen.append(('mask', path))
        return np.array([True, False])

    def vectors_for(df, mask):
        seen.append(('vectors', int(mask.sum())))
        return np.array([0.1]), np.array([2.0])

    result = collect_polar_datasets(
        active, set(active), population_mask_for=mask_for, vectors_for=vectors_for)

    assert not result.failed
    assert [d[2] for d in result.datasets] == ['a.csv', 'b.csv']
    assert [d[3] for d in result.datasets] == [FILE_COLORS[0], FILE_COLORS[1]]
    assert [d[4] for d in result.datasets] == ['/a/a.csv', '/z/b.csv']
    assert seen == [
        ('mask', '/a/a.csv'), ('vectors', 1),
        ('mask', '/z/b.csv'), ('vectors', 1),
    ]


def test_collect_polar_datasets_skips_nonvisible_paths_without_callbacks():
    active = {'a.csv': object(), 'b.csv': object()}
    seen = []

    result = collect_polar_datasets(
        active, {'b.csv'},
        population_mask_for=lambda df, path: seen.append(path) or np.array([True]),
        vectors_for=lambda df, mask: (np.array([0.2]), np.array([1.0])),
    )

    assert not result.failed
    assert [d[4] for d in result.datasets] == ['b.csv']
    assert seen == ['b.csv']
    # Color index is based on sorted active-file enumeration, as in v4.1.11.
    assert result.datasets[0][3] == FILE_COLORS[1]


def test_collect_polar_datasets_population_failure_discards_partial_collection():
    active = {'a.csv': object(), 'b.csv': object()}

    def mask_for(df, path):
        return None if path == 'b.csv' else np.array([True])

    result = collect_polar_datasets(
        active, set(active), population_mask_for=mask_for,
        vectors_for=lambda df, mask: (np.array([0.1]), np.array([1.0])),
    )

    assert result.failed
    assert result.failure_kind == 'population'
    assert result.failure_path == 'b.csv'
    assert result.datasets == ()


def test_collect_polar_datasets_vector_failure_discards_partial_collection():
    active = {'a.csv': object(), 'b.csv': object()}

    def vectors_for(df, mask):
        return (None, None) if df is active['b.csv'] else (np.array([0.1]), np.array([1.0]))

    result = collect_polar_datasets(
        active, set(active),
        population_mask_for=lambda df, path: np.array([True]),
        vectors_for=vectors_for,
    )

    assert result.failed
    assert result.failure_kind == 'vectors'
    assert result.failure_path == 'b.csv'
    assert result.datasets == ()


def test_collect_polar_datasets_does_not_swallow_callback_exceptions():
    def boom(df, path):
        raise RuntimeError('sentinel')

    try:
        collect_polar_datasets(
            {'a.csv': object()}, {'a.csv'},
            population_mask_for=boom,
            vectors_for=lambda df, mask: (np.array([]), np.array([])),
        )
    except RuntimeError as exc:
        assert str(exc) == 'sentinel'
    else:
        raise AssertionError('callback exception was unexpectedly swallowed')
