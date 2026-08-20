"""Tk-free orchestration for the legacy Batch Stats workflow.

The runner deliberately preserves the v4.2.0 workflow order.  UI validation,
the options dialog, and completion dialogs remain owned by ``FlowApp``; file
discovery, per-file processing, lineage replay, statistics assembly, and output
writing live here behind narrow callbacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Callable, Literal

import numpy as np
import pandas as pd

from vflow.core.gate_masks import selected_region_mask
from vflow.services.batch_stats_export import (
    ambiguous_stems,
    batch_exclusion_sets,
    build_batch_stats_row,
    concat_skip_reason,
    discover_batch_target_files,
    excluded_log_rows,
    ordered_batch_columns,
    previous_batch_output_skip_reason,
)


BatchOutcome = Literal[
    "success",
    "no_targets",
    "all_targets_excluded",
    "no_files_processed",
]


@dataclass(frozen=True)
class BatchStatsRequest:
    folder: str
    suffix: str
    file_types: str
    save_path: str
    x_channel: str
    y_channel: str
    applied_gates: list[dict]
    excluded_files: set[str]


@dataclass
class BatchStatsRunResult:
    outcome: BatchOutcome
    save_path: str
    target_files: list[str] = field(default_factory=list)
    skipped_exclusions: list[tuple[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rows_count: int = 0
    log_path: str | None = None


@dataclass(frozen=True)
class BatchStatsAdapters:
    """Narrow host callbacks needed by the non-Tk batch workflow."""

    load_frame: Callable[[str], tuple[object, list[str]]]
    current_valid_mask: Callable[[np.ndarray, np.ndarray], np.ndarray]
    regions_for_gate: Callable[[dict, np.ndarray, np.ndarray], dict]
    regions_in_context: Callable[[dict, np.ndarray, np.ndarray, dict], tuple[dict, object]]
    lineage_provider: Callable[[], list[dict]]
    progress: Callable[[str], None] | None = None


class BatchStatsRunner:
    """Run the behavior-frozen v4.2.0 batch-statistics pipeline without Tk."""

    def __init__(self, adapters: BatchStatsAdapters):
        self._adapters = adapters

    def run(self, request: BatchStatsRequest) -> BatchStatsRunResult:
        excluded_paths, excluded_stems = batch_exclusion_sets(request.excluded_files)
        target_files, skipped_excl = discover_batch_target_files(
            request.folder,
            request.suffix,
            request.file_types,
            excluded_paths,
            excluded_stems,
        )

        result = BatchStatsRunResult(
            outcome="success",
            save_path=request.save_path,
            target_files=list(target_files),
            skipped_exclusions=skipped_excl,
        )

        if not target_files and not skipped_excl:
            result.outcome = "no_targets"
            return result
        if not target_files:
            result.outcome = "all_targets_excluded"
            return result

        self._progress(f"Batch stats: processing 0 / {len(target_files)} files…")

        # Historical v4.2.0 compatibility quirk: this dummy evaluation builds a
        # region-column list that is never consumed later.  Keep the calls and
        # their order because gate evaluation/cache failures can be observable.
        region_cols = []
        for gate in request.applied_gates:
            dummy_xa = np.array([0.0])
            dummy_ya = np.array([0.0])
            regions = self._adapters.regions_for_gate(gate, dummy_xa, dummy_ya)
            for region_name in regions:
                region_cols.append((gate["name"], region_name))
        _ = region_cols

        # v4.2.0 constructs/copies lineage only after the dummy gate pass.
        lineage = self._adapters.lineage_provider()
        is_subgate = bool(lineage)
        ambiguous = ambiguous_stems(target_files)

        all_rows: list[dict] = []
        errors = result.errors
        warnings = result.warnings

        for index, file_path in enumerate(target_files):
            self._progress(
                f"Batch stats: {index + 1} / {len(target_files)} — "
                f"{os.path.basename(file_path)}"
            )
            try:
                df, ambiguous_aliases = self._adapters.load_frame(file_path)
                source_total = int(len(df))
                attrs = getattr(df, "attrs", {}) or {}
                compensation_metadata_keys = tuple(
                    attrs.get("fcs_compensation_metadata_keys", ()) or ())
                if bool(attrs.get(
                    "fcs_compensation_metadata_present",
                    attrs.get(
                        "fcs_compensation_unapplied",
                        attrs.get("fcs_spillover_unapplied", False),
                    ),
                )):
                    keys = compensation_metadata_keys
                    key_text = ", ".join(str(k) for k in keys) if keys else "keyword(s)"
                    warnings.append(
                        f"{os.path.basename(file_path)}: FCS compensation metadata "
                        f"present ({key_text}); compensation state requires verification"
                    )
                if ambiguous_aliases:
                    errors.append(
                        f"{os.path.basename(file_path)}: ambiguous axis alias — "
                        + "; ".join(ambiguous_aliases)
                    )
                    continue
            except Exception as exc:
                errors.append(f"{os.path.basename(file_path)}: load error — {exc}")
                continue

            skip_reason = concat_skip_reason(df)
            if skip_reason:
                skipped_excl.append((os.path.basename(file_path), skip_reason))
                continue

            skip_reason = previous_batch_output_skip_reason(df, request.x_channel)
            if skip_reason:
                skipped_excl.append((os.path.basename(file_path), skip_reason))
                continue

            if request.x_channel not in df.columns or request.y_channel not in df.columns:
                errors.append(
                    f"{os.path.basename(file_path)}: missing channel "
                    f"'{request.x_channel}' or '{request.y_channel}'"
                )
                continue

            if is_subgate:
                lineage_failed = False
                for depth, stage in enumerate(lineage, start=1):
                    context = stage.get("context") or {}
                    gx = context.get("x_channel")
                    gy = context.get("y_channel")
                    if not gx or not gy or gx not in df.columns or gy not in df.columns:
                        errors.append(
                            f"{os.path.basename(file_path)}: ancestor {depth} missing "
                            f"channel '{gx}' or '{gy}'"
                        )
                        lineage_failed = True
                        break
                    xa_ancestor = df[gx].to_numpy(dtype=float, copy=False)
                    ya_ancestor = df[gy].to_numpy(dtype=float, copy=False)
                    try:
                        regions_ancestor, _ = self._adapters.regions_in_context(
                            stage["gate"], xa_ancestor, ya_ancestor, context
                        )
                        mask_ancestor = selected_region_mask(
                            regions_ancestor,
                            total=len(df),
                            gate_type=stage["gate"].get("type", "crosshair"),
                            region_name=stage.get("region", "All regions"),
                        )
                    except Exception as exc:
                        errors.append(
                            f"{os.path.basename(file_path)}: ancestor {depth} "
                            f"could not be reconstructed — {exc}"
                        )
                        lineage_failed = True
                        break
                    df = df.loc[mask_ancestor].reset_index(drop=True)
                    if len(df) == 0:
                        break
                if lineage_failed:
                    continue

            input_total = int(len(df))
            xa_current = df[request.x_channel].to_numpy(dtype=float, copy=False)
            ya_current = df[request.y_channel].to_numpy(dtype=float, copy=False)
            valid_current = self._adapters.current_valid_mask(xa_current, ya_current)
            df = df.loc[valid_current].reset_index(drop=True)

            row = build_batch_stats_row(
                df=df,
                file_path=file_path,
                folder=request.folder,
                ambiguous=ambiguous,
                x_channel=request.x_channel,
                y_channel=request.y_channel,
                gates=request.applied_gates,
                regions_for_gate=self._adapters.regions_for_gate,
                source_total=source_total,
                input_total=input_total,
                compensation_metadata_keys=compensation_metadata_keys,
            )
            all_rows.append(row)

        if not all_rows:
            result.outcome = "no_files_processed"
            return result

        result_df = pd.DataFrame(all_rows)
        result_df = result_df[ordered_batch_columns(result_df.columns)]
        result_df.to_csv(request.save_path, index=False)

        log_path = os.path.splitext(request.save_path)[0] + "_excluded.csv"
        log_rows = excluded_log_rows(skipped_excl, errors, warnings)
        pd.DataFrame(
            log_rows,
            columns=["Filename", "Full_Path", "Reason"],
        ).to_csv(log_path, index=False)

        result.rows_count = len(all_rows)
        result.log_path = log_path
        return result

    def _progress(self, message: str) -> None:
        callback = self._adapters.progress
        if callback is not None:
            callback(message)
