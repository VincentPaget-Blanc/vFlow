from vflow.ui.folder_scan_dialog import (
    folder_scan_count_text,
    folder_scan_default_concat_filename,
    folder_scan_relative_label,
    matching_folder_scan_files,
)


def test_matching_folder_scan_files_filters_csv_fcs_and_pattern(tmp_path):
    csv_path = tmp_path / "sample_CytoFile.csv"
    fcs_path = tmp_path / "other_CytoFile.fcs"
    ignored = tmp_path / "sample_CytoFile.txt"
    csv_path.write_text("")
    fcs_path.write_bytes(b"")
    ignored.write_text("")

    assert matching_folder_scan_files(str(tmp_path), "cytofile") == [
        str(fcs_path),
        str(csv_path),
    ]


def test_matching_folder_scan_files_recurses_and_blank_pattern_matches_all(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    root_csv = tmp_path / "root.csv"
    child_fcs = sub / "child.FCS"
    root_csv.write_text("")
    child_fcs.write_bytes(b"")

    assert matching_folder_scan_files(str(tmp_path), "") == [
        str(root_csv),
        str(child_fcs),
    ]


def test_matching_folder_scan_files_invalid_folder_returns_empty():
    assert matching_folder_scan_files("", "") == []
    assert matching_folder_scan_files("/missing/folder", "") == []


def test_folder_scan_default_concat_filename():
    assert folder_scan_default_concat_filename("/tmp/run") == "run_Concatenate.csv"
    assert folder_scan_default_concat_filename("/tmp/run/") == "run_Concatenate.csv"
    assert folder_scan_default_concat_filename("") == "data_Concatenate.csv"


def test_folder_scan_count_text():
    assert folder_scan_count_text([]) == "0 files found."
    assert folder_scan_count_text(["a.csv", "b.fcs"]) == "2 file(s) found."


def test_folder_scan_relative_label(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    path = sub / "sample.csv"
    path.write_text("")

    assert folder_scan_relative_label(str(path), str(tmp_path)) == "sub/sample.csv"
