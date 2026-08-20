import pytest

pd = pytest.importorskip("pandas")

from vflow.services.concat_export import (
    build_concatenated_csv,
    concat_no_csv_message,
    concat_no_selection_message,
    concat_output_filename,
    concat_read_error_message,
    concat_save_path,
    concat_skipped_fcs_message,
    concat_success_message,
    concat_success_status,
)


def test_build_concatenated_csv_adds_source_file_and_resets_index(tmp_path):
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("Label,X\n1,10\n")
    b.write_text(",Label,X\n5,2,20\n")

    result = build_concatenated_csv([str(a), str(b)])

    assert result.error is None
    assert result.skipped_fcs == []
    assert result.data["Source_File"].tolist() == ["a.csv", "b.csv"]
    assert result.data["Source_Path"].tolist() == [str(a.resolve()), str(b.resolve())]
    assert result.data["Label"].tolist() == [1, 2]
    assert result.data["X"].tolist() == [10, 20]


def test_build_concatenated_csv_skips_fcs_files(tmp_path):
    csv_path = tmp_path / "a.csv"
    fcs_path = tmp_path / "b.fcs"
    csv_path.write_text("Label,X\n1,10\n")
    fcs_path.write_bytes(b"not used")

    result = build_concatenated_csv([str(fcs_path), str(csv_path)])

    assert result.error is None
    assert result.skipped_fcs == ["b.fcs"]
    assert result.data["Source_File"].tolist() == ["a.csv"]


def test_build_concatenated_csv_returns_none_when_no_csv_frames(tmp_path):
    fcs_path = tmp_path / "b.fcs"
    fcs_path.write_bytes(b"not used")

    result = build_concatenated_csv([str(fcs_path)])

    assert result.data is None
    assert result.skipped_fcs == ["b.fcs"]
    assert result.error is None


def test_build_concatenated_csv_reports_read_error(tmp_path):
    missing = tmp_path / "missing.csv"

    result = build_concatenated_csv([str(missing)])

    assert result.data is None
    assert result.skipped_fcs == []
    assert result.error[0] == "missing.csv"
    assert isinstance(result.error[1], Exception)


def test_concat_output_filename_and_path():
    assert concat_output_filename(" pooled ") == "pooled.csv"
    assert concat_output_filename("pooled.CSV") == "pooled.CSV"
    assert concat_save_path("/tmp/out", "pooled") == "/tmp/out/pooled.csv"


def test_concat_success_messages():
    path = "/tmp/out/pooled.csv"

    assert concat_success_status(path, n_files=2, n_rows=1234) == (
        "\u2713 2 file(s) \u00b7 1,234 rows  \u2192  pooled.csv"
    )
    assert concat_success_message(path, n_files=2, n_rows=1234) == (
        "Saved successfully:\n/tmp/out/pooled.csv\n\n"
        "2 file(s) \u00b7 1,234 rows"
    )


def test_concat_warning_and_error_messages():
    err = RuntimeError("boom")

    assert concat_no_selection_message() == (
        "No files selected \u2014 tick at least one file to concatenate."
    )
    assert concat_read_error_message("bad.csv", err) == "Could not read:\nbad.csv\n\nboom"
    assert concat_skipped_fcs_message(["a.fcs", "b.fcs"]) == (
        "FCS files are excluded from concatenation (CSV only):\n"
        "a.fcs\nb.fcs"
    )
    assert concat_no_csv_message() == "No CSV files in selection to concatenate."


def test_build_concatenated_csv_disambiguates_duplicate_basenames(tmp_path):
    a_dir = tmp_path / "run_a"
    b_dir = tmp_path / "run_b"
    a_dir.mkdir(); b_dir.mkdir()
    a = a_dir / "sample.csv"
    b = b_dir / "sample.csv"
    a.write_text("X\n1\n")
    b.write_text("X\n2\n")

    result = build_concatenated_csv([str(a), str(b)])

    assert result.error is None
    labels = result.data["Source_File"].drop_duplicates().tolist()
    assert labels == ["run_a/sample.csv", "run_b/sample.csv"]
    assert result.data["Source_Path"].tolist() == [str(a.resolve()), str(b.resolve())]


def test_build_concatenated_csv_rejects_nested_provenance(tmp_path):
    path = tmp_path / "already_concat.csv"
    path.write_text("Source_File,X\na.csv,1\n")

    result = build_concatenated_csv([str(path)])

    assert result.data is None
    assert isinstance(result.error[1], ValueError)
    assert "provenance" in str(result.error[1]).lower()


def test_concatenate_rejects_same_physical_file_via_alias(tmp_path):
    original = tmp_path / "sample.csv"
    alias = tmp_path / "alias.csv"
    original.write_text("X\n1\n", encoding="utf-8")
    try:
        alias.symlink_to(original)
    except OSError:
        pytest.skip("symlinks unavailable")

    result = build_concatenated_csv([str(original), str(alias)])
    assert result.data is None
    assert isinstance(result.error[1], ValueError)
    assert "same physical CSV" in str(result.error[1])
