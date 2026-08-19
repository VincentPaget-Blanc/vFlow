#!/usr/bin/env python3
"""Generated-data refactor-boundary checks added by B6.

Exercises failure modes that helper/unit tests can miss: complete data clear,
locked-scale carryover, degenerate density data, channel mismatch safety, and
repeated notebook child teardown using the actual Tk/Matplotlib application.
"""
from __future__ import annotations

import json
import sys
import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import tkinter as tk

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "source" / "vFlow_v4.3.0-dev"
sys.path.insert(0, str(SRC))

from vflow.config.constants import ALL_SCALES
from vflow.legacy.vflow_app import FlowApp, FlowTabManager
from vflow.legacy import vflow_app as legacy_module


class MessageBox:
    errors = []
    warnings = []
    infos = []

    @classmethod
    def showerror(cls, title, message, *args, **kwargs):
        cls.errors.append(f"{title}: {message}")

    @classmethod
    def showwarning(cls, title, message, *args, **kwargs):
        cls.warnings.append(f"{title}: {message}")

    @classmethod
    def showinfo(cls, title, message, *args, **kwargs):
        cls.infos.append(f"{title}: {message}")

    @staticmethod
    def askyesno(*args, **kwargs):
        return True


legacy_module.messagebox = MessageBox

checks = {}
failures = []
async_errors = []


def check(name, condition, detail=""):
    ok = bool(condition)
    checks[name] = ok
    if not ok:
        failures.append(f"{name}: {detail or 'failed'}")


with tempfile.TemporaryDirectory(prefix="vflow_b6_integrity_") as tmp:
    td = Path(tmp)
    old_path = td / "old.csv"
    new_path = td / "new.csv"
    constant_path = td / "constant.csv"
    mismatch_a = td / "mismatch_a.csv"
    mismatch_b = td / "mismatch_b.csv"
    nan_inf_path = td / "nan_inf.csv"
    zero_rows_path = td / "zero_rows.csv"
    one_col_path = td / "one_col.csv"

    pd.DataFrame({"A": [1.0, 2.0, 3.0], "B": [4.0, 5.0, 6.0]}).to_csv(old_path, index=False)
    pd.DataFrame({"C": [10000.0, 20000.0, 30000.0], "D": [40000.0, 50000.0, 60000.0]}).to_csv(new_path, index=False)
    pd.DataFrame({"X": np.full(64, 5.0), "Y": np.full(64, 7.0)}).to_csv(constant_path, index=False)
    pd.DataFrame({"X": [1.0, 2.0], "Y": [3.0, 4.0]}).to_csv(mismatch_a, index=False)
    pd.DataFrame({"X": [5.0, 6.0], "Z": [7.0, 8.0]}).to_csv(mismatch_b, index=False)
    pd.DataFrame({
        "X": [1.0, np.nan, np.inf, -np.inf, 5.0],
        "Y": [2.0, 3.0, 4.0, 5.0, np.nan],
    }).to_csv(nan_inf_path, index=False)
    pd.DataFrame({
        "X": pd.Series(dtype=float), "Y": pd.Series(dtype=float),
    }).to_csv(zero_rows_path, index=False)
    pd.DataFrame({"X": [1.0, 2.0, 3.0]}).to_csv(one_col_path, index=False)

    root = tk.Tk()
    root.withdraw()
    root.report_callback_exception = lambda et, ev, tb: async_errors.append(
        "".join(traceback.format_exception(et, ev, tb)))

    # Clear All must clear presentation state as well as the dataset model.
    app = FlowApp(root)
    app._load_paths([str(old_path)])
    app.plot_type_var.set("Dot Plot")
    app.refresh_plot(); app.canvas.draw(); root.update()
    old_limits = (tuple(app.ax.get_xlim()), tuple(app.ax.get_ylim()))
    app.lock_scale_var.set(True)
    app._on_lock_scale_toggle()
    check("lock_captured_before_clear", app._locked_xlim is not None and app._locked_ylim is not None)

    app.clear_all_files(); app.canvas.draw(); root.update()
    check("clear_removes_loaded_files", not app.loaded_files)
    check("clear_blanks_channel_values", list(app.x_menu['values']) == [] and list(app.y_menu['values']) == [])
    check("clear_blanks_channel_variables", app.x_var.get() == "" and app.y_var.get() == "")
    check("clear_resets_lock", not app.lock_scale_var.get() and app._locked_xlim is None and app._locked_ylim is None)
    check("clear_removes_old_scatter", len(app.ax.collections) == 0)
    check("clear_replaces_old_title", app.ax.get_title() != "A  ×  B")

    # A very different next dataset must not inherit stale limits.
    app._load_paths([str(new_path)]); app.canvas.draw(); root.update()
    xl, yl = app.ax.get_xlim(), app.ax.get_ylim()
    check("new_dataset_channels_selected", app.x_channel == "C" and app.y_channel == "D", f"{app.x_channel}/{app.y_channel}")
    check("new_dataset_not_using_old_locked_limits", tuple(xl) != old_limits[0] and tuple(yl) != old_limits[1])
    check("new_dataset_visible", xl[0] < 20000 < xl[1] and yl[0] < 50000 < yl[1], f"x={xl}, y={yl}")

    # Constant channels used to crash Density's RegularGridInterpolator from
    # a scale-variable Tk trace.  Exercise every supported scale family.
    app.clear_all_files()
    app._load_paths([str(constant_path)])
    app.plot_type_var.set("Density")
    degenerate_scale_results = {}
    for scale in ALL_SCALES:
        before = len(async_errors)
        app.x_scale_var.set(scale)
        app.y_scale_var.set(scale)
        root.update(); app.canvas.draw(); root.update()
        xl, yl = app.ax.get_xlim(), app.ax.get_ylim()
        degenerate_scale_results[scale] = {
            "ordered": bool(xl[0] < xl[1] and yl[0] < yl[1]),
            "new_async_errors": len(async_errors) - before,
        }
    check(
        "constant_density_all_scales_safe",
        all(v["ordered"] and v["new_async_errors"] == 0 for v in degenerate_scale_results.values()),
        str(degenerate_scale_results),
    )

    # Mismatched files must fail closed instead of rendering a partial subset.
    app.clear_all_files()
    app._load_paths([str(mismatch_a), str(mismatch_b)])
    root.update(); app.canvas.draw(); root.update()
    check("mismatch_common_menu_is_intersection", list(app.x_menu['values']) == ["X"] and list(app.y_menu['values']) == ["X"])
    check("mismatch_has_no_unsafe_xy_pair", app.x_channel is None and app.y_channel is None)
    check("mismatch_reports_safe_pause", "No safe shared X/Y channels" in app.status_var.get())

    # Non-finite values must be filtered consistently across every transform,
    # without producing reversed axes or callback exceptions.
    app.clear_all_files()
    app._load_paths([str(nan_inf_path)])
    app.plot_type_var.set("Density")
    nonfinite_ok = True
    for scale in ALL_SCALES:
        before = len(async_errors)
        app.x_scale_var.set(scale); app.y_scale_var.set(scale)
        root.update(); app.canvas.draw(); root.update()
        xl, yl = app.ax.get_xlim(), app.ax.get_ylim()
        nonfinite_ok = nonfinite_ok and xl[0] < xl[1] and yl[0] < yl[1]
        nonfinite_ok = nonfinite_ok and len(async_errors) == before
    check("nan_inf_all_scales_safe", nonfinite_ok)

    # Empty/single-column files are loadable but cannot define a valid 2-D
    # analysis context; they must fail closed instead of retaining old axes.
    edge_context_ok = True
    for edge_path in (zero_rows_path, one_col_path):
        app.clear_all_files(); app._load_paths([str(edge_path)])
        root.update(); app.canvas.draw(); root.update()
        edge_context_ok = edge_context_ok and app.x_channel is None and app.y_channel is None
        edge_context_ok = edge_context_ok and "No safe shared X/Y channels" in app.status_var.get()
    check("empty_and_single_column_fail_closed", edge_context_ok)

    # Repeated child tab lifecycle: forget + destroy, callback cancellation,
    # and live Tk-backed gate sanitization at the manager boundary.
    manager_root = tk.Toplevel(root)
    manager_root.withdraw()
    manager = FlowTabManager(manager_root)
    base_children = len(manager.notebook.winfo_children())
    gate_flag = tk.BooleanVar(master=manager_root, value=True)
    live_parent_gate = {
        "id": 91,
        "name": "Live parent",
        "type": "crosshair",
        "x_thresh_vars": [gate_flag],
        "y_thresh_var": gate_flag,
    }
    filtered = {str(mismatch_a): pd.DataFrame({"X": [1.0, 2.0], "Y": [3.0, 4.0]})}
    teardown_ok = True
    provenance_ok = True
    for i in range(8):
        manager.open_subgate_tab(
            f"region {i}", filtered, "X", "Y", 2,
            parent_gate=live_parent_gate, parent_region="IN", population_lineage=[])
        root.update()
        tabs = manager.notebook.tabs()
        child_id = tabs[1]
        child_widget = manager.notebook.nametowidget(child_id)
        child_app = manager._apps[1]
        pg = child_app.parent_gate
        provenance_ok = provenance_ok and pg["x_thresh_vars"] == [True] and pg["y_thresh_var"] is True
        manager._close_tab(1)
        root.update()
        teardown_ok = teardown_ok and (not child_widget.winfo_exists())
        teardown_ok = teardown_ok and len(manager._apps) == 1 and len(manager.notebook.tabs()) == 1
        teardown_ok = teardown_ok and len(manager.notebook.winfo_children()) == base_children
    check("subgate_live_gate_is_plain_provenance", provenance_ok)
    check("subgate_repeated_close_destroys_widgets", teardown_ok)

    try:
        manager_root.destroy()
        app.container.destroy()
        root.update_idletasks(); root.update(); root.destroy()
    except Exception:
        pass

checks["async_callback_errors_none"] = not async_errors
if async_errors:
    failures.extend(f"async: {e}" for e in async_errors)
checks["messagebox_errors_none"] = not MessageBox.errors
if MessageBox.errors:
    failures.extend(f"messagebox: {e}" for e in MessageBox.errors)

result = {
    "status": "PASS" if not failures else "FAIL",
    "checks": checks,
    "failures": failures,
    "async_errors": async_errors,
    "messagebox_errors": MessageBox.errors,
    "messagebox_warnings": MessageBox.warnings,
    "degenerate_scale_results": degenerate_scale_results,
}
print(json.dumps(result, indent=2))
raise SystemExit(0 if not failures else 1)
