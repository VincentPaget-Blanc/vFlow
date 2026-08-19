"""Figure export helpers."""

from __future__ import annotations

import os


def is_vector_path(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in (".pdf", ".svg", ".eps")


def save_figure(fig, path: str, *, dpi: int = 300, vector_unrasterize: bool = False):
    """Save a Matplotlib figure with legacy vFlow export settings."""
    collections_state = []
    if vector_unrasterize and is_vector_path(path):
        for ax in fig.get_axes():
            for coll in ax.collections:
                collections_state.append((coll, coll.get_rasterized()))
                coll.set_rasterized(False)
    try:
        fig.savefig(
            path,
            dpi=dpi,
            bbox_inches="tight",
            facecolor=fig.get_facecolor(),
        )
    finally:
        for coll, state in collections_state:
            coll.set_rasterized(state)

