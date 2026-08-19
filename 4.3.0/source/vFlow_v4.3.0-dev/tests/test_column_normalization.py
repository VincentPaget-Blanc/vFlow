import pytest

pd = pytest.importorskip("pandas")

from vflow.core.column_normalization import (
    column_rename_map_to_reference,
    normalize_columns_to_reference,
)


def test_column_normalization_uses_first_seen_reference_casing():
    reference = [
        pd.DataFrame(columns=["Label", "Intensity_VGAT"]),
        pd.DataFrame(columns=["Intensity_vgat"]),
    ]
    df = pd.DataFrame({"label": [1], "Intensity_vGAT": [2], "Other": [3]})

    renamed = normalize_columns_to_reference(df, reference)

    assert list(renamed.columns) == ["Label", "Intensity_VGAT", "Other"]


def test_column_rename_map_is_empty_without_case_mismatch():
    reference = [pd.DataFrame(columns=["Label", "Intensity_VGAT"])]
    df = pd.DataFrame({"Label": [1], "Intensity_VGAT": [2]})

    assert column_rename_map_to_reference(df, reference) == {}



def test_case_insensitive_duplicate_columns_are_rejected():
    from vflow.core.column_normalization import validate_unambiguous_columns

    df = pd.DataFrame([[1, 2]], columns=["Intensity_VGAT", "Intensity_vgat"])
    with pytest.raises(ValueError, match="differ only by case"):
        validate_unambiguous_columns(df)


def test_normalization_refuses_ambiguous_reference_columns():
    reference = [pd.DataFrame([[1, 2]], columns=["CD3", "cd3"])]
    df = pd.DataFrame({"CD3": [1]})
    with pytest.raises(ValueError, match="differ only by case"):
        normalize_columns_to_reference(df, reference)
