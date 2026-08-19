"""Tk-free population evaluation primitives extracted from FlowApp.

These functions preserve the frozen v4.1.11 event-universe rules.  They do not
introduce new transform mathematics, compensation, denominator semantics, or
region interpretation; they only move existing pure calculations out of Tk/UI
ownership so interactive and secondary analyses can converge on one service.
"""

from __future__ import annotations

import numpy as np

from vflow.core.gate_masks import compute_gate_regions
from vflow.core.transforms import transform_xy


def restrict_regions_to_valid(regions: dict, valid) -> dict:
    """Intersect every gate region with one finite/displayable event universe.

    This is the exact v4.1.11 invariant formerly implemented by
    ``FlowApp._restrict_regions_to_valid``.
    """
    if not isinstance(regions, dict):
        raise TypeError("Gate regions must be returned as a dict.")
    valid = np.asarray(valid, dtype=bool)
    if valid.ndim != 1:
        raise ValueError("Gate validity mask must be one-dimensional.")
    out = {}
    for name, mask in regions.items():
        m = np.asarray(mask, dtype=bool)
        if m.ndim != 1 or len(m) != len(valid):
            raise ValueError(
                f"Gate region {name!r} returned {m.size} events; "
                f"expected {len(valid)}."
            )
        out[name] = m & valid
    return out


def regions_in_explicit_context(
    gate: dict,
    xa,
    ya,
    context: dict,
    *,
    fallback_cofactor: float,
):
    """Evaluate an ancestor gate in its immutable original coordinate context.

    ``fallback_cofactor`` intentionally preserves the v4.1.11 behavior where a
    false-y/missing serialized cofactor falls back to the current app cofactor.
    No validation or reinterpretation is added in this structural extraction.
    """
    xa = np.asarray(xa, dtype=float)
    ya = np.asarray(ya, dtype=float)
    if xa.ndim != 1 or ya.ndim != 1 or len(xa) != len(ya):
        raise ValueError("Gate X/Y arrays must be one-dimensional and equal length.")

    x_scale = context.get("x_scale", "linear")
    y_scale = context.get("y_scale", "linear")
    cofactor = float(context.get("cofactor") or fallback_cofactor)
    x_transform_params = context.get("x_transform_params")
    y_transform_params = context.get("y_transform_params")
    regions, colors = compute_gate_regions(
        gate,
        xa,
        ya,
        x_scale=x_scale,
        y_scale=y_scale,
        cofactor=cofactor,
        x_transform_params=x_transform_params,
        y_transform_params=y_transform_params,
        x_channel=context.get("x_channel") or "X",
        y_channel=context.get("y_channel") or "Y",
    )
    if not regions:
        return {}, colors
    _, _, valid = transform_xy(
        xa, ya, x_scale, y_scale, cofactor,
        x_transform_params=x_transform_params,
        y_transform_params=y_transform_params)
    return restrict_regions_to_valid(regions, valid), colors


def selected_population_mask_for_dataframe(
    df,
    gate: dict | None,
    *,
    region_name: str,
    analysis_state,
):
    """Resolve one secondary-analysis population using frozen v4.1.11 rules.

    Returns ``None`` for missing/incompatible gates, channels, or gate
    computation failures.  Region-name errors intentionally remain raised by
    ``selected_region_mask`` just as they did in the legacy Polar/Batch helper
    after a successful gate computation.
    """
    from vflow.core.gate_masks import selected_region_mask

    if gate is None or not analysis_state.gate_context_matches(gate):
        return None
    xch = analysis_state.x_channel
    ych = analysis_state.y_channel
    if not xch or not ych or xch not in df.columns or ych not in df.columns:
        return None
    xa = df[xch].to_numpy(dtype=float, copy=False)
    ya = df[ych].to_numpy(dtype=float, copy=False)
    try:
        regions, _ = compute_gate_regions(
            gate,
            xa,
            ya,
            x_scale=analysis_state.x_scale,
            y_scale=analysis_state.y_scale,
            cofactor=analysis_state.cofactor,
            x_transform_params=analysis_state.x_transform_params,
            y_transform_params=analysis_state.y_transform_params,
            x_channel=xch or "X",
            y_channel=ych or "Y",
        )
    except Exception:
        return None
    if not regions:
        return None
    return selected_region_mask(
        regions,
        total=len(df),
        gate_type=gate.get("type", "crosshair"),
        region_name=region_name,
    )
