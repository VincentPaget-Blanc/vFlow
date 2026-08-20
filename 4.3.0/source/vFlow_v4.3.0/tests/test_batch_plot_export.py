import pytest

np = pytest.importorskip("numpy")

from vflow.services.batch_plot_export import (
    build_batch_plot_stats_row,
    distribution_summary,
    format_display_number,
    safe_population_column_name,
    short_display_label,
)


def test_safe_population_column_name_matches_legacy_export():
    assert safe_population_column_name("TH+/VGAT -") == "TH+_VGAT_-"


def test_build_batch_plot_stats_row_with_values_and_populations():
    row = build_batch_plot_stats_row(
        sample_label="sample 1",
        values=np.array([1.0, 2.0, 3.0, 4.0]),
        populations={"A/B C": 12.34567},
        column="Intensity",
        gate="Gate 1",
        region="All regions",
    )

    assert row["Sample"] == "sample 1"
    assert row["Col"] == "Intensity"
    assert row["Gate"] == "Gate 1"
    assert row["Region"] == "All regions"
    assert row["N"] == 4
    assert row["Mean"] == 2.5
    assert row["Median"] == 2.5
    assert row["Std"] == pytest.approx(round(float(np.std([1, 2, 3, 4], ddof=1)), 4))
    assert row["IQR"] == 1.5
    assert row["p5"] == 1.15
    assert row["p95"] == 3.85
    assert row["Pop_A_B_C_pct"] == 12.346


def test_build_batch_plot_stats_row_empty_values():
    row = build_batch_plot_stats_row(
        sample_label="empty",
        values=np.array([]),
        populations={},
        column="Intensity",
        gate="All cells",
        region="All regions",
    )

    assert row == {
        "Sample": "empty",
        "Col": "Intensity",
        "Gate": "All cells",
        "Region": "All regions",
        "N": 0,
        "Mean": "",
        "Median": "",
        "Std": "",
        "IQR": "",
        "p5": "",
        "p95": "",
    }


def test_distribution_summary_handles_empty_and_values():
    empty = distribution_summary(np.array([]))

    assert empty["n"] == 0
    assert np.isnan(empty["median"])
    assert np.isnan(empty["mean"])
    assert np.isnan(empty["iqr"])

    summary = distribution_summary(np.array([1.0, 2.0, 4.0]))

    assert summary == {
        "n": 3,
        "median": 2.0,
        "mean": pytest.approx(7.0 / 3.0),
        "iqr": 1.5,
    }


def test_format_display_number_matches_sidebar_rules():
    assert format_display_number(float("nan")) == "\u2014"
    assert format_display_number(1234567.0) == "1.235e+06"
    assert format_display_number(123.456) == "123.5"
    assert format_display_number(12.3456) == "12.346"


def test_short_display_label_matches_legacy_sidebar():
    assert short_display_label("short") == "short"
    assert short_display_label("abcdefghijklmnopqrstuvwxyz") == "abcdefghijklmnopqrstuvwx\u2026"


def test_batch_plot_export_can_include_counting_se():
    row = build_batch_plot_stats_row(
        sample_label="s1",
        values=[1.0, 2.0],
        populations={"IN": 25.0},
        population_sems={"IN": 1.25},
        column="Intensity",
        gate="Gate",
        region="IN",
    )
    assert row["Pop_IN_pct"] == 25.0
    assert row["Pop_IN_counting_SE_pct"] == 1.25


def test_batch_plot_export_rejects_population_column_name_collisions():
    with pytest.raises(ValueError, match="collide after CSV-column normalization"):
        build_batch_plot_stats_row(
            sample_label="s1",
            values=[1.0, 2.0],
            populations={"A/B": 25.0, "A_B": 75.0},
            column="Intensity",
            gate="Gate",
            region="All regions",
        )
