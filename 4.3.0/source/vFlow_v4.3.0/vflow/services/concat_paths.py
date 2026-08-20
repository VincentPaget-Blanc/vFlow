"""Dependency-light concatenate output path helpers."""

from __future__ import annotations

import os


def concat_output_filename(filename: str) -> str:
    """Return the legacy concat output filename with a .csv extension."""
    name = filename.strip()
    if name and not name.lower().endswith(".csv"):
        name += ".csv"
    return name


def concat_save_path(out_folder: str, filename: str) -> str:
    """Return the full concat save path after legacy filename normalization."""
    return os.path.join(out_folder.strip(), concat_output_filename(filename))


__all__ = ["concat_output_filename", "concat_save_path"]

