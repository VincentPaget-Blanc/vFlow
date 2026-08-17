"""Tk-free population-lineage adapters for the v4.2 structural refactor.

The frozen v4.1.11 runtime and gate-file schema use ``list[dict]`` lineage
payloads.  This module introduces typed value objects without changing that
external/in-memory compatibility surface.  Conversions intentionally use deep
copies and preserve the legacy dictionary keys/values verbatim.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class LineageStage:
    """Typed view of one ancestor population stage.

    ``gate`` must already be a Tk-free snapshot when created by runtime code.
    No gate geometry, context, region name, or serialization key is normalized
    here; this layer is ownership/plumbing only.
    """

    gate: dict[str, Any]
    region: str | None
    context: dict[str, Any]

    @classmethod
    def from_legacy_dict(cls, stage: dict[str, Any]) -> "LineageStage":
        return cls(
            gate=copy.deepcopy(stage.get("gate")),
            region=copy.deepcopy(stage.get("region")),
            context=copy.deepcopy(stage.get("context")),
        )

    @classmethod
    def from_components(
        cls, *, gate: dict[str, Any], region: str | None, context: dict[str, Any]
    ) -> "LineageStage":
        return cls(
            gate=copy.deepcopy(gate),
            region=copy.deepcopy(region),
            context=copy.deepcopy(context),
        )

    def to_legacy_dict(self) -> dict[str, Any]:
        # Preserve the exact v4.1.11 stage schema and key insertion order.
        return {
            "gate": copy.deepcopy(self.gate),
            "region": copy.deepcopy(self.region),
            "context": copy.deepcopy(self.context),
        }


@dataclass(frozen=True)
class PopulationLineage:
    """Typed lineage value with lossless adapters to the legacy list surface."""

    stages: tuple[LineageStage, ...] = ()

    @classmethod
    def from_legacy_list(cls, lineage: Iterable[dict[str, Any]] | None) -> "PopulationLineage":
        return cls(tuple(LineageStage.from_legacy_dict(stage) for stage in (lineage or [])))

    def append(self, stage: LineageStage) -> "PopulationLineage":
        return PopulationLineage(self.stages + (stage,))

    def to_legacy_list(self) -> list[dict[str, Any]]:
        return [stage.to_legacy_dict() for stage in self.stages]

    @staticmethod
    def legacy_signature(lineage: list | None) -> str:
        """Return the exact canonical signature algorithm used by v4.1.11."""
        try:
            return json.dumps(
                lineage or [],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                default=str,
            )
        except Exception:
            return repr(lineage or [])


def copy_legacy_lineage(lineage: list | None) -> list:
    """Deep-copy a legacy lineage without changing its list/dict representation."""
    return copy.deepcopy(lineage or [])


def append_legacy_stage(lineage: list | None, stage: LineageStage) -> list[dict[str, Any]]:
    """Return a deep copied legacy lineage with one typed stage appended."""
    # This is intentionally equivalent to:
    #   copy.deepcopy(lineage) + [stage_dict]
    # for valid v4.1.11 lineage payloads.
    return PopulationLineage.from_legacy_list(lineage).append(stage).to_legacy_list()
