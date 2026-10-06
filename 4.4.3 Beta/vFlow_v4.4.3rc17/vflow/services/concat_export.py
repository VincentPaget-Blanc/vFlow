"""Concatenate selected CSV files for vFlow."""

from __future__ import annotations

from dataclasses import dataclass
import os

import pandas as pd

from vflow.core.data_io import smart_read_csv
from vflow.core.path_identity import file_identity_key
from vflow.core.sample_labels import unique_source_labels
from vflow.services.concat_paths import concat_output_filename, concat_save_path


@dataclass
class ConcatResult:
    data: pd.DataFrame | None
    skipped_fcs: list[str]
    error: tuple[str, Exception] | None = None


def concat_success_status(save_path: str, *, n_files: int, n_rows: int) -> str:
    return (f"\u2713 {n_files} file(s) \u00b7 {n_rows:,} rows  \u2192  "
            f"{os.path.basename(save_path)}")


def concat_success_message(save_path: str, *, n_files: int, n_rows: int) -> str:
    return (f"Saved successfully:\n{save_path}\n\n"
            f"{n_files} file(s) \u00b7 {n_rows:,} rows")


def concat_no_selection_message() -> str:
    return "No files selected \u2014 tick at least one file to concatenate."


def concat_read_error_message(filename: str, exc: Exception) -> str:
    return f"Could not read:\n{filename}\n\n{exc}"


def concat_skipped_fcs_message(skipped_fcs: list[str]) -> str:
    return ("FCS files are excluded from concatenation "
            "(CSV only):\n" + "\n".join(skipped_fcs))


def concat_no_csv_message() -> str:
    return "No CSV files in selection to concatenate."


def build_concatenated_csv(paths: list[str]) -> ConcatResult:
    """Concatenate CSVs with collision-safe, auditable source identity.

    ``Source_File`` stays as the basename when unique.  Duplicate basenames
    are automatically disambiguated with the shortest distinguishing parent
    directory suffix so downstream grouping cannot merge different files.
    ``Source_Path`` stores the normalized absolute origin as an audit trail.
    """
    csv_paths = [str(path) for path in paths
                 if os.path.splitext(str(path))[1].lower() != ".fcs"]
    labels = unique_source_labels(csv_paths)
    frames = []
    skipped = []
    seen_physical = {}
    for raw_path in paths:
        path = str(raw_path)
        ext = os.path.splitext(path)[1].lower()
        if ext == ".fcs":
            skipped.append(os.path.basename(path))
            continue
        key = file_identity_key(path)
        if key in seen_physical:
            exc = ValueError(
                f"The same physical CSV was selected more than once: "
                f"{seen_physical[key]!r} and {path!r}. Refusing to duplicate rows."
            )
            return ConcatResult(None, skipped, (os.path.basename(path), exc))
        seen_physical[key] = path
        try:
            df = smart_read_csv(path).copy()
            if "Source_File" in df.columns or "Source_Path" in df.columns:
                raise ValueError(
                    "Input already contains Source_File/Source_Path provenance columns; "
                    "refusing to overwrite or nest concatenation provenance."
                )
            df.insert(0, "Source_Path", os.path.abspath(os.path.normpath(path)))
            df.insert(0, "Source_File", labels[path])
            frames.append(df)
        except Exception as exc:
            return ConcatResult(None, skipped, (os.path.basename(path), exc))

    if not frames:
        return ConcatResult(None, skipped, None)

    return ConcatResult(pd.concat(frames, ignore_index=True), skipped, None)
