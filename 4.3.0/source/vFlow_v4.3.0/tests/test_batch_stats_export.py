from pathlib import Path

import pytest

from vflow.services.batch_stats_export import (
    add_gate_region_counts,
    apply_parent_region_filter,
    ambiguous_stems,
    batch_exclusion_sets,
    batch_details_message,
    batch_status_message,
    batch_summary_message,
    build_batch_stats_row,
    concat_skip_reason,
    discover_batch_target_files,
    excluded_log_rows,
    all_batch_targets_excluded_message,
    family_exclusion_match,
    gate_output_labels,
    no_batch_targets_message,
    ordered_batch_columns,
    previous_batch_output_skip_reason,
    relative_path_for_output,
    sample_label_for_path,
    safe_region_column_name,
    region_universe_total,
)


def test_family_exclusion_matches_pooled_doc_case():
    prefix, matched = family_exclusion_match(
        "sample_a_1___CytoFile",
        {"sample_a_Pooled_CytoFile"},
    )

    assert prefix == "sample_a_"
    assert matched == "sample_a_pooled_cytofile"


def test_family_exclusion_rejects_substring_false_positive():
    assert family_exclusion_match("alphabet", {"alpha"}) == (None, None)


@pytest.mark.parametrize(
    ("target", "excluded"),
    [
        ("Mouse_01_Treated", "Mouse_01_Control"),
        ("Patient_001_day2", "Patient_001_day1"),
        ("exp_A_sample2", "exp_A_sample1"),
    ],
)
def test_family_exclusion_rejects_biologically_distinct_generic_prefixes(target, excluded):
    assert family_exclusion_match(target, {excluded}) == (None, None)


def test_family_exclusion_matches_acquisition_to_acquisition_in_same_cyto_family():
    assert family_exclusion_match(
        "sample_a_2___CytoFile", {"sample_a_1___CytoFile"}
    ) == ("sample_a_", "sample_a_1___cytofile")


def test_discover_batch_target_files_applies_direct_and_family_exclusions(tmp_path):
    root = tmp_path
    keep = root / "sample_b_1___CytoFile.csv"
    direct = root / "direct_1___CytoFile.csv"
    family = root / "sample_a_1___CytoFile.csv"
    nonsuffix = root / "sample_c_other.csv"
    for path in (keep, direct, family, nonsuffix):
        path.write_text("X,Y\n1,2\n")

    targets, skipped = discover_batch_target_files(
        str(root),
        "___CytoFile",
        "csv",
        batch_exclusion_sets({str(direct)})[0],
        {"sample_a_pooled_cytofile"},
    )

    assert targets == [str(keep)]
    assert skipped == [
        ("direct_1___CytoFile.csv", "directly excluded from analysis"),
        (
            "sample_a_1___CytoFile.csv",
            "family of excluded 'sample_a_pooled_cytofile' "
            "(shared prefix 'sample_a_')",
        ),
    ]


def test_batch_exclusion_sets_normalizes_paths_and_stems():
    paths = {"/Data/Sample_A.csv", "/Data/Sample_B.FCS"}

    excluded_paths, excluded_stems = batch_exclusion_sets(paths)

    from vflow.core.path_identity import file_identity_key
    assert excluded_paths == {
        file_identity_key("/Data/Sample_A.csv"),
        file_identity_key("/Data/Sample_B.FCS"),
    }
    assert excluded_stems == {"sample_a", "sample_b"}


def test_duplicate_basename_disambiguation_and_relative_path(tmp_path):
    root = tmp_path
    top = root / "file_0.csv"
    nested = root / "old_runs" / "file_0.csv"
    nested.parent.mkdir()
    top.write_text("X,Y\n1,2\n")
    nested.write_text("X,Y\n1,2\n")
    paths = [str(top), str(nested)]

    ambiguous = ambiguous_stems(paths)

    assert ambiguous == {"file_0"}
    assert sample_label_for_path(str(top), str(root), ambiguous) == "file_0"
    assert sample_label_for_path(str(nested), str(root), ambiguous) == "old_runs/file_0"
    assert relative_path_for_output(str(nested), str(root)) == "old_runs/file_0.csv"


def test_concat_and_previous_batch_skip_reasons():
    pd = pytest.importorskip("pandas")
    concat_df = pd.DataFrame({"Source_File": ["a.csv", "b.csv"]})
    previous_df = pd.DataFrame({"Sample": ["a"], "Total_Cells": [1]})

    assert concat_skip_reason(concat_df) == (
        "concatenated file (2 sources) — skipped to avoid double counting; "
        "analyze the originals instead"
    )
    assert previous_batch_output_skip_reason(previous_df, "Intensity_X") == (
        "appears to be previous batch output (Sample/Total_Cells"
        " columns present, no channel data) — skipped"
    )


def test_batch_region_column_formatting_and_rounding():
    np = pytest.importorskip("numpy")
    row = {"Sample": "s1", "Total_Cells": 3}
    regions = {"TH+/VGAT -": np.array([True, False, True])}

    add_gate_region_counts(row, "Gate 1", regions, total=3)

    assert safe_region_column_name("TH+/VGAT -") == "TH+_VGAT_-"
    assert row["Gate 1__TH+_VGAT_-__N"] == 2
    assert row["Gate 1__TH+_VGAT_-__pct"] == 66.667


def test_ordered_batch_columns_keeps_meta_edges_and_sorts_gate_columns():
    columns = [
        "Source_File",
        "B__N",
        "Sample",
        "Relative_Path",
        "A__N",
        "Total_Cells",
    ]

    assert ordered_batch_columns(columns) == [
        "Sample",
        "Total_Cells",
        "A__N",
        "B__N",
        "Relative_Path",
        "Source_File",
    ]


def test_excluded_log_rows_include_exclusions_and_errors():
    rows = excluded_log_rows(
        [("a.csv", "directly excluded")],
        ["b.csv: missing channel X", "weird unparsed error"],
    )

    assert rows == [
        {"Filename": "a.csv", "Full_Path": "", "Reason": "directly excluded"},
        {"Filename": "b.csv", "Full_Path": "", "Reason": "missing channel X"},
        {
            "Filename": "weird unparsed error",
            "Full_Path": "",
            "Reason": "weird unparsed error",
        },
    ]


def test_batch_completion_messages():
    assert batch_status_message(
        rows_count=3,
        save_path="/tmp/out.csv",
        skipped_count=2,
        errors_count=1,
    ) == "\u2713 Batch stats: 3 files \u2192 out.csv  |  2 excluded  |  1 errors"

    summary = batch_summary_message(
        save_path="/tmp/out.csv",
        rows_count=3,
        gates_count=2,
        skipped_count=1,
        errors_count=1,
        log_path="/tmp/out_excluded.csv",
    )

    assert "Files processed:          3" in summary
    assert "Gates applied:            2" in summary
    assert "Skipped (load errors):    1" in summary
    assert summary.endswith("Exclusion/warning log:\n/tmp/out_excluded.csv")

    details = batch_details_message(
        [("a.csv", "directly excluded")],
        ["b.csv: load error"],
    )

    assert "=== Excluded by family/direct rule ===" in details
    assert "  a.csv  \u2190 directly excluded" in details
    assert "=== Load errors ===" in details


def test_batch_target_warning_messages():
    assert no_batch_targets_message("/data", "___CytoFile", "csv") == (
        "No matching files found in:\n/data\n\n"
        "Pattern: '___CytoFile', types: csv"
    )

    msg = all_batch_targets_excluded_message(
        [("a.csv", "directly excluded"), ("b.csv", "family excluded")]
    )

    assert msg.startswith("All matching files were excluded (2 total).")
    assert "  a.csv  \u2190 directly excluded" in msg


def test_apply_parent_region_filter_returns_filtered_frame_or_reason():
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")
    df = pd.DataFrame({"X": [1.0, 2.0, 3.0], "Y": [1.0, 2.0, 3.0]})
    gate = {"name": "Parent"}

    filtered, reason = apply_parent_region_filter(
        df,
        x_channel="X",
        y_channel="Y",
        parent_gate=gate,
        parent_region="IN",
        regions_for_parent=lambda _gate, _x, _y: {
            "IN": np.array([False, True, False])
        },
    )

    assert reason is None
    assert filtered.to_dict("list") == {"X": [2.0], "Y": [2.0]}

    filtered, reason = apply_parent_region_filter(
        df,
        x_channel="X",
        y_channel="Y",
        parent_gate=gate,
        parent_region="MISSING",
        regions_for_parent=lambda _gate, _x, _y: {},
    )

    assert filtered is None
    assert reason == "parent region 'MISSING' is unavailable — skipped"


def test_build_batch_stats_row_uses_labels_paths_and_gate_counts(tmp_path):
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")
    root = tmp_path
    path = root / "old" / "file_0.csv"
    path.parent.mkdir()
    path.write_text("X,Y\n1,1\n2,2\n3,3\n")
    df = pd.DataFrame({"X": [1.0, 2.0, 3.0], "Y": [1.0, 2.0, 3.0]})
    gate = {"name": "Gate A"}

    row = build_batch_stats_row(
        df=df,
        file_path=str(path),
        folder=str(root),
        ambiguous={"file_0"},
        x_channel="X",
        y_channel="Y",
        gates=[gate],
        regions_for_gate=lambda _gate, _x, _y: {
            "IN": np.array([True, False, True]),
            "OUT": np.array([False, True, False]),
        },
    )

    assert row["Sample"] == "old/file_0"
    assert row["Total_Cells"] == 3
    assert row["Relative_Path"] == "old/file_0.csv"
    assert row["Source_File"] == str(path)
    assert row["Gate A__IN__N"] == 2
    assert row["Gate A__IN__pct"] == 66.667


def test_duplicate_gate_names_get_distinct_wide_export_columns(tmp_path):
    pd = pytest.importorskip("pandas")
    np = pytest.importorskip("numpy")
    path = tmp_path / "sample.csv"
    df = pd.DataFrame({"X": [1.0, 2.0], "Y": [1.0, 2.0]})
    gates = [
        {"id": 1, "name": "Gate"},
        {"id": 2, "name": "Gate"},
    ]
    assert gate_output_labels(gates) == ["Gate__id1", "Gate__id2"]
    row = build_batch_stats_row(
        df=df, file_path=str(path), folder=str(tmp_path), ambiguous=set(),
        x_channel="X", y_channel="Y", gates=gates,
        regions_for_gate=lambda gate, _x, _y: {
            "IN": np.array([gate["id"] == 1, gate["id"] == 2]),
            "OUT": np.array([gate["id"] != 1, gate["id"] != 2]),
        },
    )
    assert row["Gate__id1__IN__N"] == 1
    assert row["Gate__id2__IN__N"] == 1


def test_region_universe_total_and_batch_row_use_valid_gate_denominator(tmp_path):
    np = pytest.importorskip("numpy")
    pd = pytest.importorskip("pandas")
    # BatchStatsRunner removes transform-invalid rows before this helper.
    # Preserve the larger pre-transform input only as explicit provenance.
    df = pd.DataFrame({"X": [1.0, 2.0], "Y": [1.0, 2.0]})
    regions = {
        "IN": np.array([True, False]),
        "OUT": np.array([False, True]),
    }
    assert region_universe_total(regions, 2) == 2

    row = build_batch_stats_row(
        df=df, file_path=str(tmp_path / "sample.csv"), folder=str(tmp_path),
        ambiguous=set(), x_channel="X", y_channel="Y",
        gates=[{"id": 1, "name": "G"}],
        regions_for_gate=lambda *_args: regions,
        source_total=3, input_total=3,
    )
    assert row["Source_Total_Cells"] == 3
    assert row["Input_Total_Cells"] == 3
    assert row["Total_Cells"] == 2
    assert row["Transform_Excluded_Cells"] == 1
    assert row["G__IN__pct"] == 50.0
    assert row["G__OUT__pct"] == 50.0


def test_add_gate_region_counts_rejects_normalized_region_name_collision():
    np = pytest.importorskip("numpy")
    with pytest.raises(ValueError, match="normalize"):
        add_gate_region_counts(
            {}, "G",
            {"A/B": np.array([True]), "A_B": np.array([False])},
            total=1,
        )


def test_region_universe_total_rejects_wrong_mask_length():
    np = pytest.importorskip("numpy")
    with pytest.raises(ValueError, match="mask length"):
        region_universe_total({"IN": np.array([True])}, 2)


def test_region_universe_total_rejects_incomplete_partition():
    np = pytest.importorskip("numpy")
    with pytest.raises(ValueError, match="incomplete partition"):
        region_universe_total(
            {"IN": np.array([True, False]), "OUT": np.array([False, False])},
            2,
        )


def test_region_universe_total_rejects_overlapping_region_masks():
    np = pytest.importorskip("numpy")
    with pytest.raises(ValueError, match="overlaps"):
        region_universe_total(
            {
                "A": np.array([True, False, True]),
                "B": np.array([False, True, True]),
            },
            3,
        )


def test_batch_row_rejects_incompatible_gate_denominators(tmp_path):
    np = pytest.importorskip("numpy")
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"X": [1.0, 2.0], "Y": [1.0, 2.0]})
    gates = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
    def regions_for_gate(gate, _x, _y):
        if gate["id"] == 1:
            return {"IN": np.array([True, False]), "OUT": np.array([False, True])}
        return {"IN": np.array([True, False]), "OUT": np.array([False, False])}
    with pytest.raises(ValueError, match="incomplete partition"):
        build_batch_stats_row(
            df=df, file_path=str(tmp_path / "sample.csv"), folder=str(tmp_path),
            ambiguous=set(), x_channel="X", y_channel="Y", gates=gates,
            regions_for_gate=regions_for_gate,
        )


def test_parent_region_filter_rejects_wrong_mask_length():
    np = pytest.importorskip("numpy")
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"X": [1.0, 2.0], "Y": [1.0, 2.0]})
    with pytest.raises(ValueError, match="mask length"):
        apply_parent_region_filter(
            df, x_channel="X", y_channel="Y", parent_gate={"id": 1},
            parent_region="IN",
            regions_for_parent=lambda *_args: {"IN": np.array([True])},
        )


def test_exact_exclusions_preserve_case_on_case_sensitive_filesystems(tmp_path):
    from vflow.services.batch_stats_export import batch_exclusion_sets, discover_batch_target_files
    import os

    upper = tmp_path / "Sample.csv"
    lower = tmp_path / "sample.csv"
    upper.write_text("X,Y\n1,2\n", encoding="utf-8")
    lower.write_text("X,Y\n3,4\n", encoding="utf-8")
    excl_paths, excl_stems = batch_exclusion_sets({str(upper)})
    targets, skipped = discover_batch_target_files(
        str(tmp_path), "", "csv", excl_paths, set()
    )
    if os.path.normcase("A") != os.path.normcase("a"):
        assert str(lower) in targets
        assert str(upper) not in targets


def test_concat_detection_prefers_source_path_over_duplicate_basenames():
    import pandas as pd
    from vflow.services.batch_stats_export import concat_skip_reason

    df = pd.DataFrame({
        "Source_File": ["sample.csv", "sample.csv"],
        "Source_Path": ["/run1/sample.csv", "/run2/sample.csv"],
        "X": [1, 2],
    })
    reason = concat_skip_reason(df)
    assert reason is not None
    assert "2 sources by Source_Path" in reason


def test_batch_discovery_deduplicates_filesystem_aliases(tmp_path):
    original = tmp_path / "sample.csv"
    alias = tmp_path / "alias.csv"
    original.write_text("X,Y\n1,2\n", encoding="utf-8")
    try:
        alias.symlink_to(original)
    except OSError:
        pytest.skip("symlinks unavailable")

    targets, skipped = discover_batch_target_files(
        str(tmp_path), "", "csv", set(), set()
    )
    assert len(targets) == 1
    assert len(skipped) == 1
    assert "duplicate filesystem alias" in skipped[0][1]


def test_add_gate_region_counts_rejects_cross_gate_composite_column_collision():
    np = pytest.importorskip("numpy")
    row = {}
    add_gate_region_counts(
        row,
        "A__B",
        {"C": np.array([True, False])},
        total=1,
    )
    with pytest.raises(ValueError, match="output column collision"):
        add_gate_region_counts(
            row,
            "A",
            {"B__C": np.array([True, False])},
            total=1,
        )


def test_batch_stats_row_exposes_input_and_transform_excluded_denominator():
    np = pytest.importorskip("numpy")
    import pandas as pd

    # The runner passes only transform-valid rows to the row builder and carries
    # the larger input/source totals separately as provenance.
    df = pd.DataFrame({"X": [1.0, 2.0], "Y": [1.0, 2.0]})
    gate = {"id": 1, "name": "G", "type": "rectangle"}

    def regions_for_gate(_gate, xa, ya):
        return {
            "IN": np.array([True, False]),
            "OUT": np.array([False, True]),
        }

    row = build_batch_stats_row(
        df=df, file_path="/tmp/a.csv", folder="/tmp", ambiguous=set(),
        x_channel="X", y_channel="Y", gates=[gate],
        regions_for_gate=regions_for_gate,
        source_total=4, input_total=4,
    )
    assert row["Source_Total_Cells"] == 4
    assert row["Input_Total_Cells"] == 4
    assert row["Total_Cells"] == 2
    assert row["Transform_Excluded_Cells"] == 2
