"""Plain-Python gate definition adapter for the v4.2 structural refactor.

Live v4.1.11 UI gate dictionaries may contain tkinter Variable objects.  The
scientific core already accepts ordinary dictionaries, so this module provides
a lossless Tk-free snapshot boundary without changing gate geometry, mask
mathematics, serialization schema, or live UI ownership.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .threshold_state import flag_value


@dataclass(frozen=True)
class GateDefinition:
    """A deep, plain-Python snapshot of one legacy gate dictionary.

    ``payload`` deliberately retains the legacy dictionary schema (including
    compatibility toggle aliases) rather than introducing a new serialized
    representation during the pure refactor.
    """

    payload: dict[str, Any]

    @classmethod
    def from_plain_dict(cls, gate: dict[str, Any]) -> "GateDefinition":
        return cls(_deepcopy_mapping(gate))

    @classmethod
    def from_live_dict(
        cls,
        gate: dict[str, Any],
        *,
        variable_types: tuple[type, ...] = (),
    ) -> "GateDefinition":
        """Snapshot a legacy live gate while removing UI Variable objects.

        ``variable_types`` is injected by the UI layer (currently
        ``(tk.Variable,)``), keeping this core module independent of tkinter.
        The conversion matches the frozen v4.1.11 ``_plain_gate_snapshot``
        behavior exactly, including the three threshold-toggle aliases.
        """
        snap: dict[str, Any] = {}
        for key, value in gate.items():
            if key == "x_thresh_vars":
                snap[key] = [
                    flag_value(item, field=f"x_thresh_vars[{index}]")
                    for index, item in enumerate(value or [])
                ]
            elif key == "y_thresh_var":
                snap[key] = flag_value(value, field="y_thresh_var")
            elif key == "y_thresh_vars":
                snap[key] = [
                    flag_value(item, field=f"y_thresh_vars[{index}]")
                    for index, item in enumerate(value or [])
                ]
            elif variable_types and isinstance(value, variable_types):
                try:
                    snap[key] = value.get()
                except Exception:
                    continue
            else:
                try:
                    snap[key] = copy.deepcopy(value)
                except Exception:
                    snap[key] = value

        # Keep both live-style and serialized-style toggle keys.  This is the
        # exact compatibility behavior used by v4.1.11 ancestor replay.
        if "x_thresh_vars" in snap:
            snap["x_thresh_active"] = [bool(v) for v in snap["x_thresh_vars"]]
        if "y_thresh_var" in snap:
            snap["y_thresh_active"] = bool(snap["y_thresh_var"])
        if "y_thresh_vars" in snap:
            snap["y_thresh_actives"] = [bool(v) for v in snap["y_thresh_vars"]]
        return cls(snap)

    @property
    def gate_id(self):
        return self.payload.get("id")

    @property
    def gate_type(self) -> str:
        return self.payload.get("type", "crosshair")

    @property
    def applied(self) -> bool:
        return bool(self.payload.get("applied", False))

    @property
    def analysis_context(self) -> dict | None:
        context = self.payload.get("_analysis_context")
        return copy.deepcopy(context) if isinstance(context, dict) else None

    def to_plain_dict(self) -> dict[str, Any]:
        return _deepcopy_mapping(self.payload)


def _deepcopy_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    try:
        return copy.deepcopy(mapping)
    except Exception:
        # Mirror legacy best-effort per-value copying so one uncopyable
        # presentation value cannot alter otherwise usable gate provenance.
        out: dict[str, Any] = {}
        for key, value in mapping.items():
            try:
                out[key] = copy.deepcopy(value)
            except Exception:
                out[key] = value
        return out
