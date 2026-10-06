import pytest

np = pytest.importorskip("numpy")

from vflow.core.circular_stats import (
    auto_detect_vector_columns,
    build_polar_stats_export_row,
    circular_mean_direction,
    common_columns,
    format_polar_stats_values,
    format_rayleigh_p_value,
    is_directionally_significant,
    mean_resultant_length,
    rayleigh_p_value,
    vector_direction_stats,
    vectors_from_coordinate_columns,
)


def test_mean_resultant_length_empty_and_aligned():
    assert mean_resultant_length(np.array([])) == 0.0
    assert mean_resultant_length(np.zeros(5)) == pytest.approx(1.0)


def test_common_columns_returns_sorted_intersection():
    pd = pytest.importorskip("pandas")
    frames = [
        pd.DataFrame({"B": [1], "A": [2], "C": [3]}),
        pd.DataFrame({"A": [4], "B": [5], "D": [6]}),
    ]

    assert common_columns(frames) == ["A", "B"]
    assert common_columns([]) == []


def test_circular_mean_direction():
    angles = np.array([np.pi / 2, np.pi / 2, np.pi / 2])

    assert circular_mean_direction(angles) == pytest.approx(np.pi / 2)


def test_rayleigh_p_value_edge_cases_and_bounds():
    assert rayleigh_p_value(np.array([])) == 1.0
    assert rayleigh_p_value(np.array([0.0])) == 1.0

    p = rayleigh_p_value(np.zeros(20))

    assert 0.0 <= p <= 1.0
    assert p < 0.001


def test_rayleigh_p_value_uses_zar_circstat_approximation():
    angles = np.linspace(-0.5, 0.5, 20)
    r_bar = mean_resultant_length(angles)
    n = len(angles)
    resultant = n * r_bar
    expected = np.exp(
        np.sqrt(1 + 4 * n + 4 * (n**2 - resultant**2)) - (1 + 2 * n)
    )

    assert rayleigh_p_value(angles) == pytest.approx(expected)


def test_rayleigh_small_sample_uses_zar_approximation_not_exp_minus_z():
    angles = np.array([-0.0945724, 0.2317488, 0.0180301])
    n = len(angles)
    r_bar = mean_resultant_length(angles)
    resultant = n * r_bar
    expected = np.exp(
        np.sqrt(1 + 4 * n + 4 * (n**2 - resultant**2)) - (1 + 2 * n)
    )
    assert rayleigh_p_value(angles) == pytest.approx(expected)


def test_directional_significance_requires_p_and_mrl():
    aligned = np.zeros(20)
    dispersed = np.linspace(-np.pi, np.pi, 20)

    assert is_directionally_significant(aligned, mrl_threshold=0.3)
    assert not is_directionally_significant(dispersed, mrl_threshold=0.3)
    assert not is_directionally_significant(aligned, mrl_threshold=1.1)


def test_vectors_from_coordinate_columns_requires_all_columns():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"x1": [0.0], "y1": [0.0], "x2": [1.0]})

    assert vectors_from_coordinate_columns(
        df, np.array([True]), "x1", "y1", "x2", "y2"
    ) == (None, None)


def test_vectors_from_coordinate_columns_empty_selection():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"x1": [0.0], "y1": [0.0], "x2": [1.0], "y2": [0.0]})

    angles, magnitudes = vectors_from_coordinate_columns(
        df, np.array([False]), "x1", "y1", "x2", "y2"
    )

    assert angles.size == 0
    assert magnitudes.size == 0


def test_vectors_from_coordinate_columns_computes_angles_and_magnitudes():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame(
        {
            "x1": [0.0, 0.0, 2.0],
            "y1": [0.0, 0.0, 1.0],
            "x2": [1.0, 0.0, 2.0],
            "y2": [0.0, 1.0, 4.0],
        }
    )

    angles, magnitudes = vectors_from_coordinate_columns(
        df, np.array([True, True, False]), "x1", "y1", "x2", "y2"
    )

    assert angles == pytest.approx(np.array([0.0, np.pi / 2]))
    assert magnitudes == pytest.approx(np.array([1.0, 1.0]))




def test_zero_length_vectors_have_no_direction_and_are_excluded():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({
        "x1": [0.0, 0.0], "y1": [0.0, 0.0],
        "x2": [0.0, 1.0], "y2": [0.0, 0.0],
    })
    angles, magnitudes = vectors_from_coordinate_columns(
        df, np.array([True, True]), "x1", "y1", "x2", "y2"
    )
    assert angles == pytest.approx(np.array([0.0]))
    assert magnitudes == pytest.approx(np.array([1.0]))

def test_vector_direction_stats_empty_and_aligned():
    empty = vector_direction_stats(np.array([]), mrl_threshold=0.3)

    assert empty == {
        "n": 0,
        "mrl": None,
        "rayleigh_p": None,
        "mean_dir_deg": None,
        "significant": None,
    }

    stats = vector_direction_stats(np.zeros(20), mrl_threshold=0.3)

    assert stats["n"] == 20
    assert stats["mrl"] == pytest.approx(1.0)
    assert stats["rayleigh_p"] < 0.0001
    assert stats["mean_dir_deg"] == pytest.approx(0.0)
    assert stats["significant"] is True


def test_polar_stats_display_formatting():
    assert format_rayleigh_p_value(None) == "\u2014"
    assert format_rayleigh_p_value(0.5) == "0.5000"
    assert format_rayleigh_p_value(0.00001) == "<0.0001"
    assert format_polar_stats_values(
        {
            "n": 0,
            "mrl": None,
            "rayleigh_p": None,
            "mean_dir_deg": None,
            "significant": None,
        }
    ) == ("0", "\u2014", "\u2014", "\u2014", "\u2014")


def test_build_polar_stats_export_row():
    row = build_polar_stats_export_row(
        file_name="sample.csv",
        source_path="/data/sample.csv",
        gate="Gate 1",
        region="All regions",
        angles=np.zeros(20),
        mrl_threshold=0.3,
        x_ch1="x1",
        y_ch1="y1",
        x_ch2="x2",
        y_ch2="y2",
    )

    assert row["File"] == "sample.csv"
    assert row["Source_Path"] == "/data/sample.csv"
    assert row["N_vectors"] == 20
    assert row["MRL"] == 1.0
    assert row["Rayleigh_p"] < 1e-6
    assert row["Mean_dir_deg"] == 0.0
    assert row["Significant"] is True
    assert row["X_Ch1"] == "x1"


def test_build_polar_stats_export_row_empty():
    row = build_polar_stats_export_row(
        file_name="sample.csv",
        gate="Gate 1",
        region="All regions",
        angles=None,
        mrl_threshold=0.3,
        x_ch1="x1",
        y_ch1="y1",
        x_ch2="x2",
        y_ch2="y2",
    )

    assert row["N_vectors"] == 0
    assert row["MRL"] is None
    assert row["Significant"] is None


def test_auto_detect_vector_columns_prefers_microns_and_pairs_axes():
    columns = [
        "x_raw",
        "y_raw",
        "X_channel1_microns",
        "Y_channel1_microns",
        "X_channel2_microns",
        "Y_channel2_microns",
    ]

    assert auto_detect_vector_columns(columns) == (
        "X_channel1_microns",
        "Y_channel1_microns",
        "X_channel2_microns",
        "Y_channel2_microns",
    )


def test_auto_detect_vector_columns_pairs_channel_identity_when_column_order_is_scrambled():
    columns = [
        "X_Ch2_microns",
        "Y_Ch1_microns",
        "X_Ch1_microns",
        "Y_Ch2_microns",
    ]
    assert auto_detect_vector_columns(columns) == (
        "X_Ch1_microns",
        "Y_Ch1_microns",
        "X_Ch2_microns",
        "Y_Ch2_microns",
    )


def test_auto_detect_vector_columns_duplicates_single_axis():
    assert auto_detect_vector_columns(["centroid_x", "centroid_y"]) == (
        "centroid_x",
        "centroid_y",
        "centroid_x",
        "centroid_y",
    )


def test_auto_detect_vector_columns_handles_missing_axes():
    assert auto_detect_vector_columns(["other"]) == ("", "", "", "")


def test_vectors_drop_nonfinite_coordinate_rows():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({
        "x1": [0.0, np.nan, 0.0], "y1": [0.0, 0.0, 0.0],
        "x2": [1.0, 1.0, np.inf], "y2": [0.0, 1.0, 1.0],
    })
    angles, mags = vectors_from_coordinate_columns(
        df, np.array([True, True, True]), "x1", "y1", "x2", "y2"
    )
    assert len(angles) == 1
    assert angles[0] == pytest.approx(0.0)
    assert mags[0] == pytest.approx(1.0)

def test_vector_stats_ignore_nonfinite_angles():
    stats = vector_direction_stats(
        np.array([0.0, np.nan, np.inf]), mrl_threshold=0.5
    )
    assert stats["n"] == 1
    assert stats["mrl"] == pytest.approx(1.0)


def test_antipodal_vectors_have_undefined_mean_direction_not_roundoff_angle():
    angles = np.array([0.0, np.pi])
    assert np.isnan(circular_mean_direction(angles))
    stats = vector_direction_stats(angles, mrl_threshold=0.3)
    assert stats["mrl"] == pytest.approx(0.0, abs=1e-15)
    assert stats["mean_dir_deg"] is None
    assert stats["significant"] is False
    values = format_polar_stats_values(stats)
    assert values[3] == "\u2014"


def test_quadrature_symmetric_vectors_have_undefined_mean_direction():
    angles = np.array([0.0, np.pi / 2, np.pi, -np.pi / 2])
    stats = vector_direction_stats(angles, mrl_threshold=0.3)
    assert stats["mean_dir_deg"] is None


def test_auto_detect_vector_columns_refuses_positional_cross_pair_guess():
    assert auto_detect_vector_columns([
        "X_object_a", "Y_object_b", "X_object_c", "Y_object_d"
    ]) == ("", "", "", "")
