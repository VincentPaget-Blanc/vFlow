"""Column-name normalization helpers."""

from __future__ import annotations

import pandas as pd


def column_rename_map_to_reference(
    df: pd.DataFrame,
    reference_dfs: list[pd.DataFrame],
) -> dict:
    """Map df columns to first-seen reference casing using case-insensitive keys."""
    ref_lower: dict = {}
    for ref_df in reference_dfs:
        for col in ref_df.columns:
            ref_lower.setdefault(col.lower(), col)
    return {
        col: ref_lower[col.lower()]
        for col in df.columns
        if col.lower() in ref_lower and col != ref_lower[col.lower()]
    }


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

