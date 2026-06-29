"""Flow data file readers."""

from __future__ import annotations

import os

import pandas as pd

from .fcs_reader import read_fcs


def smart_read_csv(path: str) -> pd.DataFrame:
    """Read CSV files while discarding an unnamed leading row-index column."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            first_col = fh.readline().split(",")[0].strip()
    except Exception:
        first_col = "data"

    if first_col == "":
        df = pd.read_csv(path, index_col=0)
        df.index = range(len(df))
        return df
    return pd.read_csv(path)


def read_flow_data_file(path: str) -> pd.DataFrame:
    """Load a CSV or FCS flow data file as a DataFrame."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".fcs":
        df, _ = read_fcs(path)
        return df
    return smart_read_csv(path)

