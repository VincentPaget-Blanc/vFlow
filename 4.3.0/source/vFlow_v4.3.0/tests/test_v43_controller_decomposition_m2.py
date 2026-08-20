import numpy as np
import pytest

from scipy.spatial import ConvexHull
from scipy.signal import savgol_filter
from scipy.stats import gaussian_kde

from vflow.core.auto_gate import (
    ClusterPolygonInsufficientData,
    fit_cluster_polygons,
    kde_valley_supported,
    prepare_cluster_polygon_data,
)
from vflow.core.gate_stats import (
    binary_gate_partition_counts,
    binary_gate_partition_sort_key,
)
from vflow.legacy.vflow_app import FlowApp


def test_kde_valley_service_matches_legacy_controller_oracle():
    rng = np.random.default_rng(123)
    bimodal = np.r_[rng.normal(-2, 0.35, 3000), rng.normal(2, 0.4, 3000)]
    kde = gaussian_kde(bimodal, bw_method="scott")
    grid = np.linspace(bimodal.min(), bimodal.max(), 2048)
    smooth = savgol_filter(kde(grid), 51, 3)
    dy = np.gradient(smooth, grid)
    valleys = np.where(np.diff(np.sign(dy)) > 0)[0]
    threshold = float(grid[valleys[0]])

    args = (bimodal, threshold, 1.0, 5.0, 0.01)
    assert kde_valley_supported(*args) == FlowApp._kde_valley_supported(*args)

    unimodal = rng.normal(0, 1, 6000)
    fallback = float(np.percentile(unimodal, 5))
    args = (unimodal, fallback, 1.0, 5.0, 0.01)
    assert kde_valley_supported(*args) == FlowApp._kde_valley_supported(*args)

    degenerate = np.ones(20)
    args = (degenerate, 1.0, 1.0, 5.0, 0.01)
    assert kde_valley_supported(*args) == FlowApp._kde_valley_supported(*args) is False


def test_cluster_preparation_preserves_v42_finite_filter_sampling_and_parameters():
    n = 10020
    xt = np.linspace(-5.0, 5.0, n)
    yt = np.linspace(10.0, 20.0, n)
    xr = xt * 100.0
    yr = yt * 10.0
    xt[3] = np.nan
    yt[9] = np.inf

    prepared = prepare_cluster_polygon_data(
        xt, yt, xr, yr, min_fraction=0.01, max_points=10_000
    )

    valid = np.isfinite(xt) & np.isfinite(yt)
    xtv, ytv, xrv, yrv = xt[valid], yt[valid], xr[valid], yr[valid]
    idx = np.random.default_rng(42).choice(len(xtv), 10_000, replace=False)
    expected_pts = np.column_stack([xtv[idx], ytv[idx]])
    mins = expected_pts.min(axis=0)
    maxs = expected_pts.max(axis=0)
    ranges = np.where(maxs > mins, maxs - mins, 1.0)
    expected_norm = (expected_pts - mins) / ranges

    np.testing.assert_array_equal(prepared.transformed_x, xtv[idx])
    np.testing.assert_array_equal(prepared.transformed_y, ytv[idx])
    np.testing.assert_array_equal(prepared.raw_x, xrv[idx])
    np.testing.assert_array_equal(prepared.raw_y, yrv[idx])
    np.testing.assert_allclose(prepared.points_normalized, expected_norm, rtol=0, atol=0)
    assert prepared.n_total == n - 2
    assert prepared.min_cluster_size == max(5, int(0.01 * 10_000))
    assert prepared.min_samples == max(3, prepared.min_cluster_size // 5)


def test_cluster_preparation_preserves_insufficient_data_boundary():
    vals = np.arange(19.0)
    with pytest.raises(ClusterPolygonInsufficientData, match="Not enough data"):
        prepare_cluster_polygon_data(vals, vals, vals, vals, min_fraction=0.01)


class _FakeHDBSCAN:
    last_kwargs = None
    labels = None

    def __init__(self, **kwargs):
        type(self).last_kwargs = kwargs

    def fit(self, points):
        self.labels_ = np.asarray(type(self).labels)
        assert len(self.labels_) == len(points)
        return self


class _FailingHull:
    def __init__(self, points):
        raise RuntimeError("degenerate")


def test_cluster_fit_preserves_transform_space_hull_to_raw_vertex_mapping():
    # Two 10-point clusters with deliberately non-linear raw/display relationship.
    xt = np.r_[np.linspace(-3, -1, 10), np.linspace(1, 3, 10)]
    yt = np.r_[np.linspace(-1, 1, 10) ** 3, np.linspace(-1, 1, 10) ** 3 + 5]
    xr = np.exp(xt)
    yr = yt * 7.0 + 2.0
    prepared = prepare_cluster_polygon_data(
        xt, yt, xr, yr, min_fraction=0.1, max_points=10_000
    )
    _FakeHDBSCAN.labels = np.array([0] * 10 + [1] * 10)

    result = fit_cluster_polygons(
        prepared,
        hdbscan_cls=_FakeHDBSCAN,
        dbscan_cls=None,
        convex_hull_cls=ConvexHull,
    )

    assert _FakeHDBSCAN.last_kwargs == {
        "min_cluster_size": prepared.min_cluster_size,
        "min_samples": prepared.min_samples,
        "cluster_selection_method": "eom",
    }
    assert result.algorithm_tag == "hdbscan"
    assert result.algorithm_label == "HDBSCAN"
    assert result.cluster_count == 2
    assert result.noise_count == 0
    assert result.labels_count == 20

    expected = []
    labels = _FakeHDBSCAN.labels
    for label in sorted(set(labels)):
        mask = labels == label
        hull = ConvexHull(np.column_stack([
            prepared.transformed_x[mask], prepared.transformed_y[mask]
        ]))
        expected.append(tuple(zip(
            prepared.raw_x[mask][hull.vertices].tolist(),
            prepared.raw_y[mask][hull.vertices].tolist(),
        )))
    assert result.polygons == tuple(expected)


def test_cluster_fit_skips_degenerate_hull_instead_of_fabricating_rectangle():
    xt = np.linspace(0, 19, 20, dtype=float)
    yt = xt.copy()
    xr = xt * 2.0
    yr = yt * 3.0
    prepared = prepare_cluster_polygon_data(
        xt, yt, xr, yr, min_fraction=0.1
    )
    _FakeHDBSCAN.labels = np.zeros(20, dtype=int)
    result = fit_cluster_polygons(
        prepared,
        hdbscan_cls=_FakeHDBSCAN,
        dbscan_cls=None,
        convex_hull_cls=_FailingHull,
    )
    # A bounding rectangle would cover raw-space points that were not members
    # of the collinear fitted cluster.  Unsupported geometry must fail closed.
    assert result.polygons == ()
    assert result.cluster_count == 0


def test_binary_gate_partition_preserves_combo_order_names_and_counts():
    a = np.array([False, True, True, False, True, False])
    b = np.array([False, False, True, True, True, False])
    parts = binary_gate_partition_counts(["A", "B"], [a, b])
    assert parts == {
        "Outside all": 2,
        "A": 1,
        "B": 1,
        "A ∩ B": 2,
    }
    assert sorted(parts, key=binary_gate_partition_sort_key) == [
        "A", "B", "A ∩ B", "Outside all"
    ]


def test_binary_gate_partition_preserves_duplicate_name_aggregation():
    a = np.array([True, False, True, False])
    b = np.array([False, True, True, False])
    parts = binary_gate_partition_counts(["Same", "Same"], [a, b])
    assert parts == {
        "Outside all": 1,
        "Same": 2,
        "Same ∩ Same": 1,
    }


def test_duplicate_gate_names_can_be_disambiguated_before_partitioning():
    from vflow.services.batch_stats_export import gate_output_labels

    gates = [{"id": 11, "name": "Same"}, {"id": 12, "name": "Same"}]
    a = np.array([True, False, True, False])
    b = np.array([False, True, True, False])
    parts = binary_gate_partition_counts(gate_output_labels(gates), [a, b])
    assert parts == {
        "Outside all": 1,
        "Same__id11": 1,
        "Same__id12": 1,
        "Same__id11 ∩ Same__id12": 1,
    }
