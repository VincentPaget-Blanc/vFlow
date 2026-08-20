"""Tk-free planning for active-file population changes.

The frozen v4.1.11 callback first lets the channel-menu update mutate the active
analysis context, then chooses exactly one of two orchestration paths:

* changed coordinate context -> run the full analysis-context invalidation path;
* unchanged context -> recompute gate stats only when at least one gate is
  applied, then refresh the plot.

This module owns only that deterministic decision.  It performs no Tk mutation,
cache invalidation, gate evaluation, statistics computation, or plotting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Any

from vflow.app.state import AnalysisState


@dataclass(frozen=True)
class ActiveFileChangePlan:
    """Frozen-v4.1.11 orchestration decision after channel-menu refresh."""

    context_changed: bool
    recompute_gate_stats: bool


def plan_active_file_change(
    old_context: Mapping[str, Any],
    new_context: Mapping[str, Any],
    gates: Iterable[Mapping[str, Any]],
) -> ActiveFileChangePlan:
    """Return the exact active-file-change decision from frozen v4.1.11.

    ``recompute_gate_stats`` is intentionally false when the coordinate context
    changed because the legacy callback immediately delegates to
    ``_analysis_context_changed()`` and returns; that routine performs its own
    invalidation/recompute/refresh sequence.
    """
    context_changed = not AnalysisState.contexts_equal(
        dict(old_context) if isinstance(old_context, Mapping) else old_context,
        dict(new_context) if isinstance(new_context, Mapping) else new_context,
    )
    if context_changed:
        return ActiveFileChangePlan(True, False)

    return ActiveFileChangePlan(
        False,
        any(g.get("applied") for g in gates),
    )


def build_incompatible_gate_status(
    incompatible_gates: Iterable[Mapping[str, Any]],
) -> str | None:
    """Format the frozen status-bar notice for incompatible applied gates."""
    incompatible = list(incompatible_gates)
    if not incompatible:
        return None
    names = ", ".join(
        g.get("name", str(g.get("id"))) for g in incompatible[:4]
    )
    more = f" +{len(incompatible)-4} more" if len(incompatible) > 4 else ""
    return (
        f"Analysis context changed. {len(incompatible)} gate(s) are inactive "
        f"in this coordinate system: {names}{more}. Switch back to reuse them."
    )
