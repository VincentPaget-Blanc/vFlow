"""Tk-free application/scientific state for vFlow.

This module is intentionally small for the first v4.2 refactor slice.  It owns
only values that already existed as plain-Python attributes on ``FlowApp`` in
the frozen v4.1.11 baseline.  It does not change gate mathematics, caching,
serialization, dataset contents, or UI behavior.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from vflow.core.logicle import LogicleParameters
from vflow.core.transforms import (
    canonical_scale_name, scale_uses_cofactor, scale_uses_logicle_params,
)


@dataclass
class AnalysisState:
    """Mutable Tk-free state describing the active analysis population/context.

    The defaults exactly mirror ``FlowApp.__init__`` in v4.1.11.  The legacy
    ``FlowApp`` surface exposes compatibility properties that delegate to this
    object, allowing the rest of the monolith to remain unchanged while state
    ownership begins moving out of Tk/UI code.
    """

    x_channel: str | None = None
    y_channel: str | None = None
    x_scale: str = "asinh"
    y_scale: str = "asinh"
    cofactor: float = 150.0
    x_transform_params: dict[str, float] = field(
        default_factory=lambda: LogicleParameters().as_dict())
    y_transform_params: dict[str, float] = field(
        default_factory=lambda: LogicleParameters().as_dict())

    # Monotonic identity for the currently loaded in-memory dataset generation.
    data_generation: int = 0

    # Population ancestry/provenance for sub-gated tabs.  These remain plain
    # Python snapshots; no Tk Variable is introduced here.
    parent_gate: dict[str, Any] | None = None
    parent_region: str | None = None
    population_lineage: list = field(default_factory=list)

    def context_dict(self) -> dict:
        """Return the complete gate-coordinate context mapping."""
        needs_cofactor = scale_uses_cofactor(self.x_scale) or scale_uses_cofactor(self.y_scale)
        context = {
            "x_channel": self.x_channel or "",
            "y_channel": self.y_channel or "",
            "x_scale": self.x_scale or "linear",
            "y_scale": self.y_scale or "linear",
            "cofactor": float(self.cofactor) if needs_cofactor else None,
        }
        if scale_uses_logicle_params(self.x_scale):
            context["x_transform_params"] = (
                LogicleParameters.from_mapping(self.x_transform_params).as_dict())
        if scale_uses_logicle_params(self.y_scale):
            context["y_transform_params"] = (
                LogicleParameters.from_mapping(self.y_transform_params).as_dict())
        return context

    @staticmethod
    def contexts_equal(a: dict, b: dict) -> bool:
        """Return scientific coordinate-context equivalence."""
        if not isinstance(a, dict) or not isinstance(b, dict):
            return False
        for key in ("x_channel", "y_channel"):
            if (a.get(key) or "") != (b.get(key) or ""):
                return False
        try:
            if canonical_scale_name(a.get("x_scale") or "linear") != \
                    canonical_scale_name(b.get("x_scale") or "linear"):
                return False
            if canonical_scale_name(a.get("y_scale") or "linear") != \
                    canonical_scale_name(b.get("y_scale") or "linear"):
                return False
        except ValueError:
            return False
        ac, bc = a.get("cofactor"), b.get("cofactor")
        if ac is None and bc is None:
            pass
        else:
            try:
                if not np.isclose(float(ac), float(bc), rtol=0.0, atol=1e-12):
                    return False
            except (TypeError, ValueError):
                return False
        for axis in ("x", "y"):
            key = f"{axis}_transform_params"
            av, bv = a.get(key), b.get(key)
            if av is None and bv is None:
                continue
            try:
                ap = LogicleParameters.from_mapping(av)
                bp = LogicleParameters.from_mapping(bv)
            except (TypeError, ValueError):
                return False
            if any(
                not np.isclose(x, y, rtol=0.0, atol=1e-12)
                for x, y in zip(ap.cache_key(), bp.cache_key())
            ):
                return False
        return True

    def bind_gate_context(self, gate: dict, context: dict | None = None) -> None:
        """Bind a gate once to a plain immutable coordinate-context snapshot."""
        if gate is None:
            return
        ctx = dict(context or self.context_dict())
        bound = {
            "x_channel": ctx.get("x_channel", "") or "",
            "y_channel": ctx.get("y_channel", "") or "",
            "x_scale": ctx.get("x_scale", "linear") or "linear",
            "y_scale": ctx.get("y_scale", "linear") or "linear",
            "cofactor": ctx.get("cofactor"),
        }
        if "x_transform_params" in ctx:
            bound["x_transform_params"] = copy.deepcopy(ctx.get("x_transform_params"))
        if "y_transform_params" in ctx:
            bound["y_transform_params"] = copy.deepcopy(ctx.get("y_transform_params"))
        gate["_analysis_context"] = bound

    @staticmethod
    def context_channels_equal(a: dict, b: dict) -> bool:
        """Return whether two contexts refer to the same ordered X/Y channels."""
        if not isinstance(a, dict) or not isinstance(b, dict):
            return False
        return (
            (a.get("x_channel") or "") == (b.get("x_channel") or "")
            and (a.get("y_channel") or "") == (b.get("y_channel") or "")
        )

    def gate_context_matches(self, gate: dict, context: dict | None = None) -> bool:
        """Return whether *gate* applies to the requested X/Y measurements.

        Gate applicability is channel-affine, not display-transform-affine.
        A scale/cofactor/Logicle change keeps the same measurements, so the
        gate is rebound to that transform and its membership is recomputed.
        Selecting a different X or Y measurement remains incompatible.
        """
        if not gate:
            return False
        requested = context or self.context_dict()
        if not gate.get("_analysis_context"):
            self.bind_gate_context(gate, requested)
        saved = gate.get("_analysis_context", {})
        if not self.context_channels_equal(saved, requested):
            return False
        if not self.contexts_equal(saved, requested):
            self.bind_gate_context(gate, requested)
        return True

    def rebind_gates_matching_context(
        self, gates, previous_context: dict, new_context: dict | None = None
    ) -> int:
        """Move only gates valid in *previous_context* into a new transform context.

        Interactive scale/cofactor/Logicle-parameter changes are a change of
        display coordinates, not a request to discard gates.  The gate geometry
        is stored in raw channel coordinates and the evaluator already
        recomputes membership using the active transform, so gates that were
        valid immediately before a transform change must follow that change.

        Gates belonging to a different X/Y channel pair (or otherwise already
        incompatible) are deliberately left untouched.  This distinction is
        important: changing a measurement channel still makes those gates
        inactive, while changing only its display transform preserves them.
        """
        target = dict(new_context or self.context_dict())
        count = 0
        for gate in gates or ():
            if not gate:
                continue
            if not gate.get("_analysis_context"):
                # Legacy/in-memory gates have the same bind-on-first-use
                # semantics as gate_context_matches().  Bind to the context
                # that was active before the transform mutation.
                self.bind_gate_context(gate, previous_context)
            if self.contexts_equal(
                gate.get("_analysis_context", {}), previous_context
            ):
                self.bind_gate_context(gate, target)
                count += 1
        return count

    def advance_data_generation(self) -> int:
        """Advance and return the monotonic in-memory dataset generation token."""
        self.data_generation += 1
        return self.data_generation

    def set_population_context(
        self,
        *,
        parent_gate: dict[str, Any] | None,
        parent_region: str | None,
        population_lineage: list | None,
    ) -> None:
        """Install a child-tab population snapshot with legacy copy semantics."""
        from .lineage import copy_legacy_lineage

        self.parent_gate = (
            copy.deepcopy(parent_gate) if parent_gate is not None else None
        )
        self.parent_region = parent_region
        self.population_lineage = copy_legacy_lineage(population_lineage)
