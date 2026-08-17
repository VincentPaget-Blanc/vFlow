import warnings

import pytest

np = pytest.importorskip("numpy")

from vflow.core.auto_gate import (
    cluster_min_fraction,
    cluster_polygons_status,
    cluster_size_parameters,
    dbscan_eps_from_neighbor_distances,
    derivative_threshold,
    finite_displayable_raw_channel_values,
    finite_raw_channel_values,
    finite_transformed_channel_values,
    fit_gmm_crossings,
    gmm_component_count,
    gmm_multi_status,
    normalize_points_unit_square,
    otsu_threshold,
    percent_at_or_below,
    percent_below,
    sensitivity_parameters,
    two_axis_threshold_status,
    weighted_gaussian_crossing_between_means,
)


def test_derivative_threshold_all_nonfinite_fails_closed():
    with pytest.raises(ValueError, match="at least 10 finite"):
        derivative_threshold(np.array([np.nan, np.inf, -np.inf]))


def test_derivative_threshold_constant_data_fails_closed():
    scipy = pytest.importorskip("scipy")
    assert scipy
    with pytest.raises(ValueError, match="non-degenerate"):
        derivative_threshold(np.ones(20))


def test_otsu_threshold_does_not_emit_divide_warning():
    data = np.concatenate([np.zeros(10), np.ones(10)])

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = otsu_threshold(data)

    assert isinstance(result, float)
    assert not any("divide" in str(w.message).lower() for w in caught)


def test_sensitivity_parameters_endpoints():
    low = sensitivity_parameters(1)
    high = sensitivity_parameters(10)

    assert low["gmm_max_comp"] == 2
    assert low["kde_prominence"] == pytest.approx(200.0)
    assert low["bw_factor"] == pytest.approx(5.0)
    assert low["otsu_min_frac"] == pytest.approx(0.25)
    assert high["gmm_max_comp"] == 8
    assert high["kde_prominence"] == pytest.approx(1.001)
    assert high["bw_factor"] == pytest.approx(0.05)
    assert high["otsu_min_frac"] == pytest.approx(0.0005)


def test_channel_value_collectors_and_percent_below():
    pd = pytest.importorskip("pandas")
    frames = [
        pd.DataFrame({"X": [1.0, 10.0, np.nan], "Y": [2.0, 3.0, 4.0]}),
        pd.DataFrame({"X": [100.0], "Z": [3.0]}),
    ]

    transformed = finite_transformed_channel_values(
        frames,
        "X",
        "linear",
        cofactor=150.0,
    )
    raw = finite_raw_channel_values(frames, "X")

    assert transformed.tolist() == [1.0, 10.0, 100.0]
    assert raw.tolist() == [1.0, 10.0, 100.0]
    assert percent_below(raw, 50.0) == pytest.approx(100.0 * 2 / 3)
    assert percent_below(np.array([np.nan]), 50.0) == 0.0
    assert percent_at_or_below(np.array([1.0, 2.0, 3.0]), 2.0) == pytest.approx(200.0 / 3.0)

    displayable = finite_displayable_raw_channel_values(
        [pd.DataFrame({"X": [-1.0, 0.0, 1.0, 10.0]})],
        "X", "log", cofactor=150.0,
    )
    assert displayable.tolist() == [1.0, 10.0]


def test_two_axis_threshold_status():
    assert two_axis_threshold_status(
        "Otsu",
        x_threshold=1234.5,
        y_threshold=9.2,
        x_percent_below=12.345,
        y_percent_below=67.89,
    ) == "\u2713 Otsu: X @ 1,234 (12.3% at/below)  |  Y @ 9 (67.9% at/below)"


def test_cluster_sensitivity_helpers():
    assert cluster_min_fraction(1) == pytest.approx(0.10)
    assert cluster_min_fraction(10) == pytest.approx(0.003)
    assert cluster_size_parameters(1000, 0.10) == (100, 20)
    assert cluster_size_parameters(10, 0.001) == (5, 3)


def test_cluster_normalization_and_dbscan_eps():
    points = np.array([[2.0, 5.0], [4.0, 5.0], [6.0, 9.0]])

    normalized = normalize_points_unit_square(points)

    assert normalized == pytest.approx(
        np.array([[0.0, 0.0], [0.5, 0.0], [1.0, 1.0]])
    )
    assert dbscan_eps_from_neighbor_distances(
        np.array([[0.0, 0.001], [0.0, 0.002]])
    ) == 0.01


def test_cluster_polygons_status():
    assert cluster_polygons_status(
        algorithm="HDBSCAN",
        gates_created=2,
        noise_count=0,
        labels_count=10,
    ) == "\u2713 Cluster Polygons (HDBSCAN): 2 gate(s)"
    assert cluster_polygons_status(
        algorithm="DBSCAN",
        gates_created=1,
        noise_count=2,
        labels_count=10,
    ) == "\u2713 Cluster Polygons (DBSCAN): 1 gate(s)  |  20.0% noise points"


def test_gmm_component_count_and_status():
    assert gmm_component_count(0) == 1
    assert gmm_component_count(3) == 3
    assert gmm_component_count(99) == 8
    assert gmm_multi_status(
        x_components=3,
        x_crossings=2,
        y_components=4,
        y_crossings=3,
    ) == (
        "\u2713 GMM Multi \u2014 X: 3 comp \u2192 2 crossing(s)  "
        "|  Y: 4 comp \u2192 3 crossing(s)  "
        "|  Uncheck unwanted thresholds in the Threshold panel"
    )


def test_fit_gmm_crossings_reports_not_enough_data():
    thresholds, summary, params = fit_gmm_crossings(
        np.array([1.0, 2.0, 3.0]),
        2,
        "linear",
        lambda values, _scale: values,
    )

    assert thresholds == []
    assert summary == "not enough data"
    assert params is None


def test_fit_gmm_crossings_when_sklearn_available():
    pytest.importorskip("sklearn")
    pytest.importorskip("scipy")
    data = np.concatenate([np.zeros(30), np.ones(30) * 10.0])

    thresholds, summary, params = fit_gmm_crossings(
        data,
        2,
        "linear",
        lambda values, _scale: values,
    )

    assert len(thresholds) == 1
    assert 0.0 < thresholds[0] < 10.0
    assert "C1" in summary
    assert params["scale"] == "linear"
    assert params["n_data"] == len(data)


def test_weighted_gaussian_crossing_is_exact_for_supported_adjacent_components():
    pytest.importorskip("scipy")
    crossing = weighted_gaussian_crossing_between_means(
        0.0, 1.0, 0.5,
        10.0, 1.0, 0.5,
    )
    assert crossing == pytest.approx(5.0)


def test_weighted_gaussian_crossing_does_not_fabricate_when_one_component_dominates_both_means():
    pytest.importorskip("scipy")
    assert weighted_gaussian_crossing_between_means(
        0.0, 1.0, 0.999,
        1.0, 0.1, 0.001,
    ) is None


def test_derivative_threshold_unimodal_distribution_does_not_substitute_tail_gate():
    pytest.importorskip("scipy")
    rng = np.random.default_rng(12)
    data = rng.normal(0.0, 1.0, 5000)
    with pytest.raises(ValueError, match="No supported two-population KDE valley"):
        derivative_threshold(data, min_prominence=5.0, bw_factor=1.0)


def test_otsu_rejects_empty_constant_and_impossible_class_fraction():
    with pytest.raises(ValueError, match="at least two"):
        otsu_threshold(np.array([np.nan]))
    with pytest.raises(ValueError, match="non-degenerate"):
        otsu_threshold(np.ones(20))
    with pytest.raises(ValueError, match="min_class_fraction"):
        otsu_threshold(np.array([0.0, 1.0]), min_class_fraction=0.5)
