"""Column-name normalization helpers."""

from __future__ import annotations

import pandas as pd


def column_rename_map_to_reference(
    df: pd.DataFrame,
    reference_dfs: list[pd.DataFrame],
) -> dict:
    """Map df columns to first-seen reference casing using case-insensitive keys."""
    validate_unambiguous_columns(df)
    ref_lower: dict = {}
    for ref_df in reference_dfs:
        validate_unambiguous_columns(ref_df)
        for col in ref_df.columns:
            ref_lower.setdefault(col.lower(), col)
    return {
        col: ref_lower[col.lower()]
        for col in df.columns
        if col.lower() in ref_lower and col != ref_lower[col.lower()]
    }



def casefold_column_collisions(columns) -> dict[str, list[str]]:
    """Return case-insensitive column-name collisions.

    Pandas permits columns that differ only by case, but vFlow intentionally
    normalizes channel casing across files. Such a DataFrame is therefore
    ambiguous: normalization could collapse two distinct columns onto one name.
    """
    groups: dict[str, list[str]] = {}
    for raw in columns:
        name = str(raw)
        groups.setdefault(name.casefold(), []).append(name)
    return {key: vals for key, vals in groups.items() if len(vals) > 1}


def validate_unambiguous_columns(df: pd.DataFrame) -> None:
    """Reject DataFrames whose columns differ only by letter case."""
    collisions = casefold_column_collisions(df.columns)
    if collisions:
        details = "; ".join(" / ".join(vals) for vals in collisions.values())
        raise ValueError(
            "Ambiguous channel columns differ only by case: " + details + ". "
            "Rename the channels so every case-insensitive name is unique."
        )

def normalize_columns_to_reference(
    df: pd.DataFrame,
    reference_dfs: list[pd.DataFrame],
) -> pd.DataFrame:
    """Rename df columns to match first-seen casing in reference_dfs."""
    if not reference_dfs:
        return df
    rename_map = column_rename_map_to_reference(df, reference_dfs)
    if rename_map:
        return df.rename(columns=rename_map)
    return df

