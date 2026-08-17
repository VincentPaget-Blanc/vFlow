"""Pure helpers for batch stats export."""

from __future__ import annotations

from collections import Counter
import os
import re

import numpy as np

from vflow.core.path_identity import file_identity_key, normalized_path


_POOLED_CYTOFILE_RE = re.compile(r"^(?P<family>.+)_pooled_cytofile$", re.IGNORECASE)
_ACQUISITION_CYTOFILE_RE = re.compile(
    r"^(?P<family>.+)_(?P<index>\d+)___cytofile$", re.IGNORECASE
)


def _cytofile_family(stem: str) -> str | None:
    """Return the explicit SynaptosomesMacro acquisition-family stem."""
    value = str(stem).strip().lower()
    for pattern in (_POOLED_CYTOFILE_RE, _ACQUISITION_CYTOFILE_RE):
        match = pattern.match(value)
        if match:
            family = match.group("family")
            return family if family else None
    return None


def family_exclusion_match(target_stem: str, excluded_stems: set[str]):
    """Return a documented CytoFile-family match, never a generic prefix match."""
    ts = str(target_stem).strip().lower()
    target_family = _cytofile_family(ts)
    if target_family is None:
        return None, None

    for raw_es in excluded_stems:
        es = str(raw_es).strip().lower()
        excluded_family = _cytofile_family(es)
        if excluded_family is not None and excluded_family == target_family:
            return target_family + "_", es
    return None, None


def batch_file_extensions(file_types: str) -> list[str]:
    exts = []
    if file_types in ("csv", "both"):
        exts.append(".csv")
    if file_types in ("fcs", "both"):
        exts += [".fcs", ".FCS"]
    return exts



def normalized_path_key(path: str) -> str:
    """Backward-compatible normalized path helper."""
    return normalized_path(path)

def batch_exclusion_sets(excluded_files: set[str]) -> tuple[set[str], set[str]]:
    """Return lower-case direct paths and stems for batch exclusion matching."""
    excluded_paths = {file_identity_key(path) for path in excluded_files}
    excluded_stems = {
        os.path.splitext(os.path.basename(path))[0].lower()
        for path in excluded_files
    }
    return excluded_paths, excluded_stems


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
    seen_physical = set()

    for root_d, _, files in os.walk(folder):
        for fname in sorted(files):
            base, ext = os.path.splitext(fname)
            if ext.lower() not in ext_lowers:
                continue
            if suffix_lower and suffix_lower not in fname.lower():
                continue
            fpath = os.path.join(root_d, fname)

            if file_identity_key(fpath) in excluded_paths:
                skipped.append((fname, "directly excluded from analysis"))
                continue

            physical_key = file_identity_key(fpath)
            if physical_key in seen_physical:
                skipped.append((fname, "duplicate filesystem alias of an already discovered file"))
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
            seen_physical.add(physical_key)

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
    """Return a skip reason for concatenated files, or None.

    Prefer Source_Path provenance because distinct source files can share the
    same basename. Legacy concatenates without Source_Path fall back to
    Source_File.
    """
    source_col = None
    if "Source_Path" in df.columns:
        source_col = "Source_Path"
    elif "Source_File" in df.columns:
        source_col = "Source_File"
    if source_col is None:
        return None
    src_unique = df[source_col].dropna().astype(str).unique()
    if len(src_unique) > 1:
        provenance = " by Source_Path" if source_col == "Source_Path" else ""
        return (
            f"concatenated file ({len(src_unique)} sources{provenance}) — "
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
    """Add wide-format N/pct columns, rejecting normalized-name collisions."""
    used: dict[str, str] = {}
    for region_name, raw_mask in regions.items():
        safe = safe_region_column_name(region_name)
        previous = used.get(safe)
        if previous is not None and previous != region_name:
            raise ValueError(
                f"Gate {gate_name!r} has region names {previous!r} and "
                f"{region_name!r} that both normalize to {safe!r}."
            )
        used[safe] = region_name
        mask = np.asarray(raw_mask, dtype=bool)
        if mask.ndim != 1:
            raise ValueError(f"Gate {gate_name!r} region {region_name!r} mask is not 1-D.")
        count = int(mask.sum())
        pct = round(count / total * 100, 3) if total else 0.0
        count_col = f"{gate_name}__{safe}__N"
        pct_col = f"{gate_name}__{safe}__pct"
        collisions = [col for col in (count_col, pct_col) if col in row]
        if collisions:
            raise ValueError(
                "Batch Stats output column collision for gate/region "
                f"{gate_name!r}/{region_name!r}: {', '.join(collisions)} already exists."
            )
        row[count_col] = count
        row[pct_col] = pct
    return row


def region_universe_total(regions: dict, expected_length: int) -> int:
    """Return the covered event total after validating a disjoint region partition."""
    union = np.zeros(expected_length, dtype=bool)
    for region_name, raw_mask in regions.items():
        mask = np.asarray(raw_mask, dtype=bool)
        if mask.ndim != 1 or len(mask) != expected_length:
            raise ValueError(
                f"Region {region_name!r} mask length does not match the "
                f"{expected_length} input events."
            )
        if np.any(union & mask):
            raise ValueError(
                f"Region {region_name!r} overlaps another gate region; refusing "
                "to report percentages from a non-disjoint partition."
            )
        union |= mask
    covered = int(union.sum())
    if covered != int(expected_length):
        raise ValueError(
            f"Gate regions cover {covered} events but the transform-valid "
            f"universe contains {expected_length}; refusing to shrink the "
            "batch denominator to an incomplete partition."
        )
    return covered



def gate_output_labels(gates: list[dict]) -> list[str]:
    """Return stable wide-export labels, disambiguating duplicate gate names."""
    counts = Counter(str(gate.get("name", "Gate")) for gate in gates)
    labels = []
    for gate in gates:
        name = str(gate.get("name", "Gate"))
        if counts[name] > 1:
            labels.append(f"{name}__id{gate.get('id', 'unknown')}")
        else:
            labels.append(name)
    return labels

def ordered_batch_columns(columns) -> list:
    """Return batch stats columns with explicit denominator provenance first."""
    leading = [
        col for col in (
            "Sample", "Source_Total_Cells", "Input_Total_Cells",
            "Total_Cells", "Transform_Excluded_Cells",
            "FCS_Compensation_Metadata", "Compensation_State"
        ) if col in columns
    ]
    meta_cols = set(leading) | {"Source_File", "Relative_Path"}
    gate_cols = [col for col in columns if col not in meta_cols]
    tail = [col for col in ("Relative_Path", "Source_File") if col in columns]
    return leading + sorted(gate_cols) + tail


def excluded_log_rows(
    skipped_exclusions: list[tuple[str, str]],
    errors: list[str],
    warnings: list[str] | None = None,
) -> list[dict]:
    """Build rows for the batch exclusion/error/warning CSV log."""
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
    for warning_msg in warnings or []:
        parts = warning_msg.split(": ", 1)
        detail = parts[1] if len(parts) > 1 else warning_msg
        rows.append(
            {
                "Filename": parts[0],
                "Full_Path": "",
                "Reason": "WARNING — " + detail,
            }
        )
    return rows


def no_batch_targets_message(folder: str, suffix: str, file_types: str) -> str:
    """Return the warning shown when no batch files match."""
    return (
        f"No matching files found in:\n{folder}\n\n"
        f"Pattern: '{suffix}', types: {file_types}"
    )


def all_batch_targets_excluded_message(skipped_exclusions: list[tuple[str, str]]) -> str:
    """Return the warning shown when every matching batch file is excluded."""
    excl_summary = "\n".join(
        f"  {filename}  \u2190 {reason}"
        for filename, reason in skipped_exclusions[:10]
    )
    return (
        f"All matching files were excluded ({len(skipped_exclusions)} total).\n\n"
        f"{excl_summary}"
    )


def batch_status_message(
    *,
    rows_count: int,
    save_path: str,
    skipped_count: int,
    errors_count: int,
    warnings_count: int = 0,
) -> str:
    """Return the legacy status-bar text after batch stats export."""
    msg = f"\u2713 Batch stats: {rows_count} files \u2192 {os.path.basename(save_path)}"
    if skipped_count:
        msg += f"  |  {skipped_count} excluded"
    if errors_count:
        msg += f"  |  {errors_count} errors"
    if warnings_count:
        msg += f"  |  {warnings_count} warnings"
    return msg


def batch_summary_message(
    *,
    save_path: str,
    rows_count: int,
    gates_count: int,
    skipped_count: int,
    errors_count: int,
    log_path: str,
    warnings_count: int = 0,
) -> str:
    """Return the legacy batch stats completion dialog text."""
    msg = (
        f"Batch stats exported:\n{save_path}\n\n"
        f"  Files processed:          {rows_count}\n"
        f"  Gates applied:            {gates_count}\n"
        f"  Excluded (family/direct): {skipped_count}"
    )
    if errors_count:
        msg += f"\n  Skipped (load errors):    {errors_count}"
    if warnings_count:
        msg += f"\n  Warnings (processed):     {warnings_count}"
    return msg + f"\n\nExclusion/warning log:\n{log_path}"


def batch_details_message(
    skipped_exclusions: list[tuple[str, str]],
    errors: list[str],
    warnings: list[str] | None = None,
) -> str:
    """Return the optional skipped/error/warning details dialog text."""
    lines = []
    if skipped_exclusions:
        lines.append("=== Excluded by family/direct rule ===")
        lines += [f"  {filename}  \u2190 {reason}" for filename, reason in skipped_exclusions]
    if errors:
        lines.append("\n=== Load errors ===")
        lines += [f"  {error}" for error in errors]
    if warnings:
        lines.append("\n=== Scientific provenance warnings (files still processed) ===")
        lines += [f"  {warning}" for warning in warnings]
    return "\n".join(lines)


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
    if mask is None:
        return None, f"parent region '{parent_region}' is unavailable — skipped"
    mask = np.asarray(mask, dtype=bool)
    if mask.ndim != 1 or len(mask) != len(df):
        raise ValueError(
            f"Parent region {parent_region!r} mask length does not match "
            f"the {len(df)} input rows."
        )
    if not mask.any():
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
    source_total: int | None = None,
    input_total: int | None = None,
    compensation_metadata_keys: tuple[str, ...] | list[str] = (),
) -> dict:
    """Build one wide-format batch stats row for a file DataFrame."""
    xa = df[x_channel].to_numpy(dtype=float, copy=False)
    ya = df[y_channel].to_numpy(dtype=float, copy=False)
    valid_input_rows = len(xa)
    source_total = valid_input_rows if source_total is None else int(source_total)
    input_total = valid_input_rows if input_total is None else int(input_total)
    if source_total < input_total or input_total < valid_input_rows:
        raise ValueError(
            "Batch denominator provenance is inconsistent: "
            f"source={source_total}, input={input_total}, valid_rows={valid_input_rows}."
        )

    row = {
        "Sample": sample_label_for_path(file_path, folder, ambiguous),
        # ``Total_Cells`` remains the historical transform-valid denominator.
        # Source/input/excluded counts are additive provenance only.
        "Source_Total_Cells": source_total,
        "Input_Total_Cells": input_total,
        "Total_Cells": valid_input_rows,
        "Transform_Excluded_Cells": input_total - valid_input_rows,
        "FCS_Compensation_Metadata": "; ".join(
            str(key) for key in compensation_metadata_keys),
        "Compensation_State": "VERIFY" if compensation_metadata_keys else "",
        "Relative_Path": relative_path_for_output(file_path, folder),
        "Source_File": file_path,
    }

    expected_gate_total = None
    for gate, output_label in zip(gates, gate_output_labels(gates)):
        regions = regions_for_gate(gate, xa, ya)
        gate_total = region_universe_total(regions, valid_input_rows)
        if expected_gate_total is None:
            expected_gate_total = gate_total
            row["Total_Cells"] = gate_total
            row["Transform_Excluded_Cells"] = input_total - gate_total
        elif gate_total != expected_gate_total:
            raise ValueError(
                "Applied gates do not share the same valid event universe "
                f"({expected_gate_total} vs {gate_total}); refusing to mix "
                "incompatible denominators in one batch row."
            )
        add_gate_region_counts(row, output_label, regions, gate_total)

    return row
