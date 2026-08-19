"""Batch plot sample assembly helpers."""

from __future__ import annotations

import os
from collections import Counter

from vflow.core.sample_labels import make_sample_label, shorten_common_prefix_labels


def common_numeric_columns(dataframes: list) -> list:
    sets = [set(df.select_dtypes(include="number").columns) for df in dataframes]
    common = sorted(set.intersection(*sets)) if sets else []
    return [col for col in common if col.lower() not in ("label", "index")]


def preferred_distribution_column(columns: list) -> str:
    return next((col for col in columns if "distance" in col.lower() or "dist" in col.lower()),
                next((col for col in columns if "intensity" in col.lower()),
                     columns[0] if columns else ""))


def first_intensity_column(columns: list) -> str | None:
    return next((col for col in columns if "intensity" in col.lower()), None)


def first_distance_column(columns: list) -> str | None:
    return next((col for col in columns if "distance" in col.lower() or "dist" in col.lower()), None)


def has_source_file_samples(loaded_files: dict, active_paths: list) -> bool:
    for path in active_paths:
        df = loaded_files.get(path)
        if df is not None and "Source_File" in df.columns:
            return True
    return False


def _concat_groups(df):
    """Yield (provenance_key, source_display, group) without merging collisions."""
    if "Source_File" not in df.columns:
        return
    if "Source_Path" in df.columns:
        # New v4.1.9 concatenates: Source_Path is the stable identity.  Missing
        # paths fall back to Source_File, but remain scoped to this container.
        keys = df["Source_Path"].where(df["Source_Path"].notna(), df["Source_File"])
    else:
        keys = df["Source_File"]
    work = df.copy()
    work["__vflow_sample_key__"] = keys.astype(str)
    for key, group in work.groupby("__vflow_sample_key__", sort=True, dropna=False):
        source = str(group["Source_File"].iloc[0])
        yield str(key), source, group.drop(columns=["__vflow_sample_key__"]).reset_index(drop=True)


def _deduplicate_display_labels(records: list[dict]) -> None:
    """Make display labels unique without changing sample identity/grouping."""
    counts = Counter(rec["label"].casefold() for rec in records)
    used: set[str] = set()
    for rec in records:
        label = rec["label"]
        if counts[label.casefold()] > 1:
            container = make_sample_label(rec["container_path"])
            source_path = rec.get("source_path") or ""
            parent = os.path.basename(os.path.dirname(source_path)) if source_path else ""
            prefix = parent or container
            label = f"{prefix}/{label}" if prefix else label
        base = label
        suffix = 2
        while label.casefold() in used:
            label = f"{base} [{suffix}]"
            suffix += 1
        used.add(label.casefold())
        rec["label"] = label


def build_batch_plot_samples(
    *, loaded_files: dict, active_paths: list, file_colors: dict,
    sample_colors: list, sample_order: str = "input",
) -> list:
    """Return [(display_label, sub_df, color), ...] without dropping mixed inputs.

    Each active top-level file is processed independently.  Concatenated files
    are split into source samples; ordinary files remain ordinary samples.
    Thus selecting a concatenate and a normal CSV together never causes the
    normal CSV to disappear through a NaN ``Source_File`` groupby.
    """
    if not active_paths:
        return []

    records = []
    color_index = 0
    for path in sorted(active_paths):
        df = loaded_files.get(path)
        if df is None:
            continue
        if "Source_File" in df.columns:
            for key, source, group in _concat_groups(df):
                source_path = key if "Source_Path" in df.columns else ""
                records.append({
                    "raw_label": make_sample_label(source),
                    "df": group,
                    "color": sample_colors[color_index % len(sample_colors)],
                    "container_path": path,
                    "source_path": source_path,
                })
                color_index += 1
        else:
            records.append({
                "raw_label": make_sample_label(path),
                "df": df,
                "color": file_colors.get(path, sample_colors[color_index % len(sample_colors)]),
                "container_path": path,
                "source_path": path,
            })
            color_index += 1

    if not records:
        return []
    shortened = shorten_common_prefix_labels([rec["raw_label"] for rec in records])
    for rec, label in zip(records, shortened):
        rec["label"] = label
    _deduplicate_display_labels(records)

    samples = [(rec["label"], rec["df"], rec["color"]) for rec in records]
    if sample_order == "alpha":
        samples.sort(key=lambda item: item[0].casefold())
    return samples
