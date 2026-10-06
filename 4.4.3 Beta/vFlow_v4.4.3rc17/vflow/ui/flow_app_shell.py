"""Main FlowApp UI shell extracted during the v4.2 structural refactor.

This base owns theme handling, widget construction, matplotlib canvas creation, and
axes layout only. Scientific callbacks, gate editing, population semantics, state
transitions, statistics, exports, and data loading remain on the legacy-compatible
``FlowApp`` subclass.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from matplotlib.figure import Figure
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from vflow.config.constants import ALL_SCALES, REGION_COLORS
from vflow.config.styles import _apply_ttk_style
from vflow.config.themes import THEMES
from vflow.plotting.utils import set_spines_color as _set_spines_color


from vflow.workspace.ui import WorkspaceUIMixin
from vflow.ui.file_list import FileListPresentationMixin
from vflow.ui.gate_manager import GateManagerPresentationMixin
from vflow.ui.task_sidebar import TaskSidebarMixin, SECTION_TITLES, OPEN_SECTIONS


class FlowAppShellBase(TaskSidebarMixin, WorkspaceUIMixin, GateManagerPresentationMixin, FileListPresentationMixin):
    """Non-scientific main-window construction and presentation shell."""

    def toggle_theme(self):
        self._theme_name = 'light' if self._theme_name == 'dark' else 'dark'
        self.T = THEMES[self._theme_name]
        _apply_ttk_style(self.T)
        self._apply_theme_to_tk_widgets()
        if hasattr(self, '_workspace'): self._apply_interface_size()
        self.refresh_plot()
        # Recolour the overlay lock buttons to match the new theme.
        # _reposition_lock_buttons handles this when lock is active;
        # run it unconditionally so colours update even before next draw.
        if self._lock_btns:
            T = self.T
            _is_dark = T.get('plot_bg', '#ffffff') != '#ffffff'
            _btn_bg  = '#3a4255' if _is_dark else '#c8ccd4'
            _btn_fg  = '#ffffff' if _is_dark else '#1a1a1a'
            _btn_act = T.get('sel_bg', '#4a90d9')
            for b in self._lock_btns.values():
                try:
                    b._bg  = _btn_bg
                    b._fg  = _btn_fg
                    b._act = _btn_act
                    b.config(bg=_btn_bg, fg=_btn_fg)
                    b.bind('<Enter>', lambda e, w=b: w.config(bg=w._act, fg='white'))
                    b.bind('<Leave>', lambda e, w=b: w.config(bg=w._bg,  fg=w._fg))
                except Exception:
                    pass

    def _apply_theme_to_tk_widgets(self):
        T = self.T
        try:    self.root.configure(bg=T['sidebar_bg'])
        except Exception: pass
        for page in self._task_pages.values(): page['canvas'].configure(bg=T['sidebar_bg'])
        self._sidebar_outer_canvas.configure(bg=T['sidebar_bg'])
        self._sample_task_pane.configure(bg=T['header_bg'])
        self.right.configure(bg=T['plot_bg'])
        try:
            self._main_pane.configure(bg=T['header_bg'])
        except Exception:
            pass
        self._status_lbl.configure(bg=T['header_bg'], fg=T['fg_dim'])
        for w in self._scale_widgets:
            w.configure(bg=T['sidebar_bg'], fg=T['fg'],
                        troughcolor=T['trough'],
                        activebackground=T['sel_bg'])
        lbl = '☀  Light mode' if self._theme_name == 'dark' else '☾  Dark mode'
        self._sidebar_settings_menu.entryconfigure(0, label=lbl)

    def _build_ui(self):
        T = self.T
        C = self.container  # all top-level widgets pack here

        # Optional parent-gate banner for sub-gate tabs
        if self.parent_label:
            ttk.Label(C, text=f'  ↳ Sub-gate of:  {self.parent_label}',
                      style='Section.TLabel').pack(fill=tk.X, side=tk.TOP)

        # Resizable sidebar + plot area. A PanedWindow gives the vertical
        # divider native drag behaviour on macOS, Windows and Linux while
        # keeping the existing sidebar/plot widgets otherwise unchanged.
        self._main_pane = tk.PanedWindow(
            C, orient=tk.HORIZONTAL, bd=0, relief='flat',
            sashwidth=7, sashrelief='raised', sashcursor='sb_h_double_arrow',
            showhandle=False, opaqueresize=True, bg=T['header_bg'])
        self._main_pane.pack(fill=tk.BOTH, expand=True)

        side_outer = ttk.Frame(self._main_pane, style='TFrame', width=340)
        side_outer.pack_propagate(False)
        self._side_outer = side_outer

        self._build_adaptive_sidebar(side_outer)

        # Plot area
        self.right = tk.Frame(self._main_pane, bg=T['plot_bg'])
        self._main_pane.add(side_outer, minsize=285, width=340, stretch='never')
        self._main_pane.add(self.right, minsize=360, stretch='always')

        self._scale_widgets = []
        self._build_controls()
        self._build_plot()
        self._build_status_bar()
        # Finish construction before servicing deferred layout callbacks.
        # The normal Tk loop measures the completed controls and fonts.
        self._sidebar_restoring = False
        self._sample_pane_configured()

    def _section(self, text):
        parent = self._sidebar_section_parent(text)
        var = tk.BooleanVar(self.root, value=text in OPEN_SECTIONS)
        header = ttk.Button(parent, text=('▾ ' if var.get() else '▸ ') + SECTION_TITLES[text],
            command=lambda n=text: self._disclose_section(n), style='SidebarSection.TButton')
        header._vflow_section_name = text
        header.pack(fill='x', padx=8, pady=(6, 2))
        frame = ttk.Frame(parent, style='TFrame'); frame._section_header = header
        self._sections[text] = (var, frame)
        if var.get(): frame.pack(fill='x')
        self._control_parent = frame

    def _lbl(self, text, style='TLabel'):
        ttk.Label(getattr(self, '_control_parent', self.sidebar), text=text, style=style).pack(anchor='w', padx=8)

    def _btn(self, text, cmd, style='TButton'):
        b = ttk.Button(getattr(self, '_control_parent', self.sidebar), text=text, command=cmd, style=style)
        b.pack(fill=tk.X, padx=8, pady=2)
        return b

    def _scale_w(self, parent, **kw):
        T = self.T
        s = tk.Scale(parent, bg=T['sidebar_bg'], fg=T['fg'],
                     troughcolor=T['trough'], highlightthickness=0,
                     activebackground=T['sel_bg'], **kw)
        self._scale_widgets.append(s)
        return s

    def _build_controls(self):
        p = self.sidebar

        self._build_workspace_actions()

        # ── FILES ──
        self._section("FILES")
        p = getattr(self, "_control_parent", self.sidebar)
        file_btn_row = ttk.Frame(p, style='TFrame')
        file_btn_row.pack(fill=tk.X, padx=8, pady=(0, 2))
        ttk.Button(file_btn_row, text='+ Add Data Files…',
                   command=self.load_files,
                   style='Accent.TButton').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(file_btn_row, text='🗑 Clear All',
                   command=self.clear_all_files,
                   style='Gray.TButton').pack(side=tk.LEFT)
        self._btn("+ Load from Folder…", self.load_from_folder, 'DarkBlue.TButton')

        self.file_list_frame = ttk.Frame(p, style='TFrame')
        # Compatibility owner for data-loading/rebuild paths. The pinned tree
        # is the single loaded-sample list; BooleanVars remain authoritative.
        ttk.Label(p, text='Select samples in the pinned list for actions.',
                  style='Dim.TLabel', wraplength=280).pack(fill='x', padx=8)
        self._btn('Selected sample actions…', self._selected_sample_actions)
        self._btn('Find Missing Files…', self._workspace.find_missing)

        # ── EXCLUDED FILES ──
        self._section("EXCLUDED FILES")
        p = getattr(self, "_control_parent", self.sidebar)
        excl_btn_row = ttk.Frame(p, style='TFrame')
        excl_btn_row.pack(fill=tk.X, padx=8, pady=(0, 2))
        ttk.Button(excl_btn_row, text='💾 Save List',
                   command=self.save_excluded_list,
                   style='Gray.TButton').pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(excl_btn_row, text='📂 Load List',
                   command=self.load_excluded_list,
                   style='Gray.TButton').pack(side=tk.LEFT)
        self.excluded_list_frame = ttk.Frame(p, style='TFrame')
        self.excluded_list_frame.pack(fill=tk.X, padx=8)
        ttk.Label(self.excluded_list_frame,
                  text="(none)", style='Dim.TLabel').pack(anchor='w')

        # ── AXES ──
        self._section("AXES")
        p = getattr(self, "_control_parent", self.sidebar)
        axes = ttk.Frame(p); axes.pack(fill='x', padx=8)
        axes.columnconfigure(0, weight=1)
        self.x_var = tk.StringVar(); self.y_var = tk.StringVar()
        for column, label, variable, attr in ((0, 'X Axis:', self.x_var, 'x_menu'), (1, 'Y Axis:', self.y_var, 'y_menu')):
            cell = ttk.Frame(axes); cell.grid(row=column, column=0, sticky='ew')
            ttk.Label(cell, text=label).pack(anchor='w')
            menu = ttk.Combobox(cell, textvariable=variable, state='readonly', width=10, font='VFlowControl')
            menu.pack(fill='x', pady=(0, 4)); setattr(self, attr, menu)
            from vflow.ui.tooltips import tooltip
            tooltip(menu,menu.get)
        self._btn("Apply Axes", self.apply_axes, 'Green.TButton')
        self._btn("Channel / Axis Names…", self.open_axis_name_resolver,
                  'Gray.TButton')

        # ── SCALE ──
        self._section("SCALE")
        p = getattr(self, "_control_parent", self.sidebar)
        sf = ttk.Frame(p, style='TFrame')
        sf.pack(fill=tk.X, padx=8, pady=2)
        sf.columnconfigure((0, 1), weight=1, uniform='scales')
        for column, (lbl_text, attr) in enumerate([("X:", 'x_scale_var'), ("Y:", 'y_scale_var')]):
            cell = ttk.Frame(sf); cell.grid(row=0, column=column, sticky='ew', padx=(0, 4) if column == 0 else (4, 0))
            ttk.Label(cell, text=lbl_text, style='TLabel').pack(anchor='w')
            var = tk.StringVar(value='asinh')
            setattr(self, attr, var)
            ttk.Combobox(cell, textvariable=var, values=ALL_SCALES,
                         state='readonly', width=10, font='VFlowControl').pack(fill='x', pady=1)
        self.x_scale_var.trace_add('write', lambda *_: self._apply_scales())
        self.y_scale_var.trace_add('write', lambda *_: self._apply_scales())

        # ── DISPLAY ──
        self._section("DISPLAY")
        p = getattr(self, "_control_parent", self.sidebar)
        self._lbl("Plot Mode:")
        self.plot_type_var = tk.StringVar(value='Density')
        ttk.Combobox(p, textvariable=self.plot_type_var,
                     values=['Dot Plot', 'Density', 'Contour Plot'],
                     state='readonly', font='VFlowControl'
                     ).pack(fill=tk.X, padx=8, pady=(0, 3))
        self.plot_type_var.trace_add('write', lambda *_: self._plot_mode_controls_changed())

        sliders = ttk.Frame(p); sliders.pack(fill='x', padx=8)
        sliders.columnconfigure((0, 1), weight=1, uniform='appearance')
        self.dot_size_var = tk.IntVar(value=2)
        self.alpha_var = tk.DoubleVar(value=0.6)
        for column, label, variable, start, stop, step in ((0, 'Dot Size:', self.dot_size_var, 1, 12, 1), (1, 'Alpha:', self.alpha_var, .05, 1., .05)):
            cell = ttk.Frame(sliders); cell.grid(row=0, column=column, sticky='ew', padx=(0, 4) if column == 0 else (4, 0))
            ttk.Label(cell, text=label).pack(anchor='w')
            self._scale_w(cell, from_=start, to=stop, resolution=step, length=90,
                orient=tk.HORIZONTAL, variable=variable, command=lambda _: self.schedule_refresh()).pack(fill='x')

        contour = self._contour_controls = ttk.Frame(p)
        ttk.Label(contour, text='Contour Probability:').pack(anchor='w')
        self.prob_var = tk.StringVar(value='5%')
        ttk.Combobox(contour, textvariable=self.prob_var,
                     values=['2%', '5%', '10%', '20%'],
                     state='readonly', font='VFlowControl'
                     ).pack(fill=tk.X, pady=(0, 3))
        self.prob_var.trace_add('write', lambda *_: self.refresh_plot())

        checks = ttk.Frame(p); checks.pack(fill='x', padx=8)
        checks.columnconfigure((0, 1), weight=1, uniform='annotations')
        for i, (attr, text, default) in enumerate([
            ('show_marginals_var', 'Marginals', True),
            ('show_labels_var',    'Region % labels', True),
            ('show_legend_var',    'Legend', True),
            ('show_grid_var',      'Grid', True),
        ]):
            v = tk.BooleanVar(value=default)
            setattr(self, attr, v)
            ttk.Checkbutton(checks, text=text, variable=v,
                            command=self.refresh_plot,
                            style='TCheckbutton').grid(row=i//2, column=i%2, sticky='w')
        self._appearance_checks = checks

        self._section('PLOT LIMITS')
        p = self._control_parent
        self.fit_axes_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(p, text='Fit axes to data', variable=self.fit_axes_var,
                        command=self.refresh_plot).pack(anchor='w', padx=8)

        # ── Lock & adjust scale ───────────────────────────────────────────────
        # Mutually exclusive with "Fit axes to data": enabling lock captures the
        # current limits and disables auto-scaling; the overlay +/− buttons then
        # allow the user to nudge each axis end independently.
        self.lock_scale_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(p, text='🔒 Lock & adjust scale',
                        variable=self.lock_scale_var,
                        command=self._on_lock_scale_toggle,
                        style='TCheckbutton').pack(anchor='w', padx=8)

        self._section('TRANSFORM PARAMETERS')
        p = self._control_parent
        cf = ttk.Frame(p, style='TFrame')
        cf.pack(fill=tk.X, padx=8)
        ttk.Label(cf, text="Cofactor (asinh / legacy_logicle):",
                  style='Dim.TLabel').pack(anchor='w')
        self.cofactor_str = tk.StringVar(value='150')
        self.cofactor_str.trace_add('write', self._on_cofactor_change)
        self._cofactor_entry = ttk.Entry(
            cf, textvariable=self.cofactor_str, font='VFlowControl', width=10)
        self._cofactor_entry.pack(anchor='w', pady=(2, 0))
        self._cofactor_entry.bind('<FocusOut>', self._validate_cofactor_entry)
        self._cofactor_entry.bind('<Return>', self._validate_cofactor_entry)
        ttk.Label(
            cf,
            text=("logicle_gml2 = equation-based Gating-ML Logicle. "
                  "legacy_biexp / legacy_logicle preserve historical vFlow gates."),
            style='Dim.TLabel', wraplength=285, justify='left'
        ).pack(anchor='w', pady=(3, 0))
        ttk.Button(
            cf, text="Gating-ML Logicle parameters…",
            command=self._edit_logicle_params, style='Gray.TButton'
        ).pack(fill=tk.X, pady=(4, 0))

        self._section('FIGURE EXPORT')
        self._btn('Export Figure → PDF/PNG', self.export_figure, 'Blue2.TButton')

        # ── GATING ──
        self._section("GATING")
        p = getattr(self, "_control_parent", self.sidebar)

        # 'draw' mode: left-click draws new gates.
        # Right-click+drag ALWAYS reshapes handles (any mode).
        # 'off' mode: left-click does nothing; double-click opens sub-gate.
        self.gate_mode_var = tk.StringVar(value='none')
        self.gate_var      = tk.BooleanVar(value=False)   # True = draw mode

        draw_row = ttk.Frame(p, style='TFrame')
        draw_row.pack(fill=tk.X, padx=8, pady=(0, 2))
        ttk.Radiobutton(draw_row, text='○  Off  (sub-gate on dbl-click)',
                        variable=self.gate_mode_var, value='none',
                        command=self._on_gate_mode_change,
                        style='TRadiobutton').pack(anchor='w')
        ttk.Radiobutton(draw_row, text='✎  Draw  (left-drag to create)',
                        variable=self.gate_mode_var, value='draw',
                        command=self._on_gate_mode_change,
                        style='TRadiobutton').pack(anchor='w')
        ttk.Label(p, text='  Right-drag always reshapes handles',
                  style='Dim.TLabel').pack(anchor='w', padx=8, pady=(0, 2))

        # Gate type selector
        self._gt_frame = ttk.Frame(p, style='TFrame')
        self._gt_frame.pack(fill=tk.X, padx=16, pady=(2, 0))
        for _gval, _glbl in [('crosshair', '✛  Crosshair'),
                              ('rectangle', '▬  Rectangle'),
                              ('ellipse',   '⬭  Ellipse'),
                              ('polygon',   '⬠  Polygon')]:
            ttk.Radiobutton(self._gt_frame, text=_glbl,
                            variable=self.gate_type_var, value=_gval,
                            command=self._on_gate_type_change,
                            style='TRadiobutton').pack(anchor='w')
        self._gate_hint_var = tk.StringVar(value='Off — select Draw to create gates')
        ttk.Label(p, textvariable=self._gate_hint_var,
                  style='Dim.TLabel', wraplength=280).pack(anchor='w', padx=16, pady=(0, 2))

        # Polygon close button (shown only while drawing polygon)
        self._poly_close_btn = ttk.Button(
            p, text='✓  Close Polygon', command=self._poly_finish,
            style='Green.TButton')
        # packed/unpacked dynamically in _update_poly_close_btn()

        # Auto-gate sensitivity slider
        self._section("AUTO-GATE")
        p = getattr(self, "_control_parent", self.sidebar)
        ttk.Label(p, text='Calculate using:', style='TLabel').pack(anchor='w', padx=8)
        fitting = ttk.Combobox(p, textvariable=self.auto_gate_input_var,
            values=['Active samples (pooled)', 'Selected samples (workspace list)', 'Current sample'], state='readonly')
        fitting.pack(fill=tk.X, padx=8, pady=(2,4))
        fitting.bind('<<ComboboxSelected>>', lambda e: self._workspace.mark_dirty())
        ttk.Label(p, text='Fitting uses full source values; gate targets are chosen above.',
            style='Dim.TLabel', wraplength=285).pack(fill=tk.X, padx=8, pady=(0,4))
        sens_row = ttk.Frame(p, style='TFrame')
        sens_row.pack(fill=tk.X, padx=8, pady=(0, 4))
        ttk.Label(sens_row, text='Sensitivity:', style='TLabel').pack(side=tk.LEFT)
        self.auto_sensitivity_var = tk.IntVar(value=7)
        # BUG FIX (B18): label was hardcoded as '5', but auto_sensitivity_var
        # is initialised to 7.  The trace handler that syncs the label only
        # fires when the slider moves, so without this fix the label
        # disagrees with the actual slider position on startup.
        self._sens_val_lbl = ttk.Label(sens_row,
                                       text=str(self.auto_sensitivity_var.get()),
                                       style='TLabel', width=2)
        self._sens_val_lbl.pack(side=tk.RIGHT)
        sens_slider = ttk.Scale(sens_row, from_=1, to=10,
                                variable=self.auto_sensitivity_var,
                                orient='horizontal', length=130)
        sens_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        def _on_sens(*_):
            v = self.auto_sensitivity_var.get()
            self._sens_val_lbl.config(text=str(v))
            # Update tooltip
            hints = {
                (1, 3):  'Conservative: only obvious population gaps',
                (4, 6):  'Balanced: standard sensitivity (default)',
                (7, 10): 'Sensitive: detects subtle separations',
            }
            for (lo, hi), msg in hints.items():
                if lo <= v <= hi:
                    self._gate_hint_var.set(f'Auto-gate — {msg}')
                    break
            # Live re-run: debounce so we don't fire on every slider tick
            if self._sens_rerun_pending:
                try: self.root.after_cancel(self._sens_rerun_pending)
                except Exception: pass
            if self._last_auto_gate_fn is not None:
                self._sens_rerun_pending = self.root.after(
                    350, self._rerun_last_auto_gate)
        self.auto_sensitivity_var.trace_add('write', _on_sens)
        ttk.Label(p, text=(
            'KDE: valley support | Otsu: minimum class size\n'
            'Clusters: minimum population size'),
            style='Dim.TLabel').pack(anchor='w', padx=8, pady=(0, 2))

        # ── Per-axis GMM population count (for GMM Multi method) ─────────────
        gmm_row = self._gmm_controls = ttk.Frame(p, style='TFrame')
        gmm_row.pack(fill=tk.X, padx=8, pady=(0, 6))
        ttk.Label(gmm_row, text='GMM populations X:', style='Dim.TLabel'
                  ).pack(side=tk.LEFT)
        self.gmm_max_x_var = tk.IntVar(value=3)
        ttk.Spinbox(gmm_row, from_=1, to=8, width=3, font='VFlowControl',
                    textvariable=self.gmm_max_x_var
                    ).pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(gmm_row, text='Y:', style='Dim.TLabel'
                  ).pack(side=tk.LEFT)
        self.gmm_max_y_var = tk.IntVar(value=3)
        ttk.Spinbox(gmm_row, from_=1, to=8, width=3, font='VFlowControl',
                    textvariable=self.gmm_max_y_var
                    ).pack(side=tk.LEFT, padx=(2, 0))

        # All four original callbacks remain available through the method picker.
        from vflow.ui.task_sidebar import AUTO_METHODS
        from vflow.ui.tooltips import tooltip
        method = ttk.Frame(p); method.pack(fill='x', padx=8, pady=(0, 4), before=gmm_row)
        ttk.Label(method, text='Method:').pack(anchor='w')
        self.auto_gate_method_var = tk.StringVar(value='GMM Multi')
        self._auto_method_menu = ttk.Combobox(method, textvariable=self.auto_gate_method_var,
            values=list(AUTO_METHODS), state='readonly')
        self._auto_method_menu.pack(fill='x')
        self._auto_method_menu.bind('<<ComboboxSelected>>', self._auto_method_changed)
        tooltip(self._auto_method_menu, 'GMM: supported mixture crossings. KDE: density valleys. Otsu: between-class split. Clusters: full-population polygons.')
        self._auto_calculate_button = self._btn('Calculate gates', self._run_selected_auto_gate, 'Accent.TButton')
        clear = ttk.Frame(self._task_pages['Gates']['content']); clear.pack(fill='x', padx=8, pady=3)
        ttk.Button(clear, text='Clear selected gate', command=self.clear_gate, style='Gray.TButton').pack(side='left', fill='x', expand=True)
        ttk.Button(clear, text='Clear all gates', command=self.clear_all_gates, style='Gray.TButton').pack(side='left', fill='x', expand=True, padx=(4, 0))

        # ── GATE MANAGER ──
        self._section("GATE MANAGER")
        p = getattr(self, "_control_parent", self.sidebar)
        add_row = ttk.Frame(p, style='TFrame')
        add_row.pack(fill=tk.X, padx=8, pady=(0, 4))
        ttk.Button(add_row, text='+ Add Gate', command=self._add_gate,
                   style='Accent.TButton').pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(p, text='Apply to entire workspace…', command=lambda:self._workspace.gate_action(self,'workspace',self._sel_gate_id),
                   style='Gray.TButton').pack(fill=tk.X,padx=8,pady=(0,4))

        # Gate list (rebuilt by _rebuild_gate_manager)
        self.gate_manager_frame = ttk.Frame(p, style='TFrame')
        self.gate_manager_frame.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(self.gate_manager_frame, text="(no gates)", style='Dim.TLabel').pack(anchor='w')

        # ── THRESHOLDS / GATE INFO ──
        self._section("GATE INFO")
        p = getattr(self, "_control_parent", self.sidebar)
        self.thresh_panel = ttk.Frame(p, style='TFrame')
        self.thresh_panel.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(self.thresh_panel, text="(no gate selected)",
                  style='Dim.TLabel').pack(anchor='w')

        # ── STATISTICS ──
        self._section("STATISTICS")
        p = getattr(self, "_control_parent", self.sidebar)
        sm_row = ttk.Frame(p, style='TFrame')
        sm_row.pack(fill=tk.X, padx=8, pady=(0, 4))
        for val, lbl in [('perfile', 'Per file'), ('merged', 'Merged')]:
            ttk.Radiobutton(sm_row, text=lbl, variable=self.stats_mode_var,
                            value=val, command=self._update_stats_display,
                            style='TRadiobutton').pack(side=tk.LEFT, padx=4)

        table = ttk.Frame(p); table.pack(fill='x', padx=8, pady=(0, 4))
        table.columnconfigure(0, weight=1)
        self.stats_tree = ttk.Treeview(
            table, columns=('count', 'pct'), show='tree headings', height=5)
        self.stats_tree.heading('#0',    text='Region / File', anchor='w')
        self.stats_tree.heading('count', text='Count',         anchor='e')
        self.stats_tree.heading('pct',   text='%',             anchor='e')
        self.stats_tree.column('#0',    width=140, stretch=True)
        self.stats_tree.column('count', width=62,  anchor='e')
        self.stats_tree.column('pct',   width=50,  anchor='e')
        self.stats_tree.grid(row=0, column=0, sticky='ew')
        vertical = ttk.Scrollbar(table, orient='vertical', command=self.stats_tree.yview)
        horizontal = ttk.Scrollbar(table, orient='horizontal', command=self.stats_tree.xview)
        self.stats_tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        vertical.grid(row=0, column=1, sticky='ns'); horizontal.grid(row=1, column=0, sticky='ew')
        # Configure region-color tags once here — no need to repeat on every refresh
        for _i, _c in enumerate(REGION_COLORS):
            self.stats_tree.tag_configure(f'rc{_i}', foreground=_c)

        self._btn('Export Stats → CSV', self.export_stats, 'Green.TButton')

        self._section('STATISTICAL AUDITS')
        p = self._control_parent
        from vflow.ui.statistical_audit_dialog import StatisticalAuditDialog, AuditListDialog
        auditbar = ttk.Frame(p); auditbar.pack(fill='x', padx=8, pady=2)
        ttk.Button(auditbar, text='Statistical Audit…', command=lambda: StatisticalAuditDialog(self._workspace, self)).pack(side='left', expand=True, fill='x')
        ttk.Button(auditbar, text='Saved audits…', command=lambda: AuditListDialog(self._workspace)).pack(side='left')
        ttk.Label(p, text='Audit samples within the same condition and population.', style='Dim.TLabel', wraplength=280).pack(fill='x', padx=8)

        self._section('GATE SESSIONS')
        self._btn('Save Gates → JSON', self.save_gates, 'Blue2.TButton')
        self._btn('Load Gates ← JSON', self.load_gates, 'Blue2.TButton')
        self._section('EXPORT')
        self._btn('Export Gated Data → CSV', self.export_gated_data, 'Green.TButton')
        self._btn('Batch Stats → Folder', self.batch_export_stats, 'Teal.TButton')

        # ── VECTOR ANALYSIS ──
        self._section("VECTOR ANALYSIS")
        p = getattr(self, "_control_parent", self.sidebar)
        ttk.Label(
            p,
            text="  Requires X/Y centroid columns for two channels in the data.",
            style='Dim.TLabel', justify='left'
        ).pack(anchor='w', padx=8, pady=(0, 4))
        self._btn("🧭 Polar / Vector Analysis…",
                  self.open_polar_analysis, 'Purple.TButton')

        # ── BATCH PLOTS ──
        self._section("BATCH PLOTS")
        p = getattr(self, "_control_parent", self.sidebar)
        ttk.Label(
            p,
            text="  Violin/box/points distributions + stacked gate-population % per sample. Works from individual files or a concatenated CSV.",
            style='Dim.TLabel', justify='left', wraplength=240
        ).pack(anchor='w', padx=8, pady=(0, 4))
        self._btn("📊 Batch Plots…",
                  self.open_batch_plots, 'Cyan.TButton')

        ttk.Frame(p, style='TFrame', height=20).pack()

    def _build_plot(self):
        T = self.T
        # Use Figure() directly — plt.figure() would open a second window
        self.fig = Figure(figsize=(9.5, 7.5), facecolor=T['fig_bg'])
        self.ax_top = self.ax_right = None
        self._setup_axes()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.right)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        tf = tk.Frame(self.right, bg=T['sidebar_bg'])
        self._toolbar_frame = tf
        tf.pack(side=tk.BOTTOM, fill=tk.X, before=self.canvas.get_tk_widget())
        tb = NavigationToolbar2Tk(self.canvas, tf)
        tb.config(background=T['sidebar_bg'])
        tb.update()
        self.canvas.mpl_connect('button_press_event',   self._on_click)
        self.canvas.mpl_connect('motion_notify_event',  self._on_motion)
        self.canvas.mpl_connect('button_release_event', self._on_release)

        # Create overlay lock-scale buttons (hidden until lock is enabled).
        # Must be called AFTER the canvas widget is packed so winfo_* works.
        self._create_lock_buttons()
        # Reposition lock buttons after every canvas redraw (handles resize,
        # marginal toggle, DPI changes, etc.).
        self.canvas.mpl_connect('draw_event', self._reposition_lock_buttons)
        # FIX Bug 1 (belt-and-suspenders): rebuild handle pixel cache after
        # every full canvas render.  At draw_event time all matplotlib
        # transforms are definitively committed, so the pixel coords are
        # guaranteed to match the displayed handle positions regardless of
        # axis scale (asinh / biexp / logicle).  This is critical for loaded
        # gates whose cache is otherwise built before _set_axis_scale() runs.
        self.canvas.mpl_connect('draw_event', self._rebuild_handle_px_cache)

    def _build_status_bar(self):
        T = self.T
        self.status_var = tk.StringVar(value="No data loaded")
        self._status_lbl = tk.Label(
            self.right, textvariable=self.status_var,
            bg=T['header_bg'], fg=T['fg_dim'],
            anchor='w', font='VFlowControl', padx=6)
        self._status_lbl.pack(side=tk.BOTTOM, fill=tk.X, before=self._toolbar_frame)

    def _setup_axes(self):
        T = self.T
        # Matplotlib may emit non-positive-limit warnings while destroying
        # shared log-scaled axes (for example when toggling marginals after a
        # log plot).  Normalize old axes before Figure.clear() so layout
        # rebuilds cannot inherit or warn on an incompatible transform.
        for old_ax in tuple(self.fig.axes):
            try:
                old_ax.set_xscale('linear')
            except (AttributeError, TypeError, ValueError):
                pass
            try:
                old_ax.set_yscale('linear')
            except (AttributeError, TypeError, ValueError):
                pass
        self.fig.clear()
        self.fig.patch.set_facecolor(T['fig_bg'])
        self._preview_artists = []
        spine_c = T['spine']

        if self.show_marginals_var.get():
            gs = gridspec.GridSpec(
                2, 2, figure=self.fig,
                width_ratios=[5, 1], height_ratios=[1, 5],
                hspace=0.04, wspace=0.04,
                left=0.11, right=0.97, top=0.90, bottom=0.09)
            self.ax       = self.fig.add_subplot(gs[1, 0])
            self.ax_top   = self.fig.add_subplot(gs[0, 0], sharex=self.ax)
            self.ax_right = self.fig.add_subplot(gs[1, 1], sharey=self.ax)
            for a in (self.ax_top, self.ax_right):
                a.set_facecolor(T['ax_bg'])
                _set_spines_color(a, spine_c)
                a.tick_params(colors=T['fg'], labelsize=6)
            # Replace plt.setp() with direct tick-label control
            for lbl in self.ax_top.get_xticklabels():   lbl.set_visible(False)
            for lbl in self.ax_right.get_yticklabels(): lbl.set_visible(False)
            self.ax_top.set_ylabel('Count',  color=T['fg'], fontsize=7)
            self.ax_right.set_xlabel('Count', color=T['fg'], fontsize=7)
        else:
            self.fig.subplots_adjust(
                left=0.11, right=0.97, top=0.90, bottom=0.09)
            self.ax       = self.fig.add_subplot(111)
            self.ax_top   = None
            self.ax_right = None

        self.ax.set_facecolor(T['ax_bg'])
        _set_spines_color(self.ax, spine_c)
        self.ax.tick_params(colors=T['fg'], labelsize=8)
