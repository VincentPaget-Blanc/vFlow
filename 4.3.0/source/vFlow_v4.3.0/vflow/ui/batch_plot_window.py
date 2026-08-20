"""Batch Plot UI/lifecycle implementation for vFlow.

The public compatibility ``BatchPlotWindow`` resolves lazily through the packaged
application module. ``BatchPlotWindowBase`` owns UI construction, lifecycle, sample
preparation, rendering, and export helpers; scientifically sensitive compatibility
methods remain on the packaged subclass where required.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import matplotlib.lines as mlines
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from vflow.config.constants import (
    FILE_COLORS, REGION_COLORS, _N_FILE_COLORS, _N_REGION_COLORS,
)
from vflow.core.gate_stats import region_percentages_with_total
from vflow.core.sample_labels import make_sample_label, shorten_common_prefix_labels
from vflow.plotting.utils import set_spines_color as _set_spines_color
from vflow.services.batch_plot_export import (
    build_batch_plot_stats_row, distribution_summary, format_display_number,
    short_display_label,
)
from vflow.services.batch_plot_samples import (
    build_batch_plot_samples, common_numeric_columns, first_distance_column,
    first_intensity_column, has_source_file_samples, preferred_distribution_column,
)
from vflow.services.figure_export import save_figure
from vflow.services.population_evaluation import selected_population_mask_for_dataframe

def _set_rotated_xlabels(ax, labels: list, fontsize: int = 7) -> None:
    """Apply the frozen v4.1.11 45-degree categorical x-label layout."""
    ax.set_xticklabels(labels, rotation=45, ha='right',
                       fontsize=fontsize, rotation_mode='anchor')

class BatchPlotWindowBase:
    """
    Batch Plots window — reproduces the "Batch Export Stats — Folder Mode"
    figure directly inside the application, without writing any files.

    Left panel  : Violin (or box) plot — one shape per sample, showing the
                  full distribution of a chosen numeric column (intensity,
                  distance, etc.).  White dot = median, thick bar = IQR,
                  thin whiskers = 5th–95th percentile.

    Right panel : 100 % stacked bar chart — one bar per sample, showing
                  the gate population percentages (Ch1+Ch2+, Ch1-Ch2+, …)
                  for the currently applied FlowApp gate.

    Sample identity
    ───────────────
    The window auto-detects which mode it is in:

    • Concatenated-file mode
        If ANY loaded file contains a "Source_File" column, each unique value
        in that column becomes one sample (= the original per-file split
        produced by the Folder-dialog "Save & Load Concatenate" action).
        A short display name is derived from the Source_File stem using
        _make_sample_label().

    • Individual-files mode
        Otherwise each loaded+checked file is one sample (the same colour
        as in the scatter view).

    Gate filtering
    ──────────────
    The gate dropdown lists every applied FlowApp gate.  Selecting a gate
    computes per-sample population % exactly like batch_export_stats does
    internally, using _gate_mask_for().  "All cells" skips the stacked bar
    (no gate regions to show) and only renders the violin panel.

    UI layout mirrors PolarAnalysisWindow / BatchPlotWindow:
      scrollable sidebar (left) + matplotlib canvas (right).
    """

    # ── palette of up to 16 distinct sample colours ───────────────────────────
    _SAMPLE_COLORS = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
        '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
        '#c49c94',
    ]

    def __init__(self, parent_root, T: dict, app: 'FlowApp'):
        super().__init__(parent_root)
        self.T   = T
        self.app = app
        self.title("Batch Plots")
        self.geometry("1350x820")
        self.configure(bg=T['sidebar_bg'])
        self.resizable(True, True)

        # ── state ─────────────────────────────────────────────────────────
        self._gate_var        = tk.StringVar(value='All cells')
        self._region_var      = tk.StringVar(value='All regions')
        self._dist_col_var    = tk.StringVar()
        self._plot_kind_var   = tk.StringVar(value='violin')  # violin | box
        self._show_points_var = tk.BooleanVar(value=False)
        self._show_legend_var = tk.BooleanVar(value=True)
        self._label_bars_var  = tk.BooleanVar(value=True)
        self._sample_order_var = tk.StringVar(value='auto')   # auto | alpha

        # per-file visibility (individual-files mode only)
        self._file_vars: dict = {}

        # cache: {sample_label: (values_array, color)}
        self._dist_cache: dict = {}
        # cache: {sample_label: {region_name: pct}}
        self._pop_cache:  dict = {}
        # ordered sample label list
        self._sample_labels: list = []
        self._replot_pending: str = None  # after() id for debounced replot

        self._build_ui()
        self._build_file_list()
        self._populate_dropdowns()
        self._initial_compute_pending = self.after(180, self._do_initial_compute)
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    def _do_initial_compute(self):
        self._initial_compute_pending = None
        if self.winfo_exists():
            self._compute_and_plot()

    def _on_close(self):
        """Cancel delayed work before destroying the Batch Plot window."""
        for attr in ('_initial_compute_pending', '_replot_pending'):
            pending = getattr(self, attr, None)
            if pending:
                try:
                    self.after_cancel(pending)
                except tk.TclError:
                    pass
                setattr(self, attr, None)
        self.destroy()

    def _schedule_replot(self, delay_ms: int = 300):
        """Debounced replot — cancels any pending call and re-schedules."""
        if self._replot_pending:
            try:
                self.after_cancel(self._replot_pending)
            except Exception:
                pass
        self._replot_pending = self.after(delay_ms, self._do_replot)

    def _do_replot(self):
        self._replot_pending = None
        self._compute_and_plot()

    def _zoom(self, dx: float, dy: float):
        """Adjust horizontal or vertical zoom and re-render."""
        if dx:
            self._zoom_x.set(max(0.25, min(4.0, self._zoom_x.get() + dx)))
        if dy:
            self._zoom_y.set(max(0.25, min(4.0, self._zoom_y.get() + dy)))
        if self._sample_labels:
            self._render_figure()

    def _zoom_reset(self):
        self._zoom_x.set(1.0)
        self._zoom_y.set(1.0)
        if self._sample_labels:
            self._render_figure()

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _make_sample_label(source_file_value: str) -> str:
        """
        Derive a short, readable sample name from a Source_File value.

        Strips directory path, extension, and common instrument/pipeline
        suffixes so the label carries only the biologically meaningful part.
        """
        return make_sample_label(source_file_value)

    def _shorten_labels(self, raw_labels: list) -> list:
        """
        Strip the longest common underscore-delimited prefix so labels are
        as short as possible while still being unique.  No newlines, no
        truncation — staggered rendering handles visual separation.
        """
        return shorten_common_prefix_labels(raw_labels)

    def _is_concat_mode(self) -> bool:
        """True if any active file has a Source_File column."""
        active_paths = [p for p, v in self._file_vars.items() if v.get()]
        return has_source_file_samples(self.app.loaded_files, active_paths)

    def _get_samples(self) -> 'list[tuple[str, pd.DataFrame, str]]':
        """
        Return [(display_label, sub_df, color), ...] in current sort order.

        In concat mode: sub_df is the rows for that Source_File value.
        In file mode:   sub_df is the full per-file DataFrame.
        """
        active_paths = [p for p, v in self._file_vars.items() if v.get()]
        return build_batch_plot_samples(
            loaded_files=self.app.loaded_files,
            active_paths=active_paths,
            file_colors=self.app.file_colors,
            sample_colors=self._SAMPLE_COLORS,
            sample_order=self._sample_order_var.get(),
        )

    def _get_population_mask(self, df: pd.DataFrame) -> np.ndarray:
        import pandas as pd
        """
        Boolean row-mask for the selected gate + region.
        Fresh computation — same pattern as PolarAnalysisWindow.
        """
        n    = len(df)
        name = self._gate_var.get()
        if name == 'All cells':
            return np.ones(n, bool)
        gate = self.app._gate_from_selector(name)
        mask = selected_population_mask_for_dataframe(
            df, gate, region_name=self._region_var.get(),
            analysis_state=self.app._analysis_state_obj())
        if mask is None:
            return None
        return mask

    def _get_region_pcts_and_n(self, df: pd.DataFrame) -> 'dict[str, tuple]':
        import pandas as pd
        """
        Return {region_name: (pct, n_total)} for the selected gate on one
        sample's DataFrame.  n_total is the total cell count for that sample
        and is needed to compute the per-sample binomial SEM.
        Returns {} if no gate is selected or gate cannot be applied.
        """
        name = self._gate_var.get()
        if name == 'All cells':
            return {}
        gate = self.app._gate_from_selector(name)
        if gate is None or not self.app._gate_context_matches(gate):
            return {}
        xch = self.app.x_channel
        ych = self.app.y_channel
        if (not xch or not ych
                or xch not in df.columns or ych not in df.columns):
            return {}
        xa = df[xch].to_numpy(dtype=float, copy=False)
        ya = df[ych].to_numpy(dtype=float, copy=False)
        _, _, valid_xy = self.app._transform_xy(xa, ya)
        total = int(valid_xy.sum())
        if total == 0:
            return {}
        try:
            regions, _ = self.app._gate_mask_for(gate, xa, ya)
        except Exception:
            return {}
        return region_percentages_with_total(regions, total)

    def _get_region_pcts(self, df: pd.DataFrame) -> 'dict[str, float]':
        import pandas as pd
        """
        Return {region_name: pct} — convenience wrapper around
        _get_region_pcts_and_n that drops the cell-count component.
        """
        return {rname: pct
                for rname, (pct, _n) in self._get_region_pcts_and_n(df).items()}

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        T = self.T

        # scrollable sidebar
        sb_outer = tk.Frame(self, bg=T['sidebar_bg'], width=270)
        sb_outer.pack(side=tk.LEFT, fill=tk.Y)
        sb_outer.pack_propagate(False)
        sv = ttk.Scrollbar(sb_outer, orient='vertical')
        sv.pack(side=tk.RIGHT, fill=tk.Y)
        self._sb_canvas = tk.Canvas(sb_outer, bg=T['sidebar_bg'],
                                    highlightthickness=0,
                                    yscrollcommand=sv.set)
        self._sb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sv.config(command=self._sb_canvas.yview)
        self._sb = ttk.Frame(self._sb_canvas, style='TFrame')
        self._sb_canvas.create_window((0, 0), window=self._sb,
                                       anchor='nw', width=254)
        self._sb.bind('<Configure>',
            lambda e: self._sb_canvas.configure(
                scrollregion=self._sb_canvas.bbox('all')))
        def _scroll(evt):
            self._sb_canvas.yview_scroll(int(-1*(evt.delta/120)), 'units')
        self._sb_canvas.bind('<MouseWheel>', _scroll)
        self._sb.bind('<MouseWheel>', _scroll)

        p = self._sb

        def _sec(txt):
            ttk.Label(p, text=f'  {txt}', style='Section.TLabel',
                      anchor='w').pack(fill=tk.X, pady=(10, 2))

        def _lbl(txt):
            ttk.Label(p, text=txt, style='TLabel').pack(anchor='w', padx=8)

        def _btn(txt, cmd, style='TButton'):
            b = ttk.Button(p, text=txt, command=cmd, style=style)
            b.pack(fill=tk.X, padx=8, pady=2)
            return b

        def _combo(var, vals, width=22):
            cb = ttk.Combobox(p, textvariable=var, values=vals,
                              state='readonly', font=('Arial', 8), width=width)
            cb.pack(fill=tk.X, padx=8, pady=(0, 3))
            return cb

        # ── GATE / POPULATION ─────────────────────────────────────────────
        _sec("POPULATION")
        _lbl("Gate (for population % bar):")
        self._gate_combo = _combo(self._gate_var, ['All cells'])
        self._gate_combo.bind('<<ComboboxSelected>>', self._on_gate_changed)
        _lbl("Region filter (optional):")
        self._region_combo = _combo(self._region_var, ['All regions'])
        self._region_combo.bind('<<ComboboxSelected>>',
                                lambda _e: self._schedule_replot())
        ttk.Label(p,
                  text="  Region filter applies to the violin/box data only.",
                  style='Dim.TLabel', wraplength=230
                  ).pack(anchor='w', padx=8, pady=(0, 4))

        # ── FILES ─────────────────────────────────────────────────────────
        _sec("FILES")
        self._file_list_frame = ttk.Frame(p, style='TFrame')
        self._file_list_frame.pack(fill=tk.X, padx=8, pady=(0, 4))
        ttk.Label(p,
                  text="  If a file has a Source_File column, samples are split from it automatically.",
                  style='Dim.TLabel', wraplength=230
                  ).pack(anchor='w', padx=8, pady=(0, 4))

        # ── DISTRIBUTION COLUMN ───────────────────────────────────────────
        _sec("DISTRIBUTION COLUMN")
        _lbl("Column for violin / box:")
        self._dist_combo = _combo(self._dist_col_var, [])
        self._dist_combo.bind('<<ComboboxSelected>>',
                              lambda _e: self._schedule_replot())
        row_auto = ttk.Frame(p, style='TFrame')
        row_auto.pack(fill=tk.X, padx=8, pady=(0, 4))
        ttk.Button(row_auto, text='Auto: Intensity',
                   command=self._auto_intensity,
                   style='Gray.TButton').pack(side=tk.LEFT, padx=(0,3),
                                              fill=tk.X, expand=True)
        ttk.Button(row_auto, text='Auto: Distance',
                   command=self._auto_distance,
                   style='Gray.TButton').pack(side=tk.LEFT,
                                              fill=tk.X, expand=True)

        # ── DISPLAY ───────────────────────────────────────────────────────
        _sec("DISPLAY")
        _lbl("Distribution style:")
        kind_cb = _combo(self._plot_kind_var, ['violin', 'box', 'points only'])
        kind_cb.bind('<<ComboboxSelected>>', lambda _e: self._schedule_replot())
        _lbl("Sample order:")
        order_cb = _combo(self._sample_order_var, ['auto', 'alpha'])
        order_cb.bind('<<ComboboxSelected>>', lambda _e: self._schedule_replot())
        for var, txt in [
            (self._show_points_var, 'Overlay individual points (violin/box)'),
            (self._label_bars_var,  'Label % on stacked bars'),
            (self._show_legend_var, 'Legend'),
        ]:
            ttk.Checkbutton(p, text=txt, variable=var,
                            command=self._schedule_replot,
                            style='TCheckbutton').pack(anchor='w', padx=8)

        # ── ACTIONS ───────────────────────────────────────────────────────
        _sec("ACTIONS")
        _btn("💾  Export figure",      self._export_figure,    'Green.TButton')
        _btn("📋  Export stats → CSV", self._export_stats,     'Blue2.TButton')

        # ── STATISTICS ────────────────────────────────────────────────────
        _sec("STATISTICS")
        self._stats_tree = ttk.Treeview(
            p, columns=('n', 'median', 'mean', 'iqr'),
            show='tree headings', height=10)
        for cid, hd, w, anc in [
            ('#0',    'Sample',  120, 'w'),
            ('n',     'n',        44, 'e'),
            ('median','Median',   68, 'e'),
            ('mean',  'Mean',     68, 'e'),
            ('iqr',   'IQR',      60, 'e'),
        ]:
            self._stats_tree.heading(cid, text=hd, anchor=anc)
            self._stats_tree.column(cid, width=w, anchor=anc,
                                    stretch=(cid == '#0'))
        self._stats_tree.pack(fill=tk.X, padx=8, pady=(0, 4))

        ttk.Frame(p, style='TFrame', height=12).pack()

        # ── plot area — scrollable in both directions, with zoom controls ──
        self._plot_frame = tk.Frame(self, bg=T['plot_bg'])
        self._plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Zoom scale factor (multiplier on per-sample width)
        self._zoom_x = tk.DoubleVar(value=1.0)   # horizontal zoom
        self._zoom_y = tk.DoubleVar(value=1.0)   # vertical zoom (figure height)

        # ── scrollbars ───────────────────────────────────────────────────
        h_scroll = tk.Scrollbar(self._plot_frame, orient='horizontal',
                                bg=T['sidebar_bg'])
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        v_scroll = tk.Scrollbar(self._plot_frame, orient='vertical',
                                bg=T['sidebar_bg'])
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._plot_canvas_widget = tk.Canvas(
            self._plot_frame,
            bg=T['plot_bg'],
            highlightthickness=0,
            xscrollcommand=h_scroll.set,
            yscrollcommand=v_scroll.set,
        )
        self._plot_canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        h_scroll.config(command=self._plot_canvas_widget.xview)
        v_scroll.config(command=self._plot_canvas_widget.yview)

        # Matplotlib figure lives inside a plain Frame embedded in the Canvas
        self._fig_frame = tk.Frame(self._plot_canvas_widget, bg=T['plot_bg'])
        self._fig_frame_id = self._plot_canvas_widget.create_window(
            (0, 0), window=self._fig_frame, anchor='nw')

        self._fig = Figure(figsize=(max(13, len(self._sample_labels) * 0.55 + 4), 6),
                           facecolor=T['fig_bg'])
        self._canvas = FigureCanvasTkAgg(self._fig, master=self._fig_frame)
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Keep scroll region in sync whenever the inner frame is resized
        def _on_fig_frame_configure(event):
            self._plot_canvas_widget.configure(
                scrollregion=self._plot_canvas_widget.bbox('all'))
        self._fig_frame.bind('<Configure>', _on_fig_frame_configure)

        # Mouse-wheel: vertical scroll; Shift+wheel: horizontal scroll
        def _vscroll(event):
            self._plot_canvas_widget.yview_scroll(
                int(-1 * (event.delta / 120)), 'units')
        def _hscroll(event):
            self._plot_canvas_widget.xview_scroll(
                int(-1 * (event.delta / 120)), 'units')
        self._plot_canvas_widget.bind('<MouseWheel>',       _vscroll)
        self._plot_canvas_widget.bind('<Shift-MouseWheel>', _hscroll)

        tf = tk.Frame(self._fig_frame, bg=T['sidebar_bg'])
        tf.pack(fill=tk.X)
        tb = NavigationToolbar2Tk(self._canvas, tf)
        tb.config(background=T['sidebar_bg'])
        tb.update()

        self._status_var = tk.StringVar(value="Opening  …  auto-computing")
        tk.Label(self._plot_frame, textvariable=self._status_var,
                 bg=T['header_bg'], fg=T['fg_dim'],
                 anchor='w', font=('Arial', 8), padx=6
                 ).pack(side=tk.BOTTOM, fill=tk.X)

    def _build_file_list(self):
        for w in self._file_list_frame.winfo_children():
            w.destroy()
        self._file_vars.clear()
        for fi, path in enumerate(sorted(self.app.loaded_files.keys())):
            # BUG FIX (B14): pull existing value without creating a throwaway
            # Tk variable on every call (Tk vars never GC).
            existing = self.app.file_vars.get(path)
            init_val = existing.get() if existing is not None else True
            var = tk.BooleanVar(value=init_val)
            self._file_vars[path] = var
            color = self.app.file_colors.get(
                path, FILE_COLORS[fi % _N_FILE_COLORS])
            row = ttk.Frame(self._file_list_frame, style='TFrame')
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, bg=color, width=2,
                     relief='raised').pack(side=tk.LEFT, padx=(0, 4),
                                           anchor='n', pady=2)
            name = os.path.basename(path)
            # Use wraplength so the name flows onto as many lines as needed
            # instead of being truncated. 220 px fits inside the 254 px sidebar
            # after the colour swatch.
            ttk.Checkbutton(row, text=name, variable=var,
                            command=self._schedule_replot,
                            style='TCheckbutton').pack(side=tk.LEFT,
                                                       fill=tk.X, expand=True)

    def _populate_dropdowns(self):
        # ── Gate dropdown ──────────────────────────────────────────────────
        gate_names = self.app._gate_selector_labels()
        self._gate_combo['values'] = gate_names
        # Default: auto-select the first applied gate (not "All cells") so
        # the stacked bar renders immediately on open.
        current = self._gate_var.get()
        if current not in gate_names:
            self._gate_var.set(gate_names[1] if len(gate_names) > 1 else 'All cells')
        elif current == 'All cells' and len(gate_names) > 1:
            # First open: promote to real gate
            self._gate_var.set(gate_names[1])
        self._on_gate_changed()

        # ── Distribution column dropdown ───────────────────────────────────
        cols = self._numeric_columns()
        self._dist_combo['values'] = cols
        if self._dist_col_var.get() not in cols:
            # Auto-pick: prefer Distance, then Intensity, then first numeric
            self._dist_col_var.set(preferred_distribution_column(cols))

    def _numeric_columns(self) -> list:
        """Return all numeric columns common to all active files.
        Only exclude columns that are pure row indices (named 'label' or
        'index'). All intensity, distance, coordinate and background columns
        are included so the user can choose freely."""
        dfs = [self.app.loaded_files[p] for p, v in self._file_vars.items()
               if v.get() and p in self.app.loaded_files]
        if not dfs:
            dfs = list(self.app.loaded_files.values())
        return common_numeric_columns(dfs)

    def _on_gate_changed(self, event=None):
        name = self._gate_var.get()
        if name == 'All cells':
            self._region_combo['values'] = ['All regions']
            self._region_var.set('All regions')
            self._schedule_replot()
            return
        gate = self.app._gate_from_selector(name)
        if gate is None:
            self._schedule_replot()
            return
        xch = self.app.x_channel
        ych = self.app.y_channel
        if not xch or not ych:
            self._region_combo['values'] = ['All regions']
            self._region_var.set('All regions')
            self._schedule_replot()
            return
        try:
            regions, _ = self.app._gate_mask_for(
                gate, np.array([0.0]), np.array([0.0]))
            rnames = ['All regions'] + list(regions.keys())
        except Exception:
            rnames = ['All regions']
        self._region_combo['values'] = rnames
        if self._region_var.get() not in rnames:
            self._region_var.set('All regions')
        self._schedule_replot()

    def _auto_intensity(self):
        cols = self._dist_combo['values']
        hit = first_intensity_column(cols)
        if hit:
            self._dist_col_var.set(hit)
            self._schedule_replot()

    def _auto_distance(self):
        cols = self._dist_combo['values']
        hit = first_distance_column(cols)
        if hit:
            self._dist_col_var.set(hit)
            self._schedule_replot()

    # ── compute ───────────────────────────────────────────────────────────────


    # ── render ────────────────────────────────────────────────────────────────

    def _render_figure(self):
        T     = self.T
        labels = self._sample_labels
        if not labels:
            return

        # Resize figure using zoom factors
        # BUG FIX (B14): avoid leaking Tk DoubleVars on every render by
        # using a plain getattr fallback to a float, not a Tk variable.
        n_samples     = len(labels)
        _zx = getattr(self, '_zoom_x', None)
        _zy = getattr(self, '_zoom_y', None)
        zoom_x = _zx.get() if _zx is not None else 1.0
        zoom_y = _zy.get() if _zy is not None else 1.0
        bottom_margin = 0.38
        fig_w  = max(13, n_samples * 0.6 * zoom_x + 4)
        fig_h  = 6 * zoom_y
        self._fig.set_size_inches(fig_w, fig_h)

        self._fig.clear()
        self._fig.patch.set_facecolor(T['fig_bg'])

        has_dist = bool(self._dist_col_var.get()) and any(
            len(v) > 0 for v, _ in self._dist_cache.values())
        has_pop  = any(bool(d) for d in self._pop_cache.values())

        if has_dist and has_pop:
            gs = self._fig.add_gridspec(1, 2, wspace=0.35,
                                         left=0.06, right=0.87,
                                         top=0.90, bottom=bottom_margin)
            ax_vio = self._fig.add_subplot(gs[0])
            ax_bar = self._fig.add_subplot(gs[1])
        elif has_dist:
            ax_vio = self._fig.add_subplot(1, 1, 1)
            self._fig.subplots_adjust(left=0.08, right=0.97,
                                       top=0.90, bottom=bottom_margin)
            ax_bar = None
        elif has_pop:
            ax_vio = None
            ax_bar = self._fig.add_subplot(1, 1, 1)
            self._fig.subplots_adjust(left=0.08, right=0.82,
                                       top=0.90, bottom=bottom_margin)
        else:
            self._canvas.draw()
            return

        for ax in filter(None, [ax_vio, ax_bar]):
            ax.set_facecolor(T['ax_bg'])
            _set_spines_color(ax, T['spine'])
            ax.tick_params(colors=T['fg'], labelsize=8)
            ax.grid(True, alpha=0.20, color=T['grid'])

        n = len(labels)
        x_pos = np.arange(n)

        # ── LEFT: violin / box / points only ─────────────────────────────
        if ax_vio is not None:
            col  = self._dist_col_var.get()
            kind = self._plot_kind_var.get()
            colors_ordered = [self._dist_cache[lbl][1] for lbl in labels]

            if kind == 'violin':
                data_for_vio = []
                for lbl in labels:
                    vals, _ = self._dist_cache[lbl]
                    data_for_vio.append(vals if len(vals) >= 4 else np.array([0.0]))

                try:
                    parts = ax_vio.violinplot(
                        data_for_vio,
                        positions=x_pos,
                        showmedians=False, showextrema=False,
                        widths=0.65)
                    for i, body in enumerate(parts['bodies']):
                        body.set_facecolor(colors_ordered[i])
                        body.set_alpha(0.75)
                        body.set_edgecolor(T['spine'])
                        body.set_linewidth(0.6)
                except Exception:
                    pass

                # Manual median dot + IQR bar + 5–95 whisker
                for xi, lbl in enumerate(labels):
                    vals, col_c = self._dist_cache[lbl]
                    if len(vals) < 2:
                        continue
                    med              = float(np.median(vals))
                    p5, q1, q3, p95  = np.percentile(vals, [5, 25, 75, 95])
                    ax_vio.vlines(xi, p5,  p95, color='white', lw=1.2, zorder=4)
                    ax_vio.vlines(xi, q1,  q3,  color='white', lw=3.5, zorder=5)
                    ax_vio.scatter([xi], [med], s=28, color='white',
                                   zorder=6, linewidths=0)

            elif kind == 'box':
                data_for_box = []
                for lbl in labels:
                    vals, _ = self._dist_cache[lbl]
                    data_for_box.append(vals if len(vals) >= 2 else np.array([0.0]))
                try:
                    bp = ax_vio.boxplot(
                        data_for_box, positions=x_pos,
                        patch_artist=True, widths=0.55,
                        medianprops=dict(color='white', lw=1.5),
                        whiskerprops=dict(color=T['fg_dim'], lw=0.8),
                        capprops=dict(color=T['fg_dim'], lw=0.8),
                        flierprops=dict(marker='.', markersize=2,
                                        markerfacecolor=T['fg_dim'],
                                        markeredgecolor='none', alpha=0.4))
                    for i, patch in enumerate(bp['boxes']):
                        patch.set_facecolor(colors_ordered[i])
                        patch.set_alpha(0.75)
                        patch.set_edgecolor(T['spine'])
                    # Color flier dots to match their box color
                    for i, flier in enumerate(bp['fliers']):
                        flier.set_markerfacecolor(colors_ordered[i])
                        flier.set_markeredgecolor('none')
                        flier.set_alpha(0.5)
                except Exception:
                    pass

            else:
                # points only — strip plot, no violin/box behind
                pass   # points drawn unconditionally below for this mode

            # Individual points — always on for 'points only', optional for others
            show_pts = self._show_points_var.get() or kind == 'points only'
            if show_pts:
                # Use a fresh Generator with a fixed seed each render so
                # subsampling and jitter are identical across re-draws and
                # the y-axis scale does not shift between views.
                _rng_pts = np.random.default_rng(42)
                # Collect all visible values first to set stable y-limits
                _all_sub_vals: list = []
                MAX_PTS = 500
                _per_sample: list = []
                for xi, lbl in enumerate(labels):
                    vals, col_c = self._dist_cache[lbl]
                    if len(vals) == 0:
                        _per_sample.append((xi, col_c, np.array([]), np.array([])))
                        continue
                    if len(vals) > MAX_PTS:
                        idx = _rng_pts.choice(len(vals), MAX_PTS, replace=False)
                        sub = vals[idx]
                    else:
                        sub = vals.copy()
                    jitter = _rng_pts.uniform(-0.18, 0.18, size=len(sub))
                    _per_sample.append((xi, col_c, sub, jitter))
                    _all_sub_vals.append(sub)
                # Pin y-limits from the full data range (not just the subsample)
                # to prevent axis rescaling when switching between modes.
                _all_full = np.concatenate(
                    [v for v, _ in self._dist_cache.values() if len(v) > 0]
                ) if self._dist_cache else np.array([0.0])
                if len(_all_full) > 0 and np.isfinite(_all_full).any():
                    _ymin = float(np.nanmin(_all_full))
                    _ymax = float(np.nanmax(_all_full))
                    _pad  = (_ymax - _ymin) * 0.05 if _ymax > _ymin else 1.0
                    ax_vio.set_ylim(_ymin - _pad, _ymax + _pad)
                for xi, col_c, sub, jitter in _per_sample:
                    if len(sub) == 0:
                        continue
                    ax_vio.scatter(xi + jitter, sub,
                                   s=5, color=col_c, alpha=0.55,
                                   linewidths=0, zorder=7)

            # Legend
            if self._show_legend_var.get() and n <= 16:
                handles = [mlines.Line2D([], [], color=c, lw=4,
                                         label=lbl, alpha=0.75)
                           for lbl, (_, c) in self._dist_cache.items()
                           if lbl in labels]
                ax_vio.legend(handles=handles, fontsize=6,
                              loc='upper right',
                              facecolor=T['legend_bg'],
                              labelcolor=T['fg'],
                              framealpha=0.75,
                              ncol=max(1, n // 8))

            ax_vio.set_xticks(x_pos)
            short = self._shorten_labels(labels)
            _set_rotated_xlabels(ax_vio, short)
            # Use the full column name for both y-label and title
            ax_vio.set_ylabel(col, color=T['fg'], fontsize=8)
            ax_vio.set_title(f'{col}  —  Distribution per Sample',
                              color=T['fg'], fontsize=9)

        # ── RIGHT: stacked 100 % bar ───────────────────────────────────────
        if ax_bar is not None:
            # Collect all region names (union across all samples)
            all_regions: list = []
            seen_r: set = set()
            for lbl in labels:
                for r in self._pop_cache.get(lbl, {}):
                    if r not in seen_r:
                        seen_r.add(r)
                        all_regions.append(r)

            bottoms = np.zeros(n)
            for ri, rname in enumerate(all_regions):
                heights = np.array([
                    self._pop_cache.get(lbl, {}).get(rname, 0.0)
                    for lbl in labels])
                col_bar = REGION_COLORS[ri % _N_REGION_COLORS]
                bars = ax_bar.bar(x_pos, heights, bottom=bottoms,
                                  color=col_bar, width=0.65,
                                  label=rname, edgecolor='none')

                # % labels inside bars
                if self._label_bars_var.get():
                    for xi, (h, b) in enumerate(zip(heights, bottoms)):
                        if h >= 5.0:
                            ax_bar.text(xi, b + h / 2.0,
                                        f'{h:.1f}%',
                                        ha='center', va='center',
                                        fontsize=6.5, color='white',
                                        fontweight='bold', clip_on=True)

                # Per-bar binomial SEM: each sample gets its own error bar
                # looked up by (sample_label, region_name) key.
                sem_cache = getattr(self, '_pop_sem_cache', {})
                for xi, (lbl_xi, h, b) in enumerate(
                        zip(labels, heights, bottoms)):
                    if h >= 3.0:
                        sem_bar = sem_cache.get((lbl_xi, rname), 0.0)
                        if sem_bar > 0:
                            top_y = b + h
                            ax_bar.errorbar(
                                xi, top_y,
                                yerr=sem_bar,
                                fmt='none',
                                ecolor='white',
                                elinewidth=1.2,
                                capsize=3.5,
                                capthick=1.2,
                                zorder=6,
                            )
                bottoms += heights

            ax_bar.set_ylim(0, 100)
            ax_bar.set_xticks(x_pos)
            short2 = self._shorten_labels(labels)
            _set_rotated_xlabels(ax_bar, short2)
            ax_bar.set_ylabel('Population (%)', color=T['fg'], fontsize=9)
            gate_lbl = self._gate_var.get()
            ax_bar.set_title(
                f'Gate Population % — Per Sample  [{gate_lbl}]\n'
                'Error bars = within-sample binomial counting SE; not biological replicate SEM',
                color=T['fg'], fontsize=8.5)

            if self._show_legend_var.get() and all_regions:
                ax_bar.legend(fontsize=7,
                              loc='upper left',
                              bbox_to_anchor=(1.01, 1.0),
                              borderaxespad=0,
                              facecolor=T['legend_bg'],
                              labelcolor=T['fg'],
                              framealpha=0.85)

        self._fig.suptitle('Batch Plots', color=T['fg'], fontsize=10)
        self._canvas.draw()

        # Update the scrollable canvas scroll region to match the new figure size
        dpi = self._fig.get_dpi()
        pw = int(fig_w * dpi)
        ph = int(fig_h * dpi)
        self._canvas.get_tk_widget().config(width=pw, height=ph)
        self._plot_canvas_widget.configure(
            scrollregion=(0, 0, pw, ph))

    # ── display-only refresh ──────────────────────────────────────────────────

    def _update_stats(self):
        for item in self._stats_tree.get_children():
            self._stats_tree.delete(item)
        if not self._dist_cache:
            return

        for lbl in self._sample_labels:
            vals, _ = self._dist_cache.get(lbl, (np.array([]), None))
            stats = distribution_summary(vals)
            short = short_display_label(lbl)
            self._stats_tree.insert(
                '', 'end', text=f'  {short}',
                values=(
                    f"{stats['n']:,}",
                    format_display_number(stats['median']),
                    format_display_number(stats['mean']),
                    format_display_number(stats['iqr']),
                ))

    # ── export ────────────────────────────────────────────────────────────────

    def _export_figure(self):
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension='.pdf',
            initialfile='batch_plots.pdf',
            filetypes=[("PDF", "*.pdf"), ("PNG", "*.png"),
                       ("SVG", "*.svg"), ("All", "*.*")])
        if not path:
            return
        try:
            save_figure(self._fig, path)
            messagebox.showinfo("Saved", f"Figure saved:\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("Save Error", str(e), parent=self)

    def _export_stats(self):
        import pandas as pd
        if not self._dist_cache and not self._pop_cache:
            messagebox.showwarning("Export",
                "No data yet — select a column and gate first.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension='.csv',
            initialfile='batch_stats.csv',
            filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if not path:
            return
        rows = []
        for lbl in self._sample_labels:
            vals, _ = self._dist_cache.get(lbl, (np.array([]), None))
            rows.append(build_batch_plot_stats_row(
                sample_label=lbl,
                values=vals,
                populations=self._pop_cache.get(lbl, {}),
                population_sems={
                    rname: self._pop_sem_cache[(lbl, rname)]
                    for rname in self._pop_cache.get(lbl, {})
                    if (lbl, rname) in self._pop_sem_cache
                },
                column=self._dist_col_var.get(),
                gate=self._gate_var.get(),
                region=self._region_var.get(),
            ))
        try:
            pd.DataFrame(rows).to_csv(path, index=False)
            messagebox.showinfo("Export",
                f"Stats saved ({len(rows)} rows):\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("Export", str(e), parent=self)


def __getattr__(name: str):
    if name == "BatchPlotWindow":
        from vflow.legacy.vflow_legacy import BatchPlotWindow
        return BatchPlotWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["BatchPlotWindow", "BatchPlotWindowBase"]
