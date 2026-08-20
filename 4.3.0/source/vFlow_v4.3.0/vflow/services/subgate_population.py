"""Tk-free sub-gate population resolution for vFlow.

The service preserves the frozen v4.1.11 double-click semantics: selected gate
first, then other applied gates; shape gates select only ``IN``; crosshair gates
select the clicked quadrant; each active file is filtered through the same
cached gate evaluator used by rendering.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vflow.config.constants import _GMC_MAX
from vflow.core.gates import clicked_subgate_region, subgate_candidate_order
from vflow.services.gate_evaluation import evaluate_gate_regions


class SubgateChannelMismatchError(ValueError):
    """Raised when an active file cannot participate in the current X/Y context."""

    def __init__(self, missing_files: list[str] | tuple[str, ...], x_channel: str, y_channel: str):
        self.missing_files = tuple(missing_files)
        self.x_channel = x_channel
        self.y_channel = y_channel
        names = ", ".join(self.missing_files[:3])
        if len(self.missing_files) > 3:
            names += f", … (+{len(self.missing_files) - 3} more)"
        super().__init__(
            f"Active file(s) missing required channel(s) {x_channel!r}/{y_channel!r}: {names}"
        )


@dataclass(frozen=True)
class SubgateSelection:
    """Resolved parent gate/region and per-file child population."""

    target_gate: dict
    region: str
    filtered_data: dict
    total_cells: int


def resolve_subgate_selection(
    *,
    gates: list[dict],
    selected_gate: dict | None,
    click_x: float,
    click_y: float,
    active_files: dict,
    analysis_state,
    analysis_cache,
    max_cache_entries: int = _GMC_MAX,
) -> SubgateSelection | None:
    """Resolve and materialize the frozen-v4.1.11 child population.

    Returns ``None`` when the click does not land in an applied compatible gate.
    A successful gate/region resolution may contain an empty ``filtered_data``
    mapping; the UI wrapper retains the legacy informational dialog for that case.
    """
    if not analysis_state.x_channel or not analysis_state.y_channel:
        return None

    px = np.array([click_x], dtype=float)
    py = np.array([click_y], dtype=float)

    target_gate = None
    clicked_region = None
    for gate in subgate_candidate_order(gates, selected_gate):
        if not gate or not gate.get("applied"):
            continue
        regions_pt, _ = evaluate_gate_regions(
            gate,
            px,
            py,
            analysis_state=analysis_state,
            analysis_cache=analysis_cache,
            max_cache_entries=max_cache_entries,
        )
        region_name = clicked_subgate_region(gate, regions_pt)
        if region_name is not None:
            target_gate = gate
            clicked_region = region_name
            break

    if target_gate is None or clicked_region is None:
        return None

    x_channel = analysis_state.x_channel
    y_channel = analysis_state.y_channel
    missing_files = [
        path for path, df in active_files.items()
        if x_channel not in df.columns or y_channel not in df.columns
    ]
    if missing_files:
        # Never materialize a biologically plausible sub-population from only
        # the subset of active files that happen to contain the current axes.
        # The channel selector normally prevents this state, but failing here
        # as well protects programmatic/legacy call paths and stale UI state.
        raise SubgateChannelMismatchError(missing_files, x_channel, y_channel)

    filtered: dict = {}
    for path, df in active_files.items():
        xa = df[x_channel].to_numpy(dtype=float, copy=False)
        ya = df[y_channel].to_numpy(dtype=float, copy=False)
        regions, _ = evaluate_gate_regions(
            target_gate,
            xa,
            ya,
            analysis_state=analysis_state,
            analysis_cache=analysis_cache,
            cache_path=path,
            max_cache_entries=max_cache_entries,
        )
        if clicked_region in regions:
            sub_df = df[regions[clicked_region]].reset_index(drop=True)
            if len(sub_df) > 0:
                filtered[path] = sub_df

    return SubgateSelection(
        target_gate=target_gate,
        region=clicked_region,
        filtered_data=filtered,
        total_cells=sum(len(df) for df in filtered.values()),
    )
