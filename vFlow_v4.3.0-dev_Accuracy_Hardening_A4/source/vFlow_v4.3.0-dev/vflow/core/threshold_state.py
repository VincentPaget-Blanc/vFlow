"""Plain-Python threshold-toggle compatibility adapters.

Live v4.1.11 crosshair gate dictionaries may store threshold toggles as Tk
Variable objects, while serialized/provenance gates store ordinary booleans.
This module centralizes the legacy flag-reading rules without changing the
legacy gate dictionary surface or making the typed gate model authoritative.

Important: active-region/cache interpretation and JSON serialization have
slightly different historical fallback rules.  They intentionally remain
separate here so the structural refactor cannot silently normalize behavior.
"""

from __future__ import annotations

from dataclasses import dataclass


class ThresholdSchemaError(ValueError):
    """Raised when a live threshold-toggle payload cannot be interpreted safely.

    Valid legacy representations keep their existing semantics.  This exception is
    reserved for malformed containers/getters that previously failed through
    incidental ``TypeError``/getter exceptions without identifying the offending
    threshold field.
    """


def flag_value(value, default=False, *, field: str = "threshold flag") -> bool:
    """Read one legacy Tk-like/plain threshold flag.

    Plain legacy values without ``.get`` retain their historical truth-value
    semantics. Malformed getter objects now raise :class:`ThresholdSchemaError`
    with field context instead of leaking incidental getter exceptions.
    """
    if value is None:
        return bool(default)

    try:
        getter = getattr(value, "get")
    except AttributeError:
        # Plain booleans/numbers/other legacy truthy values remain supported.
        try:
            return bool(value)
        except Exception as exc:
            raise ThresholdSchemaError(
                f"Invalid {field}: truth-value evaluation failed: {exc}") from exc

    if not callable(getter):
        raise ThresholdSchemaError(
            f"Invalid {field}: '.get' exists but is not callable.")

    try:
        return bool(getter())
    except Exception as exc:
        raise ThresholdSchemaError(
            f"Invalid {field}: .get() could not be read: {exc}") from exc


def flag_tuple(values, *, field: str = "threshold flags") -> tuple[bool, ...]:
    """Read a legacy optional flag sequence using cache/activity semantics."""
    source = values or []
    try:
        iterator = iter(source)
    except TypeError as exc:
        raise ThresholdSchemaError(
            f"Invalid {field}: expected an iterable threshold-flag sequence.") from exc
    return tuple(
        flag_value(value, field=f"{field}[{index}]")
        for index, value in enumerate(iterator)
    )


def x_threshold_flags(gate: dict) -> tuple[bool, ...]:
    """Return X flags using live-variable then serialized-alias fallback."""
    source = gate.get("x_thresh_vars") or gate.get("x_thresh_active") or []
    return flag_tuple(source, field="x_thresh_vars/x_thresh_active")


def single_y_threshold_flag(gate: dict) -> bool:
    """Return the scalar Y flag using the exact legacy fallback/default."""
    value = gate.get("y_thresh_var")
    if value is None:
        value = gate.get("y_thresh_active", True)
    return flag_value(value, field="y_thresh_var/y_thresh_active")


def multi_y_threshold_flags(gate: dict) -> tuple[bool, ...]:
    """Return multi-Y flags using live-variable then serialized-alias fallback."""
    source = gate.get("y_thresh_vars") or gate.get("y_thresh_actives") or []
    return flag_tuple(source, field="y_thresh_vars/y_thresh_actives")


@dataclass(frozen=True)
class ThresholdState:
    """Tk-free snapshot of threshold toggle truth values for one gate."""

    x_flags: tuple[bool, ...]
    y_flag: bool
    y_flags: tuple[bool, ...]

    @classmethod
    def from_gate(cls, gate: dict) -> "ThresholdState":
        """Snapshot activity/cache interpretation without mutating ``gate``."""
        return cls(
            x_flags=x_threshold_flags(gate),
            y_flag=single_y_threshold_flag(gate),
            y_flags=multi_y_threshold_flags(gate),
        )

    def active_x(self, boundaries) -> list:
        """Return active X boundaries with legacy length-mismatch fallback."""
        xbs = list(boundaries or [])
        if len(self.x_flags) != len(xbs):
            return xbs
        return [xb for xb, active in zip(xbs, self.x_flags) if active]

    def active_y(self, y_boundary, y_boundaries) -> list:
        """Return active Y boundaries with legacy scalar/multi-Y behavior."""
        if y_boundaries:
            ybs = list(y_boundaries)
            if len(self.y_flags) != len(ybs):
                return ybs
            return [yb for yb, active in zip(ybs, self.y_flags) if active]
        if y_boundary is None:
            return []
        return [y_boundary] if self.y_flag else []


@dataclass(frozen=True)
class SerializedThresholdFlags:
    """Threshold booleans projected using the legacy JSON-save rules."""

    x_active: tuple[bool, ...]
    y_active: bool
    y_actives: tuple[bool, ...]


def _serialized_flag_sequence(gate: dict, field: str) -> tuple[bool, ...]:
    values = gate.get(field, [])
    if values is None:
        raise ThresholdSchemaError(
            f"Invalid {field}: expected an iterable threshold-flag sequence, got None.")
    try:
        iterator = iter(values)
    except TypeError as exc:
        raise ThresholdSchemaError(
            f"Invalid {field}: expected an iterable threshold-flag sequence, "
            f"got {type(values).__name__}.") from exc
    return tuple(
        flag_value(value, field=f"{field}[{index}]")
        for index, value in enumerate(iterator)
    )


def serialized_threshold_flags(gate: dict) -> SerializedThresholdFlags:
    """Project live gate flags using the legacy JSON-save value semantics.

    Missing live ``*_vars`` lists still serialize as empty lists and serialized
    aliases are still intentionally ignored.  Malformed explicitly-present
    containers/getters now raise :class:`ThresholdSchemaError` with field/index
    context instead of leaking incidental iteration/getter exceptions.
    """
    x_active = _serialized_flag_sequence(gate, "x_thresh_vars")
    y_active = flag_value(
        gate.get("y_thresh_var"), True, field="y_thresh_var")
    y_actives = _serialized_flag_sequence(gate, "y_thresh_vars")
    return SerializedThresholdFlags(x_active, y_active, y_actives)
