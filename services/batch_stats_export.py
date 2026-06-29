"""Pure helpers for batch stats export."""

from __future__ import annotations

from collections import Counter
import os


def family_exclusion_match(target_stem: str, excluded_stems: set[str]):
    """Return (shared_prefix, matched_excluded_stem) for family exclusions."""
    ts = target_stem.lower()
    for raw_es in excluded_stems:
        es = raw_es.lower()
        if es == ts:
            return es + "_", es
        cp = os.path.commonprefix([es, ts])
        if "_" not in cp:
            continue
        cp = cp[: cp.rfind("_") + 1]
        if len(cp) >= len(es) or len(cp) >= len(ts):
            continue
        if cp.count("_") < 2:
            continue
        return cp, es
    return None, None


def batch_file_extensions(file_types: str) -> list[str]:
    exts = []
    if file_types in ("csv", "both"):
        exts.append(".csv")
    if file_types in ("fcs", "both"):
        exts += [".fcs", ".FCS"]
    return exts


def discover_batch_target_files(
    folder: str,
    suffix: str,
    file_types: str,
    excluded_paths: set[str],
    excluded_stems: set[str],
):
    """Find batch targets and return (target_files, skipped_exclusions)."""
    exts = batch_file_extensions(file_types)
    ext_lowers = [ext.lower() for ext in exts]
    suffix_lower = suffix.strip().lower()
    target_files = []
    skipped = []

    for root_d, _, files in os.walk(folder):
        for fname in sorted(files):
            base, ext = os.path.splitext(fname)
            if ext.lower() not in ext_lowers:
                continue
            if suffix_lower and suffix_lower not in fname.lower():
                continue
            fpath = os.path.join(root_d, fname)

            if fpath.lower() in excluded_paths:
                skipped.append((fname, "directly excluded from analysis"))
                continue

            prefix, matched_excl = family_exclusion_match(base, excluded_stems)
            if prefix is not None:
                skipped.append(
                    (
                        fname,
                        f"family of excluded '{matched_excl}' "
                        f"(shared prefix '{prefix}')",
                    )
                )
                continue

            target_files.append(fpath)

    return target_files, skipped


def ambiguous_stems(paths: list[str]) -> set[str]:
    counts = Counter(os.path.splitext(os.path.basename(path))[0] for path in paths)
    return {stem for stem, count in counts.items() if count > 1}


def sample_label_for_path(path: str, folder: str, ambiguous: set[str]) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    if stem not in ambiguous:
        return stem
    try:
        rel_dir = os.path.relpath(os.path.dirname(path), folder)
        if rel_dir and rel_dir != ".":
            return f"{rel_dir.replace(os.sep, '/')}/{stem}"
    except ValueError:
        pass
    return stem


def relative_path_for_output(path: str, folder: str) -> str:
    try:
        return os.path.relpath(path, folder).replace(os.sep, "/")
    except ValueError:
        return path


def concat_skip_reason(df):
    """Return a skip reason for concatenated files, or None."""
    if "Source_File" not in df.columns:
        return None
    src_unique = df["Source_File"].dropna().unique()
    if len(src_unique) > 1:
        return (
            f"concatenated file ({len(src_unique)} sources) — "
            f"skipped to avoid double counting; analyze the originals instead"
        )
    return None


def previous_batch_output_skip_reason(df, x_channel: str):
    """Return a skip reason for previous batch outputs, or None."""
    if (
        "Sample" in df.columns
        and "Total_Cells" in df.columns
        and x_channel not in df.columns
    ):
        return (
            "appears to be previous batch output (Sample/Total_Cells"
            " columns present, no channel data) — skipped"
        )
    return None


def safe_region_column_name(region_name: str) -> str:
    return region_name.replace("/", "_").replace(" ", "_")


def add_gate_region_counts(row: dict, gate_name: str, regions: dict, total: int) -> dict:
    """Add wide-format N/pct columns for one gate's region masks."""
    for region_name, mask in regions.items():
        count = int(mask.sum())
        pct = round(count / total * 100, 3) if total else 0.0
        safe = safe_region_column_name(region_name)
        row[f"{gate_name}__{safe}__N"] = count
        row[f"{gate_name}__{safe}__pct"] = pct
    return row


def ordered_batch_columns(columns) -> list:
    """Return legacy batch stats column order."""
    meta_cols = {"Sample", "Total_Cells", "Source_File", "Relative_Path"}
    gate_cols = [col for col in columns if col not in meta_cols]
    tail = [col for col in ("Relative_Path", "Source_File") if col in columns]
    return ["Sample", "Total_Cells"] + sorted(gate_cols) + tail


def excluded_log_rows(skipped_exclusions: list[tuple[str, str]], errors: list[str]) -> list[dict]:
    """Build rows for the batch excluded/error CSV log."""
    rows = [
        {"Filename": filename, "Full_Path": "", "Reason": reason}
        for filename, reason in skipped_exclusions
    ]
    for err_msg in errors:
        parts = err_msg.split(": ", 1)
        rows.append(
            {
                "Filename": parts[0],
                "Full_Path": "",
                "Reason": parts[1] if len(parts) > 1 else err_msg,
            }
        )
    return rows


def apply_parent_region_filter(
    df,
    *,
    x_channel: str,
    y_channel: str,
    parent_gate: dict,
    parent_region: str,
    regions_for_parent,
):
    """Return (filtered_df, error_reason) for sub-gate batch prefiltering."""
    xa_all = df[x_channel].to_numpy(dtype=float, copy=False)
    ya_all = df[y_channel].to_numpy(dtype=float, copy=False)
    regions = regions_for_parent(parent_gate, xa_all, ya_all)
    mask = regions.get(parent_region)
    if mask is None or not mask.any():
        return None, f"no cells in parent region '{parent_region}' — skipped"
    return df[mask].reset_index(drop=True), None


def build_batch_stats_row(
    *,
    df,
    file_path: str,
    folder: str,
    ambiguous: set[str],
    x_channel: str,
    y_channel: str,
    gates: list[dict],
    regions_for_gate,
) -> dict:
    """Build one wide-format batch stats row for a file DataFrame."""
    xa = df[x_channel].to_numpy(dtype=float, copy=False)
    ya = df[y_channel].to_numpy(dtype=float, copy=False)
    total = len(xa)

    row = {
        "Sample": sample_label_for_path(file_path, folder, ambiguous),
        "Total_Cells": total,
        "Relative_Path": relative_path_for_output(file_path, folder),
        "Source_File": file_path,
    }

    for gate in gates:
        regions = regions_for_gate(gate, xa, ya)
        add_gate_region_counts(row, gate["name"], regions, total)

    return row
