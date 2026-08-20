#!/usr/bin/env python3
"""Generated-data end-to-end GUI regression checks for vFlow A5.

Run under a display (CI/headless example):
    xvfb-run -a python validation_tools/regression_hardening_a5_gui_checks.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import tkinter as tk

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "source" / "vFlow_v4.3.0"
sys.path.insert(0, str(SRC))

from vflow.config.constants import ALL_SCALES
from vflow.legacy.vflow_app import FlowApp
from vflow.legacy import vflow_app as legacy_module


class _MessageBox:
    errors: list[str] = []
    warnings: list[str] = []

    @classmethod
    def showerror(cls, title, message, *args, **kwargs):
        cls.errors.append(f"{title}: {message}")

    @classmethod
    def showwarning(cls, title, message, *args, **kwargs):
        cls.warnings.append(f"{title}: {message}")

    @staticmethod
    def showinfo(*args, **kwargs):
        return None

    @staticmethod
    def askyesno(*args, **kwargs):
        return False


legacy_module.messagebox = _MessageBox


def _build_app(csv_path: str, x: str = "X", y: str = "Y"):
    root = tk.Tk()
    root.withdraw()
    app = FlowApp(root)
    app._load_paths([csv_path])
    app.show_labels_var.set(False)
    app.show_legend_var.set(False)
    app.x_var.set(x)
    app.y_var.set(y)
    app.apply_axes()
    app.canvas.draw()
    return root, app


_KEEPALIVE = []

def _destroy_app(root, app):
    """Keep short-lived headless Tk roots alive until process exit.

    FigureCanvasTkAgg schedules idle-draw Tcl commands; explicitly destroying
    the root before those callbacks are serviced can itself create a false
    Tcl teardown error.  This validator is a one-shot process, so retaining
    the two withdrawn roots until interpreter shutdown is the cleanest path.
    """
    _KEEPALIVE.append((root, app))

def _positive_scale_matrix(tmp: Path) -> dict:
    rng = np.random.default_rng(20260817)
    n = 260
    frame = pd.DataFrame({
        "X": np.exp(rng.uniform(np.log(1.0), np.log(1e5), n)),
        "Y": np.exp(rng.uniform(np.log(2.0), np.log(5e4), n)),
        "Z": rng.normal(size=n),
    })
    path = tmp / "scale_matrix.csv"
    frame.to_csv(path, index=False)
    root, app = _build_app(str(path))
    try:
        gate = app._add_gate(
            auto_type="rectangle",
            auto_apply={"x0": 10.0, "x1": 10000.0, "y0": 20.0, "y1": 8000.0},
        )
        app._finish_gate(gate)
        app.canvas.draw()

        failures = []
        checked = 0
        for x_scale in ALL_SCALES:
            for y_scale in ALL_SCALES:
                app.x_scale_var.set(x_scale)
                app.y_scale_var.set(y_scale)
                app.canvas.draw()
                checked += 1

                if (app.x_scale, app.y_scale) != (x_scale, y_scale):
                    failures.append([x_scale, y_scale, "state-axis-assignment"])
                    continue
                if (app.ax.get_xscale(), app.ax.get_yscale()) != (x_scale, y_scale):
                    failures.append([x_scale, y_scale, "matplotlib-axis-assignment"])
                    continue
                if not app._gate_context_matches(gate) or not app._preview_artists:
                    failures.append([x_scale, y_scale, "gate-not-visible"])
                    continue

                xlim = app.ax.get_xlim()
                ylim = app.ax.get_ylim()
                if not (np.all(np.isfinite(xlim)) and xlim[0] < xlim[1]):
                    failures.append([x_scale, y_scale, "x-limits-reversed-or-invalid"])
                if not (np.all(np.isfinite(ylim)) and ylim[0] < ylim[1]):
                    failures.append([x_scale, y_scale, "y-limits-reversed-or-invalid"])

                x_probe = np.array([3.0, 10.0, 100.0, 1000.0, 10000.0])
                x_pix = app.ax.transData.transform(
                    np.c_[x_probe, np.full(x_probe.size, 100.0)])[:, 0]
                y_probe = np.array([3.0, 10.0, 100.0, 1000.0, 10000.0])
                y_pix = app.ax.transData.transform(
                    np.c_[np.full(y_probe.size, 100.0), y_probe])[:, 1]
                if not np.all(np.diff(x_pix) > 0):
                    failures.append([x_scale, y_scale, "x-transform-reversed"])
                if not np.all(np.diff(y_pix) > 0):
                    failures.append([x_scale, y_scale, "y-transform-reversed"])

        # Gate must disappear only when a measurement channel changes, then
        # return/recompute even if the display scale changed while it was inactive.
        app.x_var.set("Z")
        app.y_var.set("Y")
        app.apply_axes()
        app.canvas.draw()
        inactive_on_other_channel = (
            not app._gate_context_matches(gate) and len(app._preview_artists) == 0
        )
        app.x_scale_var.set("linear")
        app.x_var.set("X")
        app.y_var.set("Y")
        app.apply_axes()
        app.canvas.draw()
        returns_after_scale_change = (
            app._gate_context_matches(gate)
            and bool(app._preview_artists)
            and gate["_analysis_context"]["x_scale"] == "linear"
        )

        return {
            "scale_combinations_checked": checked,
            "scale_failures": failures,
            "inactive_on_different_channel": bool(inactive_on_other_channel),
            "returns_after_scale_change_on_original_channels": bool(returns_after_scale_change),
        }
    finally:
        _destroy_app(root, app)


def _auto_gate_checks(tmp: Path) -> dict:
    rng = np.random.default_rng(91)
    per = 350
    parts = []
    for mx, my in [(-600, -400), (-600, 1600), (2200, -400), (2400, 1800)]:
        parts.append(np.c_[rng.normal(mx, 180, per), rng.normal(my, 210, per)])
    xy = np.vstack(parts)
    path = tmp / "autogate.csv"
    pd.DataFrame({"X": xy[:, 0], "Y": xy[:, 1]}).to_csv(path, index=False)
    root, app = _build_app(str(path))
    outcomes = {}
    try:
        for method_name in (
            "auto_gate_derivative",
            "auto_gate_otsu",
            "auto_gate_gmm_multi",
            "auto_gate_cluster_polygons",
        ):
            _MessageBox.errors.clear()
            _MessageBox.warnings.clear()
            app.clear_all_gates()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                getattr(app, method_name)()
            app.canvas.draw()
            applied = [g for g in app.gates if g.get("applied")]
            outcomes[method_name] = {
                "applied_gates": len(applied),
                "preview_artists": len(app._preview_artists),
                "stats_gates": len(app.gate_stats),
                "errors": list(_MessageBox.errors),
                "warnings": list(_MessageBox.warnings),
                "status": app.status_var.get(),
            }
        return outcomes
    finally:
        _destroy_app(root, app)


def main() -> int:
    if not os.environ.get("DISPLAY"):
        raise SystemExit("A display is required; use xvfb-run -a on headless systems.")
    with tempfile.TemporaryDirectory(prefix="vflow_a5_gui_") as d:
        tmp = Path(d)
        scale = _positive_scale_matrix(tmp)
        auto = _auto_gate_checks(tmp)

    auto_ok = all(
        result["applied_gates"] >= 1 and not result["errors"]
        for result in auto.values()
    )
    passed = (
        not scale["scale_failures"]
        and scale["inactive_on_different_channel"]
        and scale["returns_after_scale_change_on_original_channels"]
        and auto_ok
    )
    result = {"status": "PASS" if passed else "FAIL", "scale_matrix": scale, "auto_gates": auto}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
