"""Deterministic planning helpers for main-window file loading.

These helpers intentionally do not perform file IO, Tk mutation, dialogs, dataset
commits, cache invalidation, or generation changes.  They only reproduce the
frozen v4.1.11 decisions that surround those side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Iterable, Mapping, Sequence

import pandas as pd

from vflow.core.column_normalization import column_rename_map_to_reference
from vflow.core.path_identity import file_identity_key


@dataclass(frozen=True)
class PathAdmissionPlan:
    """Decision for one requested path before any read occurs."""

    should_load: bool
    duplicate_notice: str | None = None


@dataclass(frozen=True)
class LoadedFramePlan:
    """Deterministic post-read normalization/notice plan for one DataFrame."""

    rename_map: dict
    rename_notice: str | None
    uncompensated_fcs_name: str | None
    fcs_compatibility_notice: str | None


@dataclass(frozen=True)
class LoadWarningPlan:
    """Ordered status-bar suffixes and compensation-dialog file summary."""

    suffix_parts: tuple[str, ...]
    spillover_files_summary: str | None


def plan_path_admission(
    path: str,
    loaded_paths: Iterable[str],
    excluded_paths: Iterable[str],
) -> PathAdmissionPlan:
    """Reproduce v4.1.11 exact/physical duplicate admission behavior."""
    loaded_paths = list(loaded_paths)
    excluded_paths = list(excluded_paths)

    if path in loaded_paths:
        return PathAdmissionPlan(False, None)

    incoming_identity = file_identity_key(path)
    loaded_identity = {file_identity_key(p): p for p in loaded_paths}
    excluded_identity = {file_identity_key(p): p for p in excluded_paths}

    if incoming_identity in loaded_identity:
        existing = loaded_identity[incoming_identity]
        return PathAdmissionPlan(
            False,
            f"{os.path.basename(path)} = already loaded as "
            f"{os.path.basename(existing)}",
        )
    if incoming_identity in excluded_identity:
        existing = excluded_identity[incoming_identity]
        return PathAdmissionPlan(
            False,
            f"{os.path.basename(path)} = same physical file as excluded "
            f"{os.path.basename(existing)}",
        )
    return PathAdmissionPlan(True, None)


def plan_loaded_frame(
    path: str,
    df: pd.DataFrame,
    reference_dfs: Sequence[pd.DataFrame],
) -> LoadedFramePlan:
    """Plan legacy FCS notices and first-loaded column-casing normalization."""
    basename = os.path.basename(path)
    attrs: Mapping = getattr(df, "attrs", {})

    uncompensated_name = (
        basename
        if bool(attrs.get(
            "fcs_compensation_metadata_present",
            attrs.get(
                "fcs_compensation_unapplied",
                attrs.get("fcs_spillover_unapplied", False),
            ),
        ))
        else None
    )
    compat_fixes = tuple(attrs.get("fcs_compatibility_fixes", ()) or ())
    compat_notice = None
    if compat_fixes:
        compat_notice = (
            f"{basename} ({len(compat_fixes)} metadata normalization"
            f"{'s' if len(compat_fixes) != 1 else ''})"
        )

    rename_map: dict = {}
    rename_notice = None
    if reference_dfs:
        rename_map = column_rename_map_to_reference(df, list(reference_dfs))
        if rename_map:
            rename_notice = (
                f"{basename}: "
                + ", ".join(f"'{k}'→'{v}'" for k, v in rename_map.items())
            )

    return LoadedFramePlan(
        rename_map=rename_map,
        rename_notice=rename_notice,
        uncompensated_fcs_name=uncompensated_name,
        fcs_compatibility_notice=compat_notice,
    )


def build_load_warning_plan(
    *,
    duplicate_file_notices: Sequence[str],
    rename_notices: Sequence[str],
    mismatch: str,
    fcs_compat_notices: Sequence[str],
    uncompensated_fcs: Sequence[str],
) -> LoadWarningPlan:
    """Build status suffixes in the exact frozen v4.1.11 order."""
    suffix_parts: list[str] = []
    if duplicate_file_notices:
        suffix_parts.append(
            "⚠ Duplicate physical file skipped: "
            + "  |  ".join(duplicate_file_notices)
        )
    if rename_notices:
        suffix_parts.append(
            "⚠ Column case corrected: " + "  |  ".join(rename_notices)
        )
    if mismatch:
        suffix_parts.append(mismatch)
    if fcs_compat_notices:
        shown_compat = ", ".join(fcs_compat_notices[:4])
        more_compat = (
            f" +{len(fcs_compat_notices)-4} more"
            if len(fcs_compat_notices) > 4
            else ""
        )
        suffix_parts.append(
            "ℹ FCS exporter compatibility metadata normalized (DATA values unchanged): "
            f"{shown_compat}{more_compat}"
        )

    spillover_files_summary = None
    if uncompensated_fcs:
        shown = ", ".join(uncompensated_fcs[:4])
        more = (
            f" +{len(uncompensated_fcs)-4} more"
            if len(uncompensated_fcs) > 4
            else ""
        )
        spillover_files_summary = f"{shown}{more}"
        suffix_parts.append(
            "⚠ FCS compensation metadata present; compensation state requires verification: "
            f"{spillover_files_summary}"
        )

    return LoadWarningPlan(tuple(suffix_parts), spillover_files_summary)
