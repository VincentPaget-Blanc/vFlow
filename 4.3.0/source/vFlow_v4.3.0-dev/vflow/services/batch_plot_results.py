"""Tk-free Batch Plot per-sample result computation for vFlow.

This module preserves the frozen v4.1.11 Batch Plot denominator and counting-SE
semantics.  It does not render, mutate Tk state, choose gates, or decide user-facing
status text.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np

from vflow.core.gate_masks import selected_region_mask
from vflow.core.gate_stats import binomial_percentage_sem, region_percentages


BatchSample = tuple[str, object, str]


@dataclass(frozen=True)
class BatchPlotResults:
    """Computed caches and fail-closed outcome for one Batch Plot refresh."""

    dist_cache: dict[str, tuple[np.ndarray, str]]
    pop_cache: dict[str, dict[str, float]]
    pop_sem_cache: dict[tuple[str, str], float]
    sample_labels: tuple[str, ...]
    failed_samples: tuple[str, ...]

    @property
    def failed(self) -> bool:
        return bool(self.failed_samples)


def compute_batch_plot_results(
    samples: Sequence[BatchSample],
    *,
    dist_col: str,
    gate: dict | None,
    region_name: str,
    x_channel: str | None,
    y_channel: str | None,
    use_gate: bool,
    transform_xy: Callable[[np.ndarray, np.ndarray], tuple],
    gate_mask_for: Callable[[dict, np.ndarray, np.ndarray], tuple[dict, object]],
    dist_cache: dict[str, tuple[np.ndarray, str]] | None = None,
    pop_cache: dict[str, dict[str, float]] | None = None,
    pop_sem_cache: dict[tuple[str, str], float] | None = None,
) -> BatchPlotResults:
    """Compute frozen v4.1.11 Batch Plot caches without Tk/UI work.

    Scientific invariants intentionally preserved:
    - gated percentages use only finite/displayable X/Y events as denominator;
    - distribution filtering uses the selected gate region over original rows;
    - binomial percentage SEM uses the same finite gate denominator;
    - gate transform/mask failures mark that sample failed;
    - all requested samples are still evaluated so the complete failure list is
      retained, but any failure causes the returned caches to be empty rather
      than yielding a plausible-looking subset.

    Exception boundaries also mirror the legacy method: only transform/gate-mask
    evaluation is swallowed into a failed sample.  Data conversion, selected-region
    resolution, distribution conversion, and statistics errors still propagate.
    """
    if dist_cache is None:
        dist_cache = {}
    if pop_cache is None:
        pop_cache = {}
    if pop_sem_cache is None:
        pop_sem_cache = {}
    failed_samples: list[str] = []

    for lbl, df, color in samples:
        n_rows = len(df)
        gate_total = n_rows

        regions: dict = {}
        if use_gate:
            if (not x_channel or not y_channel
                    or x_channel not in df.columns or y_channel not in df.columns):
                failed_samples.append(lbl)
                continue

            xa = df[x_channel].to_numpy(dtype=float, copy=False)
            ya = df[y_channel].to_numpy(dtype=float, copy=False)
            try:
                _, _, valid_xy = transform_xy(xa, ya)
                gate_total = int(valid_xy.sum())
                regions, _ = gate_mask_for(gate, xa, ya)
            except Exception:
                regions = {}
            if not regions:
                failed_samples.append(lbl)
                continue

        if not regions:
            pop_mask = np.ones(n_rows, bool)
        else:
            pop_mask = selected_region_mask(
                regions,
                total=n_rows,
                gate_type=gate.get('type', 'crosshair'),
                region_name=region_name,
            )

        if dist_col and dist_col in df.columns:
            vals = df[dist_col].to_numpy(dtype=float, copy=False)[pop_mask]
            vals = vals[np.isfinite(vals)]
        else:
            vals = np.array([])
        dist_cache[lbl] = (vals, color)

        if regions and gate_total > 0:
            pct_map = region_percentages(regions, gate_total)
            pop_cache[lbl] = pct_map
            for rname, pct in pct_map.items():
                pop_sem_cache[(lbl, rname)] = float(
                    binomial_percentage_sem(pct, gate_total))
        else:
            pop_cache[lbl] = {}

    labels = tuple(lbl for lbl, _, _ in samples)
    if failed_samples:
        dist_cache.clear()
        pop_cache.clear()
        pop_sem_cache.clear()
        return BatchPlotResults(
            dist_cache=dist_cache, pop_cache=pop_cache, pop_sem_cache=pop_sem_cache,
            sample_labels=(), failed_samples=tuple(failed_samples),
        )

    return BatchPlotResults(
        dist_cache=dist_cache,
        pop_cache=pop_cache,
        pop_sem_cache=pop_sem_cache,
        sample_labels=labels,
        failed_samples=(),
    )
