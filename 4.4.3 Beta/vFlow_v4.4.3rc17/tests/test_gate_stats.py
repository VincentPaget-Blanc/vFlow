import pytest

np = pytest.importorskip("numpy")

from vflow.core.gate_stats import (
    binomial_percentage_sem,
    build_gate_stats_export_rows,
    merge_gate_stats,
    region_percentages,
    region_percentages_with_total,
    stats_from_regions,
)


def test_stats_from_regions_preserves_legacy_shape():
    regions = {
        "IN": np.array([True, False, True]),
        "OUT": np.array([False, True, False]),
    }

    stats = stats_from_regions(regions, total=3)

    assert stats == {
        "stats": {
            "IN": {"count": 2, "pct": pytest.approx(66.6666666667)},
            "OUT": {"count": 1, "pct": pytest.approx(33.3333333333)},
        },
        "total": 3,
    }


def test_stats_from_regions_handles_zero_total():
    stats = stats_from_regions({"IN": np.array([], dtype=bool)}, total=0)

    assert stats["stats"]["IN"] == {"count": 0, "pct": 0.0}
    assert stats["total"] == 0


def test_merge_gate_stats_sums_counts_and_percentages():
    gate_data = {
        "a.csv": {
            "stats": {
                "IN": {"count": 2, "pct": 0.0},
                "OUT": {"count": 1, "pct": 0.0},
            },
            "total": 3,
        },
        "b.csv": {
            "stats": {
                "IN": {"count": 1, "pct": 0.0},
                "OUT": {"count": 2, "pct": 0.0},
            },
            "total": 3,
        },
    }

    merged = merge_gate_stats(gate_data)

    assert merged["total"] == 6
    assert merged["stats"]["IN"] == {"count": 3, "pct": 50.0}
    assert merged["stats"]["OUT"] == {"count": 3, "pct": 50.0}


def test_merge_gate_stats_empty_input():
    assert merge_gate_stats({}) == {}


def test_region_percentages_helpers():
    regions = {
        "IN": np.array([True, False, True, False]),
        "OUT": np.array([False, True, False, True]),
    }

    assert region_percentages(regions, 4) == {
        "IN": 50.0,
        "OUT": 50.0,
    }
    assert region_percentages_with_total(regions, 4) == {
        "IN": (50.0, 4),
        "OUT": (50.0, 4),
    }
    with pytest.raises(ValueError, match="denominator"):
        region_percentages(regions, 0)
    assert region_percentages({"IN": np.array([], dtype=bool)}, 0) == {"IN": 0.0}


def test_binomial_percentage_sem():
    assert binomial_percentage_sem(50.0, 100) == pytest.approx(5.0)
    assert binomial_percentage_sem(0.0, 100) == 0.0
    assert binomial_percentage_sem(50.0, 0) == 0.0


def test_build_gate_stats_export_rows_merged_preserves_zero_y_gate():
    rows = build_gate_stats_export_rows(
        mode="merged",
        gate_stats_for={},
        merged_stats={
            "stats": {"Q1": {"count": 2, "pct": 66.6666}},
            "total": 3,
        },
        x_channel="X",
        y_channel="Y",
        x_boundaries=[1.23456, 7.0],
        y_boundary=0.0,
    )

    assert rows == [
        {
            "File": "MERGED",
            "Source_Path": "",
            "X Channel": "X",
            "Y Channel": "Y",
            "X Gates": "1.2346; 7.0000",
            "Y Gate": 0.0,
            "Population": "Q1",
            "Count": 2,
            "Total": 3,
            "Input Total": 3,
            "Transform Excluded": 0,
            "FCS Compensation Metadata": "",
            "Compensation State": "",
            "Percentage": 66.667,
        }
    ]


def test_build_gate_stats_export_rows_per_file_uses_basename():
    rows = build_gate_stats_export_rows(
        mode="per-file",
        gate_stats_for={
            "/tmp/sample.csv": {
                "stats": {"IN": {"count": 1, "pct": 12.3456}},
                "total": 8,
            }
        },
        merged_stats={},
        x_channel="X",
        y_channel="Y",
        x_boundaries=[],
        y_boundary=None,
    )

    assert rows == [
        {
            "File": "sample.csv",
            "Source_Path": "/tmp/sample.csv",
            "X Channel": "X",
            "Y Channel": "Y",
            "X Gates": "",
            "Y Gate": "",
            "Population": "IN",
            "Count": 1,
            "Total": 8,
            "Input Total": 8,
            "Transform Excluded": 0,
            "FCS Compensation Metadata": "",
            "Compensation State": "",
            "Percentage": 12.346,
        }
    ]


def test_stats_from_regions_rejects_overlap_or_incomplete_denominator():
    with pytest.raises(ValueError, match="overlaps"):
        stats_from_regions({
            "A": np.array([True, False]),
            "B": np.array([True, True]),
        }, total=2)
    with pytest.raises(ValueError, match="cover 1 events"):
        stats_from_regions({
            "IN": np.array([True, False]),
            "OUT": np.array([False, False]),
        }, total=2)


def test_merge_gate_stats_rejects_region_schema_drift_and_bad_totals():
    with pytest.raises(ValueError, match="region schema"):
        merge_gate_stats({
            "a": {"stats": {"IN": {"count": 1}}, "total": 1},
            "b": {"stats": {"Q1": {"count": 1}}, "total": 1},
        })
    with pytest.raises(ValueError, match="sum to"):
        merge_gate_stats({
            "a": {"stats": {"IN": {"count": 1}, "OUT": {"count": 0}}, "total": 2},
        })


def test_gate_stats_export_disambiguates_duplicate_basenames():
    rows = build_gate_stats_export_rows(
        mode="per-file",
        gate_stats_for={
            "/a/sample.csv": {"stats": {"IN": {"count": 1, "pct": 100.0}}, "total": 1},
            "/b/sample.csv": {"stats": {"IN": {"count": 1, "pct": 100.0}}, "total": 1},
        },
        merged_stats={}, x_channel="X", y_channel="Y",
        x_boundaries=[], y_boundary=None,
    )
    assert len({row["File"] for row in rows}) == 2
    assert {row["Source_Path"] for row in rows} == {"/a/sample.csv", "/b/sample.csv"}


def test_binomial_percentage_sem_rejects_impossible_percentage():
    with pytest.raises(ValueError, match="between 0 and 100"):
        binomial_percentage_sem(101.0, 10)


def test_gate_stats_export_adds_complete_gate_and_transform_provenance_when_provided():
    gate = {
        "id": 4, "name": "Multi Y", "type": "crosshair",
        "_analysis_context": {
            "x_channel": "X", "y_channel": "Y",
            "x_scale": "logicle_gml2", "y_scale": "asinh", "cofactor": 150.0,
            "x_transform_params": {"T": 262144.0, "W": 0.5, "M": 4.5, "A": 0.0},
        },
    }
    rows = build_gate_stats_export_rows(
        mode="per-file",
        gate_stats_for={"/tmp/a.csv": {"stats": {"Q": {"count": 1, "pct": 50.0}}, "total": 2}},
        merged_stats={}, x_channel="X", y_channel="Y",
        x_boundaries=[1.0], y_boundary=2.0, y_boundaries=[2.0, 3.0], gate=gate,
    )
    row = rows[0]
    assert row["Gate ID"] == 4
    assert row["Gate Name"] == "Multi Y"
    assert row["Gate Type"] == "crosshair"
    assert row["Y Gate"] == 2.0  # backward-compatible first threshold
    assert row["Y Gates"] == "2.0000; 3.0000"
    assert row["X Scale"] == "logicle_gml2"
    assert row["Y Scale"] == "asinh"
    assert '"T":262144.0' in row["X Transform Params"]


def test_shape_gate_stats_export_includes_geometry():
    gate = {
        "id": 5, "name": "ROI", "type": "rectangle",
        "x0": 1.0, "y0": 2.0, "x1": 3.0, "y1": 4.0,
        "_analysis_context": {"x_scale": "linear", "y_scale": "linear", "cofactor": None},
    }
    row = build_gate_stats_export_rows(
        mode="merged", gate_stats_for={},
        merged_stats={"stats": {"IN": {"count": 1, "pct": 100.0}}, "total": 1},
        x_channel="X", y_channel="Y", x_boundaries=[], y_boundary=None,
        y_boundaries=[], gate=gate,
    )[0]
    assert row["Gate Type"] == "rectangle"
    assert row["Gate Geometry"] == '{"x0":1.0,"x1":3.0,"y0":2.0,"y1":4.0}'


def test_gate_stats_export_preserves_raw_and_transform_excluded_counts():
    rows = build_gate_stats_export_rows(
        mode="per-file",
        gate_stats_for={
            "/tmp/sample.csv": {
                "stats": {"IN": {"count": 2, "pct": 50.0},
                          "OUT": {"count": 2, "pct": 50.0}},
                "total": 4,
                "raw_total": 6,
                "transform_excluded": 2,
            }
        },
        merged_stats={},
        x_channel="X", y_channel="Y",
        x_boundaries=[], y_boundary=None,
    )
    assert {row["Input Total"] for row in rows} == {6}
    assert {row["Transform Excluded"] for row in rows} == {2}
    assert {row["Total"] for row in rows} == {4}


def test_merge_gate_stats_sums_raw_denominator_provenance():
    merged = merge_gate_stats({
        "a": {
            "stats": {"IN": {"count": 2}, "OUT": {"count": 1}},
            "total": 3, "raw_total": 5, "transform_excluded": 2,
        },
        "b": {
            "stats": {"IN": {"count": 1}, "OUT": {"count": 1}},
            "total": 2, "raw_total": 2, "transform_excluded": 0,
        },
    })
    assert merged["total"] == 5
    assert merged["raw_total"] == 7
    assert merged["transform_excluded"] == 2


def test_gate_stats_export_carries_compensation_provenance():
    rows = build_gate_stats_export_rows(
        mode="per-file",
        gate_stats_for={
            "/tmp/sample.fcs": {
                "stats": {"IN": {"count": 2, "pct": 100.0}},
                "total": 2, "raw_total": 2, "transform_excluded": 0,
                "compensation_metadata_keys": ("$SPILLOVER",),
            }
        },
        merged_stats={}, x_channel="X", y_channel="Y",
        x_boundaries=[], y_boundary=None,
    )
    assert rows[0]["FCS Compensation Metadata"] == "$SPILLOVER"
    assert rows[0]["Compensation State"] == "VERIFY"

    merged = merge_gate_stats({
        "a.fcs": {
            "stats": {"IN": {"count": 1, "pct": 100.0}},
            "total": 1, "raw_total": 1, "transform_excluded": 0,
            "compensation_metadata_keys": ("$SPILLOVER",),
        },
        "b.fcs": {
            "stats": {"IN": {"count": 1, "pct": 100.0}},
            "total": 1, "raw_total": 1, "transform_excluded": 0,
            "compensation_metadata_keys": ("$COMP",),
        },
    })
    assert merged["compensation_metadata_keys"] == ("$COMP", "$SPILLOVER")
