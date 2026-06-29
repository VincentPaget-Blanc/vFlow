"""Matplotlib backend configuration for vFlow."""

from __future__ import annotations


def configure_matplotlib_backend(headless: bool = False) -> None:
    """Select the Matplotlib backend before plotting modules are imported."""
    import matplotlib

    matplotlib.use("Agg" if headless else "TkAgg")

