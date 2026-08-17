"""Shared export filename helpers."""

from __future__ import annotations

import os


def export_channel_token(channel: str | None, fallback: str) -> str:
    """Return the legacy channel token used in export filenames."""
    return (channel or fallback).replace(" ", "_")


def active_export_stem(active_files: dict, fallback: str = "flowjo_export") -> str:
    """Return the legacy export stem from the first active path."""
    if active_files:
        return os.path.splitext(os.path.basename(next(iter(active_files))))[0]
    return fallback


def xy_export_prefix(active_files: dict, x_channel: str | None, y_channel: str | None) -> str:
    """Return the legacy '<stem>_<x>_vs_<y>' export filename prefix."""
    stem = active_export_stem(active_files)
    x_token = export_channel_token(x_channel, "X")
    y_token = export_channel_token(y_channel, "Y")
    return f"{stem}_{x_token}_vs_{y_token}"
