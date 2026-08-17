#!/usr/bin/env python3
"""Deterministic legacy-render probe for vFlow A1/A2 differential certification.

Run this script with PYTHONPATH pointing at a vFlow source tree.  It deliberately
uses the historical public scale aliases ``logicle`` and ``biexp`` so an A2 run
proves those aliases remain visually equivalent to A1.
"""
from __future__ import annotations

import hashlib
import json
import sys

import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np

# Import registers the custom Matplotlib scales.
from vflow.core.scales import register_flow_scales
register_flow_scales()
from vflow.core.transforms import forward_transform
from vflow.rendering.flow_renderer import FlowRenderer
from vflow.controllers.gate_interaction_controller import GateInteractionController


class Host:
    def __init__(self, ax):
        self.ax = ax
        self.x_channel = "X"
        self.y_channel = "Y"
        self.x_scale = "logicle"
        self.y_scale = "biexp"
        self.cofactor = 150.0
        # A2 consults these; A1 harmlessly ignores them.  Historical aliases
        # must ignore standards-Logicle parameters by definition.
        self.x_transform_params = {"T": 262144.0, "W": 0.5, "M": 4.5, "A": 0.0}
        self.y_transform_params = {"T": 100000.0, "W": 0.25, "M": 4.0, "A": 0.0}


def _canvas_hash(fig: Figure) -> str:
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    return hashlib.sha256(bytes(canvas.buffer_rgba())).hexdigest()


def _axes():
    fig = Figure(figsize=(5.0, 4.0), dpi=100)
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.set_xscale("logicle", cofactor=150.0)
    ax.set_yscale("biexp")
    ax.set_xlim(-2400.0, 3200.0)
    ax.set_ylim(-1800.0, 2800.0)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.grid(True, alpha=0.15)
    return fig, canvas, ax


def _dataset():
    rng = np.random.default_rng(20260814)
    n = 900
    x = np.concatenate([
        rng.normal(-550.0, 260.0, n // 3),
        rng.normal(420.0, 310.0, n // 3),
        rng.normal(1500.0, 460.0, n - 2 * (n // 3)),
    ])
    y = np.concatenate([
        rng.normal(-300.0, 230.0, n // 3),
        rng.normal(700.0, 330.0, n // 3),
        rng.normal(1300.0, 410.0, n - 2 * (n // 3)),
    ])
    # Add deterministic tails/near-zero values to exercise both custom scales.
    x[:10] = np.array([-2200, -1200, -300, -1, 0, 1, 8, 80, 800, 2800], float)
    y[:10] = np.array([-1600, -900, -250, -1, 0, 1, 6, 60, 600, 2400], float)
    xt = forward_transform(x, "logicle", 150.0)
    yt = forward_transform(y, "biexp", 150.0)
    valid = np.isfinite(xt) & np.isfinite(yt)
    return x, y, xt, yt, valid


def probe_dot():
    fig, _, ax = _axes()
    host = Host(ax)
    r = FlowRenderer(host)
    x, y, xt, yt, valid = _dataset()
    r.plot_dot(x, y, valid, "#3366aa", "legacy", 7.0, 0.55)
    ax.legend(loc="upper left", fontsize=7)
    return _canvas_hash(fig)


def probe_density():
    fig, _, ax = _axes()
    host = Host(ax)
    r = FlowRenderer(host)
    x, y, xt, yt, valid = _dataset()
    r.plot_density(x, y, xt, yt, valid, 7.0, 0.60, "legacy")
    return _canvas_hash(fig)


def probe_contour():
    fig, _, ax = _axes()
    host = Host(ax)
    r = FlowRenderer(host)
    x, y, xt, yt, valid = _dataset()
    r.plot_contour(x, y, xt, yt, valid, "#224488", "legacy", 6.0, 0.60, 0.90)
    return _canvas_hash(fig)


def probe_gate_preview():
    fig, _, ax = _axes()
    host = Host(ax)
    host.gates = [
        {
            "id": 71,
            "type": "rectangle",
            "name": "R1",
            "applied": False,
            "x0": -700.0,
            "x1": 1300.0,
            "y0": -450.0,
            "y1": 1700.0,
            "color": "#7c4dff",
        },
        {
            "id": 72,
            "type": "polygon",
            "name": "P1",
            "applied": False,
            "vertices": [(-1100.0, -500.0), (-100.0, 1600.0), (1800.0, 1200.0)],
            "color": "#00897b",
        },
    ]
    host._sel_gate_id = None
    host._poly_active = False
    host._poly_cursor = None
    host._draw_gate_id = None
    host._preview_artists = []
    host._handle_artists = []
    host._handle_px_cache = {}
    host._gate_context_matches = lambda gate: True

    controller = GateInteractionController(host)
    # We are certifying gate-outline rendering, not handle-hit-test state.
    controller.draw_handles = lambda: None
    controller.rebuild_handle_px_cache = lambda: None
    controller.preview_gate()
    return _canvas_hash(fig)


def main():
    result = {
        "dot": probe_dot(),
        "density": probe_density(),
        "contour": probe_contour(),
        "gate_preview": probe_gate_preview(),
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
