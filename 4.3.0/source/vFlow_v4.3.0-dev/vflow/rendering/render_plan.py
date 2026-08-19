"""Immutable render-input snapshot for one FlowApp refresh pass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class RenderPlan:
    """Stable inputs materialized before renderer-side drawing begins.

    Tk variables whose repeated reads are historically observable (for example
    legend/grid/fit/lock/label toggles) intentionally remain renderer-side and
    are *not* snapshotted here.  This preserves v4.2 interaction/failure order
    while giving the heavy render pass a narrow, explicit structural snapshot.
    """

    theme: Mapping[str, Any]
    active: Mapping[str, Any]
    display: Mapping[str, Any]
    applied_gates: Sequence[dict]
    effective_gate: bool
    need_marginals: bool
    plot_type: str
    dot_size: Any
    alpha: Any
    probability: float
    x_channel: str
    y_channel: str
    x_scale: str
    y_scale: str
