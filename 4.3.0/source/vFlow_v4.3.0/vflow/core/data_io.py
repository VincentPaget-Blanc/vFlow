"""Flow data file readers."""

from __future__ import annotations

import csv
import os

import numpy as np
import pandas as pd

from .fcs_reader import read_fcs
from .column_normalization import validate_unambiguous_columns


def _validate_csv_header(path: str) -> tuple[int, ...]:
    """Reject duplicate/ambiguous raw CSV headers before pandas mangles them.

    ``pandas.read_csv`` silently rewrites duplicate headers such as ``X,X`` to
    ``X,X.1``.  For channel data that changes the schema rather than reporting
    the ambiguity, so inspect the raw CSV header first.
    """
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            return ()

    blank_positions = tuple(
        i for i, raw_name in enumerate(header) if not str(raw_name).strip()
    )
    groups: dict[str, list[str]] = {}
    for raw_name in header:
        name = str(raw_name).strip()
        if not name:
            # A single blank first header can be a saved DataFrame index and is
            # handled by _looks_like_saved_row_index after parsing. Multiple
            # blank headers are intrinsically ambiguous channel identities.
            key = "<blank>"
        else:
            key = name.casefold()
        groups.setdefault(key, []).append(name or "<blank>")
    collisions = [values for values in groups.values() if len(values) > 1]
    if collisions:
        details = "; ".join(" / ".join(values) for values in collisions)
        case_only = any(len(set(values)) > 1 for values in collisions)
        qualifier = "; some differ only by case" if case_only else ""
        raise ValueError(
            "Ambiguous duplicate CSV column header(s): " + details + qualifier + ". "
            "Rename the columns so every channel header is unique before loading."
        )
    return blank_positions


def _looks_like_saved_row_index(values) -> bool:
    """Return True only for an integer 0..N-1 or 1..N row-number column."""
    series = pd.Series(values)
    if series.empty or series.isna().any():
        return False
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isna().any():
        return False
    arr = numeric.to_numpy(dtype=float, copy=False)
    if not np.isfinite(arr).all() or not np.equal(arr, np.floor(arr)).all():
        return False
    ints = arr.astype(np.int64)
    n = len(ints)
    return bool(
        np.array_equal(ints, np.arange(n, dtype=np.int64))
        or np.array_equal(ints, np.arange(1, n + 1, dtype=np.int64))
    )


def smart_read_csv(path: str) -> pd.DataFrame:
    """Read a CSV without silently deleting a legitimate unnamed column.

    Pandas names a blank first header ``Unnamed: 0``.  vFlow discards that
    column only when its values are demonstrably a saved row-number index
    (0..N-1 or 1..N).  Otherwise the column is preserved as data.
    """
    blank_positions = _validate_csv_header(path)
    df = pd.read_csv(path)
    dropped_first_index = False
    if len(df.columns):
        first = str(df.columns[0]).strip()
        if first == "" or first.lower().startswith("unnamed:"):
            if _looks_like_saved_row_index(df.iloc[:, 0]):
                df = df.iloc[:, 1:].copy()
                df.index = range(len(df))
                dropped_first_index = True
    validate_unambiguous_columns(df)

    # Preserve a legitimate unnamed measurement within one CSV, but never let
    # pandas' synthetic ``Unnamed: N`` label become an automatic biological
    # channel identity across multiple files.  The saved-row-index case above
    # is removed and therefore needs no ambiguity marker.
    ambiguous = []
    for raw_pos in blank_positions:
        if dropped_first_index and raw_pos == 0:
            continue
        pos = raw_pos - 1 if dropped_first_index and raw_pos > 0 else raw_pos
        if 0 <= pos < len(df.columns):
            ambiguous.append(str(df.columns[pos]))
    df.attrs["csv_ambiguous_channel_names"] = tuple(ambiguous)
    return df


def read_flow_data_file(path: str) -> pd.DataFrame:
    """Load a CSV or FCS flow data file as a DataFrame."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".fcs":
        df, _ = read_fcs(path)
        validate_unambiguous_columns(df)
        return df
    return smart_read_csv(path)
