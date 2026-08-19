"""Failure-atomic helpers for live gate-dictionary assignments."""

from __future__ import annotations


def snapshot_gate_assignment(gate: dict, key, before: dict, order: list) -> None:
    """Capture one field without adding observable dict-subclass reads."""
    if key in before:
        return
    before[key] = (dict.__contains__(gate, key), dict.get(gate, key))
    order.append(key)


def rollback_gate_assignments(gate: dict, before: dict, order: list) -> None:
    """Restore touched fields without invoking dict-subclass mutation hooks."""
    for key in reversed(order):
        was_present, old_value = before[key]
        if was_present:
            dict.__setitem__(gate, key, old_value)
        else:
            dict.pop(gate, key, None)
