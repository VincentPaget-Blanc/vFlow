"""Lazy public import path for the packaged FlowApp implementation."""

from __future__ import annotations


def __getattr__(name: str):
    if name == "FlowApp":
        from vflow.legacy.vflow_legacy import FlowApp

        return FlowApp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["FlowApp"]

