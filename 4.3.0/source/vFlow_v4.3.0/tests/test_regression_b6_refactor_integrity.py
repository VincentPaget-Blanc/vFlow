from types import SimpleNamespace
import tkinter as tk

import pandas as pd

from vflow.app.state import AnalysisState
from vflow.legacy import vflow_app as app_module
from vflow.legacy.vflow_app import FlowApp
from vflow.rendering.flow_renderer import FlowRenderer
from vflow.ui.tab_manager import FlowTabManagerBase
from vflow.controllers import project_data_load_coordinator as load_module
from vflow.controllers.project_data_load_coordinator import ProjectDataLoadCoordinator


class Var:
    def __init__(self, value=None): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = value


class Menu(dict):
    pass


class Frame:
    def __init__(self): self.children = []
    def winfo_children(self): return list(self.children)


def test_renderer_clears_stale_artists_when_all_data_was_removed():
    calls = []

    class Axis:
        transAxes = object()
        def set_facecolor(self, value): pass
        def text(self, *args, **kwargs): calls.append(("text", args[2]))
        def set_xticks(self, value): pass
        def set_yticks(self, value): pass

    class Host:
        loaded_files = {}
        x_channel = None
        y_channel = None
        T = {"ax_bg": "a", "fg_dim": "d"}
        status_var = Var()
        canvas = SimpleNamespace(draw_idle=lambda: calls.append("draw"))
        def _active(self): return {}
        def _setup_axes(self):
            calls.append("setup")
            self.ax = Axis()

    FlowRenderer(Host()).refresh()
    assert calls[0] == "setup"
    assert ("text", "No data loaded.") in calls
    assert calls[-1] == "draw"


def test_clear_all_resets_visible_channels_and_dataset_locked_limits(monkeypatch):
    app = FlowApp.__new__(FlowApp)
    app.loaded_files = {"old.csv": pd.DataFrame({"A": [1.0], "B": [2.0]})}
    app.excluded_files = {"excluded.csv": pd.DataFrame({"A": [3.0], "B": [4.0]})}
    app.file_vars = {"old.csv": Var(True)}
    app.file_colors = {"old.csv": "#fff"}
    app.axis_aliases = {"A": "Alias"}
    app.gate_stats = {0: {"n": 1}}
    app.gates = []
    app._minor_loc_cache = {}
    app._data_generation = 0
    app.x_channel = "A"
    app.y_channel = "B"

    app.x_menu = Menu(values=("A", "B"))
    app.y_menu = Menu(values=("A", "B"))
    app.x_var = Var("A")
    app.y_var = Var("B")
    app.lock_scale_var = Var(True)
    app._locked_xlim = (0.0, 5.0)
    app._locked_ylim = (10.0, 20.0)
    app.file_list_frame = Frame()
    app.status_var = Var()

    calls = []
    app._show_lock_buttons = lambda value: calls.append(("lock_buttons", value))
    app._rebuild_excluded_list = lambda: calls.append("excluded")
    app._update_channel_menus = lambda: calls.append("menus")
    app.refresh_plot = lambda: calls.append("refresh")
    app._update_stats_display = lambda: calls.append("stats")
    monkeypatch.setattr(app_module.messagebox, "askyesno", lambda *a, **k: True)

    app.clear_all_files()

    assert app.loaded_files == {}
    assert app.excluded_files == {}
    assert app.x_channel is None and app.y_channel is None
    assert app.x_menu["values"] == () and app.y_menu["values"] == ()
    assert app.x_var.get() == "" and app.y_var.get() == ""
    assert app.lock_scale_var.get() is False
    assert app._locked_xlim is None and app._locked_ylim is None
    assert ("lock_buttons", False) in calls
    assert "refresh" in calls


def test_close_subgate_destroys_forgotten_notebook_child_and_cancels_callbacks():
    class Widget:
        def __init__(self): self.destroyed = False
        def winfo_exists(self): return not self.destroyed
        def destroy(self): self.destroyed = True

    class Notebook:
        def __init__(self, widget):
            self.ids = ["main", "sub"]
            self.widget = widget
        def tabs(self): return tuple(self.ids)
        def nametowidget(self, tab_id):
            assert tab_id == "sub"
            return self.widget
        def forget(self, tab_id): self.ids.remove(tab_id)

    cancelled = []
    sub_app = SimpleNamespace(
        root=SimpleNamespace(after_cancel=lambda token: cancelled.append(token)),
        _refresh_pending="r", _replot_pending="p", _sens_rerun_pending="s",
    )
    widget = Widget()
    manager = FlowTabManagerBase.__new__(FlowTabManagerBase)
    manager.notebook = Notebook(widget)
    manager._apps = [object(), sub_app]

    manager._close_tab(1)

    assert manager.notebook.tabs() == ("main",)
    assert len(manager._apps) == 1
    assert widget.destroyed is True
    assert cancelled == ["r", "p", "s"]


def test_subgate_boundary_strips_tk_variables_before_analysis_state_deepcopy():
    interp = tk.Tcl()
    live_flag = tk.BooleanVar(master=interp, value=True)
    analysis = AnalysisState()
    app = SimpleNamespace(
        axis_aliases={},
        loaded_files={},
        _analysis_state_obj=lambda: analysis,
    )
    live_gate = {
        "id": 7,
        "type": "crosshair",
        "x_thresh_vars": [live_flag],
        "y_thresh_var": live_flag,
    }

    FlowTabManagerBase._load_filtered(
        app, {}, None, None,
        parent_gate=live_gate,
        parent_region="Q1",
        population_lineage=[],
    )

    assert analysis.parent_gate["id"] == 7
    assert analysis.parent_gate["x_thresh_vars"] == [True]
    assert analysis.parent_gate["y_thresh_var"] is True
    assert not isinstance(analysis.parent_gate["x_thresh_vars"][0], tk.Variable)


def test_gate_save_reports_filesystem_failure_instead_of_crashing(monkeypatch, tmp_path):
    dialogs = []
    host = SimpleNamespace(
        gates=[{"id": 1}],
        population_lineage=[],
        x_channel="X", y_channel="Y",
        status_var=Var(),
        _auto_stem=lambda: "sample",
        _analysis_state_obj=lambda: AnalysisState(x_channel="X", y_channel="Y"),
    )
    coordinator = ProjectDataLoadCoordinator(host)
    monkeypatch.setattr(load_module, "build_gate_session_payload", lambda *a, **k: {"gates": []})
    filedialog = SimpleNamespace(asksaveasfilename=lambda **kwargs: str(tmp_path))
    messagebox = SimpleNamespace(
        showwarning=lambda *a, **k: None,
        showinfo=lambda *a, **k: None,
        showerror=lambda title, message: dialogs.append((title, message)),
    )

    coordinator.save_gates(filedialog=filedialog, messagebox=messagebox)

    assert len(dialogs) == 1
    assert dialogs[0][0] == "Save Gates"
    assert "Could not write the gate file" in dialogs[0][1]
    assert "writable location" in dialogs[0][1]


def test_density_and_contour_kde_fall_back_for_degenerate_spans():
    import numpy as np
    from vflow.plotting.kde_payloads import (
        compute_contour_surface_payload,
        compute_density_render_payload,
    )

    x = np.full(50, 5.0)
    y = np.linspace(1.0, 10.0, 50)
    valid = np.ones(50, dtype=bool)
    density = compute_density_render_payload(x, y, x, y, valid)
    contour = compute_contour_surface_payload(
        x, y, valid, x_scale="linear", y_scale="linear", cofactor=5.0
    )
    assert density.action == "dot"
    assert contour.action == "dot"
