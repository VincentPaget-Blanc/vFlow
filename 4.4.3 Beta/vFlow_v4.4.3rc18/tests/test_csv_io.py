import pytest

pd = pytest.importorskip("pandas")

from vflow.core.data_io import read_flow_data_file, smart_read_csv


def test_smart_read_csv_keeps_named_first_column(tmp_path):
    path = tmp_path / "named.csv"
    path.write_text("Label,Intensity_TH\n1,107\n2,209\n")

    df = smart_read_csv(str(path))

    assert list(df.columns) == ["Label", "Intensity_TH"]
    assert list(df["Intensity_TH"]) == [107, 209]


def test_smart_read_csv_drops_unnamed_index_column(tmp_path):
    path = tmp_path / "indexed.csv"
    path.write_text(",Label,Intensity_TH\n1,1,107\n2,2,209\n")

    df = smart_read_csv(str(path))

    assert list(df.columns) == ["Label", "Intensity_TH"]
    assert list(df.index) == [0, 1]
    assert df.attrs["csv_ambiguous_channel_names"] == ()


def test_read_flow_data_file_uses_csv_reader(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text(",Label,Intensity_TH\n1,1,107\n")

    df = read_flow_data_file(str(path))

    assert list(df.columns) == ["Label", "Intensity_TH"]



def test_smart_read_csv_preserves_legitimate_unnamed_measurement_column(tmp_path):
    path = tmp_path / "unnamed_measurement.csv"
    path.write_text(",Label,Intensity_TH\n10.5,1,107\n11.5,2,209\n")

    df = smart_read_csv(str(path))

    assert len(df.columns) == 3
    assert str(df.columns[0]).lower().startswith("unnamed:")
    assert df.iloc[:, 0].tolist() == [10.5, 11.5]
    assert df.attrs["csv_ambiguous_channel_names"] == (str(df.columns[0]),)


def test_smart_read_csv_does_not_drop_nonsequential_integer_first_column(tmp_path):
    path = tmp_path / "unnamed_ids.csv"
    path.write_text(",Label\n10,1\n20,2\n")

    df = smart_read_csv(str(path))

    assert len(df.columns) == 2
    assert df.iloc[:, 0].tolist() == [10, 20]
    assert df.attrs["csv_ambiguous_channel_names"] == (str(df.columns[0]),)


def test_csv_case_insensitive_channel_collision_is_rejected(tmp_path):
    path = tmp_path / "ambiguous.csv"
    path.write_text("CD3,cd3\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differ only by case"):
        smart_read_csv(path)


def test_smart_read_csv_rejects_exact_duplicate_headers_before_pandas_mangles_them(tmp_path):
    path = tmp_path / "duplicate_headers.csv"
    path.write_text("X,X,Y\n1,2,3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate CSV column"):
        smart_read_csv(str(path))
