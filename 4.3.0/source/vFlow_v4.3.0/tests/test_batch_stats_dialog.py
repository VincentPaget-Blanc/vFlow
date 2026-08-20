from vflow.ui.batch_stats_dialog import (
    batch_preview_message,
    matching_batch_preview_files,
    validate_batch_stats_selection,
)


def test_matching_batch_preview_files_filters_suffix_and_type(tmp_path):
    (tmp_path / "a___CytoFile.csv").write_text("")
    (tmp_path / "b___CytoFile.FCS").write_text("")
    (tmp_path / "c_other.csv").write_text("")

    assert matching_batch_preview_files(str(tmp_path), "___CytoFile", "csv") == [
        "a___CytoFile.csv"
    ]
    assert matching_batch_preview_files(str(tmp_path), "___cytofile", "fcs") == [
        "b___CytoFile.FCS"
    ]
    assert matching_batch_preview_files(str(tmp_path), "___CytoFile", "both") == [
        "a___CytoFile.csv",
        "b___CytoFile.FCS",
    ]


def test_matching_batch_preview_files_recurses_and_blank_suffix_matches_all(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "root.csv").write_text("")
    (sub / "child.fcs").write_text("")
    (tmp_path / "ignore.txt").write_text("")

    assert matching_batch_preview_files(str(tmp_path), "", "both") == [
        "root.csv",
        "child.fcs",
    ]


def test_matching_batch_preview_files_invalid_folder_returns_empty():
    assert matching_batch_preview_files("", "", "both") == []
    assert matching_batch_preview_files("/missing/folder", "", "both") == []


def test_batch_preview_message_for_no_matches():
    assert batch_preview_message([]) == ("No matching files found.", "#df4a4a")


def test_batch_preview_message_limits_examples():
    text, color = batch_preview_message(["a.csv", "b.csv", "c.csv", "d.csv", "e.csv"])

    assert text == (
        "5 file(s) matched:\n  a.csv\n  b.csv\n  c.csv\n  d.csv  … and 1 more"
    )
    assert color == "#4adf8a"


def test_validate_batch_stats_selection_returns_result(tmp_path):
    result, warning = validate_batch_stats_selection(
        f" {tmp_path} ", " suffix ", " csv ", " /tmp/out.csv "
    )

    assert result == (str(tmp_path), "suffix", "csv", "/tmp/out.csv")
    assert warning is None


def test_validate_batch_stats_selection_requires_valid_folder(tmp_path):
    result, warning = validate_batch_stats_selection(
        str(tmp_path / "missing"), "", "csv", "/tmp/out.csv"
    )

    assert result is None
    assert warning == "Select a valid root folder."


def test_validate_batch_stats_selection_requires_save_path(tmp_path):
    result, warning = validate_batch_stats_selection(str(tmp_path), "", "csv", "")

    assert result is None
    assert warning == "Choose an output file path."
