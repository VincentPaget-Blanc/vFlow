"""Tk-free Polar dataset collection for vFlow.

This module does not compute circular statistics and does not render.  It owns only
frozen v4.1.11 per-file collection order and fail-closed handling for population
or vector-resolution failures.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Callable, Mapping, Sequence

import numpy as np

from vflow.config.constants import FILE_COLORS, _N_FILE_COLORS


PolarDataset = tuple[np.ndarray, np.ndarray, str, str, str]


@dataclass(frozen=True)
class PolarDatasetCollection:
    datasets: tuple[PolarDataset, ...]
    failure_kind: str | None = None
    failure_path: str | None = None

    @property
    def failed(self) -> bool:
        return self.failure_kind is not None


def collect_polar_datasets(
    active: Mapping[str, object],
    visible_paths: Sequence[str] | set[str],
    *,
    population_mask_for: Callable[[object, str], np.ndarray | None],
    vectors_for: Callable[[object, np.ndarray], tuple[np.ndarray | None, np.ndarray | None]],
) -> PolarDatasetCollection:
    """Collect visible Polar datasets with frozen fail-closed semantics.

    Ordering, color assignment, and failure behavior intentionally mirror the
    v4.1.11 ``PolarAnalysisWindow._compute_and_plot`` loop.  A failure for any
    requested sample discards the partial collection rather than returning a
    plausible-looking subset.
    """
    visible = set(visible_paths)
    datasets: list[PolarDataset] = []

    for fi, path in enumerate(sorted(active.keys())):
        if path not in visible:
            continue
        df = active[path]
        mask = population_mask_for(df, path)
        if mask is None:
            return PolarDatasetCollection(
                datasets=(), failure_kind='population', failure_path=path)

        angles, mags = vectors_for(df, mask)
        if angles is None:
            return PolarDatasetCollection(
                datasets=(), failure_kind='vectors', failure_path=path)

        color = FILE_COLORS[fi % _N_FILE_COLORS]
        label = os.path.basename(path)
        datasets.append((angles, mags, label, color, path))

    return PolarDatasetCollection(datasets=tuple(datasets))
