#!/usr/bin/env python3
"""End-to-end generated-data interaction/session smoke checks for vFlow A5."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import tkinter as tk

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "source" / "vFlow_v4.3.0"
sys.path.insert(0, str(SRC))

from vflow.legacy.vflow_app import FlowApp
from vflow.legacy import vflow_app as legacy_module


class _MessageBox:
    errors: list[str] = []
    warnings: list[str] = []
    @classmethod
    def showerror(cls, title, message, *args, **kwargs): cls.errors.append(f"{title}: {message}")
    @classmethod
    def showwarning(cls, title, message, *args, **kwargs): cls.warnings.append(f"{title}: {message}")
    @staticmethod
    def showinfo(*args, **kwargs): return None
    @staticmethod
    def askyesno(*args, **kwargs): return True


class _FileDialog:
    path: str = ""
    @classmethod
    def asksaveasfilename(cls, *args, **kwargs): return cls.path
    @classmethod
    def askopenfilename(cls, *args, **kwargs): return cls.path


legacy_module.messagebox = _MessageBox
legacy_module.filedialog = _FileDialog
_KEEPALIVE = []


def _event(app, point, *, button=1, dblclick=False):
    px = app.ax.transData.transform(point)
    return SimpleNamespace(
        inaxes=app.ax, xdata=float(point[0]), ydata=float(point[1]),
        x=float(px[0]), y=float(px[1]), button=button, dblclick=dblclick,
    )


def _draw_drag_gate(app, gate_type, p0, p1):
    app.gate_type_var.set(gate_type)
    app.gate_mode_var.set("draw")
    app.gate_var.set(True)
    app._on_gate_type_change()
    app._on_click(_event(app, p0))
    app._on_motion(_event(app, p1))
    app._on_release(_event(app, p1))
    app.canvas.draw()
    return app._sel_gate()


def _draw_polygon(app, vertices):
    app.gate_type_var.set("polygon")
    app.gate_mode_var.set("draw")
    app.gate_var.set(True)
    app._on_gate_type_change()
    for point in vertices:
        app._on_click(_event(app, point))
    app._on_click(_event(app, vertices[-1], dblclick=True))
    app.canvas.draw()
    return app._sel_gate()


def main() -> int:
    if not os.environ.get("DISPLAY"):
        raise SystemExit("A display is required; use xvfb-run -a on headless systems.")

    with tempfile.TemporaryDirectory(prefix="vflow_a5_interaction_") as d:
        tmp = Path(d)
        rng = np.random.default_rng(8117)
        paths = []
        for i, (mx, my) in enumerate(((500.0, 700.0), (700.0, 900.0))):
            frame = pd.DataFrame({
                "X": np.clip(rng.normal(mx, 180, 320), 1.0, None),
                "Y": np.clip(rng.normal(my, 220, 320), 1.0, None),
                "Z": np.clip(rng.normal(300.0, 90, 320), 1.0, None),
            })
            path = tmp / f"sample_{i}.csv"
            frame.to_csv(path, index=False)
            paths.append(str(path))

        root = tk.Tk(); root.withdraw()
        app = FlowApp(root)
        _KEEPALIVE.append((root, app))
        app._load_paths(paths)
        app.show_labels_var.set(False)
        app.show_legend_var.set(False)
        app.x_var.set("X"); app.y_var.set("Y"); app.apply_axes(); app.canvas.draw()

        # Manual rectangle + real right-drag resize and body move.
        rect = _draw_drag_gate(app, "rectangle", (200, 250), (900, 1100))
        rect_created = bool(rect and rect.get("applied") and rect["id"] in app.gate_stats)
        before_resize = (rect["x0"], rect["y0"], rect["x1"], rect["y1"])
        app._on_click(_event(app, (rect["x1"], rect["y0"]), button=3))
        app._on_motion(_event(app, (rect["x1"] + 80, rect["y0"] - 40), button=3))
        app._on_release(_event(app, (rect["x1"] + 80, rect["y0"] - 40), button=3))
        app.canvas.draw()
        after_resize = (rect["x0"], rect["y0"], rect["x1"], rect["y1"])
        resize_changed = before_resize != after_resize and app._handle_drag is None

        cx = (rect["x0"] + rect["x1"]) / 2
        cy = (rect["y0"] + rect["y1"]) / 2
        before_move = (rect["x0"], rect["y0"], rect["x1"], rect["y1"])
        app._on_click(_event(app, (cx, cy), button=3))
        app._on_motion(_event(app, (cx + 60, cy + 50), button=3))
        app._on_release(_event(app, (cx + 60, cy + 50), button=3))
        app.canvas.draw()
        after_move = (rect["x0"], rect["y0"], rect["x1"], rect["y1"])
        move_changed = before_move != after_move and app._gate_move is None

        ellipse = _draw_drag_gate(app, "ellipse", (250, 300), (950, 1200))
        crosshair = _draw_drag_gate(app, "crosshair", (350, 450), (650, 800))
        polygon = _draw_polygon(app, [(180, 220), (980, 240), (930, 1250), (210, 1180)])
        manual_types_ok = all(
            gate is not None and gate.get("applied") and gate["id"] in app.gate_stats
            for gate in (rect, ellipse, crosshair, polygon)
        )

        # Shared marginal axes must survive log -> asinh without inversion.
        app.show_marginals_var.set(True); app.refresh_plot(); app.canvas.draw()
        app.x_scale_var.set("log"); app.y_scale_var.set("log"); app.canvas.draw()
        app.x_scale_var.set("asinh"); app.y_scale_var.set("asinh"); app.canvas.draw()
        marginal_limits_ok = (
            app.ax.get_xlim()[0] < app.ax.get_xlim()[1]
            and app.ax.get_ylim()[0] < app.ax.get_ylim()[1]
            and app.ax_top.get_xscale() == "asinh"
            and app.ax_right.get_yscale() == "asinh"
        )

        # Overlay/cycle and active-file stats behavior.
        overlay_stats_files = len(app.gate_stats[rect["id"]])
        app.view_mode_var.set("cycle"); app._on_view_mode_change(); app.canvas.draw()
        cycle_one_file = "Shown: 1/2 files" in app.status_var.get()
        app._cycle_next(); app.canvas.draw()
        cycle_label_nonempty = bool(app.cycle_label_var.get())
        app.view_mode_var.set("overlay"); app._on_view_mode_change(); app.canvas.draw()
        app.file_vars[paths[0]].set(False); app._on_active_files_changed(); app.canvas.draw()
        one_active_stats_file = len(app.gate_stats[rect["id"]]) == 1
        app.file_vars[paths[0]].set(True); app._on_active_files_changed(); app.canvas.draw()

        # Save gates under asinh, change transform, clear, reload: same-channel
        # gates must rebind to the live transform and render/stat correctly.
        session_path = tmp / "gates.json"
        _FileDialog.path = str(session_path)
        app.save_gates()
        app.x_scale_var.set("linear"); app.y_scale_var.set("linear")
        app.clear_all_gates()
        app.load_gates(); app.canvas.draw()
        session_reload_ok = (
            len(app.gates) == 4
            and all(app._gate_context_matches(g) for g in app.gates)
            and all(g["_analysis_context"]["x_scale"] == "linear" for g in app.gates)
            and len(app._preview_artists) >= 4
        )

        # Different channel hides gates; returning after a scale change restores.
        app.x_var.set("Z"); app.y_var.set("Y"); app.apply_axes(); app.canvas.draw()
        channel_hide_ok = len(app._preview_artists) == 0
        app.x_scale_var.set("legacy_logicle")
        app.x_var.set("X"); app.y_var.set("Y"); app.apply_axes(); app.canvas.draw()
        channel_return_ok = (
            len(app._preview_artists) >= 4
            and all(app._gate_context_matches(g) for g in app.gates)
        )

        result = {
            "manual_rectangle_created": rect_created,
            "handle_resize_changed_geometry": resize_changed,
            "body_move_changed_geometry": move_changed,
            "manual_gate_types_all_applied_with_stats": manual_types_ok,
            "marginal_log_to_asinh_limits_ordered": marginal_limits_ok,
            "overlay_stats_file_count": overlay_stats_files,
            "cycle_shows_one_of_two": cycle_one_file,
            "cycle_label_nonempty": cycle_label_nonempty,
            "active_file_change_recomputes_stats": one_active_stats_file,
            "session_reload_rebinds_current_scale": session_reload_ok,
            "different_channel_hides_gates": channel_hide_ok,
            "return_to_original_channels_restores_gates": channel_return_ok,
            "messagebox_errors": list(_MessageBox.errors),
        }
        checks = [v for k, v in result.items() if isinstance(v, bool)]
        passed = all(checks) and overlay_stats_files == 2 and not _MessageBox.errors
        result["status"] = "PASS" if passed else "FAIL"
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
