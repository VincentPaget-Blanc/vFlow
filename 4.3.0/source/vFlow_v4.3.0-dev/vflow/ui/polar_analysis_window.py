"""Polar Analysis UI/lifecycle implementation for vFlow.

The compatibility ``PolarAnalysisWindow`` still resolves through the frozen legacy
module.  ``PolarAnalysisWindowBase`` owns UI construction, lifecycle, data retrieval,
rendering and export helpers; the scientifically sensitive ``_compute_and_plot``
method intentionally remains on the legacy compatibility subclass in this milestone.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from vflow.config.constants import FILE_COLORS, _N_FILE_COLORS
from vflow.core.circular_stats import (
    auto_detect_vector_columns, build_polar_stats_export_row,
    circular_mean_direction, common_columns, format_polar_stats_values,
    mean_resultant_length, rayleigh_p_value, vector_direction_stats,
    vectors_from_coordinate_columns, Y_ORIENTATION_CARTESIAN,
    Y_ORIENTATION_IMAGE,
)
from vflow.plotting.utils import set_spines_color as _set_spines_color
from vflow.services.figure_export import save_figure
from vflow.services.population_evaluation import selected_population_mask_for_dataframe

class PolarAnalysisWindowBase:
    """
    Polar / Vector Analysis window  (v3.9.4)

    One polar axes, files overlaid with FILE_COLORS.
    Non-rasterised output → true vector PDF/SVG export.

    Sidebar
    -------
    POPULATION    gate + region selectors
    FILES         per-file visibility checkboxes (mirrors main window)
    CHANNEL MAP   X/Y Ch1, X/Y Ch2 centroid column combos + auto-detect
    SETTINGS      histogram bins, bar alpha, MRL threshold for arrow
    DISPLAY       show/hide stats annotation on plot, legend
    ACTIONS       Export figure, Export stats CSV
    STATISTICS    per-file / merged treeview (n, MRL, p, mean dir°, sig)

    Statistics
    ----------
    MRL   : Mean Resultant Length  R̄ = |∑exp(iθ)| / n ∈ [0, 1]
    Rayleigh p : Zar approximation used by CircStat — with R = n·R̄,
                 p ≈ exp(sqrt(1 + 4n + 4(n² − R²)) − (1 + 2n)).
    Significance : marked ✓ when BOTH p < 0.05 AND MRL ≥ threshold.
                   Using both criteria together is intentional:
                   • p alone can flag large-n samples with trivially small MRL
                     (statistically significant but biologically irrelevant).
                   • MRL alone can appear high in small-n samples that are
                     simply underpowered for the Rayleigh test.
                   For typical synaptosome data (n = 12–36 per file), requiring
                   both an effect-size threshold (MRL) and a significance test
                   (p) guards against both failure modes.  This is the circular-
                   statistics analogue of a two-criterion gate in flow cytometry.
    """

    # ── construction ─────────────────────────────────────────────────────────

    def __init__(self, parent_root, T: dict, app: 'FlowApp'):
        super().__init__(parent_root)
        self.T   = T
        self.app = app
        self.title("Vector / Polar Analysis")
        self.geometry("1150x820")
        self.configure(bg=T['sidebar_bg'])
        self.resizable(True, True)

        # ── tk variables ─────────────────────────────────────────────────
        self._mrl_thresh_var = tk.StringVar(value='0.5')
        self._n_bins_var     = tk.StringVar(value='36')
        self._alpha_var      = tk.StringVar(value='0.55')

        self._cx1_var = tk.StringVar()
        self._cy1_var = tk.StringVar()
        self._cx2_var = tk.StringVar()
        self._cy2_var = tk.StringVar()
        self._y_orientation_var = tk.StringVar(value=Y_ORIENTATION_CARTESIAN)

        self._gate_var   = tk.StringVar(value='All cells')
        self._region_var = tk.StringVar(value='All regions')

        self._show_stats_ann_var = tk.BooleanVar(value=True)
        self._show_legend_var    = tk.BooleanVar(value=True)
        self._stats_mode_var     = tk.StringVar(value='perfile')

        # per-file visibility: {path: BooleanVar}
        self._file_vars: dict = {}

        # last computed datasets for stats refresh without replot
        self._last_datasets: list = []   # [(angles, mags, label, color, path)]
        self._replot_pending: str = None  # after() id for debounced replot

        self._build_ui()
        self._build_file_list()
        self._auto_detect_channels()
        self._populate_gate_dropdown()
        # Auto-compute after the window is fully drawn. Keep the callback id so
        # closing the Toplevel before it fires cannot call into destroyed widgets.
        self._initial_compute_pending = self.after(150, self._do_initial_compute)
        self.protocol('WM_DELETE_WINDOW', self._on_close)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        T = self.T

        # ── Scrollable sidebar ────────────────────────────────────────────
        sb_outer = tk.Frame(self, bg=T['sidebar_bg'], width=270)
        sb_outer.pack(side=tk.LEFT, fill=tk.Y)
        sb_outer.pack_propagate(False)

        sv = ttk.Scrollbar(sb_outer, orient='vertical')
        sv.pack(side=tk.RIGHT, fill=tk.Y)
        self._sb_canvas = tk.Canvas(sb_outer, bg=T['sidebar_bg'],
                                    highlightthickness=0, yscrollcommand=sv.set)
        self._sb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sv.config(command=self._sb_canvas.yview)

        self._sb = ttk.Frame(self._sb_canvas, style='TFrame')
        self._sb_canvas.create_window((0, 0), window=self._sb,
                                       anchor='nw', width=254)
        self._sb.bind('<Configure>',
            lambda e: self._sb_canvas.configure(
                scrollregion=self._sb_canvas.bbox('all')))
        def _scroll(evt):
            self._sb_canvas.yview_scroll(int(-1 * (evt.delta / 120)), 'units')
        self._sb_canvas.bind('<MouseWheel>', _scroll)
        self._sb.bind('<MouseWheel>', _scroll)

        p = self._sb   # shorthand

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

        def _entry(var):
            e = ttk.Entry(p, textvariable=var, font=('Arial', 8), width=8)
            e.pack(anchor='w', padx=8, pady=(0, 3))
            return e

        # ── POPULATION ────────────────────────────────────────────────────
        _sec("POPULATION")
        _lbl("Gate:")
        self._gate_combo = _combo(self._gate_var, ['All cells'])
        self._gate_combo.bind('<<ComboboxSelected>>', self._on_gate_changed)
        _lbl("Region:")
        self._region_combo = _combo(self._region_var, ['All regions'])
        self._region_combo.bind('<<ComboboxSelected>>',
                                lambda _e: self._schedule_replot())

        # ── FILES ─────────────────────────────────────────────────────────
        _sec("FILES")
        self._file_list_frame = ttk.Frame(p, style='TFrame')
        self._file_list_frame.pack(fill=tk.X, padx=8, pady=(0, 4))
        # populated by _build_file_list()

        # ── CHANNEL MAPPING ───────────────────────────────────────────────
        _sec("CHANNEL MAPPING")
        # Vectors run Ch1->Ch2. X cols = horizontal centroid,
        # Y cols = vertical centroid. Always pair X with X and
        # Y with Y so axes are never mixed across channels.
        cols = self._get_columns()
        ttk.Label(p,
                  text="  Direction: Ch1 centroid → Ch2 centroid\n"
                       "  Map X and Y separately for each channel.",
                  style='Dim.TLabel', wraplength=230,
                  justify='left').pack(anchor='w', padx=8, pady=(0, 4))
        _lbl("Channel 1  —  X centroid (horizontal):")
        self._cx1_combo = _combo(self._cx1_var, cols)
        self._cx1_combo.bind('<<ComboboxSelected>>',
                             lambda _e: self._schedule_replot())
        _lbl("Channel 1  —  Y centroid (vertical):")
        self._cy1_combo = _combo(self._cy1_var, cols)
        self._cy1_combo.bind('<<ComboboxSelected>>',
                             lambda _e: self._schedule_replot())
        _lbl("Channel 2  —  X centroid (horizontal):")
        self._cx2_combo = _combo(self._cx2_var, cols)
        self._cx2_combo.bind('<<ComboboxSelected>>',
                             lambda _e: self._schedule_replot())
        _lbl("Channel 2  —  Y centroid (vertical):")
        self._cy2_combo = _combo(self._cy2_var, cols)
        self._cy2_combo.bind('<<ComboboxSelected>>',
                             lambda _e: self._schedule_replot())
        _btn("⟳  Auto-detect columns", self._auto_detect_channels, 'Gray.TButton')
        _lbl("Y coordinate orientation:")
        self._y_orientation_combo = _combo(
            self._y_orientation_var,
            [Y_ORIENTATION_CARTESIAN, Y_ORIENTATION_IMAGE])
        self._y_orientation_combo.bind(
            '<<ComboboxSelected>>', lambda _e: self._schedule_replot())
        ttk.Label(
            p,
            text=("  cartesian_y_up: +Y is upward.  image_y_down: +Y is "
                  "downward and is reflected before angle calculation."),
            style='Dim.TLabel', wraplength=230, justify='left'
        ).pack(anchor='w', padx=8, pady=(0, 4))

        # ── SETTINGS ──────────────────────────────────────────────────────
        _sec("SETTINGS")
        _lbl("Histogram bins (rose):")
        e_bins = _entry(self._n_bins_var)
        e_bins.bind('<KeyRelease>', lambda _e: self._schedule_replot())
        _lbl("Bar alpha (0–1):")
        e_alpha = _entry(self._alpha_var)
        e_alpha.bind('<KeyRelease>', lambda _e: self._schedule_replot())
        _lbl("MRL threshold (arrow + sig.):")
        e_mrl = _entry(self._mrl_thresh_var)
        e_mrl.bind('<KeyRelease>', lambda _e: self._schedule_replot())
        ttk.Label(p, text="  ✓ sig. requires p<0.05 AND MRL ≥ threshold",
                  style='Dim.TLabel').pack(anchor='w', padx=8, pady=(0, 4))

        # ── DISPLAY ───────────────────────────────────────────────────────
        _sec("DISPLAY")
        for var, txt in [
            (self._show_stats_ann_var, 'Stats annotation on plot'),
            (self._show_legend_var,    'Legend'),
        ]:
            ttk.Checkbutton(p, text=txt, variable=var,
                            command=self._refresh_display,
                            style='TCheckbutton').pack(anchor='w', padx=8)

        # ── ACTIONS ───────────────────────────────────────────────────────
        _sec("ACTIONS")
        _btn("💾  Export figure",      self._export_current,   'Green.TButton')
        _btn("📋  Export stats → CSV", self._export_stats,     'Blue2.TButton')

        # ── STATISTICS ────────────────────────────────────────────────────
        _sec("STATISTICS")
        sm_row = ttk.Frame(p, style='TFrame')
        sm_row.pack(fill=tk.X, padx=8, pady=(0, 4))
        for val, lbl_txt in [('perfile', 'Per file'), ('merged', 'Merged')]:
            ttk.Radiobutton(sm_row, text=lbl_txt,
                            variable=self._stats_mode_var, value=val,
                            command=self._update_stats_display,
                            style='TRadiobutton').pack(side=tk.LEFT, padx=4)

        self._stats_tree = ttk.Treeview(
            p, columns=('n', 'mrl', 'p', 'dir', 'sig'),
            show='tree headings', height=8)
        self._stats_tree.heading('#0',  text='File',      anchor='w')
        self._stats_tree.heading('n',   text='N',         anchor='e')
        self._stats_tree.heading('mrl', text='MRL',       anchor='e')
        self._stats_tree.heading('p',   text='p',         anchor='e')
        self._stats_tree.heading('dir', text='Dir°',      anchor='e')
        self._stats_tree.heading('sig', text='Sig.',      anchor='center')
        self._stats_tree.column('#0',  width=100, stretch=True)
        self._stats_tree.column('n',   width=40,  anchor='e', stretch=False)
        self._stats_tree.column('mrl', width=46,  anchor='e', stretch=False)
        self._stats_tree.column('p',   width=58,  anchor='e', stretch=False)
        self._stats_tree.column('dir', width=44,  anchor='e', stretch=False)
        self._stats_tree.column('sig', width=36,  anchor='center', stretch=False)
        self._stats_tree.pack(fill=tk.X, padx=8, pady=(0, 6))

        ttk.Frame(p, style='TFrame', height=12).pack()

        # ── Plot area ─────────────────────────────────────────────────────
        self._plot_frame = tk.Frame(self, bg=T['plot_bg'])
        self._plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._fig = Figure(figsize=(9.5, 7.5), facecolor=T['fig_bg'])
        self._canvas = FigureCanvasTkAgg(self._fig, master=self._plot_frame)
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        tf = tk.Frame(self._plot_frame, bg=T['sidebar_bg'])
        tf.pack(fill=tk.X)
        tb = NavigationToolbar2Tk(self._canvas, tf)
        tb.config(background=T['sidebar_bg'])
        tb.update()

        self._status_var = tk.StringVar(value="Opening  …  auto-computing")
        tk.Label(self._plot_frame, textvariable=self._status_var,
                 bg=T['header_bg'], fg=T['fg_dim'],
                 anchor='w', font=('Arial', 8), padx=6
                 ).pack(side=tk.BOTTOM, fill=tk.X)

    def _do_initial_compute(self):
        self._initial_compute_pending = None
        if self.winfo_exists():
            self._compute_and_plot()

    def _on_close(self):
        """Cancel delayed work before destroying the Polar window."""
        for attr in ('_initial_compute_pending', '_replot_pending'):
            pending = getattr(self, attr, None)
            if pending:
                try:
                    self.after_cancel(pending)
                except tk.TclError:
                    pass
                setattr(self, attr, None)
        self.destroy()

    def _schedule_replot(self, delay_ms: int = 350):
        """Debounced replot — cancels any pending call and re-schedules.
        Entries (bins, alpha, MRL) call this so rapid typing only fires once."""
        if self._replot_pending:
            try:
                self.after_cancel(self._replot_pending)
            except Exception:
                pass
        self._replot_pending = self.after(delay_ms, self._do_replot)

    def _do_replot(self):
        self._replot_pending = None
        self._compute_and_plot()

    # ── File list ─────────────────────────────────────────────────────────────

    def _build_file_list(self):
        """Build per-file visibility checkboxes in the FILES section."""
        for w in self._file_list_frame.winfo_children():
            w.destroy()
        active = self.app._active()
        file_keys = sorted(active.keys())
        # Preserve existing checkbox state; create new vars only for new files
        for path in list(self._file_vars.keys()):
            if path not in file_keys:
                del self._file_vars[path]
        for fi, path in enumerate(file_keys):
            if path not in self._file_vars:
                self._file_vars[path] = tk.BooleanVar(value=True)
            var   = self._file_vars[path]
            color = FILE_COLORS[fi % _N_FILE_COLORS]
            row   = ttk.Frame(self._file_list_frame, style='TFrame')
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, bg=color, width=2, relief='raised'
                     ).pack(side=tk.LEFT, padx=(0, 4))
            name  = os.path.basename(path)
            disp  = (name[:20] + '…') if len(name) > 21 else name
            ttk.Checkbutton(row, text=disp, variable=var,
                            command=self._schedule_replot,
                            style='TCheckbutton').pack(side=tk.LEFT)
        if not file_keys:
            ttk.Label(self._file_list_frame, text="(no files loaded)",
                      style='Dim.TLabel').pack(anchor='w')

    def _get_active_paths(self) -> list:
        """Return list of paths where the per-file checkbox is checked."""
        # BUG FIX (B14): `dict.get(key, tk.BooleanVar(value=True))` creates a
        # new Tk variable on every call when the key is missing — Tk vars
        # are registered with the interpreter and never garbage-collected,
        # so this leaks one variable per missing-key path per invocation.
        # Inline the lookup to avoid constructing the default unless used.
        active = self.app._active()
        out = []
        for p in sorted(active.keys()):
            v = self._file_vars.get(p)
            if v is None or v.get():
                out.append(p)
        return out

    # ── helpers ───────────────────────────────────────────────────────────────

    def _get_columns(self):
        files = self.app._active()
        if not files:
            return []
        return common_columns(list(files.values()))

    def _auto_detect_channels(self):
        """
        Heuristic auto-assignment of the four centroid columns.
        Prefers X_{ch}_microns / Y_{ch}_microns naming (vSynApp convention).
        Falls back to any X_* / Y_* prefix or centroid_x / centroid_y naming.
        Clears StringVars first so stale values do not survive.
        """
        cols = self._get_columns()
        for cb in (self._cx1_combo, self._cy1_combo,
                   self._cx2_combo, self._cy2_combo):
            cb['values'] = cols
        for v in (self._cx1_var, self._cy1_var, self._cx2_var, self._cy2_var):
            v.set('')

        cx1, cy1, cx2, cy2 = auto_detect_vector_columns(cols)
        self._cx1_var.set(cx1); self._cy1_var.set(cy1)
        self._cx2_var.set(cx2); self._cy2_var.set(cy2)

    def _populate_gate_dropdown(self):
        names = self.app._gate_selector_labels()
        self._gate_combo['values'] = names
        if self._gate_var.get() not in names:
            self._gate_var.set('All cells')
        self._on_gate_changed()

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
        dummy_x = np.array([0.0]); dummy_y = np.array([0.0])
        try:
            regions, _ = self.app._gate_mask_for(gate, dummy_x, dummy_y)
            rnames = ['All regions'] + list(regions.keys())
        except Exception:
            rnames = ['All regions']
        self._region_combo['values'] = rnames
        if self._region_var.get() not in rnames:
            self._region_var.set('All regions')
        self._schedule_replot()

    # ── data retrieval ────────────────────────────────────────────────────────

    def _get_population_mask(self, df: pd.DataFrame, path: str) -> np.ndarray:
        import pandas as pd
        """
        Boolean row-mask for the selected gate + region.
        Does NOT pass _cache_path to _gate_mask_for — always computes fresh
        to avoid wrong-length cached masks from the main window's full-file
        DataFrame being returned for a differently-sized sub-gate DataFrame.
        """
        name = self._gate_var.get()
        n    = len(df)
        if name == 'All cells':
            return np.ones(n, bool)
        gate = self.app._gate_from_selector(name)
        mask = selected_population_mask_for_dataframe(
            df, gate, region_name=self._region_var.get(),
            analysis_state=self.app._analysis_state_obj())
        if mask is None:
            return None
        return mask

    def _get_vectors_for_df(self, df: pd.DataFrame, mask: np.ndarray):
        import pandas as pd
        """Return (angles_rad, magnitudes) or (None, None)."""
        return vectors_from_coordinate_columns(
            df,
            mask,
            self._cx1_var.get(),
            self._cy1_var.get(),
            self._cx2_var.get(),
            self._cy2_var.get(),
            y_coordinate_orientation=self._y_orientation_var.get(),
        )

    # ── circular statistics ───────────────────────────────────────────────────

    @staticmethod
    def _mrl(angles: np.ndarray) -> float:
        """
        Mean Resultant Length: R̄ = |∑ exp(iθ)| / n ∈ [0, 1].
        0 = uniform distribution, 1 = all vectors identical.
        """
        return mean_resultant_length(angles)

    @staticmethod
    def _mean_dir(angles: np.ndarray) -> float:
        """Circular mean direction in radians ∈ (−π, π]."""
        return circular_mean_direction(angles)

    @staticmethod
    def _rayleigh_p(angles: np.ndarray) -> float:
        """
        Rayleigh test p-value using the Zar approximation implemented by
        CircStat. With R = n·R̄:

          p ≈ exp(sqrt(1 + 4n + 4(n² − R²)) − (1 + 2n))
        """
        return rayleigh_p_value(angles)

    # ── plotting ──────────────────────────────────────────────────────────────

    def _refresh_display(self):
        """Re-render the figure from cached datasets (no data recomputation).
        Called by display-option checkboxes to show/hide annotation / legend."""
        if self._last_datasets:
            self._render_figure(self._last_datasets)


    def _render_figure(self, datasets: list):
        """Build and draw the polar figure from pre-collected datasets."""
        try:
            mrl_thresh = float(self._mrl_thresh_var.get())
            n_bins     = max(4, int(self._n_bins_var.get()))
            bar_alpha  = float(np.clip(float(self._alpha_var.get()), 0.05, 1.0))
        except ValueError:
            return

        T = self.T
        self._fig.clear()
        self._fig.patch.set_facecolor(T['fig_bg'])

        ax = self._fig.add_subplot(111, projection='polar')
        ax.set_facecolor(T['ax_bg'])
        _set_spines_color(ax, T['spine'])
        ax.tick_params(colors=T['fg'], labelsize=7)
        ax.grid(True, color=T['grid'], alpha=0.45)
        ax.set_xticks(np.linspace(0, 2 * np.pi, 8, endpoint=False))
        ax.set_xticklabels(
            ['0°', '45°', '90°', '135°', '180°', '225°', '270°', '315°'],
            fontsize=7, color=T['fg'])
        ax.set_rlabel_position(30)

        bin_edges   = np.linspace(-np.pi, np.pi, n_bins + 1)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
        bin_width   = 2 * np.pi / n_bins

        stats_lines = []

        for angles, mags, label, color, path in datasets:
            if len(angles) == 0:
                continue

            counts, _ = np.histogram(angles, bins=bin_edges)
            fracs     = counts / len(angles)   # normalised fraction

            # Rose bars — non-rasterised for vector PDF export
            short_lbl = os.path.splitext(label)[0]
            short_lbl = (short_lbl[:26] + '…') if len(short_lbl) > 27 else short_lbl
            ax.bar(bin_centers, fracs,
                   width=bin_width, bottom=0.0,
                   color=color, alpha=bar_alpha,
                   edgecolor=T['spine'], linewidth=0.5,
                   label=f'{short_lbl}  (n={len(angles):,})',
                   zorder=2)

            mrl   = self._mrl(angles)
            p_val = self._rayleigh_p(angles)

            # Mean-direction arrow when MRL meets threshold
            if mrl >= mrl_thresh and fracs.max() > 0:
                mean_dir = self._mean_dir(angles)
                arrow_r  = fracs.max() * 0.82
                ax.annotate(
                    '', xy=(mean_dir, arrow_r), xytext=(0, 0),
                    arrowprops=dict(arrowstyle='->', color=color,
                                    lw=2.0, shrinkA=0, shrinkB=0),
                    zorder=5)

            p_fmt = f'p={p_val:.4f}' if p_val >= 0.0001 else 'p=< 0.0001'
            sig   = '\u2713 sig.' if (p_val < 0.05 and mrl >= mrl_thresh) else 'n.s.'
            stats_lines.append(
                f'{short_lbl}\n'
                f'  n={len(angles):,}   MRL={mrl:.3f}   {p_fmt}   {sig}')

        # ── Stats annotation on plot (optional) ───────────────────────────
        if stats_lines and self._show_stats_ann_var.get():
            stats_txt = '\n'.join(stats_lines)
            ax.text(0.01, 0.01, stats_txt,
                    transform=ax.transAxes,
                    fontsize=7, ha='left', va='bottom',
                    color=T['fg'],
                    bbox=dict(boxstyle='round,pad=0.4',
                              facecolor=T['label_box'],
                              alpha=0.82, linewidth=0),
                    zorder=10)

        # ── Legend (optional) ─────────────────────────────────────────────
        if self._show_legend_var.get() and datasets:
            ax.legend(fontsize=7, loc='upper right',
                      facecolor=T['legend_bg'], labelcolor=T['fg'],
                      framealpha=0.75)

        # ── Title ─────────────────────────────────────────────────────────
        gate_lbl   = self._gate_var.get()
        region_lbl = self._region_var.get()
        pop_info   = (f'{gate_lbl} / {region_lbl}'
                      if gate_lbl != 'All cells' else 'All cells')
        self._fig.suptitle(
            f'Vector directionality  \u2014  {pop_info}\n'
            'Radial scale = fraction of vectors per bin  |  '
            f'Arrow = mean direction (shown when MRL \u2265 {mrl_thresh})',
            color=T['fg'], fontsize=9, y=1.02)

        self._fig.tight_layout()
        self._canvas.draw()

        total_vecs = sum(len(a) for a, _, _, _, _ in datasets)
        self._status_var.set(
            f"{total_vecs:,} vectors  \u00b7  {len(datasets)} file(s)  "
            f"\u00b7  {pop_info}  "
            f"\u00b7  bins: {n_bins}  \u00b7  MRL-arrow \u2265 {mrl_thresh}  "
            "\u00b7  radial scale: fraction of vectors per bin")

    # ── Statistics treeview ───────────────────────────────────────────────────

    def _update_stats_display(self):
        """Populate the statistics treeview from _last_datasets."""
        for item in self._stats_tree.get_children():
            self._stats_tree.delete(item)

        datasets = self._last_datasets
        if not datasets:
            return

        mode = self._stats_mode_var.get()

        # Read MRL threshold once — used for both significance tests and arrow
        try:
            mrl_thresh = float(self._mrl_thresh_var.get())
            if not np.isfinite(mrl_thresh) or not (0.0 <= mrl_thresh <= 1.0):
                return
        except ValueError:
            return

        if mode == 'merged':
            # Concatenate all angles and compute combined stats
            all_angles = np.concatenate(
                [a for a, _, _, _, _ in datasets if len(a) > 0])
            if len(all_angles) == 0:
                return
            stats = vector_direction_stats(
                all_angles,
                mrl_threshold=mrl_thresh,
            )
            self._stats_tree.insert(
                '', 'end',
                text='  All files merged',
                values=format_polar_stats_values(stats),
                open=False)
        else:
            # Per-file rows
            for fi, (angles, mags, label, color, path) in enumerate(datasets):
                name  = os.path.splitext(os.path.basename(path))[0]
                short = (name[:24] + '\u2026') if len(name) > 25 else name
                if len(angles) == 0:
                    self._stats_tree.insert(
                        '', 'end',
                        text=f'  {short}',
                        values=format_polar_stats_values(
                            vector_direction_stats(
                                angles,
                                mrl_threshold=mrl_thresh,
                            )))
                    continue
                stats = vector_direction_stats(
                    angles,
                    mrl_threshold=mrl_thresh,
                )
                tag      = f'fc{fi % _N_FILE_COLORS}'
                self._stats_tree.tag_configure(
                    tag, foreground=FILE_COLORS[fi % _N_FILE_COLORS])
                self._stats_tree.insert(
                    '', 'end',
                    text=f'  {short}',
                    values=format_polar_stats_values(stats),
                    tags=(tag,))

    # ── export ────────────────────────────────────────────────────────────────

    def _export_current(self):
        """Save the current figure. PDF/SVG are true vector output."""
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension='.pdf',
            initialfile='polar_analysis.pdf',
            filetypes=[("PDF", "*.pdf"), ("SVG", "*.svg"),
                       ("PNG", "*.png"), ("All", "*.*")])
        if not path:
            return
        try:
            save_figure(self._fig, path)
            messagebox.showinfo("Saved", f"Figure saved:\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("Save Error", str(e), parent=self)

    def _export_stats(self):
        import pandas as pd
        """
        Compute per-file vector statistics and save a CSV.
        Uses the corrected Rayleigh p-value (Zar 2010).
        Columns: File, Gate, Region, N_vectors, MRL, Rayleigh_p,
                 Mean_dir_deg, Significant, X_Ch1, Y_Ch1, X_Ch2, Y_Ch2,
                 Y_Coordinate_Orientation, Angle_Convention
        """
        try:
            mrl_thresh = float(self._mrl_thresh_var.get())
            if not np.isfinite(mrl_thresh) or not (0.0 <= mrl_thresh <= 1.0):
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Export Stats", "MRL threshold must be a finite value between 0 and 1.",
                parent=self)
            return

        active_all = self.app._active()
        visible_paths = set(self._get_active_paths())
        active = {p: df for p, df in active_all.items() if p in visible_paths}
        if not active:
            messagebox.showwarning(
                "Export Stats", "No visible files selected in Polar Analysis.", parent=self)
            return
        if not all([self._cx1_var.get(), self._cy1_var.get(),
                    self._cx2_var.get(), self._cy2_var.get()]):
            messagebox.showerror("Export Stats",
                "Please select all four coordinate columns.", parent=self)
            return

        path_out = filedialog.asksaveasfilename(
            parent=self,
            defaultextension='.csv',
            initialfile='polar_vector_stats.csv',
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path_out:
            return

        gate_lbl   = self._gate_var.get()
        region_lbl = self._region_var.get()
        rows = []

        for path, df in active.items():
            mask = self._get_population_mask(df, path)
            if mask is None:
                messagebox.showerror(
                    "Export Stats",
                    f"Selected gate cannot be evaluated for {os.path.basename(path)}. "
                    "Export cancelled rather than substituting All Cells.",
                    parent=self)
                return
            angles, mags = self._get_vectors_for_df(df, mask)
            fname        = os.path.basename(path)

            rows.append(build_polar_stats_export_row(
                file_name=fname,
                source_path=os.path.abspath(os.path.normpath(path)),
                gate=gate_lbl,
                region=region_lbl,
                angles=angles,
                mrl_threshold=mrl_thresh,
                x_ch1=self._cx1_var.get(),
                y_ch1=self._cy1_var.get(),
                x_ch2=self._cx2_var.get(),
                y_ch2=self._cy2_var.get(),
                y_coordinate_orientation=self._y_orientation_var.get(),
            ))

        if not rows:
            messagebox.showwarning("Export Stats", "No vector data.", parent=self)
            return

        try:
            pd.DataFrame(rows).to_csv(path_out, index=False)
            messagebox.showinfo("Export Stats",
                f"Stats saved ({len(rows)} file(s)):\n{path_out}", parent=self)
        except Exception as e:
            messagebox.showerror("Export Stats", str(e), parent=self)


def __getattr__(name: str):
    if name == "PolarAnalysisWindow":
        from vflow.legacy.vflow_legacy import PolarAnalysisWindow
        return PolarAnalysisWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["PolarAnalysisWindow", "PolarAnalysisWindowBase"]
