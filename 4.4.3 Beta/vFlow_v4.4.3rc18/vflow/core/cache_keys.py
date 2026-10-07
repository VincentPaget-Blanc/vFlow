"""Cache key helpers for gate-dependent computations."""

from __future__ import annotations


from .threshold_state import (
    multi_y_threshold_flags,
    single_y_threshold_flag,
    x_threshold_flags,
)


def gate_signature(gate: dict) -> int:
    """Return a stable integer hash of a gate's geometry and active flags."""
    vertex_prec = 8

    gt = gate.get("type", "crosshair")
    if gt == "crosshair":
        y_boundaries = gate.get("y_boundaries") or []
        key = (
            gt,
            tuple(gate.get("x_boundaries") or []),
            gate.get("y_boundary"),
            x_threshold_flags(gate),
            single_y_threshold_flag(gate),
            tuple(y_boundaries),
            multi_y_threshold_flags(gate),
        )
    elif gt in ("rectangle", "ellipse"):
        key = (
            gt,
            gate.get("x0"),
            gate.get("y0"),
            gate.get("x1"),
            gate.get("y1"),
        )
    elif gt == "polygon":
        raw_verts = gate.get("vertices") or []
        rounded = tuple(
            (round(float(x), vertex_prec), round(float(y), vertex_prec))
            for x, y in raw_verts
        )
        key = (gt, rounded)
    else:
        key = (gt,)
    return hash(key)


def gate_mask_cache_keys_for_gate_ids(cache, gate_ids) -> list:
    """Return gate-mask cache keys whose gate-id slot matches one of gate_ids.

    Gate-mask keys contain the data-generation/context prefix and store the
    gate ID at slot 7. A2 appends two transform-parameter tuples after the
    historical gate-id/signature slots so eviction semantics stay stable.  The shorter five-item shape is retained
    for compatibility with historical cache fixtures/diagnostics.
    """
    ids = set(gate_ids)
    matches = []
    for key in cache:
        if len(key) in (9, 11):
            gate_id = key[7]
        elif len(key) == 5:
            gate_id = key[3]
        else:
            continue
        if gate_id in ids:
            matches.append(key)
    return matches


def scatter_cache_keys_for_gate_signature(cache, gate_sig: int) -> list:
    """Return scatter-cache keys whose gate-signature tuple contains gate_sig.

    Current scatter keys store the gate-signature tuple at slot 7 after the
    data-generation/context prefix. A2 appends two transform-parameter tuples
    after the historical visual fields so the gate-signature slot stays stable.  The historical eight-item key shape keeps
    that tuple at slot 3 and remains accepted for compatibility fixtures.
    """
    matches = []
    for key in cache:
        if len(key) in (12, 14):
            gate_sigs = key[7]
        elif len(key) == 8:
            gate_sigs = key[3]
        else:
            continue
        if gate_sig in gate_sigs:
            matches.append(key)
    return matches


def evict_cache_keys(cache, keys) -> int:
    """Remove keys from a cache dict and return the number removed."""
    removed = 0
    for key in keys:
        if key in cache:
            cache.pop(key, None)
            removed += 1
    return removed
