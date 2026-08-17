"""Tk-free gate-session serialization/provenance helpers."""

from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np

from vflow.app.lineage import copy_legacy_lineage
from vflow.config.constants import ALL_SCALES, LEGACY_SCALE_NAMES
from vflow.core.gate_serialization import gates_to_json_payload, sanitize_raw_gates
from vflow.core.logicle import validate_logicle_params
from vflow.services.gate_axis_swap import (
    apply_serialized_gate_axis_swap_plan,
    is_pure_axis_swap,
    plan_gate_axis_swap,
    swap_analysis_context_axes,
)
from vflow.core.transforms import (
    VALID_SCALES,
    canonical_scale_name,
    scale_uses_cofactor,
    scale_uses_logicle_params,
)

GATE_SESSION_VERSION = 3


def normalize_gate_context(context: dict) -> dict:
    """Return a copied context with historical scale aliases made explicit.

    This is a provenance-only migration. ``biexp`` and ``logicle`` are mapped
    to the mathematically identical ``legacy_biexp``/``legacy_logicle`` names;
    gate geometry and coordinates are never converted to the new Gating-ML
    transform. Partial lineage fixtures remain partial rather than gaining
    invented provenance keys.
    """
    if not isinstance(context, dict):
        return context
    out = copy.deepcopy(context)
    for axis in ("x", "y"):
        scale_key = f"{axis}_scale"
        params_key = f"{axis}_transform_params"
        if scale_key not in out:
            continue
        scale = out.get(scale_key)
        if scale in VALID_SCALES:
            out[scale_key] = canonical_scale_name(scale)
        if scale_uses_logicle_params(out.get(scale_key, "linear")):
            if out.get(params_key) is not None:
                out[params_key] = validate_logicle_params(out.get(params_key))
        else:
            out.pop(params_key, None)
    if "cofactor" in out and not (
            scale_uses_cofactor(out.get("x_scale", "linear")) or
            scale_uses_cofactor(out.get("y_scale", "linear"))):
        out["cofactor"] = None
    return out


def normalize_lineage_contexts(lineage: list | None) -> list:
    """Normalize scale identities in a copied legacy lineage for v3 provenance."""
    result = copy_legacy_lineage(lineage)
    for stage in result:
        if not isinstance(stage, dict):
            continue
        if isinstance(stage.get("context"), dict):
            stage["context"] = normalize_gate_context(stage["context"])
        gate = stage.get("gate")
        if isinstance(gate, dict) and isinstance(gate.get("_analysis_context"), dict):
            gate["_analysis_context"] = normalize_gate_context(gate["_analysis_context"])
    return result


def build_gate_session_payload(
    gates: list[dict],
    *,
    analysis_state,
    population_lineage: list,
) -> dict:
    """Build a v3 gate payload with explicit transform provenance."""
    payload = gates_to_json_payload(
        gates, analysis_state.x_channel, analysis_state.y_channel)
    payload["version"] = GATE_SESSION_VERSION
    current_context = normalize_gate_context(analysis_state.context_dict())
    payload["x_scale"] = current_context["x_scale"]
    payload["y_scale"] = current_context["y_scale"]
    payload["cofactor"] = current_context["cofactor"]
    payload["x_transform_params"] = current_context.get("x_transform_params")
    payload["y_transform_params"] = current_context.get("y_transform_params")
    payload["gate_contexts"] = {
        str(g["id"]): normalize_gate_context(
            g.get("_analysis_context") or current_context)
        for g in gates
    }
    payload["population_lineage"] = normalize_lineage_contexts(population_lineage)
    return payload


def validate_gate_context_payload(context: dict) -> tuple[bool, str]:
    """Validate serialized v2/v3 gate provenance without reinterpreting geometry."""
    if not isinstance(context, dict):
        return False, "context is not an object"
    xch = context.get("x_channel")
    ych = context.get("y_channel")
    xs = context.get("x_scale")
    ys = context.get("y_scale")
    if not isinstance(xch, str) or not xch.strip():
        return False, "missing X channel"
    if not isinstance(ych, str) or not ych.strip():
        return False, "missing Y channel"
    if xs not in VALID_SCALES:
        return False, f"unsupported X scale {xs!r}"
    if ys not in VALID_SCALES:
        return False, f"unsupported Y scale {ys!r}"
    if scale_uses_cofactor(xs) or scale_uses_cofactor(ys):
        try:
            cof = float(context.get("cofactor"))
        except (TypeError, ValueError):
            return False, "missing/non-numeric cofactor"
        if not np.isfinite(cof) or cof <= 0:
            return False, "cofactor must be finite and > 0"
    for axis, scale in (("X", xs), ("Y", ys)):
        if scale_uses_logicle_params(scale):
            key = f"{axis.lower()}_transform_params"
            if context.get(key) is None:
                return False, f"missing {axis} Logicle parameters"
            try:
                validate_logicle_params(context.get(key))
            except (TypeError, ValueError) as exc:
                return False, f"invalid {axis} Logicle parameters: {exc}"
    return True, ""


@dataclass(frozen=True)
class GateSessionLoadPreparation:
    clean_gates: list[dict]
    next_gate_id: int
    skipped_count: int
    saved_contexts: dict | None
    context_errors: tuple[str, ...]
    contexts_container_valid: bool


def prepare_gate_session_load(
    payload: dict,
    *,
    gate_file_version: int,
    current_next_id: int,
) -> GateSessionLoadPreparation:
    """Prepare sanitized gates and normalized v2/v3 provenance without UI effects."""
    raw_gates = payload.get("gates", [])
    clean_gates, next_gate_id, skipped = sanitize_raw_gates(
        raw_gates, current_next_id)

    if gate_file_version < 2:
        return GateSessionLoadPreparation(
            clean_gates=clean_gates,
            next_gate_id=next_gate_id,
            skipped_count=skipped,
            saved_contexts=None,
            context_errors=(),
            contexts_container_valid=True,
        )

    saved_contexts_raw = payload.get("gate_contexts", {})
    if not isinstance(saved_contexts_raw, dict):
        return GateSessionLoadPreparation(
            clean_gates=clean_gates,
            next_gate_id=next_gate_id,
            skipped_count=skipped,
            saved_contexts=None,
            context_errors=(),
            contexts_container_valid=False,
        )

    saved_contexts = {
        str(key): normalize_gate_context(ctx)
        for key, ctx in saved_contexts_raw.items()
    }
    context_errors: list[str] = []
    for gate in clean_gates:
        ctx = saved_contexts.get(str(gate["id"]))
        ok, why = validate_gate_context_payload(ctx)
        if not ok:
            context_errors.append(
                f"Gate {gate.get('name', gate.get('id'))}: {why}")

    return GateSessionLoadPreparation(
        clean_gates=clean_gates,
        next_gate_id=next_gate_id,
        skipped_count=skipped,
        saved_contexts=saved_contexts,
        context_errors=tuple(context_errors),
        contexts_container_valid=True,
    )


def transpose_loaded_gate_for_current_axes(
    gate: dict,
    context: dict,
    *,
    current_x: str | None,
    current_y: str | None,
) -> tuple[dict, dict, bool]:
    """Transpose one loaded gate iff its saved channels are the current X/Y pair reversed.

    This is the persistence counterpart of A3 interactive axis preservation.
    Genuinely different channel pairs are left untouched/inactive; only a pure
    X<->Y swap moves geometry and axis-affine provenance.
    """
    if not is_pure_axis_swap(
        current_x, current_y, context.get("x_channel"), context.get("y_channel")
    ):
        return copy.deepcopy(gate), copy.deepcopy(context), False

    swapped_gate = copy.deepcopy(gate)
    plan = plan_gate_axis_swap(swapped_gate)
    apply_serialized_gate_axis_swap_plan(swapped_gate, plan)
    swapped_context = normalize_gate_context(swap_analysis_context_axes(context))
    return swapped_gate, swapped_context, True
