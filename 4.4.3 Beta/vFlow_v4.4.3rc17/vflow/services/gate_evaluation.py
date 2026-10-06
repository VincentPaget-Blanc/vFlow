"""Tk-free cached gate evaluation extracted from :class:`FlowApp`.

This service is a structural refactor of the frozen v4.1.11 ``_gate_mask_for``
algorithm.  It deliberately preserves gate-context binding, ndarray coercion,
cache-key structure, finite/displayable-event restriction, and cache eviction
semantics.  Gate geometry itself remains implemented by ``compute_gate_regions``.
"""

from __future__ import annotations

import numpy as np

from vflow.config.constants import _GMC_MAX
from vflow.core.cache_keys import gate_signature
from vflow.core.gate_masks import compute_gate_regions


def evaluate_gate_regions(
    gate: dict,
    xa,
    ya,
    *,
    analysis_state,
    analysis_cache,
    cache_path: str | None = None,
    max_cache_entries: int = _GMC_MAX,
):
    """Return ``(regions, colors)`` using the frozen v4.1.11 gate rules.

    ``analysis_state`` and ``analysis_cache`` are duck-typed intentionally so
    this module remains independent of Tk and avoids introducing a new runtime
    ownership requirement of the packaged compatibility layer.
    """
    if not gate or not gate.get("applied"):
        return {}, []
    if not analysis_state.gate_context_matches(gate):
        return {}, []

    # Preserve the legacy hot-path optimization: already-float64 ndarrays are
    # passed through without an unnecessary np.asarray dtype check/allocation.
    if not isinstance(xa, np.ndarray) or xa.dtype != np.float64:
        xa = np.asarray(xa, float)
    if not isinstance(ya, np.ndarray) or ya.dtype != np.float64:
        ya = np.asarray(ya, float)
    if xa.ndim != 1 or ya.ndim != 1 or len(xa) != len(ya):
        raise ValueError("Gate X/Y arrays must be one-dimensional and equal length.")

    cache_key = None
    if cache_path is not None:
        cache_key = (
            analysis_state.data_generation,
            cache_path,
            analysis_state.x_channel,
            analysis_state.y_channel,
            analysis_state.x_scale,
            analysis_state.y_scale,
            analysis_state.cofactor,
            gate["id"],
            gate_signature(gate),
            tuple(sorted((getattr(analysis_state, "x_transform_params", {}) or {}).items())),
            tuple(sorted((getattr(analysis_state, "y_transform_params", {}) or {}).items())),
        )
        cached = analysis_cache.get_gate_mask(
            cache_key, expected_length=len(xa))
        if cached is not None:
            return cached

    regions, colors = compute_gate_regions(
        gate,
        xa,
        ya,
        x_scale=analysis_state.x_scale,
        y_scale=analysis_state.y_scale,
        cofactor=analysis_state.cofactor,
        x_transform_params=getattr(analysis_state, "x_transform_params", None),
        y_transform_params=getattr(analysis_state, "y_transform_params", None),
        x_channel=analysis_state.x_channel or "X",
        y_channel=analysis_state.y_channel or "Y",
    )
    if not regions:
        return {}, colors

    # ``compute_gate_regions`` already applies the shared finite/displayable
    # event universe to every returned region.  Re-transforming the complete
    # event arrays here duplicated the most expensive scale operation on every
    # cold gate evaluation without changing any mask.
    result = (regions, colors)

    if cache_key is not None:
        analysis_cache.put_gate_mask(
            cache_key, result, max_entries=max_cache_entries)

    return result
