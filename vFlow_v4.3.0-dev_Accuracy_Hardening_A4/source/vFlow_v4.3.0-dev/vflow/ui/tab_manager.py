"""Notebook/tab lifecycle implementation for vFlow.

``FlowTabManagerBase`` is the first physically extracted major UI class in the
v4.2 refactor.  It deliberately resolves ``FlowApp`` only when a manager is
constructed, preserving the lightweight/lazy import behavior of the public
``FlowTabManager`` proxy symbol.
"""

from __future__ import annotations


class FlowTabManagerBase:
    """Own a ttk.Notebook containing independent FlowApp instances."""

    flow_app_class = None
    app_version = None

    def _flow_app_type(self):
        cls = self.flow_app_class
        if cls is not None:
            return cls
        from vflow.ui.app import FlowApp
        return FlowApp

    def __init__(self, root):
        import tkinter as tk
        from tkinter import ttk

        from vflow import __version__
        from vflow.config.styles import _apply_ttk_style
        from vflow.config.themes import THEMES

        self.root = root
        root.title(f"vFlow {self.app_version or __version__}")
        root.geometry("1500x960")

        self._theme_name = 'dark'
        self.T = THEMES['dark']
        T = self.T
        _apply_ttk_style(T)
        root.configure(bg=T['sidebar_bg'])

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self._apps: list = []
        self._new_tab(title=' ✦ Main ', parent_label=None,
                      filtered_data=None, default_x=None, default_y=None)
        self.notebook.bind('<Button-3>', self._on_tab_rclick)

    def _new_tab(self, title, parent_label, filtered_data,
                 default_x, default_y,
                 parent_gate=None, parent_region=None, population_lineage=None,
                 excluded_files=None, axis_aliases=None):
        import tkinter as tk
        from tkinter import ttk

        frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(frame, text=title)

        if parent_label is not None:
            T = self.T
            hdr = tk.Frame(frame, bg=T['header_bg'], height=24)
            hdr.pack(fill=tk.X, side=tk.TOP)
            hdr.pack_propagate(False)

            def _close_this():
                idx = self.notebook.index(frame)
                self._close_tab(idx)

            tk.Label(hdr, text=f'  ↳ {parent_label}',
                     bg=T['header_bg'], fg=T['fg'],
                     font=('Arial', 8)).pack(side=tk.LEFT, padx=4)
            close_btn = tk.Button(
                hdr, text=' ✕ ', command=_close_this,
                bg=T['header_bg'], fg=T['fg_dim'],
                activebackground='#c33', activeforeground='white',
                relief='flat', font=('Arial', 9, 'bold'), bd=0, padx=4)
            close_btn.pack(side=tk.RIGHT, padx=4)
            inner = ttk.Frame(frame, style='TFrame')
            inner.pack(fill=tk.BOTH, expand=True)
        else:
            inner = frame

        app = self._flow_app_type()(
            self.root, container=inner,
            parent_label=parent_label, manager=self)
        if filtered_data:
            self._load_filtered(
                app, filtered_data, default_x, default_y,
                parent_gate=parent_gate,
                parent_region=parent_region,
                population_lineage=population_lineage,
                excluded_files=excluded_files or {},
                axis_aliases=axis_aliases or {})
        self._apps.append(app)
        self.notebook.select(frame)
        return app

    @staticmethod
    def _load_filtered(app, filtered_data, default_x, default_y,
                       parent_gate=None, parent_region=None, population_lineage=None,
                       excluded_files=None, axis_aliases=None):
        """Pre-load one child population with frozen v4.1.11 tab semantics."""
        from vflow.config.constants import FILE_COLORS, _N_FILE_COLORS

        app._analysis_state_obj().set_population_context(
            parent_gate=parent_gate,
            parent_region=parent_region,
            population_lineage=population_lineage,
        )

        # Child tabs inherit the exact session-scoped nomenclature map so raw
        # Batch Stats rereads use the same labels as their parent analysis.
        app.axis_aliases = dict(axis_aliases or {})

        if excluded_files:
            app._dataset_state_obj().inherit_excluded_files(excluded_files)
            app._rebuild_excluded_list()

        for path, df in filtered_data.items():
            if path in app.loaded_files:
                continue
            cidx = len(app.loaded_files)
            app.file_colors[path] = FILE_COLORS[cidx % _N_FILE_COLORS]
            try:
                # Scientific/behavioral invariant: UI registration succeeds
                # before the DataFrame becomes visible in loaded_files.
                app._add_file_row(path)
            except Exception:
                app.file_colors.pop(path, None)
                app.file_vars.pop(path, None)
                raise
            app.loaded_files[path] = df
            app._data_generation += 1

        if not app.loaded_files:
            return
        sample = next(iter(app.loaded_files.values()))
        cols = list(sample.columns)
        app.x_menu['values'] = cols
        app.y_menu['values'] = cols

        if default_x and default_x in cols:
            app.x_var.set(default_x); app.x_channel = default_x
        elif cols:
            app.x_var.set(cols[0]); app.x_channel = cols[0]

        if default_y and default_y in cols:
            app.y_var.set(default_y); app.y_channel = default_y
        elif len(cols) > 1:
            app.y_var.set(cols[1]); app.y_channel = cols[1]

        if not app.lock_scale_var.get():
            app.fit_axes_var.set(True)

        app.refresh_plot()

    def open_subgate_tab(self, label: str, filtered_data: dict,
                         parent_x: str, parent_y: str, total_cells: int,
                         parent_gate: dict = None, parent_region: str = None,
                         population_lineage: list = None,
                         excluded_files: dict = None,
                         axis_aliases: dict = None):
        """Called by a FlowApp when the user double-clicks a gated region."""
        short = label[:22]
        tab_title = f' ↳ {short}  ({total_cells:,}) '
        self._new_tab(
            title=tab_title, parent_label=label,
            filtered_data=filtered_data,
            default_x=parent_x, default_y=parent_y,
            parent_gate=parent_gate, parent_region=parent_region,
            population_lineage=population_lineage or [],
            excluded_files=excluded_files or {},
            axis_aliases=axis_aliases or {})

    def _on_tab_rclick(self, event):
        import tkinter as tk

        try:
            idx = self.notebook.index(f'@{event.x},{event.y}')
        except tk.TclError:
            return
        if idx == 0:
            return
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(
            label='✕  Close tab', command=lambda i=idx: self._close_tab(i))
        menu.tk_popup(event.x_root, event.y_root)

    def _close_tab(self, idx: int):
        """Close sub-gate tab by notebook index and cancel pending callbacks."""
        tabs = self.notebook.tabs()
        if idx <= 0 or idx >= len(tabs):
            return
        if 0 < idx < len(self._apps):
            sub_app = self._apps[idx]
            for attr in ('_refresh_pending', '_replot_pending',
                         '_sens_rerun_pending'):
                pending = getattr(sub_app, attr, None)
                if pending:
                    try:
                        sub_app.root.after_cancel(pending)
                    except Exception:
                        pass
                    setattr(sub_app, attr, None)
            self._apps.pop(idx)
        self.notebook.forget(tabs[idx])


def __getattr__(name: str):
    # Preserve the existing public lazy-proxy contract.  The legacy module now
    # defines FlowTabManager as a thin subclass of FlowTabManagerBase.
    if name == "FlowTabManager":
        from vflow.legacy.vflow_legacy import FlowTabManager
        return FlowTabManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["FlowTabManager", "FlowTabManagerBase"]
