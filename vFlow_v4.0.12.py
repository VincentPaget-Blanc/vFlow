#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flow Cytometry Visualization Tool - v4.0.12
@author: vincentpb

Changelog v4.0.9 -> v4.0.12
---------------------------
BUG FIX
  1. Sub-gate tab: placing a gate no longer zooms out to full scale
       * After opening a sub-gate tab the data occupies only a small
         region of the full instrument range (e.g. 10^5-10^6 out of
         -10^5 to 10^6).  When a crosshair or shape gate was drawn,
         refresh_plot re-applied _set_axis_scale() which reset the
         view to the full biexp/asinh range, shrinking the visible
         population to a tiny speck in one corner.
       * Fix: _load_filtered now sets app.fit_axes_var = True for
         every sub-gate tab on creation.  The existing "Fit axes to
         data" logic (p0.5/p99.5 with 5% padding in transform space)
         already handles this perfectly -- it just was not enabled.
         The checkbox remains visible in the sidebar so the user can
         still disable it and see the full scale if needed.
       * No logic changes in refresh_plot or _set_axis_scale.

Changelog v4.0.8 -> v4.0.9
--------------------------
BUG FIX
  1. Sub-gate tab: changing X / Y axis now takes effect
       * _update_channel_menus replaced the combobox values list on every
         file-toggle but did NOT re-sync the StringVars when x_channel was
         already set (non-None).  On certain platforms a ttk readonly
         Combobox blanks its displayed text when its 'values' list is
         replaced even if the current value is still present in the new
         list.  As a result the combobox appeared correct but the internal
         StringVar was cleared, so Apply Axes had nothing to act on.
       * Fix: _update_channel_menus now always calls x_var.set(x_channel)
         / y_var.set(y_channel) after rebuilding the values list, keeping
         the displayed selection and the StringVar in sync at all times.
       * Additional: apply_axes now clears self._tc (transform cache)
         whenever the channel selection actually changes, preventing a
         stale cached transform from being served for the new columns.

IMPROVEMENTS
  2. Vector / Polar window: channel mapping UI regrouped by channel
       * The four centroid column selectors were ordered Y-Ch1, X-Ch1,
         Y-Ch2, X-Ch2 -- an axis-first layout that made it easy to
         accidentally assign Ch1 X to the Ch2 X slot.
       * Fix: selectors are now ordered Ch1-X, Ch1-Y, Ch2-X, Ch2-Y
         (channel-first) with a note stating "Direction: Ch1 -> Ch2;
         map X and Y separately for each channel."
       * The vector direction formula (dx = X_Ch2 - X_Ch1,
         dy = Y_Ch2 - Y_Ch1) is unchanged; the axis convention is now
         explicit in every label.

  3. Vector / Polar window: radial scale now explained in title and
     status bar
       * The polar rose plot radial axis was unlabelled.  It now states
         "Radial scale = fraction of vectors per bin" in the figure
         suptitle and the status bar, so it is clear that each bar
         height is a proportion (0-1) not a raw count.
       * The mean-direction arrow threshold is also shown inline:
         "Arrow shown when MRL >= <threshold>".

  4. Folder dialogs: last-used directory persisted within the session
       * Every askdirectory / askopenfilenames call opened the OS
         native picker at the home directory regardless of previous use.
       * Fix: a module-level _last_folder_dir string is updated whenever
         the user confirms a folder selection in FolderScanDialog,
         BatchExportDialog, or FlowApp.load_files.  Subsequent opens of
         any of those dialogs start at the same directory, eliminating
         repeated navigation across a session.

Changelog v4.0.7 -> v4.0.8
--------------------------
BUG FIXES (BatchPlotWindow only)
  1. Box plot: outlier dots now match their box colour
       * flierprops previously set a single fixed colour (T['fg_dim']) for
         all outlier points regardless of which sample they belonged to.
       * Fix: after boxplot() returns, each bp['fliers'][i] element is
         updated with colors_ordered[i] so outlier dots are coloured
         identically to their parent box.

  2. Strip / "points only" view: y-axis scale no longer shifts between
     renders
       * _get_rng(42) returns a cached, stateful Generator -- calling it
         across multiple renders advanced its internal state, producing
         different subsample indices and jitter values each time, which
         caused matplotlib to autoscale to a different data range every
         render.
       * Fix: the strip-plot block now creates a local
         np.random.default_rng(42) each time _render_figure() is called
         so subsampling and jitter are identical on every redraw.
       * Additional fix: y-limits are explicitly set from the full data
         range (not the subsample) before scatter() is called, so the
         axis scale is pinned and cannot drift.

  3. Stacked bar legend no longer overlaps bars
       * Legend was drawn at loc='upper right' inside the axes bounding
         box, covering the tallest bars.
       * Fix: legend is now anchored outside the axes at
         bbox_to_anchor=(1.01, 1.0) with loc='upper left', and the
         figure right margin is reduced (right=0.82 / 0.87) to leave
         room for the legend panel.

PERFORMANCE (BatchPlotWindow)
  4. _compute_and_plot: halved gate-mask computation per sample
       * Previously _get_population_mask and _get_region_pcts_and_n each
         called self.app._gate_mask_for independently -- two full gate
         evaluations per sample.
       * Fix: _compute_and_plot now calls _gate_mask_for exactly once per
         sample, builds the population mask and the region-pct dict from
         that single result, and accumulates the SEM cache inline.
         _get_population_mask and _get_region_pcts_and_n are retained as
         helpers for other callers but are no longer invoked from the
         hot compute path.


Changelog v4.0.5 -> v4.0.6
--------------------------
BUG FIXES
  1. BatchPlotWindow: per-bar binomial SEM for stacked population chart
       • _pop_sem_cache previously stored one SEM per region computed as
         std(all_samples)/sqrt(n_samples) — a global cross-sample aggregate
         drawn identically on every bar regardless of sample size.
       • Fix: SEM is now computed per bar as the binomial standard error
         sqrt(p*(1-p)/n) where p is that sample's proportion and n is its
         cell count.  Stored as {(label, region_name): sem_pct} so each bar
         carries its own uncertainty estimate.
       • _get_region_pcts_and_n() added to return (pct, n_total) pairs;
         _get_region_pcts() now wraps it for backward compatibility.

  2. BatchPlotWindow: staggered x-axis label misalignment (properly fixed)
       • The custom annotate-based _draw_staggered_xlabels helper mixed
         data-space x coordinates with axes-space y offsets expressed in
         points.  This coordinate-space mismatch caused labels to drift
         away from their tick marks depending on figure size, DPI, and
         label length — ha='right' or ha='center' both produced incorrect
         placement.
       • Fix: replaced the entire custom helper with _set_rotated_xlabels,
         which calls the standard ax.set_xticklabels(labels, rotation=45,
         ha='right', rotation_mode='anchor').  This pins the top-right
         corner of each label exactly at its tick mark — the canonical
         matplotlib approach that is robust to any figure size or label
         length.
       • bottom_margin increased from 0.32 → 0.38 to give rotated labels
         sufficient vertical clearance.

  2. BatchPlotWindow: removed Zoom X / Zoom Y toolbar
       • The zoom buttons (−/+/Reset for both axes) have been removed
         from the batch-plot panel.  The scrollable canvas already
         provides panning; the zoom controls were non-intuitive and
         cluttered the toolbar.  Internal _zoom_x / _zoom_y variables
         are retained at their default value (1.0) so _render_figure
         is unchanged.

Changelog v4.0.1 → v4.0.4
──────────────────────────
Dead code removed (10 methods, 105 lines):
  • _plot_gated            — superseded by _plot_gated_multi; never called
  • _compute_gate_stats    — thin wrapper around _compute_gate_stats_for; never called
  • _new_thresh_vars       — never called (BooleanVars created inline)
  • _new_y_thresh_var      — never called
  • _gate_mask             — convenience alias for _gate_mask_for; never called
  • _gate_mask_for_id      — backward-compat alias; _open_subgate uses _gate_mask_for directly
  • _region_display_name   — never called (region names built inline in _region_masks)
  • _collect_2d_transform  — was for 2-D GMM path (removed in v4.0.0); never called
  • _deepest_gmm_threshold — same; never called
  • BatchPlotWindow._refresh_display — defined but never wired to any control

Changelog v4.0.0 → v4.0.0
──────────────────────────
NEW FEATURES
  1. Distribution Analysis window (DistributionWindow)
       • Dedicated Toplevel for 1-D intensity and distance distributions.
       • Works on individual files or pooled (concatenated) data — toggled
         via a "Pool all checked files" checkbox.
       • Columns auto-detected (Intensity / Distance keywords); all numeric
         columns are available for manual multi-selection (up to 6).
       • Gate + region filtering: same gate/region dropdowns as PolarWindow,
         using the exact same _get_population_mask logic.
       • Per-file colour coding matches the scatter view.
       • KDE curve overlay, gate threshold shading, descriptive stats table
         (n, mean, median, std, CV%, p5, p95).
       • Export figure (PDF/PNG/SVG) and export stats → CSV.

  2. Histogram Analysis window (HistogramAnalysisWindow) [introduced v4.0.0]
       • 1-D histogram for the selected X / Y channels.
       • Pool files toggle, population band shading, GMM curve overlay.

  3. Population shading on marginal histograms for KDE / Otsu gates.

REMOVED
  1. "Mixed (GMM X + KDE Y)" auto-gate button and method.
     GMM Multi, KDE Valley, Otsu, and Cluster Polygons are unchanged.

Changelog v3.9.2 → v3.9.3
──────────────────────────
BUG FIXES
  1. Region % labels on plot not appearing after gating
       • _draw_region_labels() was called BEFORE _set_axis_scale().
         Moving it to AFTER ensures the custom axis transform (asinh /
         biexp / logicle) is fully in place when label positions are
         resolved, preventing clipping or misplacement caused by the
         axis autoscale range being recalculated for the new scale type.
       • Added an unconditional canvas.draw_idle() at the very end of
         refresh_plot so every code path (no gate, gate but labels off,
         gate + labels) flushes exactly once after all changes.
       • Wrapped _draw_region_labels call in try/except so a label
         error can never crash the full plot refresh.

  2. Polar analysis: X/Y centroid columns not loading from gated population
       • _get_population_mask in PolarAnalysisWindow passed _cache_path
         to _gate_mask_for.  The gate-mask cache was built against the
         full-file DataFrame; if the polar window operated on a filtered
         (sub-gate) DataFrame the cached boolean arrays had a different
         length, raising an exception that was silently swallowed, causing
         the gate filter to be ignored (all cells used instead).
       • Fix: _get_population_mask no longer passes _cache_path — it
         always triggers a fresh, correct computation.
       • Additional safety: _gate_mask_for now validates cached mask length
         before using it; a length mismatch forces a recompute.

  3. _clear_preview() called canvas.draw_idle() prematurely
       • _clear_preview is invoked at the very start of _preview_gate(),
         which is itself called early in refresh_plot (before gate outlines,
         labels, scale, and limits are set).  The premature draw_idle()
         could fire a repaint while the canvas was still in an incomplete
         state.  Removed draw_idle() from _clear_preview(); all interactive
         callers of _preview_gate() already issued their own draw_idle().

  4. _auto_detect_channels improvements
       • Removed duplicate startswith condition (case-insensitive check
         already subsumed the case-sensitive one).
       • StringVars are now cleared before re-detection so stale column
         names from a previous session do not survive if detection fails.
       • Combo value lists are updated BEFORE var.set() to avoid the
         ttk readonly-Combobox display glitch where a new value is not
         shown until the widget is interacted with.
       • Added fallback detection for 'centroid_x'/'centroid_y' naming
         conventions used by some analysis pipelines.
"""

import os
import sys
import functools
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ── Splash screen — shown BEFORE heavy imports so the user sees feedback ──────
# matplotlib, numpy, scipy each take ~0.5-2 s to import on first launch.
# By starting the splash here we show progress during that dead time.
if __name__ == '__main__':
    try:
        from vflow_splash import SplashScreen as _SplashScreen
        _splash = _SplashScreen(version="4.0.12", total_steps=7)
    except Exception:
        _splash = None

# ── Heavy imports (each one advances the splash bar) ─────────────────────────
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.lines as mlines
# Use Figure directly — avoids pyplot registering a second window
from matplotlib.figure import Figure
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.scale import ScaleBase
from matplotlib.transforms import Transform
from matplotlib import scale as mscale
from matplotlib.ticker import FuncFormatter, FixedLocator
from matplotlib.path import Path as MplPath
from matplotlib.patches import Rectangle as MplRect, Ellipse as MplEllipse
if __name__ == '__main__' and _splash: _splash.step("matplotlib")

import copy
import numpy as np
if __name__ == '__main__' and _splash: _splash.step("numpy")

import pandas as pd
if __name__ == '__main__' and _splash: _splash.step("pandas")

from scipy.stats import gaussian_kde
from scipy.signal import savgol_filter
from scipy.interpolate import RegularGridInterpolator
if __name__ == '__main__' and _splash: _splash.step("scipy")

try:
    from sklearn.mixture import GaussianMixture
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
if __name__ == '__main__' and _splash: _splash.step("scikit-learn")

# ─────────────────────────────────────────────────────────────────────────────
#  Theme palettes
# ─────────────────────────────────────────────────────────────────────────────

THEMES = {
    'dark': {
        'sidebar_bg': '#2b2b2b',
        'plot_bg':    '#1e1e1e',
        'fg':         '#e0e0e0',
        'fg_dim':     '#aaaaaa',
        'header_bg':  '#3c3f41',
        'field_bg':   '#3c3f41',
        'sel_bg':     '#3c7fbd',
        'trough':     '#3c3f41',
        'entry_ins':  '#e0e0e0',
        'fig_bg':     '#1e1e1e',
        'ax_bg':      '#1e1e1e',
        'spine':      '#555555',
        'grid':       '#888888',
        'gate_line':  'white',
        'legend_bg':  '#333333',
        'label_box':  '#111111',
        'label_txt':  'white',
    },
    'light': {
        'sidebar_bg': '#f2f2f2',
        'plot_bg':    '#ffffff',
        'fg':         '#111111',
        'fg_dim':     '#555555',
        'header_bg':  '#d8d8d8',
        'field_bg':   '#ffffff',
        'sel_bg':     '#3c7fbd',
        'trough':     '#cccccc',
        'entry_ins':  '#111111',
        'fig_bg':     '#ffffff',
        'ax_bg':      '#ffffff',
        'spine':      '#aaaaaa',
        'grid':       '#cccccc',
        'gate_line':  '#222222',
        'legend_bg':  '#f8f8f8',
        'label_box':  '#eeeeee',
        'label_txt':  '#111111',
    },
}

# ─────────────────────────────────────────────────────────────────────────────
#  ttk style configurator
# ─────────────────────────────────────────────────────────────────────────────

def _apply_ttk_style(T: dict):
    style = ttk.Style()
    try:
        style.theme_use('clam')
    except Exception:
        pass

    BG  = T['sidebar_bg']
    FG  = T['fg']
    DIM = T['fg_dim']
    SEL = T['sel_bg']
    FLD = T['field_bg']
    HDR = T['header_bg']
    TRO = T['trough']

    style.configure('.', background=BG, foreground=FG,
                    troughcolor=TRO, selectbackground=SEL,
                    selectforeground=FG, fieldbackground=FLD,
                    insertcolor=T['entry_ins'], relief='flat')

    style.configure('TButton', background=HDR, foreground=FG,
                    padding=(6, 3), relief='flat', font=('Arial', 8))
    style.map('TButton',
              background=[('active', SEL), ('pressed', '#2a70b9')],
              foreground=[('active', FG)])

    for name, bg, hover in [
        ('Accent.TButton',   '#4a90d9', '#6aaaf9'),
        ('Green.TButton',    '#3a7d3a', '#4a9d4a'),
        ('Blue2.TButton',    '#3a5f8a', '#4a7faa'),
        ('Purple.TButton',   '#7b5ea7', '#9b7ec7'),
        ('Orange.TButton',   '#b05e3e', '#d07e5e'),
        ('Teal.TButton',     '#2a7d7d', '#3a9d9d'),
        ('Cyan.TButton',     '#1a6b7a', '#2a8b9a'),
        ('Indigo.TButton',   '#3949ab', '#5c6bc0'),
        ('Brown.TButton',    '#6d4c41', '#8d6e63'),
        ('Olive.TButton',    '#5d7a2a', '#7a9d3a'),
        ('Gray.TButton',     '#666666', '#888888'),
        ('DarkBlue.TButton', '#3a6fa8', '#5a8fc8'),
    ]:
        style.configure(name, background=bg, foreground='white',
                        font=('Arial', 8), relief='flat', padding=(6, 3))
        style.map(name, background=[('active', hover), ('pressed', bg)])

    style.configure('TCombobox',
                    background=FLD, foreground=FG,
                    fieldbackground=FLD, selectbackground=SEL,
                    selectforeground=FG, arrowcolor=FG, font=('Arial', 8))
    style.map('TCombobox',
              fieldbackground=[('readonly', FLD)],
              foreground=[('readonly', FG)],
              selectbackground=[('readonly', SEL)])

    style.configure('TScrollbar',
                    background=HDR, troughcolor=BG,
                    arrowcolor=FG, relief='flat')

    tree_bg = T['plot_bg']
    style.configure('Treeview',
                    background=tree_bg, foreground=FG,
                    fieldbackground=tree_bg,
                    rowheight=18, font=('Arial', 7))
    style.configure('Treeview.Heading',
                    background=HDR, foreground=FG,
                    font=('Arial', 7, 'bold'))
    style.map('Treeview',
              background=[('selected', SEL)],
              foreground=[('selected', 'white')])

    for w in ('TCheckbutton', 'TRadiobutton'):
        style.configure(w, background=BG, foreground=FG, font=('Arial', 8))
        style.map(w, background=[('active', BG)], foreground=[('active', FG)])

    style.configure('TFrame',         background=BG)
    style.configure('TLabel',         background=BG, foreground=FG,  font=('Arial', 8))
    style.configure('Section.TLabel', background=HDR, foreground=DIM, font=('Arial', 9, 'bold'))
    style.configure('Dim.TLabel',     background=BG, foreground=DIM, font=('Arial', 7))
    style.configure('Mono.TLabel',    background=BG, foreground=FG,  font=('Courier', 8))

    # ── Notebook tab styling (dark/light aware) ──
    style.configure('TNotebook',
                    background=BG, tabmargins=[2, 4, 0, 0])
    style.configure('TNotebook.Tab',
                    background=HDR, foreground=FG,
                    padding=[10, 4], font=('Arial', 8))
    style.map('TNotebook.Tab',
              background=[('selected', BG),   ('active', SEL)],
              foreground=[('selected', FG),   ('active', FG)])

    # Close-button label inside sub-gate tab header bars
    style.configure('Close.TLabel', background=HDR, foreground=DIM,
                    font=('Arial', 9, 'bold'), padding=[4, 2])
    style.map('Close.TLabel', foreground=[('active', '#ff6b6b')])

    style.configure('Red.TButton', background='#922', foreground='white',
                    font=('Arial', 8), relief='flat', padding=(6, 3))
    style.map('Red.TButton', background=[('active', '#c33')])

    style.configure('TEntry',
                    fieldbackground=FLD, foreground=FG,
                    insertcolor=T['entry_ins'], font=('Arial', 8))
    return style


# ─────────────────────────────────────────────────────────────────────────────
#  Custom flow-cytometry scales
# ─────────────────────────────────────────────────────────────────────────────

_FLOW_TICKS = [-1_000_000, -100_000, -10_000, -1_000, -100, 0,
                100, 1_000, 10_000, 100_000, 1_000_000]
_FLOW_LABELS = ['-10⁶', '-10⁵', '-10⁴', '-10³', '-10²', '0',
                '10²', '10³', '10⁴', '10⁵', '10⁶']
_TICK_MAP = dict(zip(_FLOW_TICKS, _FLOW_LABELS))

def _flow_fmt(x, pos):
    if x in _TICK_MAP: return _TICK_MAP[x]
    if x == 0: return '0'
    ax = abs(x)
    if ax >= 1e4:
        exp = int(round(np.log10(ax)))
        return f'-10{exp}' if x < 0 else f'10{exp}'
    return f'{int(x)}'

class _FlowScale(ScaleBase):
    def set_default_locators_and_formatters(self, axis):
        axis.set_major_locator(FixedLocator(_FLOW_TICKS))
        axis.set_major_formatter(FuncFormatter(_flow_fmt))
        axis.set_minor_locator(mticker.NullLocator())

class BiexpScale(_FlowScale):
    name = 'biexp'
    def __init__(self, axis, **kw):
        super().__init__(axis); self.thresh = kw.pop('threshold', 1.0)
    def get_transform(self): return self._T(self.thresh)
    class _T(Transform):
        input_dims = output_dims = 1
        def __init__(self, t): Transform.__init__(self); self.t = t
        def transform_non_affine(self, a):
            return np.sign(a) * np.log1p(np.abs(a) / self.t) * self.t
        def inverted(self): return BiexpScale._Ti(self.t)
    class _Ti(Transform):
        input_dims = output_dims = 1
        def __init__(self, t): Transform.__init__(self); self.t = t
        def transform_non_affine(self, a):
            return np.sign(a) * (np.exp(np.abs(a) / self.t) - 1) * self.t
        def inverted(self): return BiexpScale._T(self.t)

class AsinhScale(_FlowScale):
    name = 'asinh'
    def __init__(self, axis, **kw):
        super().__init__(axis); self.cofactor = kw.pop('cofactor', 150.0)
    def get_transform(self): return self._T(self.cofactor)
    class _T(Transform):
        input_dims = output_dims = 1
        def __init__(self, c): Transform.__init__(self); self.c = c
        def transform_non_affine(self, a): return np.arcsinh(a / self.c)
        def inverted(self): return AsinhScale._Ti(self.c)
    class _Ti(Transform):
        input_dims = output_dims = 1
        def __init__(self, c): Transform.__init__(self); self.c = c
        def transform_non_affine(self, a): return np.sinh(a) * self.c
        def inverted(self): return AsinhScale._T(self.c)

class LogicleScale(_FlowScale):
    name = 'logicle'
    def __init__(self, axis, **kw):
        super().__init__(axis); self.cofactor = kw.pop('cofactor', 150.0)
    def get_transform(self): return self._T(self.cofactor)
    class _T(Transform):
        input_dims = output_dims = 1
        def __init__(self, c): Transform.__init__(self); self.c = c
        def transform_non_affine(self, a):
            return np.sign(a) * np.log10(1.0 + np.abs(a) / self.c)
        def inverted(self): return LogicleScale._Ti(self.c)
    class _Ti(Transform):
        input_dims = output_dims = 1
        def __init__(self, c): Transform.__init__(self); self.c = c
        def transform_non_affine(self, a):
            return np.sign(a) * (10 ** np.abs(a) - 1.0) * self.c
        def inverted(self): return LogicleScale._T(self.c)

for _cls in (BiexpScale, AsinhScale, LogicleScale):
    try: mscale.register_scale(_cls)
    except Exception: pass

ALL_SCALES = ['linear', 'log', 'biexp', 'asinh', 'logicle']

# ─────────────────────────────────────────────────────────────────────────────
#  Performance helpers
# ─────────────────────────────────────────────────────────────────────────────

def _hex_to_rgba(hex_color: str, alpha: float) -> np.ndarray:
    """Convert a '#rrggbb' hex string to a (4,) float32 RGBA array.
    Result is cached: same (color, alpha) → same array object reused."""
    return _HEX_RGBA_CACHE(hex_color, alpha)

@functools.lru_cache(maxsize=256)
def _hex_to_rgba_cached(hex_color: str, alpha: float) -> np.ndarray:
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    arr = np.array([r, g, b, float(alpha)], dtype=np.float32)
    arr.flags.writeable = False   # make immutable so callers can't corrupt cache
    return arr

# Alias used everywhere — thin wrapper that returns immutable cached array.
# Callers that need a mutable copy (rgba[:] = ...) do arr.copy() implicitly
# when they assign into a slice.
_HEX_RGBA_CACHE = _hex_to_rgba_cached

# ── Module-level RNG singletons ───────────────────────────────────────────────
# np.random.default_rng() allocates a PCG64 state object (~5µs each).
# Creating one per render call across 8 hot-path sites wastes meaningful time.
# Fixed seeds → reproducible subsampling; dict lookup replaces allocation.
_RNG: dict = {}

def _get_rng(seed: int) -> np.random.Generator:
    """Return a cached Generator for *seed*. Creates once, reuses thereafter."""
    if seed not in _RNG:
        _RNG[seed] = np.random.default_rng(seed)
    return _RNG[seed]


def _gate_sig(gate: dict) -> int:
    """
    Return a stable integer hash of the gate's geometric parameters.
    Changes whenever thresholds, vertices, or active-flags change.
    Used as part of the persistent gate-mask cache key so stale entries
    are naturally bypassed without explicit invalidation.

    BUG FIXED (v3.9.3 → v3.9.4):
    The original implementation read gate.get('x_thresh_active', []),
    gate.get('y_thresh_active', True) and gate.get('y_thresh_actives', []).
    Those keys are the *serialised* names used in save/load JSON.  Live gate
    dicts store threshold toggle state in BooleanVar objects under the keys
    x_thresh_vars, y_thresh_var and y_thresh_vars — meaning the toggle state
    was NEVER included in the cache key.  Two consequences:
      1. tuple(gate.get('y_boundaries', [])) crashed with TypeError when
         y_boundaries=None (its initial value in _add_gate), because the key
         exists in the dict with value None so .get() returns None rather
         than the [] default, and tuple(None) raises TypeError.  That
         TypeError silently aborted _finish_gate() at _compute_gate_stats_for
         so the stats panel stayed empty, the plot was never refreshed, and
         the gate-manager row was never rebuilt.
      2. Toggling a threshold checkbox left the stale cached mask in _gmc
         (same hash) so stats and cell colours did not update.
    The fix reads BooleanVar.get() for live gates and falls back to plain
    bool for serialised gates.  All tuple() calls are guarded against None.
    """
    gt = gate.get('type', 'crosshair')
    if gt == 'crosshair':
        # ── X threshold active-state ──────────────────────────────────────
        x_tvs = gate.get('x_thresh_vars') or []
        if x_tvs:
            try:
                x_ta = tuple(bool(v.get()) for v in x_tvs)
            except AttributeError:
                x_ta = tuple(bool(v) for v in x_tvs)
        else:
            x_ta = tuple(bool(v) for v in (gate.get('x_thresh_active') or []))

        # ── Y threshold active-state (single) ─────────────────────────────
        ytv = gate.get('y_thresh_var')
        if ytv is not None:
            try:
                y_ta = bool(ytv.get())
            except AttributeError:
                y_ta = bool(ytv)
        else:
            y_ta = bool(gate.get('y_thresh_active', True))

        # ── Y threshold active-state (multi-valley) ───────────────────────
        y_tvs = gate.get('y_thresh_vars') or []
        if y_tvs:
            try:
                y_tas = tuple(bool(v.get()) for v in y_tvs)
            except AttributeError:
                y_tas = tuple(bool(v) for v in y_tvs)
        else:
            y_tas = tuple(bool(v) for v in (gate.get('y_thresh_actives') or []))

        # guard: y_boundaries may be None for single-Y crosshair gates
        y_boundaries = gate.get('y_boundaries') or []

        key = (gt,
               tuple(gate.get('x_boundaries') or []),
               gate.get('y_boundary'),
               x_ta,
               y_ta,
               tuple(y_boundaries),
               y_tas)
    elif gt in ('rectangle', 'ellipse'):
        key = (gt,
               gate.get('x0'), gate.get('y0'),
               gate.get('x1'), gate.get('y1'))
    elif gt == 'polygon':
        key = (gt, tuple(tuple(v) for v in (gate.get('vertices') or [])))
    else:
        key = (gt,)
    return hash(key)


# ─────────────────────────────────────────────────────────────────────────────
#  Pure-Python FCS reader (no external dependencies)
#  Supports FCS 2.0, 3.0, 3.1 — list-mode (L), float/double/integer data.
# ─────────────────────────────────────────────────────────────────────────────

def read_fcs(path: str):
    """
    Read an FCS file and return (DataFrame, metadata_dict).

    Column names prefer $PnS (stain/marker name, e.g. "TH-488") over
    $PnN (short technical name, e.g. "FITC-A").  Falls back to "Ch{n}".

    Handles:
      - FCS 2.0 / 3.0 / 3.1
      - DATATYPE F (float32), D (float64), I (integer, 8/16/32-bit)
      - Big-endian and little-endian byte order
      - $PnE log-decade encoding for integer data
      - $BEGINDATA / $ENDDATA override for non-standard writers
    """
    with open(path, 'rb') as f:
        raw = f.read()

    version = raw[:6].decode('ascii', errors='replace').strip()
    if not version.startswith('FCS'):
        raise ValueError(f"Not a valid FCS file — header: {version!r}")

    def _hdr_int(b):
        s = b.decode('ascii', errors='replace').strip()
        return int(s) if s else 0

    text_start = _hdr_int(raw[10:18])
    text_end   = _hdr_int(raw[18:26])
    data_start = _hdr_int(raw[26:34])
    data_end   = _hdr_int(raw[34:42])

    # ── Parse TEXT segment ────────────────────────────────────────────────
    text_raw = raw[text_start:text_end + 1].decode('latin-1', errors='replace')
    if not text_raw:
        raise ValueError("FCS TEXT segment is empty")
    delim    = text_raw[0]
    parts    = text_raw[1:].split(delim)
    if parts and parts[-1] == '':
        parts = parts[:-1]
    meta: dict = {}
    for i in range(0, len(parts) - 1, 2):
        meta[parts[i].strip().upper()] = parts[i + 1]

    n_params = int(meta.get('$PAR', '0'))
    if n_params == 0:
        raise ValueError("FCS file reports 0 parameters ($PAR=0)")

    # ── Channel names (prefer $PnS stain label) ───────────────────────────
    channels = []
    seen: dict = {}
    for i in range(1, n_params + 1):
        short = meta.get(f'$P{i}N', f'Ch{i}').strip()
        stain = meta.get(f'$P{i}S', '').strip()
        name  = stain if stain else short
        # Deduplicate
        if name in seen:
            seen[name] += 1
            name = f'{name}_{seen[name]}'
        else:
            seen[name] = 0
        channels.append(name)

    # ── Locate DATA segment ($BEGINDATA / $ENDDATA override header) ───────
    if '$BEGINDATA' in meta:
        try: data_start = int(meta['$BEGINDATA'])
        except ValueError: pass
    if '$ENDDATA' in meta:
        try: data_end = int(meta['$ENDDATA'])
        except ValueError: pass

    # ── Determine dtype ───────────────────────────────────────────────────
    data_type  = meta.get('$DATATYPE', 'F').upper()
    byte_order = meta.get('$BYTEORD', '1,2,3,4').strip()
    big_endian = byte_order.startswith('4')
    endian     = '>' if big_endian else '<'

    if data_type == 'F':
        dtype = endian + 'f4'; bpp = 4
    elif data_type == 'D':
        dtype = endian + 'f8'; bpp = 8
    elif data_type == 'I':
        max_bits = max(int(meta.get(f'$P{i}B', '32')) for i in range(1, n_params + 1))
        if   max_bits <=  8: dtype = endian + 'u1'; bpp = 1
        elif max_bits <= 16: dtype = endian + 'u2'; bpp = 2
        else:                dtype = endian + 'u4'; bpp = 4
    else:
        raise ValueError(f"Unsupported FCS $DATATYPE: {data_type!r}")

    # ── Read DATA ─────────────────────────────────────────────────────────
    total_events = int(meta.get('$TOT', '0'))
    data_bytes   = raw[data_start:data_end + 1] if data_end > data_start else raw[data_start:]
    row_bytes    = n_params * bpp
    if row_bytes > 0:
        n_fit = len(data_bytes) // row_bytes
        if total_events == 0 or n_fit < total_events:
            total_events = n_fit

    arr = np.frombuffer(data_bytes[:total_events * row_bytes],
                        dtype=np.dtype(dtype)).reshape(total_events, n_params).astype(np.float64)

    # ── Apply $PnE (log-decade) scaling for integer channels ─────────────
    if data_type == 'I':
        for i in range(n_params):
            pne = meta.get(f'$P{i+1}E', '0,0')
            try:
                f1, f2 = (float(x) for x in pne.split(','))
                rng    = float(meta.get(f'$P{i+1}R', '1024'))
                if f1 > 0 and rng > 0:
                    arr[:, i] = 10.0 ** (f1 * arr[:, i] / rng) * (f2 if f2 else 1.0)
            except Exception:
                pass

    return pd.DataFrame(arr, columns=channels), meta


GATE_PALETTE = [
    '#ff6b6b', '#ffd93d', '#6bcb77', '#4d96ff',
    '#ff9a3c', '#c77dff', '#ff6bcd', '#4ecdc4',
]
HANDLE_PX   = 12   # handle hit-test radius (pixels)
HANDLE_SZ   = 70   # matplotlib marker size² for handle dots

FILE_COLORS = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
]
# Session-persistent last-used folder for all askdirectory dialogs.
_last_folder_dir: str = ''
REGION_COLORS = [
    '#e41a1c', '#377eb8', '#4daf4a', '#ff7f00',
    '#984ea3', '#a65628', '#f781bf', '#aaaaaa',
    '#66c2a5', '#fc8d62', '#8da0cb', '#e78ac3',
    '#a6d854', '#ffd92f', '#e5c494', '#b3b3b3',
]
KDE_SUBSAMPLE = 30_000   # max pts used to FIT a KDE (auto-gating + density)
RENDER_CAP    = 50_000   # max pts DRAWN per file (stats always on full data)
# Gate-mask cache: bound size to prevent unbounded growth over long sessions
_GMC_MAX      = 400      # max entries in persistent gate-mask cache

# ─────────────────────────────────────────────────────────────────────────────
#  Auto-gating helpers
# ─────────────────────────────────────────────────────────────────────────────

def gmm_thresholds(data: np.ndarray, max_components: int = 3) -> list:
    """
    BIC-best 1D GMM → valley thresholds between adjacent components.

    Operates in transform (display) space.  Key design choices:
    - max_components capped at 3 by default — 4 components overfits tails
      of typical bimodal flow distributions and generates spurious thresholds.
    - Subsamples to GMM_MAX_FIT points for speed on large datasets.
    - Valley search widened to 3σ each side (catches asymmetric distributions).
    """
    if not HAS_SKLEARN:
        raise RuntimeError("scikit-learn required: pip install scikit-learn")
    data = data[np.isfinite(data)]
    if len(data) < 10: return []

    # Subsample for speed — GMM result is statistically stable at 30k points
    GMM_MAX_FIT = 30_000
    if len(data) > GMM_MAX_FIT:
        rng = _get_rng(42)
        data = data[rng.choice(len(data), GMM_MAX_FIT, replace=False)]
    data = data.reshape(-1, 1)

    best_bic, best_gmm, best_n = np.inf, None, 1
    for n in range(1, max_components + 1):
        try:
            g = GaussianMixture(n_components=n, n_init=5,
                                covariance_type='full', random_state=42)
            g.fit(data)
            b = g.bic(data)
            if b < best_bic: best_bic, best_gmm, best_n = b, g, n
        except Exception: pass
    if best_n == 1 or best_gmm is None: return []

    order   = np.argsort(best_gmm.means_.flatten())
    means   = best_gmm.means_.flatten()[order]
    weights = best_gmm.weights_[order]
    stds    = np.sqrt(best_gmm.covariances_[order][:, 0, 0])
    from scipy.stats import norm as _norm
    thresholds = []
    for i in range(best_n - 1):
        # Widen search to 3σ each side to catch asymmetric distributions
        lo_x = means[i]     - 3 * stds[i]
        hi_x = means[i + 1] + 3 * stds[i + 1]
        x    = np.linspace(lo_x, hi_x, 2000)
        dens = sum(weights[j] * _norm.pdf(x, means[j], stds[j])
                   for j in range(best_n))
        # Search for density minimum between the two means (not outside them)
        lo_idx = int(np.searchsorted(x, means[i]))
        hi_idx = int(np.searchsorted(x, means[i + 1]))
        if hi_idx > lo_idx:
            thresholds.append(float(x[lo_idx + np.argmin(dens[lo_idx:hi_idx])]))
        else:
            thresholds.append(float((means[i] + means[i + 1]) / 2.0))
    return thresholds


def derivative_threshold(data: np.ndarray, min_prominence: float = 5.0,
                         bw_factor: float = 1.0,
                         min_peak_frac: float = 0.01) -> float:
    """
    Find the gate threshold separating two populations via KDE valley detection.

    bw_factor scales Scott's bandwidth: <1.0 narrows the KDE (resolves closely
    spaced populations); >1.0 broadens it (smoother, ignores small gaps).
    At high sensitivity, passing bw_factor≈0.4 is the most impactful change
    for resolving flow populations that are close together on a log/biexp scale.
    
    typical). The function then fell back to the 3rd percentile, which is the
    middle of the negative cloud, not the separation point.

    New strategy — no hard percentage constraints:
    1. Compute a smoothed KDE over the (already-transformed) data.
    2. Find ALL local maxima (peaks) and minima (valleys) via sign changes of
       the first derivative.
    3. A valley is "valid" when it has at least one genuine KDE peak on both
       its left and right AND both surrounding peaks are ≥5× taller than the
       valley depth (ensures the valley represents a real gap, not a shoulder).
    4. Return the x-coordinate of the DEEPEST valid valley.
    5. Fallback for unimodal distributions: walk left from the main peak until
       the KDE drops to 15 % of its peak height (estimates the left edge of
       the bulk distribution, a reasonable single-population gate).
    """
    data = data[np.isfinite(data)]
    if len(data) < 10:
        return float(np.percentile(data, 10))

    # Subsample for speed — KDE is stable above ~10k; fitting on 100k is slow
    _KDE_MAX = 30_000
    if len(data) > _KDE_MAX:
        data = data[_get_rng(7).choice(len(data), _KDE_MAX, replace=False)]

    kde = gaussian_kde(data, bw_method='scott')
    if bw_factor != 1.0:
        kde.set_bandwidth(bw_method=kde.factor * bw_factor)
    x   = np.linspace(data.min(), data.max(), 2048)
    y   = kde(x)
    win = min(51, max(5, (len(y) // 10) | 1))
    y_s = savgol_filter(y, window_length=win, polyorder=3)
    dy  = np.gradient(y_s, x)
    peak_val = float(np.max(y_s))

    # All local maxima and minima (unfiltered — let the geometry decide)
    peak_idx_all   = np.where(np.diff(np.sign(dy)) < 0)[0]
    valley_idx_all = np.where(np.diff(np.sign(dy)) > 0)[0]

    valid_valleys = []
    for vi in valley_idx_all:
        left_peaks  = peak_idx_all[peak_idx_all < vi]
        right_peaks = peak_idx_all[peak_idx_all > vi]
        if len(left_peaks) == 0 or len(right_peaks) == 0:
            continue
        vdepth = max(float(y_s[vi]), 1e-12)
        li     = left_peaks [np.argmax(y_s[left_peaks ])]
        ri     = right_peaks[np.argmax(y_s[right_peaks])]
        lbest  = float(y_s[li])
        rbest  = float(y_s[ri])
        # Both flanking peaks must be substantially higher than the valley
        if (lbest >= min_prominence * vdepth and rbest >= min_prominence * vdepth
                and lbest >= min_peak_frac * peak_val and rbest >= min_peak_frac * peak_val):
            # Score: distance from the midpoint between the two flanking peaks.
            # Picking the valley CLOSEST to the midpoint gives the most natural
            # biological threshold — centred in the gap between populations.
            # This is deterministic and avoids the numerical floor problem where
            # many valleys in a completely empty region all have vdepth ≈ 0.
            midpt      = (float(x[li]) + float(x[ri])) / 2.0
            dist_mid   = abs(float(x[vi]) - midpt)
            valid_valleys.append((vi, dist_mid))

    if valid_valleys:
        best_vi = min(valid_valleys, key=lambda t: t[1])[0]
        return float(x[best_vi])

    # Fallback: unimodal — walk left from main peak to 5 % of peak height
    # (was 15 % — reduced so we sit closer to the true negative/positive boundary)
    main_peak = int(np.argmax(y_s))
    level = 0.05 * peak_val
    for i in range(main_peak - 1, -1, -1):
        if y_s[i] <= level:
            return float(x[i])
    return float(np.percentile(data, 5))



def otsu_threshold(data: np.ndarray, n_bins: int = 512,
                   min_class_fraction: float = 0.0) -> float:
    """
    Otsu threshold in transform space — maximises between-class variance.

    Minimises the weighted sum of within-class variances across all binary
    splits of the histogram.  O(n_bins) after one histogram build — much
    faster than GMM.  No distributional assumptions (works for any bimodal
    shape).  Reliable for 20/80 to 80/20 population splits; less reliable
    for very unequal splits (5/95) where derivative_threshold is better.

    min_class_fraction: skip splits where the smaller class has fewer than
    this fraction of total cells.  Sensitivity slider increases it → forces
    the threshold to sit where both classes are non-trivial.
    """
    data = data[np.isfinite(data)]
    if len(data) < 2:
        return float(np.median(data)) if len(data) else 0.0

    hist, bin_edges = np.histogram(data, bins=n_bins)
    hist         = hist.astype(float)
    bin_centers  = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    total        = hist.sum()

    w0   = np.cumsum(hist) / total
    cm0  = np.cumsum(hist * bin_centers)
    mu0  = cm0 / (np.cumsum(hist) + 1e-12)

    total_mean = float(np.sum(hist * bin_centers) / total)
    w1   = 1.0 - w0
    mu1  = np.where(w1 > 1e-9,
                    (total_mean - w0 * mu0) / w1, 0.0)

    between_var = w0 * w1 * (mu0 - mu1) ** 2
    # Mask out splits where a class is too small (controlled by sensitivity)
    if min_class_fraction > 0:
        too_small = (w0 < min_class_fraction) | (w1 < min_class_fraction)
        between_var = np.where(too_small, -1.0, between_var)
    idx = int(np.argmax(between_var))
    return float(bin_centers[idx])


# ─────────────────────────────────────────────────────────────────────────────
#  Folder-scan dialog (theme-aware)
# ─────────────────────────────────────────────────────────────────────────────

class FolderScanDialog(tk.Toplevel):
    """
    Load-from-Folder dialog with an integrated Concatenate & Export section.

    result attribute after closing:
      - list of individual file paths  →  normal "Load Selected" workflow
      - [single_concat_path]           →  "Save & Load Concatenate" workflow
    """

    def __init__(self, parent, T: dict):
        super().__init__(parent)
        self.T = T
        self.title("Load from Folder")
        self.geometry("700x660")
        self.configure(bg=T['sidebar_bg'])
        self.resizable(True, True)
        self.result = []
        self._folder            = tk.StringVar(value=_last_folder_dir)
        self._pattern           = tk.StringVar()
        self._vars              = []
        # ── Concatenate section state ─────────────────────────────────────
        self._concat_out_folder = tk.StringVar()
        self._concat_filename   = tk.StringVar(value="Concatenate.csv")
        self._build()
        self.grab_set()

    # ── Layout ────────────────────────────────────────────────────────────

    def _build(self):
        T = self.T

        # ── Top: pattern filter + folder + scan ──────────────────────────
        fr1 = ttk.Frame(self, style='TFrame')
        fr1.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(fr1, text="Filename must contain  (leave blank = all CSVs):",
                  style='TLabel').grid(row=0, column=0, columnspan=3,
                                       sticky='w', pady=(0, 2))
        self._pat_entry = ttk.Entry(fr1, textvariable=self._pattern,
                                     font=('Arial', 9), width=34)
        self._pat_entry.grid(row=1, column=0, columnspan=3,
                              sticky='we', pady=(0, 6))
        self._pat_entry.focus_set()

        ttk.Label(fr1, text="Root folder:", style='TLabel').grid(
            row=2, column=0, sticky='w', pady=(4, 2))
        ttk.Entry(fr1, textvariable=self._folder,
                  font=('Arial', 8), width=36).grid(
            row=3, column=0, sticky='we', padx=(0, 4))
        ttk.Button(fr1, text="Browse…", command=self._browse,
                   style='Gray.TButton').grid(row=3, column=1, sticky='w')
        ttk.Button(fr1, text=" Scan ", command=self._scan,
                   style='Accent.TButton').grid(row=3, column=2,
                                                 sticky='w', padx=(6, 0))
        fr1.columnconfigure(0, weight=1)

        self._count_lbl = ttk.Label(self, text="No scan yet.", style='Dim.TLabel')
        self._count_lbl.pack(anchor='w', padx=10, pady=(2, 0))

        # ── Pack bottom frames FIRST so the list gets remaining space ─────
        # (pack with side=BOTTOM stacks from the bottom upward)

        # Bottom action row
        btn_fr = ttk.Frame(self, style='TFrame')
        btn_fr.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=6)
        ttk.Button(btn_fr, text="Select All",
                   command=self._sel_all, style='Gray.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_fr, text="Deselect All",
                   command=self._desel_all, style='Gray.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_fr, text="Load Selected",
                   command=self._confirm, style='Accent.TButton').pack(side=tk.RIGHT, padx=2)
        ttk.Button(btn_fr, text="Cancel",
                   command=self.destroy, style='Gray.TButton').pack(side=tk.RIGHT, padx=2)

        # ── Concatenate & Export section (above btn_fr, packed BOTTOM) ───
        cat_outer = ttk.Frame(self, style='TFrame')
        cat_outer.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 2))

        # Header label (styled like a section title)
        hdr_fr = tk.Frame(cat_outer, bg=T['header_bg'])
        hdr_fr.pack(fill=tk.X, pady=(4, 4))
        tk.Label(hdr_fr, text="  ⊞  Concatenate & Export",
                 bg=T['header_bg'], fg=T['fg'],
                 font=('Arial', 8, 'bold')).pack(side=tk.LEFT, padx=4, pady=3)

        # Row 1: output folder
        row_folder = ttk.Frame(cat_outer, style='TFrame')
        row_folder.pack(fill=tk.X, pady=2)
        ttk.Label(row_folder, text="Output folder:", style='TLabel',
                  width=13).pack(side=tk.LEFT)
        ttk.Entry(row_folder, textvariable=self._concat_out_folder,
                  font=('Arial', 8)).pack(side=tk.LEFT, fill=tk.X,
                                          expand=True, padx=(4, 4))
        ttk.Button(row_folder, text="Browse…",
                   command=self._browse_concat_out,
                   style='Gray.TButton').pack(side=tk.LEFT)

        # Row 2: filename + action buttons
        row_file = ttk.Frame(cat_outer, style='TFrame')
        row_file.pack(fill=tk.X, pady=(2, 4))
        ttk.Label(row_file, text="Filename:", style='TLabel',
                  width=13).pack(side=tk.LEFT)
        ttk.Entry(row_file, textvariable=self._concat_filename,
                  font=('Arial', 8)).pack(side=tk.LEFT, fill=tk.X,
                                          expand=True, padx=(4, 4))
        ttk.Button(row_file, text="Save & Load",
                   command=self._do_concat_save_load,
                   style='Green.TButton').pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(row_file, text="Save Only",
                   command=self._do_concat_save,
                   style='Teal.TButton').pack(side=tk.RIGHT, padx=(4, 0))

        # Status line for concat feedback
        self._concat_status_var = tk.StringVar(value="")
        ttk.Label(cat_outer, textvariable=self._concat_status_var,
                  style='Dim.TLabel').pack(anchor='w', pady=(0, 2))

        # Thin separator above concat section
        ttk.Separator(self, orient='horizontal').pack(
            side=tk.BOTTOM, fill=tk.X, padx=8, pady=0)

        # ── Scrollable file list (takes all remaining middle space) ───────
        list_fr = ttk.Frame(self, style='TFrame')
        list_fr.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        vsb = ttk.Scrollbar(list_fr, orient='vertical')
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._cv = tk.Canvas(list_fr, bg=T['plot_bg'],
                              highlightthickness=0, yscrollcommand=vsb.set)
        self._cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.config(command=self._cv.yview)
        self._inner = ttk.Frame(self._cv, style='TFrame')
        self._cv.create_window((0, 0), window=self._inner, anchor='nw')
        self._inner.bind('<Configure>',
            lambda e: self._cv.configure(scrollregion=self._cv.bbox('all')))

        self._pat_entry.bind('<Return>', lambda e: self._scan())

    # ── Browsing ──────────────────────────────────────────────────────────

    def _browse(self):
        global _last_folder_dir
        init = (self._folder.get().strip()
                or _last_folder_dir
                or os.path.expanduser('~'))
        d = filedialog.askdirectory(parent=self, title="Select root folder",
                                    initialdir=init)
        if not d:
            return
        _last_folder_dir = d
        self._folder.set(d)
        # Auto-fill the concat output folder to the same directory
        if not self._concat_out_folder.get().strip():
            self._concat_out_folder.set(d)

    def _browse_concat_out(self):
        init = (self._concat_out_folder.get().strip()
                or self._folder.get().strip() or os.path.expanduser('~'))
        d = filedialog.askdirectory(parent=self,
                                    title="Select output folder for concatenated file",
                                    initialdir=init)
        if d:
            self._concat_out_folder.set(d)

    # ── Scanning ──────────────────────────────────────────────────────────

    def _scan(self):
        folder = self._folder.get().strip()
        if not folder or not os.path.isdir(folder):
            self._browse()
            folder = self._folder.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Folder", "Please choose a valid folder.",
                                   parent=self)
            return

        # Auto-fill concat output folder from root folder if not yet set
        if not self._concat_out_folder.get().strip():
            self._concat_out_folder.set(folder)

        # Auto-suggest filename from the root folder name
        folder_stem = os.path.basename(folder.rstrip('/\\')) or "data"
        self._concat_filename.set(f"{folder_stem}_Concatenate.csv")

        pat   = self._pattern.get().strip().lower()
        found = []
        for root, _, files in os.walk(folder):
            for f in sorted(files):
                if f.lower().endswith(('.csv', '.fcs')):
                    if not pat or pat in f.lower():
                        found.append(os.path.join(root, f))

        self._vars = []
        self._concat_status_var.set("")
        for w in self._inner.winfo_children():
            w.destroy()
        if not found:
            ttk.Label(self._inner, text="No matching files found.",
                      style='Dim.TLabel').pack(padx=4, pady=4)
            self._count_lbl.config(text="0 files found.")
            return
        self._count_lbl.config(text=f"{len(found)} file(s) found.")
        for path in found:
            var = tk.BooleanVar(value=True)
            self._vars.append((path, var))
            rel = os.path.relpath(path, folder)
            ttk.Checkbutton(self._inner, text=rel,
                            variable=var).pack(anchor='w', padx=4, pady=1)

    # ── Selection helpers ─────────────────────────────────────────────────

    def _sel_all(self):
        for _, v in self._vars: v.set(True)

    def _desel_all(self):
        for _, v in self._vars: v.set(False)

    # ── Load selected (unchanged behaviour) ───────────────────────────────

    def _confirm(self):
        self.result = [p for p, v in self._vars if v.get()]
        self.destroy()

    # ── Concatenate helpers ───────────────────────────────────────────────

    def _selected_paths(self) -> list:
        """Return the currently checked file paths."""
        return [p for p, v in self._vars if v.get()]

    def _build_concat_save_path(self) -> str | None:
        """
        Validate the concat output settings and return the full save path,
        or None if something is missing / invalid.
        """
        out_folder = self._concat_out_folder.get().strip()
        filename   = self._concat_filename.get().strip()

        if not out_folder:
            messagebox.showwarning("Concatenate",
                "Please specify an output folder.", parent=self)
            return None
        if not os.path.isdir(out_folder):
            try:
                os.makedirs(out_folder, exist_ok=True)
            except OSError as e:
                messagebox.showerror("Concatenate",
                    f"Cannot create output folder:\n{e}", parent=self)
                return None
        if not filename:
            messagebox.showwarning("Concatenate",
                "Please enter a filename.", parent=self)
            return None
        if not filename.lower().endswith('.csv'):
            filename += '.csv'
        return os.path.join(out_folder, filename)

    @staticmethod
    def _smart_read_csv(path: str) -> pd.DataFrame:
        """
        Read a CSV robustly, handling two common layouts produced by
        image-analysis exporters:

        Layout A — CytoFile style  (no leading index column):
            Label,Intensity_TH,...
            1,10742176,...

        Layout B — Results style  (unnamed integer index as first column):
             ,Label,X_TH_microns,...
            1,1,23.99,...

        Detection rule: if the first column header is empty (or whitespace
        only), treat it as a row-number index and discard it via index_col=0.
        """
        # Peek at just the header to decide
        with open(path, newline='', encoding='utf-8-sig') as fh:
            first_line = fh.readline()
        first_col_name = first_line.split(',')[0].strip()

        if first_col_name == '':
            # Layout B — unnamed leading index column → discard it
            df = pd.read_csv(path, index_col=0)
            df.index = range(len(df))   # reset to clean 0-based RangeIndex
        else:
            # Layout A — normal CSV, no index column
            df = pd.read_csv(path)

        return df

    def _run_concat(self, selected: list) -> 'pd.DataFrame | None':
        """
        Read and concatenate the selected CSV files.
        Adds a 'Source_File' column (basename of each source file) as the
        first column so the origin of every row is traceable after merging.
        Returns the combined DataFrame, or None on error.
        Skips FCS files with a warning (concatenation is CSV-only).
        """
        if not selected:
            messagebox.showwarning("Concatenate",
                "No files selected — tick at least one file to concatenate.",
                parent=self)
            return None

        frames = []
        skipped = []
        for path in selected:
            ext = os.path.splitext(path)[1].lower()
            if ext == '.fcs':
                skipped.append(os.path.basename(path))
                continue
            try:
                df = self._smart_read_csv(path)
                # Insert Source_File as the very first column
                df.insert(0, 'Source_File', os.path.basename(path))
                frames.append(df)
            except Exception as e:
                messagebox.showerror("Concatenate",
                    f"Could not read:\n{os.path.basename(path)}\n\n{e}",
                    parent=self)
                return None

        if skipped:
            messagebox.showwarning("Concatenate",
                f"FCS files are excluded from concatenation "
                f"(CSV only):\n" + "\n".join(skipped), parent=self)

        if not frames:
            messagebox.showwarning("Concatenate",
                "No CSV files in selection to concatenate.", parent=self)
            return None

        return pd.concat(frames, ignore_index=True)

    def _do_concat_save(self):
        """Save the concatenated file; keep the dialog open."""
        selected = self._selected_paths()
        save_path = self._build_concat_save_path()
        if save_path is None:
            return
        combined = self._run_concat(selected)
        if combined is None:
            return

        try:
            combined.to_csv(save_path, index=False)
        except OSError as e:
            messagebox.showerror("Concatenate", f"Could not save file:\n{e}",
                                 parent=self)
            return

        n_cells = len(combined)
        n_files = len(selected)
        msg = (f"✓ {n_files} file(s) · {n_cells:,} rows  →  "
               f"{os.path.basename(save_path)}")
        self._concat_status_var.set(msg)
        messagebox.showinfo("Concatenate",
            f"Saved successfully:\n{save_path}\n\n"
            f"{n_files} file(s) · {n_cells:,} rows",
            parent=self)

    def _do_concat_save_load(self):
        """Save the concatenated file, then load it into the app."""
        selected = self._selected_paths()
        save_path = self._build_concat_save_path()
        if save_path is None:
            return
        combined = self._run_concat(selected)
        if combined is None:
            return

        try:
            combined.to_csv(save_path, index=False)
        except OSError as e:
            messagebox.showerror("Concatenate", f"Could not save file:\n{e}",
                                 parent=self)
            return

        # Return the single concatenated file path so the caller loads it
        self.result = [save_path]
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
#  Batch Stats Dialog
# ─────────────────────────────────────────────────────────────────────────────

class BatchStatsDialog(tk.Toplevel):
    """
    Dialog for the Batch Stats → Folder feature.

    Collects:
      - Root folder to scan
      - Filename suffix pattern (default '___CytoFile')
      - File types (CSV / FCS / Both)
      - Output CSV path

    Returns result = (folder, suffix, file_types, save_path)  or  None if cancelled.
    """

    def __init__(self, parent, T: dict, auto_folders: list,
                 x_channel: str, y_channel: str):
        super().__init__(parent)
        self.T          = T
        self.x_channel  = x_channel
        self.y_channel  = y_channel
        self.result     = None

        self.title("Batch Stats → Folder")
        self.geometry("600x460")
        self.configure(bg=T['sidebar_bg'])
        self.resizable(True, True)
        self.grab_set()

        self._folder_var  = tk.StringVar(value=auto_folders[0] if auto_folders else '')
        self._suffix_var  = tk.StringVar(value='___CytoFile')
        self._type_var    = tk.StringVar(value='csv')   # csv | fcs | both
        self._preview_var = tk.StringVar(value='')
        self._save_var    = tk.StringVar(value='')

        self._build(auto_folders)
        self._refresh_preview()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self, auto_folders):
        T = self.T
        BG = T['sidebar_bg']; FG = T['fg']
        pad = {'padx': 10, 'pady': 4}

        # ── Root folder ──────────────────────────────────────────────────
        ttk.Label(self, text="Root folder to scan:", foreground=FG,
                  background=BG).pack(anchor='w', **pad)
        fr1 = tk.Frame(self, bg=BG)
        fr1.pack(fill=tk.X, padx=10, pady=(0, 4))
        ttk.Entry(fr1, textvariable=self._folder_var, width=52).pack(
            side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(fr1, text='Browse…', command=self._browse_folder
                   ).pack(side=tk.LEFT, padx=(4, 0))

        # Recent folders shortcut
        if auto_folders:
            ttk.Label(self, text="Detected from loaded files:", foreground=T.get('dim_fg', FG),
                      background=BG, font=('Arial', 8)).pack(anchor='w', padx=10)
            for f in auto_folders[:3]:
                lbl = tk.Label(self, text=f'  {f}', fg='#4a9aff', bg=BG,
                               cursor='hand2', font=('Arial', 8), anchor='w')
                lbl.pack(fill=tk.X, padx=10)
                lbl.bind('<Button-1>', lambda e, v=f: self._folder_var.set(v)
                         or self._refresh_preview())

        ttk.Separator(self, orient='horizontal').pack(fill=tk.X, padx=10, pady=6)

        # ── Suffix pattern ───────────────────────────────────────────────
        ttk.Label(self, text="Filename must contain (suffix pattern):",
                  foreground=FG, background=BG).pack(anchor='w', **pad)
        fr2 = tk.Frame(self, bg=BG)
        fr2.pack(fill=tk.X, padx=10, pady=(0, 4))
        e = ttk.Entry(fr2, textvariable=self._suffix_var, width=36)
        e.pack(side=tk.LEFT)
        e.bind('<KeyRelease>', lambda _: self._refresh_preview())
        ttk.Label(fr2, text="  (leave blank = all files)",
                  foreground=T.get('dim_fg', FG), background=BG,
                  font=('Arial', 8)).pack(side=tk.LEFT)

        # ── File type ────────────────────────────────────────────────────
        ttk.Label(self, text="File types:", foreground=FG,
                  background=BG).pack(anchor='w', **pad)
        fr3 = tk.Frame(self, bg=BG)
        fr3.pack(fill=tk.X, padx=10, pady=(0, 4))
        for val, lbl in [('csv', 'CSV'), ('fcs', 'FCS'), ('both', 'CSV + FCS')]:
            tk.Radiobutton(fr3, text=lbl, variable=self._type_var, value=val,
                           bg=BG, fg=FG, selectcolor=BG, activebackground=BG,
                           command=self._refresh_preview).pack(side=tk.LEFT, padx=8)

        ttk.Separator(self, orient='horizontal').pack(fill=tk.X, padx=10, pady=6)

        # ── Preview ──────────────────────────────────────────────────────
        ttk.Label(self, text="Preview (matching files):", foreground=FG,
                  background=BG).pack(anchor='w', **pad)
        self._preview_lbl = tk.Label(self, textvariable=self._preview_var,
                                     fg='#4adf8a', bg=BG, font=('Arial', 9),
                                     justify='left', anchor='w', wraplength=560)
        self._preview_lbl.pack(anchor='w', padx=14, pady=(0, 4))

        ttk.Separator(self, orient='horizontal').pack(fill=tk.X, padx=10, pady=6)

        # ── Output file ──────────────────────────────────────────────────
        ttk.Label(self, text="Save results to:", foreground=FG,
                  background=BG).pack(anchor='w', **pad)
        fr4 = tk.Frame(self, bg=BG)
        fr4.pack(fill=tk.X, padx=10, pady=(0, 4))
        ttk.Entry(fr4, textvariable=self._save_var, width=46).pack(
            side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(fr4, text='Browse…', command=self._browse_save
                   ).pack(side=tk.LEFT, padx=(4, 0))

        # ── Buttons ──────────────────────────────────────────────────────
        fr5 = tk.Frame(self, bg=BG)
        fr5.pack(fill=tk.X, padx=10, pady=10, side=tk.BOTTOM)
        ttk.Button(fr5, text='Cancel', command=self.destroy
                   ).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(fr5, text='Run Batch Export', command=self._confirm,
                   style='Green.TButton').pack(side=tk.RIGHT)

        # Channels label
        ttk.Label(self, text=f"Channels: X={self.x_channel}  Y={self.y_channel}",
                  foreground=T.get('dim_fg', FG), background=BG,
                  font=('Arial', 8)).pack(side=tk.BOTTOM, padx=10, pady=(0, 2))

    def _browse_folder(self):
        global _last_folder_dir
        init = (self._folder_var.get().strip()
                or _last_folder_dir
                or os.path.expanduser('~'))
        d = filedialog.askdirectory(parent=self, title="Select root folder",
                                    initialdir=init)
        if d:
            _last_folder_dir = d
            self._folder_var.set(d)
            self._refresh_preview()

    def _browse_save(self):
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension='.csv',
            initialfile='batch_stats.csv',
            filetypes=[("CSV", "*.csv")])
        if path:
            self._save_var.set(path)

    def _refresh_preview(self):
        folder = self._folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            self._preview_var.set("(no valid folder selected)")
            return
        suffix = self._suffix_var.get().strip().lower()
        ftype  = self._type_var.get()
        exts   = []
        if ftype in ('csv', 'both'): exts.append('.csv')
        if ftype in ('fcs', 'both'): exts += ['.fcs', '.FCS']
        found = []
        for root_d, _, files in os.walk(folder):
            for fname in sorted(files):
                _, ext = os.path.splitext(fname)
                if ext.lower() not in [e.lower() for e in exts]: continue
                if suffix and suffix not in fname.lower(): continue
                found.append(fname)
        n = len(found)
        if n == 0:
            self._preview_var.set("No matching files found.")
            self._preview_lbl.config(fg='#df4a4a')
        else:
            examples = found[:4]
            more     = f"  … and {n-4} more" if n > 4 else ""
            self._preview_var.set(
                f"{n} file(s) matched:\n  " + "\n  ".join(examples) + more)
            self._preview_lbl.config(fg='#4adf8a')

    def _confirm(self):
        folder    = self._folder_var.get().strip()
        suffix    = self._suffix_var.get().strip()
        file_type = self._type_var.get()
        save_path = self._save_var.get().strip()

        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Batch Stats", "Select a valid root folder.", parent=self)
            return
        if not save_path:
            messagebox.showwarning("Batch Stats", "Choose an output file path.", parent=self)
            return
        self.result = (folder, suffix, file_type, save_path)
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
#  Polar / Vector Analysis Window
# ─────────────────────────────────────────────────────────────────────────────

class PolarAnalysisWindow(tk.Toplevel):
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
    Rayleigh p : Zar (2010) §27.2 corrected series —
                 Z = n·R̄²,  p ≈ exp(-Z)·(1 + (2Z−Z²)/4n − (24Z−132Z²+76Z³−9Z⁴)/288n²)
                 This is the standard finite-sample correction; for high MRL
                 (|R̄| ≥ 0.4) the correction is substantial and should not
                 be omitted.
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
        # Auto-compute after the window is fully drawn
        self.after(150, self._compute_and_plot)

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
            color = FILE_COLORS[fi % len(FILE_COLORS)]
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
        active = self.app._active()
        return [p for p in sorted(active.keys())
                if self._file_vars.get(p, tk.BooleanVar(value=True)).get()]

    # ── helpers ───────────────────────────────────────────────────────────────

    def _get_columns(self):
        files = self.app._active()
        if not files:
            return []
        sets = [set(df.columns) for df in files.values()]
        return sorted(set.intersection(*sets)) if sets else []

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

        x_cols = [c for c in cols
                  if c.lower().startswith('x_') or 'centroid_x' in c.lower()
                  or ('centroid' in c.lower() and 'x' in c.lower().split('_'))]
        y_cols = [c for c in cols
                  if c.lower().startswith('y_') or 'centroid_y' in c.lower()
                  or ('centroid' in c.lower() and 'y' in c.lower().split('_'))]

        seen = set(); x_cols_u = []
        for c in x_cols:
            if c not in seen: seen.add(c); x_cols_u.append(c)
        seen = set(); y_cols_u = []
        for c in y_cols:
            if c not in seen: seen.add(c); y_cols_u.append(c)
        x_cols, y_cols = x_cols_u, y_cols_u

        x_mu = [c for c in x_cols if 'micron' in c.lower()]
        y_mu = [c for c in y_cols if 'micron' in c.lower()]
        if x_mu: x_cols = x_mu
        if y_mu: y_cols = y_mu

        if len(x_cols) >= 2:
            self._cx1_var.set(x_cols[0]); self._cx2_var.set(x_cols[1])
        elif len(x_cols) == 1:
            self._cx1_var.set(x_cols[0]); self._cx2_var.set(x_cols[0])
        if len(y_cols) >= 2:
            self._cy1_var.set(y_cols[0]); self._cy2_var.set(y_cols[1])
        elif len(y_cols) == 1:
            self._cy1_var.set(y_cols[0]); self._cy2_var.set(y_cols[0])

    def _populate_gate_dropdown(self):
        applied = [g for g in self.app.gates if g.get('applied')]
        names   = ['All cells'] + [g['name'] for g in applied]
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
        gate = next((g for g in self.app.gates
                     if g['name'] == name and g.get('applied')), None)
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
        gate = next((g for g in self.app.gates
                     if g['name'] == name and g.get('applied')), None)
        if gate is None:
            return np.ones(n, bool)
        xch = self.app.x_channel
        ych = self.app.y_channel
        if (not xch or not ych or
                xch not in df.columns or ych not in df.columns):
            return np.ones(n, bool)
        xa = df[xch].to_numpy(dtype=float, copy=False)
        ya = df[ych].to_numpy(dtype=float, copy=False)
        try:
            regions, _ = self.app._gate_mask_for(gate, xa, ya)
        except Exception:
            return np.ones(n, bool)
        region_sel = self._region_var.get()
        if region_sel == 'All regions':
            combined = np.zeros(n, bool)
            for rname, mask in regions.items():
                if gate.get('type', 'crosshair') != 'crosshair' \
                        and rname == 'OUT':
                    continue
                combined |= mask
            return combined
        return regions.get(region_sel, np.ones(n, bool))

    def _get_vectors_for_df(self, df: pd.DataFrame, mask: np.ndarray):
        """Return (angles_rad, magnitudes) or (None, None)."""
        cx1 = self._cx1_var.get(); cy1 = self._cy1_var.get()
        cx2 = self._cx2_var.get(); cy2 = self._cy2_var.get()
        for col in (cx1, cy1, cx2, cy2):
            if not col or col not in df.columns:
                return None, None
        sub = df[mask]
        if len(sub) == 0:
            return np.array([]), np.array([])
        dx = sub[cx2].to_numpy(dtype=float, copy=False) - sub[cx1].to_numpy(dtype=float, copy=False)
        dy = sub[cy2].to_numpy(dtype=float, copy=False) - sub[cy1].to_numpy(dtype=float, copy=False)
        return np.arctan2(dy, dx), np.sqrt(dx**2 + dy**2)

    # ── circular statistics ───────────────────────────────────────────────────

    @staticmethod
    def _mrl(angles: np.ndarray) -> float:
        """
        Mean Resultant Length: R̄ = |∑ exp(iθ)| / n ∈ [0, 1].
        0 = uniform distribution, 1 = all vectors identical.
        """
        n = len(angles)
        if n == 0:
            return 0.0
        return float(np.sqrt(np.sum(np.cos(angles))**2 +
                              np.sum(np.sin(angles))**2) / n)

    @staticmethod
    def _mean_dir(angles: np.ndarray) -> float:
        """Circular mean direction in radians ∈ (−π, π]."""
        return float(np.arctan2(np.mean(np.sin(angles)),
                                 np.mean(np.cos(angles))))

    @staticmethod
    def _rayleigh_p(angles: np.ndarray) -> float:
        """
        Rayleigh test p-value with Zar (2010) §27.2 finite-sample correction.

        The simple approximation  p ≈ exp(−n·R̄²)  is the leading-order
        Greenwood & Durand (1955) result and is adequate only for small R̄.
        For moderate-to-large R̄ (> 0.4, common in synaptosome data) the
        higher-order correction terms are substantial — up to ~75% difference
        for n≈30, R̄≈0.7.

        Corrected formula (n ≥ 10):
          Z = n · R̄²
          p ≈ exp(−Z) × (1 + (2Z − Z²)/4n − (24Z − 132Z² + 76Z³ − 9Z⁴)/288n²)

        For n < 10 the series expansion is unreliable and we fall back to
        the simple exp(−Z) approximation, noting the result is conservative
        (slightly over-estimates p).
        """
        n = len(angles)
        if n < 2:
            return 1.0
        R_bar = PolarAnalysisWindow._mrl(angles)
        Z     = n * R_bar**2
        p     = np.exp(-Z)
        if n >= 10:
            p *= (1.0
                  + (2*Z - Z**2) / (4*n)
                  - (24*Z - 132*Z**2 + 76*Z**3 - 9*Z**4) / (288*n**2))
        return float(np.clip(p, 0.0, 1.0))

    # ── plotting ──────────────────────────────────────────────────────────────

    def _refresh_display(self):
        """Re-render the figure from cached datasets (no data recomputation).
        Called by display-option checkboxes to show/hide annotation / legend."""
        if self._last_datasets:
            self._render_figure(self._last_datasets)

    def _compute_and_plot(self):
        """
        Collect per-file vector data for visible files, render polar figure,
        and populate the statistics treeview.
        """
        # ── Parse parameters ──────────────────────────────────────────────
        try:
            float(self._mrl_thresh_var.get())
            max(4, int(self._n_bins_var.get()))
            float(np.clip(float(self._alpha_var.get()), 0.05, 1.0))
        except ValueError:
            messagebox.showerror("Polar Analysis",
                "Invalid parameter value(s).", parent=self)
            return

        # ── Validate column selection ─────────────────────────────────────
        if not all([self._cx1_var.get(), self._cy1_var.get(),
                    self._cx2_var.get(), self._cy2_var.get()]):
            self._status_var.set("Select all four coordinate columns, then compute")
            return

        active = self.app._active()
        if not active:
            self._status_var.set("No data loaded")
            return

        # ── Refresh file list to pick up any new/removed files ────────────
        self._build_file_list()

        # ── Collect data for visible files ────────────────────────────────
        visible_paths = self._get_active_paths()
        datasets = []   # list of (angles, mags, label, color, path)
        for fi, path in enumerate(sorted(active.keys())):
            if path not in visible_paths:
                continue
            df   = active[path]
            mask = self._get_population_mask(df, path)
            angles, mags = self._get_vectors_for_df(df, mask)
            if angles is None:
                continue
            color = FILE_COLORS[fi % len(FILE_COLORS)]
            label = os.path.basename(path)
            datasets.append((angles, mags, label, color, path))

        if not datasets or not any(len(a) > 0 for a, _, _, _, _ in datasets):
            self._status_var.set(
                "No valid vector data — check coordinate columns and gate")
            self._fig.clear()
            self._canvas.draw()
            self._last_datasets = []
            self._update_stats_display()
            return

        self._last_datasets = datasets
        self._render_figure(datasets)
        self._update_stats_display()

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
        for sp in ax.spines.values():
            sp.set_color(T['spine'])
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
            f'Radial scale = fraction of vectors per bin  |  '
            f'Arrow = mean direction (shown when MRL \u2265 {mrl_thresh})',
            color=T['fg'], fontsize=9, y=1.02)

        self._fig.tight_layout()
        self._canvas.draw()

        total_vecs = sum(len(a) for a, _, _, _, _ in datasets)
        self._status_var.set(
            f"{total_vecs:,} vectors  \u00b7  {len(datasets)} file(s)  "
            f"\u00b7  {pop_info}  "
            f"\u00b7  bins: {n_bins}  \u00b7  MRL-arrow \u2265 {mrl_thresh}  "
            f"\u00b7  radial scale: fraction of vectors per bin")

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
        except ValueError:
            mrl_thresh = 0.3

        if mode == 'merged':
            # Concatenate all angles and compute combined stats
            all_angles = np.concatenate(
                [a for a, _, _, _, _ in datasets if len(a) > 0])
            if len(all_angles) == 0:
                return
            mrl      = self._mrl(all_angles)
            p_val    = self._rayleigh_p(all_angles)
            mean_deg = float(np.degrees(self._mean_dir(all_angles)))
            sig      = '\u2713' if (p_val < 0.05 and mrl >= mrl_thresh) else 'n.s.'
            p_disp   = f'{p_val:.4f}' if p_val >= 0.0001 else '<0.0001'
            self._stats_tree.insert(
                '', 'end',
                text=f'  All files merged',
                values=(f'{len(all_angles):,}',
                        f'{mrl:.3f}',
                        p_disp,
                        f'{mean_deg:.1f}',
                        sig),
                open=False)
        else:
            # Per-file rows
            for fi, (angles, mags, label, color, path) in enumerate(datasets):
                if len(angles) == 0:
                    name  = os.path.splitext(os.path.basename(path))[0]
                    short = (name[:24] + '\u2026') if len(name) > 25 else name
                    self._stats_tree.insert(
                        '', 'end',
                        text=f'  {short}',
                        values=('0', '\u2014', '\u2014', '\u2014', '\u2014'))
                    continue
                mrl      = self._mrl(angles)
                p_val    = self._rayleigh_p(angles)
                mean_deg = float(np.degrees(self._mean_dir(angles)))
                sig      = '\u2713' if (p_val < 0.05 and mrl >= mrl_thresh) else 'n.s.'
                p_disp   = f'{p_val:.4f}' if p_val >= 0.0001 else '<0.0001'
                name     = os.path.splitext(os.path.basename(path))[0]
                short    = (name[:24] + '\u2026') if len(name) > 25 else name
                tag      = f'fc{fi % len(FILE_COLORS)}'
                self._stats_tree.tag_configure(
                    tag, foreground=FILE_COLORS[fi % len(FILE_COLORS)])
                self._stats_tree.insert(
                    '', 'end',
                    text=f'  {short}',
                    values=(f'{len(angles):,}',
                            f'{mrl:.3f}',
                            p_disp,
                            f'{mean_deg:.1f}',
                            sig),
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
            self._fig.savefig(path, dpi=300, bbox_inches='tight',
                              facecolor=self._fig.get_facecolor())
            messagebox.showinfo("Saved", f"Figure saved:\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("Save Error", str(e), parent=self)

    def _export_stats(self):
        """
        Compute per-file vector statistics and save a CSV.
        Uses the corrected Rayleigh p-value (Zar 2010).
        Columns: File, Gate, Region, N_vectors, MRL, Rayleigh_p,
                 Mean_dir_deg, Significant, X_Ch1, Y_Ch1, X_Ch2, Y_Ch2
        """
        try:
            mrl_thresh = float(self._mrl_thresh_var.get())
        except ValueError:
            mrl_thresh = 0.3

        active = self.app._active()
        if not active:
            messagebox.showwarning("Export Stats", "No data loaded.", parent=self)
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
            mask         = self._get_population_mask(df, path)
            angles, mags = self._get_vectors_for_df(df, mask)
            fname        = os.path.basename(path)

            if angles is None or len(angles) == 0:
                rows.append({
                    'File': fname, 'Gate': gate_lbl, 'Region': region_lbl,
                    'N_vectors': 0,
                    'MRL': None, 'Rayleigh_p': None,
                    'Mean_dir_deg': None, 'Significant': None,
                    'X_Ch1': self._cx1_var.get(), 'Y_Ch1': self._cy1_var.get(),
                    'X_Ch2': self._cx2_var.get(), 'Y_Ch2': self._cy2_var.get(),
                })
                continue

            mrl      = self._mrl(angles)
            p_val    = self._rayleigh_p(angles)
            mean_dir = float(np.degrees(self._mean_dir(angles)))
            sig      = bool(p_val < 0.05 and mrl >= mrl_thresh)

            rows.append({
                'File':         fname,
                'Gate':         gate_lbl,
                'Region':       region_lbl,
                'N_vectors':    len(angles),
                'MRL':          round(mrl, 6),
                'Rayleigh_p':   round(p_val, 6) if p_val >= 1e-6 else p_val,
                'Mean_dir_deg': round(mean_dir, 3),
                'Significant':  sig,
                'X_Ch1':        self._cx1_var.get(),
                'Y_Ch1':        self._cy1_var.get(),
                'X_Ch2':        self._cx2_var.get(),
                'Y_Ch2':        self._cy2_var.get(),
            })

        if not rows:
            messagebox.showwarning("Export Stats", "No vector data.", parent=self)
            return

        try:
            pd.DataFrame(rows).to_csv(path_out, index=False)
            messagebox.showinfo("Export Stats",
                f"Stats saved ({len(rows)} file(s)):\n{path_out}", parent=self)
        except Exception as e:
            messagebox.showerror("Export Stats", str(e), parent=self)

# ─────────────────────────────────────────────────────────────────────────────
#  Main application
# ─────────────────────────────────────────────────────────────────────────────

class FlowApp:
    def __init__(self, root: tk.Tk, container=None,
                 parent_label: str = None, manager=None):
        """
        root         – Tk root window (always needed for messagebox parent)
        container    – ttk.Frame to build UI into; None → build into root
        parent_label – name of the parent gate population (sub-gate tabs only)
        manager      – FlowTabManager; enables double-click sub-gate opening
        """
        self.root         = root
        self.manager      = manager
        self.parent_label = parent_label

        # In standalone mode, build directly into root.
        # In tab mode, build into the supplied container frame.
        if container is None:
            root.title("vFlow 4.0.12")
            root.geometry("1500x960")
            self._theme_name = 'dark'
            self.T = THEMES['dark']
            _apply_ttk_style(self.T)
            root.configure(bg=self.T['sidebar_bg'])
            # Wrap in a frame so _build_ui always has a Frame container
            self.container = tk.Frame(root, bg=self.T['sidebar_bg'])
            self.container.pack(fill=tk.BOTH, expand=True)
        else:
            self.container   = container
            self._theme_name = 'dark'
            self.T           = THEMES['dark']

        # Data
        self.loaded_files:   dict = {}
        self.excluded_files: dict = {}   # path → df (excluded from analysis)
        self.file_vars:      dict = {}
        self.file_colors:  dict = {}

        # Sub-gate context (set by FlowTabManager._load_filtered for sub-gate tabs;
        # None on the main tab).  batch_export_stats uses these to pre-filter each
        # raw file through the parent gate before applying the sub-gate's own gates.
        self.parent_gate:   dict = None   # gate dict from parent tab
        self.parent_region: str  = None   # region name that was double-clicked

        # ── Performance caches ────────────────────────────────────────────
        # _tc  : transform cache  — {(path, x_ch, y_ch, x_sc, y_sc, cof): (xt, yt, valid)}
        #        self-invalidating: different settings → different key → cache miss
        # _gmc : gate-mask cache  — {(path, x_ch, y_ch, gid, sig): (regions, colors)}
        #        self-invalidating: gate geometry change → sig changes → cache miss
        self._tc:  dict = {}
        self._gmc: dict = {}

        # Plot state
        self.x_channel = None
        self.y_channel = None
        self.x_scale   = 'asinh'
        self.y_scale   = 'asinh'
        self.cofactor  = 150.0

        # View mode
        self.view_mode_var = tk.StringVar(value='overlay')
        self.cycle_idx     = 0

        # ── Multi-gate system ──────────────────────────────────────────────────
        # Each gate dict: {id, name, type, applied, color, ...geometry...}
        #   crosshair: x_boundaries, y_boundary, x_thresh_vars, y_thresh_var
        #   rectangle/ellipse: x0, y0, x1, y1
        #   polygon: vertices [(x,y),...]
        self.gates:           list = []
        self._sel_gate_id:    int  = None  # selected gate (stats/coloring)
        self._draw_gate_id:   int  = None  # gate currently being drawn
        self._next_gate_id:   int  = 0

        # Current drawing state
        self.moving_gate:      bool  = False
        self._poly_active:     bool  = False
        self._poly_cursor:     tuple = None

        # Handle-editing state
        self._handle_drag:     dict  = None  # {gate_id, handle, idx, ox, oy}
        self._hover_gate_id:   int   = None  # gate whose handles are visible via hover
        self._pinned_gate_id:  int   = None  # gate whose handles are pinned via right-click
        # Debounce: pending after_id for throttled refresh_plot calls
        self._refresh_pending:   str   = None
        self._last_auto_gate_fn        = None   # callable: last-used auto-gate method
        self._sens_rerun_pending: str  = None   # debounce after_id for slider re-run
        # Cached handle pixel coords: {gate_id: [(px,py,handle,idx),...]}
        # Rebuilt after every full plot redraw, used by _hover_test_handles
        self._handle_px_cache: dict  = {}
        self._handle_artists:  list  = []    # matplotlib artists for handles

        # Preview artists (in-progress gate outline)
        self._preview_artists: list  = []

        # Gate type for NEW gates
        self.gate_type_var  = tk.StringVar(value='crosshair')
        # Gate interaction mode: 'none' | 'draw' | 'edit'
        # gate_var is a BooleanVar alias: True when mode == 'draw'
        # Both are created before _build_ui() so _build_ui() can reference them.
        self.gate_mode_var  = tk.StringVar(value='none')

        # Gate stats (keyed by gate id)
        self.gate_stats:       dict = {}

        # Stats display mode
        self.stats_mode_var = tk.StringVar(value='perfile')

        self._build_ui()

    # ── Theme ─────────────────────────────────────────────────────────────────

    def toggle_theme(self):
        self._theme_name = 'light' if self._theme_name == 'dark' else 'dark'
        self.T = THEMES[self._theme_name]
        _apply_ttk_style(self.T)
        self._apply_theme_to_tk_widgets()
        self.refresh_plot()

    def _apply_theme_to_tk_widgets(self):
        T = self.T
        try:    self.root.configure(bg=T['sidebar_bg'])
        except Exception: pass
        self._side_canvas.configure(bg=T['sidebar_bg'])
        self.right.configure(bg=T['plot_bg'])
        self._status_lbl.configure(bg=T['header_bg'], fg=T['fg_dim'])
        for w in self._scale_widgets:
            w.configure(bg=T['sidebar_bg'], fg=T['fg'],
                        troughcolor=T['trough'],
                        activebackground=T['sel_bg'])
        lbl = '☀  Light mode' if self._theme_name == 'dark' else '☾  Dark mode'
        self._theme_btn.configure(text=lbl)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        T = self.T
        C = self.container  # all top-level widgets pack here

        # Optional parent-gate banner for sub-gate tabs
        if self.parent_label:
            ttk.Label(C, text=f'  ↳ Sub-gate of:  {self.parent_label}',
                      style='Section.TLabel').pack(fill=tk.X, side=tk.TOP)

        # Scrollable sidebar
        side_outer = ttk.Frame(C, style='TFrame', width=340)
        side_outer.pack(side=tk.LEFT, fill=tk.Y)
        side_outer.pack_propagate(False)

        self._side_canvas = tk.Canvas(side_outer, bg=T['sidebar_bg'],
                                       highlightthickness=0, width=338)
        vsb = ttk.Scrollbar(side_outer, orient='vertical',
                             command=self._side_canvas.yview)
        self._side_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._side_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.sidebar = ttk.Frame(self._side_canvas, style='TFrame')
        self._side_canvas.create_window(
            (0, 0), window=self.sidebar, anchor='nw', width=320)
        self.sidebar.bind('<Configure>',
            lambda e: self._side_canvas.configure(
                scrollregion=self._side_canvas.bbox('all')))

        def _scroll(evt):
            self._side_canvas.yview_scroll(int(-1 * (evt.delta / 120)), 'units')
        self._side_canvas.bind('<MouseWheel>', _scroll)
        self.sidebar.bind('<MouseWheel>', _scroll)

        # Plot area
        self.right = tk.Frame(C, bg=T['plot_bg'])
        self.right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._scale_widgets = []
        self._build_controls()
        self._build_plot()
        self._build_status_bar()

    # ── Widget helpers ────────────────────────────────────────────────────────

    def _section(self, text):
        ttk.Label(self.sidebar, text=f'  {text}',
                  style='Section.TLabel', anchor='w').pack(fill=tk.X, pady=(10, 2))

    def _lbl(self, text, style='TLabel'):
        ttk.Label(self.sidebar, text=text, style=style).pack(anchor='w', padx=8)

    def _btn(self, text, cmd, style='TButton'):
        b = ttk.Button(self.sidebar, text=text, command=cmd, style=style)
        b.pack(fill=tk.X, padx=8, pady=2)
        return b

    def _scale_w(self, parent, **kw):
        T = self.T
        s = tk.Scale(parent, bg=T['sidebar_bg'], fg=T['fg'],
                     troughcolor=T['trough'], highlightthickness=0,
                     activebackground=T['sel_bg'], **kw)
        self._scale_widgets.append(s)
        return s

    # ── Build controls ────────────────────────────────────────────────────────

    def _build_controls(self):
        p = self.sidebar

        # Theme toggle
        self._theme_btn = ttk.Button(
            p, text='☀  Light mode', command=self.toggle_theme,
            style='Gray.TButton')
        self._theme_btn.pack(fill=tk.X, padx=8, pady=(8, 2))

        # ── FILES ──
        self._section("FILES")
        file_btn_row = ttk.Frame(p, style='TFrame')
        file_btn_row.pack(fill=tk.X, padx=8, pady=(0, 2))
        ttk.Button(file_btn_row, text='+ Load CSV Files',
                   command=self.load_files,
                   style='Accent.TButton').pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(file_btn_row, text='🗑 Clear All',
                   command=self.clear_all_files,
                   style='Gray.TButton').pack(side=tk.LEFT)
        self._btn("+ Load from Folder…", self.load_from_folder, 'DarkBlue.TButton')

        # ── Select All / Unselect All ──
        sel_row = ttk.Frame(p, style='TFrame')
        sel_row.pack(fill=tk.X, padx=8, pady=(1, 2))
        ttk.Button(sel_row, text='☑  Select All',
                   command=self._select_all,
                   style='Gray.TButton').pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(sel_row, text='☐  Unselect All',
                   command=self._unselect_all,
                   style='Gray.TButton').pack(side=tk.LEFT)

        self.file_list_frame = ttk.Frame(p, style='TFrame')
        self.file_list_frame.pack(fill=tk.X, padx=8)

        # ── EXCLUDED FILES ──
        self._section("EXCLUDED FILES")
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

        # ── VIEW MODE ──
        self._section("VIEW MODE")
        vm_row = ttk.Frame(p, style='TFrame')
        vm_row.pack(fill=tk.X, padx=8)
        for val, lbl in [('overlay', 'Overlay'), ('cycle', 'Cycle through')]:
            ttk.Radiobutton(vm_row, text=lbl, variable=self.view_mode_var,
                            value=val, command=self._on_view_mode_change,
                            style='TRadiobutton').pack(side=tk.LEFT, padx=4)

        nav = ttk.Frame(p, style='TFrame')
        nav.pack(fill=tk.X, padx=8, pady=2)
        self._btn_prev = ttk.Button(nav, text='◀ Prev', command=self._cycle_prev,
                                     style='Gray.TButton', state=tk.DISABLED)
        self._btn_prev.pack(side=tk.LEFT, padx=(0, 4))
        self._btn_next = ttk.Button(nav, text='Next ▶', command=self._cycle_next,
                                     style='Gray.TButton', state=tk.DISABLED)
        self._btn_next.pack(side=tk.LEFT)
        self.cycle_label_var = tk.StringVar(value='')
        ttk.Label(nav, textvariable=self.cycle_label_var,
                  style='Dim.TLabel').pack(side=tk.LEFT, padx=6)

        # ── AXES ──
        self._section("AXES")
        self._lbl("Y Axis:")
        self.y_var = tk.StringVar()
        self.y_menu = ttk.Combobox(p, textvariable=self.y_var,
                                    state='readonly', font=('Arial', 8))
        self.y_menu.pack(fill=tk.X, padx=8, pady=(0, 4))
        self._lbl("X Axis:")
        self.x_var = tk.StringVar()
        self.x_menu = ttk.Combobox(p, textvariable=self.x_var,
                                    state='readonly', font=('Arial', 8))
        self.x_menu.pack(fill=tk.X, padx=8, pady=(0, 4))
        self._btn("Apply Axes", self.apply_axes, 'Green.TButton')

        # ── SCALE ──
        self._section("SCALE")
        sf = ttk.Frame(p, style='TFrame')
        sf.pack(fill=tk.X, padx=8, pady=2)
        for row_i, (lbl_text, attr) in enumerate([("Y:", 'y_scale_var'),
                                                   ("X:", 'x_scale_var')]):
            ttk.Label(sf, text=lbl_text, style='TLabel', width=3
                      ).grid(row=row_i, column=0, sticky='w')
            var = tk.StringVar(value='asinh')
            setattr(self, attr, var)
            ttk.Combobox(sf, textvariable=var, values=ALL_SCALES,
                         state='readonly', width=12, font=('Arial', 8)
                         ).grid(row=row_i, column=1, sticky='w', pady=1)
        self.x_scale_var.trace_add('write', lambda *_: self._apply_scales())
        self.y_scale_var.trace_add('write', lambda *_: self._apply_scales())

        cf = ttk.Frame(p, style='TFrame')
        cf.pack(fill=tk.X, padx=8)
        ttk.Label(cf, text="Cofactor (asinh / logicle):",
                  style='Dim.TLabel').pack(anchor='w')
        self.cofactor_str = tk.StringVar(value='150')
        self.cofactor_str.trace_add('write', self._on_cofactor_change)
        ttk.Entry(cf, textvariable=self.cofactor_str,
                  font=('Arial', 8), width=10).pack(anchor='w', pady=(2, 0))

        # ── DISPLAY ──
        self._section("DISPLAY")
        self._lbl("Plot Mode:")
        self.plot_type_var = tk.StringVar(value='Density')
        ttk.Combobox(p, textvariable=self.plot_type_var,
                     values=['Dot Plot', 'Density', 'Contour Plot'],
                     state='readonly', font=('Arial', 8)
                     ).pack(fill=tk.X, padx=8, pady=(0, 3))
        self.plot_type_var.trace_add('write', lambda *_: self.refresh_plot())

        self._lbl("Dot Size:")
        self.dot_size_var = tk.IntVar(value=2)
        s1 = self._scale_w(p, from_=1, to=12, orient=tk.HORIZONTAL,
                            variable=self.dot_size_var,
                            command=lambda _: self.schedule_refresh())
        s1.pack(fill=tk.X, padx=8)

        self._lbl("Alpha:")
        self.alpha_var = tk.DoubleVar(value=0.6)
        s2 = self._scale_w(p, from_=0.05, to=1.0, resolution=0.05,
                            orient=tk.HORIZONTAL, variable=self.alpha_var,
                            command=lambda _: self.schedule_refresh())
        s2.pack(fill=tk.X, padx=8)

        self._lbl("Contour Probability:")
        self.prob_var = tk.StringVar(value='5%')
        ttk.Combobox(p, textvariable=self.prob_var,
                     values=['2%', '5%', '10%', '20%'],
                     state='readonly', font=('Arial', 8)
                     ).pack(fill=tk.X, padx=8, pady=(0, 3))
        self.prob_var.trace_add('write', lambda *_: self.refresh_plot())

        for attr, text, default in [
            ('show_marginals_var', 'Marginal histograms', True),
            ('show_labels_var',    'Region % labels on plot', True),
            ('show_legend_var',    'Legend', True),
            ('show_grid_var',      'Grid', True),
            ('fit_axes_var',       'Fit axes to data', False),
        ]:
            v = tk.BooleanVar(value=default)
            setattr(self, attr, v)
            ttk.Checkbutton(p, text=text, variable=v,
                            command=self.refresh_plot,
                            style='TCheckbutton').pack(anchor='w', padx=8)

        # ── GATING ──
        self._section("GATING")

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
                  style='Dim.TLabel').pack(anchor='w', padx=16, pady=(0, 2))

        # Polygon close button (shown only while drawing polygon)
        self._poly_close_btn = ttk.Button(
            p, text='✓  Close Polygon', command=self._poly_finish,
            style='Green.TButton')
        # packed/unpacked dynamically in _update_poly_close_btn()

        # Auto-gate sensitivity slider
        self._section("AUTO-GATE")
        sens_row = ttk.Frame(p, style='TFrame')
        sens_row.pack(fill=tk.X, padx=8, pady=(0, 4))
        ttk.Label(sens_row, text='Sensitivity:', style='TLabel').pack(side=tk.LEFT)
        self.auto_sensitivity_var = tk.IntVar(value=7)
        self._sens_val_lbl = ttk.Label(sens_row, text='5',
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
            '  GMM: max populations  |  KDE/Valley: valley depth\n'
            '  Multi-Valley: min gap  |  Otsu: min class size'),
            style='Dim.TLabel').pack(anchor='w', padx=8, pady=(0, 2))

        # ── Per-axis GMM population count (for GMM Multi method) ─────────────
        gmm_row = ttk.Frame(p, style='TFrame')
        gmm_row.pack(fill=tk.X, padx=8, pady=(0, 6))
        ttk.Label(gmm_row, text='GMM pops — X:', style='Dim.TLabel'
                  ).pack(side=tk.LEFT)
        self.gmm_max_x_var = tk.IntVar(value=3)
        ttk.Spinbox(gmm_row, from_=1, to=8, width=3, font=('Arial', 8),
                    textvariable=self.gmm_max_x_var
                    ).pack(side=tk.LEFT, padx=(2, 10))
        ttk.Label(gmm_row, text='Y:', style='Dim.TLabel'
                  ).pack(side=tk.LEFT)
        self.gmm_max_y_var = tk.IntVar(value=3)
        ttk.Spinbox(gmm_row, from_=1, to=8, width=3, font=('Arial', 8),
                    textvariable=self.gmm_max_y_var
                    ).pack(side=tk.LEFT, padx=(2, 0))
        ttk.Label(gmm_row, text='  (GMM Multi only)', style='Dim.TLabel'
                  ).pack(side=tk.LEFT, padx=(4, 0))

        # Auto-gate buttons
        self._btn("GMM Multi  (all crossings, X+Y indep.)", self.auto_gate_gmm_multi,       'Purple.TButton')
        self._btn("KDE Valley  (X + Y)",                    self.auto_gate_derivative,      'Orange.TButton')
        self._btn("Otsu  (X + Y)",                          self.auto_gate_otsu,            'Teal.TButton')
        self._btn("Cluster Polygons  (HDBSCAN 2D)",         self.auto_gate_cluster_polygons,'Olive.TButton')
        self._btn("Clear Selected Gate",             self.clear_gate,                'Gray.TButton')
        self._btn("Clear All Gates",                 self.clear_all_gates,           'Gray.TButton')

        # ── GATE MANAGER ──
        self._section("GATE MANAGER")
        add_row = ttk.Frame(p, style='TFrame')
        add_row.pack(fill=tk.X, padx=8, pady=(0, 4))
        ttk.Button(add_row, text='+ Add Gate', command=self._add_gate,
                   style='Accent.TButton').pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Gate list (rebuilt by _rebuild_gate_manager)
        self.gate_manager_frame = ttk.Frame(p, style='TFrame')
        self.gate_manager_frame.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(self.gate_manager_frame, text="(no gates)", style='Dim.TLabel').pack(anchor='w')

        # ── THRESHOLDS / GATE INFO ──
        self._section("GATE INFO")
        self.thresh_panel = ttk.Frame(p, style='TFrame')
        self.thresh_panel.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(self.thresh_panel, text="(no gate selected)",
                  style='Dim.TLabel').pack(anchor='w')

        # ── STATISTICS ──
        self._section("STATISTICS")
        sm_row = ttk.Frame(p, style='TFrame')
        sm_row.pack(fill=tk.X, padx=8, pady=(0, 4))
        for val, lbl in [('perfile', 'Per file'), ('merged', 'Merged')]:
            ttk.Radiobutton(sm_row, text=lbl, variable=self.stats_mode_var,
                            value=val, command=self._update_stats_display,
                            style='TRadiobutton').pack(side=tk.LEFT, padx=4)

        self.stats_tree = ttk.Treeview(
            p, columns=('count', 'pct'), show='tree headings', height=9)
        self.stats_tree.heading('#0',    text='Region / File', anchor='w')
        self.stats_tree.heading('count', text='Count',         anchor='e')
        self.stats_tree.heading('pct',   text='%',             anchor='e')
        self.stats_tree.column('#0',    width=140, stretch=True)
        self.stats_tree.column('count', width=62,  anchor='e')
        self.stats_tree.column('pct',   width=50,  anchor='e')
        self.stats_tree.pack(fill=tk.X, padx=8, pady=(0, 4))
        # Configure region-color tags once here — no need to repeat on every refresh
        for _i, _c in enumerate(REGION_COLORS):
            self.stats_tree.tag_configure(f'rc{_i}', foreground=_c)

        # ── EXPORT ──
        self._section("EXPORT")
        self._btn("💾 Save Gates → JSON",      self.save_gates,         'Blue2.TButton')
        self._btn("📂 Load Gates ← JSON",      self.load_gates,         'Blue2.TButton')
        self._btn("Export Stats → CSV",        self.export_stats,       'Green.TButton')
        self._btn("Export Gated Data → CSV",   self.export_gated_data,  'Green.TButton')
        self._btn("📊 Batch Stats → Folder",   self.batch_export_stats, 'Teal.TButton')
        self._btn("Export Figure → PDF/PNG",   self.export_figure,      'Blue2.TButton')

        # ── VECTOR ANALYSIS ──
        self._section("VECTOR ANALYSIS")
        ttk.Label(
            p,
            text="  Requires X/Y centroid columns for two channels in the data.",
            style='Dim.TLabel', justify='left'
        ).pack(anchor='w', padx=8, pady=(0, 4))
        self._btn("🧭 Polar / Vector Analysis…",
                  self.open_polar_analysis, 'Purple.TButton')

        # ── BATCH PLOTS ──
        self._section("BATCH PLOTS")
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
        tf.pack(fill=tk.X)
        tb = NavigationToolbar2Tk(self.canvas, tf)
        tb.config(background=T['sidebar_bg'])
        tb.update()
        self.canvas.mpl_connect('button_press_event',   self._on_click)
        self.canvas.mpl_connect('motion_notify_event',  self._on_motion)
        self.canvas.mpl_connect('button_release_event', self._on_release)

    def _build_status_bar(self):
        T = self.T
        self.status_var = tk.StringVar(value="No data loaded")
        self._status_lbl = tk.Label(
            self.right, textvariable=self.status_var,
            bg=T['header_bg'], fg=T['fg_dim'],
            anchor='w', font=('Arial', 8), padx=6)
        self._status_lbl.pack(side=tk.BOTTOM, fill=tk.X)

    # ── Axes layout ───────────────────────────────────────────────────────────

    def _setup_axes(self):
        T = self.T
        self.fig.clear()
        self.fig.patch.set_facecolor(T['fig_bg'])
        self._preview_artists = []

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
                for sp in a.spines.values(): sp.set_color(T['spine'])
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
        for sp in self.ax.spines.values(): sp.set_color(T['spine'])
        self.ax.tick_params(colors=T['fg'], labelsize=8)

    # ── File management ───────────────────────────────────────────────────────

    def load_files(self):
        global _last_folder_dir
        init = _last_folder_dir or os.path.expanduser('~')
        paths = filedialog.askopenfilenames(
            title="Select CSV or FCS Files",
            initialdir=init,
            filetypes=[("Flow data", "*.csv *.fcs *.FCS"),
                       ("CSV files", "*.csv"),
                       ("FCS files", "*.fcs *.FCS"),
                       ("All files", "*.*")])
        if paths:
            _last_folder_dir = os.path.dirname(list(paths)[0])
        self._load_paths(list(paths))

    def load_from_folder(self):
        dlg = FolderScanDialog(self.root, self.T)
        self.root.wait_window(dlg)
        if dlg.result:
            self._load_paths(dlg.result)

    def _load_paths(self, paths: list):
        cidx = len(self.loaded_files)
        for path in paths:
            if path in self.loaded_files: continue
            try:
                df = self._read_data_file(path)
                self.loaded_files[path] = df
                self.file_colors[path]  = FILE_COLORS[cidx % len(FILE_COLORS)]
                cidx += 1
                self._add_file_row(path)
            except Exception as e:
                messagebox.showerror("Load Error",
                    f"Could not read {os.path.basename(path)}:\n{e}")
        self._update_channel_menus()
        self._on_active_files_changed()

    @staticmethod
    def _read_data_file(path: str) -> 'pd.DataFrame':
        """Load a CSV or FCS file and return a DataFrame."""
        ext = os.path.splitext(path)[1].lower()
        if ext == '.fcs':
            df, _ = read_fcs(path)
            return df
        else:
            return pd.read_csv(path)

    def _add_file_row(self, path: str):
        color = self.file_colors[path]
        row   = ttk.Frame(self.file_list_frame, style='TFrame')
        row.pack(fill=tk.X, pady=1)
        tk.Label(row, bg=color, width=2, relief='raised'
                 ).pack(side=tk.LEFT, padx=(0, 4), anchor='n', pady=2)
        # ✕ exclude button
        ttk.Button(row, text='✕', width=2,
                   command=lambda p=path: self._exclude_file(p),
                   style='Gray.TButton').pack(side=tk.RIGHT, padx=(2, 0), anchor='n')
        # Preserve existing checkbox state; create new var only for genuinely new files.
        # Without this guard _exclude_file → re-builds all rows → each rebuild called
        # BooleanVar(value=True), silently reselecting every surviving file.
        if path not in self.file_vars:
            self.file_vars[path] = tk.BooleanVar(value=True)
        var  = self.file_vars[path]
        name = os.path.basename(path)
        ttk.Checkbutton(row, text=name, variable=var,
                        command=self._on_active_files_changed,
                        style='TCheckbutton').pack(side=tk.LEFT,
                                                   fill=tk.X, expand=True)

    def _on_active_files_changed(self):
        """Called whenever a file checkbox is toggled or new files loaded.
        Re-computes gate stats for every currently active file, updates both
        the stats treeview and the on-plot labels to match the selection."""
        if any(g.get('applied') for g in self.gates):
            for g in self.gates:
                if g.get('applied'):
                    self._compute_gate_stats_for(g)
            self._update_stats_display()
        self.refresh_plot()

    def _select_all(self):
        """Check all file checkboxes."""
        for v in self.file_vars.values():
            v.set(True)
        self._on_active_files_changed()

    def _unselect_all(self):
        """Uncheck all file checkboxes."""
        for v in self.file_vars.values():
            v.set(False)
        self._on_active_files_changed()

    def clear_all_files(self):
        """Unload every loaded file and reset the UI."""
        if self.loaded_files and not messagebox.askyesno(
                "Clear Files",
                f"Unload all {len(self.loaded_files)} file(s)?\n"
                "(Gates are kept. Excluded files are also cleared.)"):
            return
        self.loaded_files.clear()
        self.excluded_files.clear()
        self.file_vars.clear()
        for w in self.file_list_frame.winfo_children():
            w.destroy()
        self._rebuild_excluded_list()
        self._update_channel_menus()
        self.refresh_plot()
        self._update_stats_display()
        self.status_var.set("All files cleared.")

    def _exclude_file(self, path: str):
        """Move a file from the active list to the excluded list."""
        if path not in self.loaded_files:
            return
        self.excluded_files[path] = self.loaded_files.pop(path)
        self.file_vars.pop(path, None)
        # Destroy the matching row widget
        for w in self.file_list_frame.winfo_children():
            w.destroy()
        for p in self.loaded_files:
            self._add_file_row(p)
        self._rebuild_excluded_list()
        self._on_active_files_changed()

    def _restore_file(self, path: str):
        """Move a file from the excluded list back into the active list.

        If the entry was registered via load_excluded_list() without the file
        being loaded (df is None), just drop it from the exclusion dict —
        there is nothing to restore to the active list.
        """
        if path not in self.excluded_files:
            return
        df = self.excluded_files.pop(path)
        if df is None:
            # Path was registered from a saved list but never loaded in this
            # session — simply un-register it from the exclusion set.
            self._rebuild_excluded_list()
            return
        self.loaded_files[path] = df
        self._add_file_row(path)
        self._rebuild_excluded_list()
        self._on_active_files_changed()

    def _rebuild_excluded_list(self):
        """Rebuild the excluded-files UI section."""
        for w in self.excluded_list_frame.winfo_children():
            w.destroy()
        if not self.excluded_files:
            ttk.Label(self.excluded_list_frame,
                      text="(none)", style='Dim.TLabel').pack(anchor='w')
            return
        for path in self.excluded_files:
            row = ttk.Frame(self.excluded_list_frame, style='TFrame')
            row.pack(fill=tk.X, pady=1)
            # Restore button
            ttk.Button(row, text='↩', width=2,
                       command=lambda p=path: self._restore_file(p),
                       style='Green.TButton').pack(side=tk.LEFT, padx=(0, 4), anchor='n')
            name = os.path.basename(path)
            ttk.Label(row, text=name,
                      style='Dim.TLabel', wraplength=220,
                      justify='left').pack(side=tk.LEFT, fill=tk.X, expand=True)

    def save_excluded_list(self):
        """Save the current excluded-file paths to a CSV for later reuse.

        The CSV has a single column 'Path' containing absolute paths.
        It can be loaded back via load_excluded_list() in any session,
        in either a main tab or a sub-gate tab.
        """
        if not self.excluded_files:
            messagebox.showinfo("Save Excluded List",
                                "No files are currently excluded.")
            return
        global _last_folder_dir
        init = (_last_folder_dir or
                os.path.dirname(next(iter(self.excluded_files))) or
                os.path.expanduser('~'))
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save excluded file list",
            initialdir=init,
            initialfile="excluded_files.csv",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*")])
        if not path:
            return
        try:
            pd.DataFrame({'Path': list(self.excluded_files.keys())}
                         ).to_csv(path, index=False)
            self.status_var.set(
                f"Excluded list saved: {len(self.excluded_files)} file(s) → "
                f"{os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e), parent=self.root)

    def load_excluded_list(self):
        """Load a previously saved excluded-file list CSV.

        For each path in the CSV:
          • If the file is currently in loaded_files → _exclude_file() moves it
            to the excluded panel and updates the UI normally.
          • If the file is not loaded (e.g. a different session, or the file
            was never opened) → the path is recorded in excluded_files with a
            None DataFrame so that batch_export_stats still skips it.

        Paths that are already excluded are silently skipped.
        """
        global _last_folder_dir
        init = _last_folder_dir or os.path.expanduser('~')
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Load excluded file list",
            initialdir=init,
            filetypes=[("CSV", "*.csv"), ("All files", "*")])
        if not path:
            return
        try:
            df_csv = pd.read_csv(path)
        except Exception as e:
            messagebox.showerror("Load Error", str(e), parent=self.root)
            return

        if 'Path' not in df_csv.columns:
            messagebox.showerror(
                "Load Error",
                "CSV must have a 'Path' column.\n"
                "Use a list saved by 'Save List'.",
                parent=self.root)
            return

        paths      = df_csv['Path'].dropna().astype(str).tolist()
        moved      = 0   # excluded via _exclude_file (were loaded)
        registered = 0   # added directly (not currently loaded)
        already    = 0   # already in excluded_files

        for p in paths:
            if p in self.excluded_files:
                already += 1
                continue
            if p in self.loaded_files:
                # Proper move: removes from UI list, adds to excluded panel
                self._exclude_file(p)
                moved += 1
            else:
                # Not loaded — register as excluded so batch export skips it.
                # DataFrame is None; the batch exclusion logic uses path keys,
                # not DataFrame contents, so None is safe here.
                self.excluded_files[p] = None
                registered += 1

        self._rebuild_excluded_list()
        self._on_active_files_changed()

        parts = []
        if moved:      parts.append(f"{moved} moved to excluded")
        if registered: parts.append(f"{registered} registered (not loaded)")
        if already:    parts.append(f"{already} already excluded")
        self.status_var.set("Excluded list loaded: " + ", ".join(parts) if parts
                            else "Excluded list loaded: nothing new to exclude.")

    def _active(self) -> dict:
        return {p: df for p, df in self.loaded_files.items()
                if self.file_vars[p].get()}

    def _display_files(self, active: dict = None) -> dict:
        if active is None:
            active = self._active()
        if self.view_mode_var.get() == 'cycle' and active:
            keys = list(active.keys())
            idx  = self.cycle_idx % len(keys)
            return {keys[idx]: active[keys[idx]]}
        return active

    def _update_cycle_label(self, active: dict = None):
        if active is None:
            active = self._active()
        if self.view_mode_var.get() == 'cycle' and active:
            keys = list(active.keys())
            idx  = self.cycle_idx % len(keys)
            self.cycle_label_var.set(
                f'{idx+1}/{len(keys)}  {os.path.basename(keys[idx])[:20]}')
        else:
            self.cycle_label_var.set('')

    def _on_view_mode_change(self):
        mode  = self.view_mode_var.get()
        state = tk.NORMAL if mode == 'cycle' else tk.DISABLED
        self._btn_prev.config(state=state)
        self._btn_next.config(state=state)
        self.cycle_idx = 0
        self._update_cycle_label()
        self.refresh_plot()

    def _cycle_prev(self):
        n = len(self._active())
        if n: self.cycle_idx = (self.cycle_idx - 1) % n
        self._update_cycle_label(); self.refresh_plot()

    def _cycle_next(self):
        n = len(self._active())
        if n: self.cycle_idx = (self.cycle_idx + 1) % n
        self._update_cycle_label(); self.refresh_plot()

    def _update_channel_menus(self):
        if not self.loaded_files: return
        all_cols = [set(df.columns) for df in self.loaded_files.values()]
        cols = sorted(set.intersection(*all_cols)) if all_cols else []
        if not cols:
            cols = list(next(iter(self.loaded_files.values())).columns)
        self.x_menu['values'] = cols
        self.y_menu['values'] = cols
        if self.x_channel is None and len(cols) >= 2:
            # First-time initialisation
            self.x_var.set(cols[0]); self.y_var.set(cols[1])
            self.x_channel = cols[0]; self.y_channel = cols[1]
        else:
            # Channels already assigned (e.g. sub-gate tab).
            # Re-sync StringVars after the values list is replaced so a
            # ttk readonly Combobox does not blank out on platforms where
            # replacing 'values' clears the displayed text.
            if self.x_channel and self.x_channel in cols:
                self.x_var.set(self.x_channel)
            elif self.x_channel and cols:
                self.x_channel = cols[0]; self.x_var.set(cols[0])
            if self.y_channel and self.y_channel in cols:
                self.y_var.set(self.y_channel)
            elif self.y_channel and cols:
                self.y_channel = cols[0]; self.y_var.set(cols[0])

    # ── Scale helpers ─────────────────────────────────────────────────────────

    def _fwd(self, a, which):
        a = np.asarray(a, float); c = self.cofactor
        if which == 'asinh':   return np.arcsinh(a / c)
        if which == 'logicle': return np.sign(a) * np.log10(1.0 + np.abs(a) / c)
        if which == 'biexp':   return np.sign(a) * np.log1p(np.abs(a))
        if which == 'log':     return np.where(a > 0, np.log10(a), np.nan)
        return a

    def _inv(self, a, which):
        a = np.asarray(a, float); c = self.cofactor
        if which == 'asinh':   return np.sinh(a) * c
        if which == 'logicle': return np.sign(a) * (10 ** np.abs(a) - 1.0) * c
        if which == 'biexp':   return np.sign(a) * (np.exp(np.abs(a)) - 1.0)
        if which == 'log':     return 10.0 ** a
        return a

    def _transform_xy(self, x_raw, y_raw):
        xt = self._fwd(np.asarray(x_raw, float), self.x_scale)
        yt = self._fwd(np.asarray(y_raw, float), self.y_scale)
        return xt, yt, np.isfinite(xt) & np.isfinite(yt)

    def _transform_xy_cached(self, path: str, x_raw, y_raw):
        """
        Cached version of _transform_xy.  Returns identical results but
        avoids repeating the numpy transform on every redraw when axes/scales
        haven't changed.  The cache key encodes all parameters that affect
        the result, so it self-invalidates on any setting change.
        """
        key = (path, self.x_channel, self.y_channel,
               self.x_scale, self.y_scale, self.cofactor)
        if key in self._tc:
            return self._tc[key]
        result = self._transform_xy(x_raw, y_raw)
        # Partial eviction (drop oldest half) to avoid a cold-cache cliff
        # where all 200 entries clear at once and the next 200 all miss.
        if len(self._tc) >= 200:
            evict = list(self._tc)[:100]
            for k in evict:
                del self._tc[k]
        self._tc[key] = result
        return result

    def apply_axes(self):
        x, y = self.x_var.get(), self.y_var.get()
        if not x or not y:
            messagebox.showwarning("Axes", "Select both X and Y channels.")
            return
        if x == self.x_channel and y == self.y_channel:
            self.refresh_plot()
            return
        self.x_channel, self.y_channel = x, y
        # Flush transform cache: new channels need fresh computation,
        # not stale entries keyed on the previous (path, x_ch, y_ch).
        self._tc.clear()
        self.refresh_plot()

    def _apply_scales(self):
        self.x_scale = self.x_scale_var.get()
        self.y_scale = self.y_scale_var.get()
        try: self.cofactor = float(self.cofactor_str.get())
        except Exception: self.cofactor = 150.0
        self.refresh_plot()

    def _on_cofactor_change(self, *_):
        try:
            v = float(self.cofactor_str.get())
            if v > 0:
                self.cofactor = v; self.refresh_plot()
        except Exception: pass

    def _set_axis_scale(self):
        for scale, setter in [(self.x_scale, self.ax.set_xscale),
                               (self.y_scale, self.ax.set_yscale)]:
            try:
                if scale in ('asinh', 'logicle'):
                    setter(scale, cofactor=self.cofactor)
                else:
                    setter(scale)
            except Exception:
                try: setter('linear')
                except Exception: pass

    # ── Threshold helpers ─────────────────────────────────────────────────────

    def _active_xbs_for(self, g: dict) -> list:
        """Return enabled X boundaries for a specific crosshair gate dict."""
        if not g or g.get('type', 'crosshair') != 'crosshair': return []
        xbs = g.get('x_boundaries', [])
        tvs = g.get('x_thresh_vars', [])
        if len(tvs) != len(xbs): return list(xbs)
        return [xb for xb, v in zip(xbs, tvs) if v.get()]

    def _active_yb_for(self, g: dict):
        """Return y_boundary for a specific crosshair gate dict if enabled.
        For multi-valley gates that have y_boundaries list, returns the first
        enabled value (backward compat for callers expecting a scalar)."""
        if not g or g.get('type', 'crosshair') != 'crosshair': return None
        # Multi-valley gate: y_boundaries list takes priority
        if g.get('y_boundaries'):
            ybs = self._active_ybs_for(g)
            return ybs[0] if ybs else None
        yb  = g.get('y_boundary')
        if yb is None: return None
        ytv = g.get('y_thresh_var')
        if ytv is None: return yb
        return yb if ytv.get() else None

    def _active_ybs_for(self, g: dict) -> list:
        """Return all active Y boundaries for a crosshair gate.
        Single-Y gates: returns [y_boundary] or [].
        Multi-Y gates:  returns enabled subset of y_boundaries list."""
        if not g or g.get('type', 'crosshair') != 'crosshair': return []
        ybs_list = g.get('y_boundaries')
        if ybs_list:
            tvs = g.get('y_thresh_vars', [])
            if len(tvs) != len(ybs_list):
                return list(ybs_list)
            return [yb for yb, v in zip(ybs_list, tvs) if v.get()]
        # Fallback: single y_boundary
        yb = self._active_yb_for(g)
        return [yb] if yb is not None else []

    def _active_xbs(self) -> list:
        """Return enabled X boundaries of the selected gate (compat)."""
        return self._active_xbs_for(self._sel_gate())

    def _active_yb(self):
        """Return y_boundary of selected gate if enabled (compat)."""
        return self._active_yb_for(self._sel_gate())

    # ── Main plot ─────────────────────────────────────────────────────────────

    def schedule_refresh(self, delay_ms: int = 80):
        """Debounced refresh: cancel any pending redraw and re-schedule.
        Sliders and checkboxes call this instead of refresh_plot directly,
        so rapid changes (e.g. dragging alpha slider) only fire one replot
        after the user pauses, not one per pixel moved."""
        if self._refresh_pending:
            try:
                self.root.after_cancel(self._refresh_pending)
            except Exception:
                pass
        self._refresh_pending = self.root.after(delay_ms, self._do_refresh)

    def _do_refresh(self):
        self._refresh_pending = None
        self.refresh_plot()

    def refresh_plot(self):
        if not self.x_channel or not self.y_channel: return
        T = self.T
        # Compute active-file dict once — reused by _update_cycle_label,
        # _display_files, and the status bar at the bottom of this method.
        active = self._active()

        need_marg = self.show_marginals_var.get()
        if (self.ax_top is not None) != need_marg:
            self._setup_axes()
        else:
            self.fig.patch.set_facecolor(T['fig_bg'])
            self.ax.set_facecolor(T['ax_bg'])
            for sp in self.ax.spines.values(): sp.set_color(T['spine'])
            if self.ax_top:
                self.ax_top.set_facecolor(T['ax_bg'])
                for sp in self.ax_top.spines.values(): sp.set_color(T['spine'])
            if self.ax_right:
                self.ax_right.set_facecolor(T['ax_bg'])
                for sp in self.ax_right.spines.values(): sp.set_color(T['spine'])

        self._update_cycle_label(active)
        display = self._display_files(active)

        # Collect all *effective* applied gates (filter out disabled crosshairs)
        applied_gates = []
        for g in self.gates:
            if not g.get('applied'): continue
            if g.get('type', 'crosshair') == 'crosshair':
                xbs = self._active_xbs_for(g)
                yb  = self._active_yb_for(g)
                if xbs or yb is not None:
                    applied_gates.append(g)
            else:
                applied_gates.append(g)

        eff_gate = bool(applied_gates)

        plot_type = self.plot_type_var.get()
        dot_size  = self.dot_size_var.get()
        alpha     = self.alpha_var.get()
        prob      = float(self.prob_var.get().strip('%')) / 100

        self.ax.clear()
        self.ax.set_facecolor(T['ax_bg'])
        if self.ax_top:
            self.ax_top.clear(); self.ax_top.set_facecolor(T['ax_bg'])
            self.ax_top.set_ylabel('Count', color=T['fg'], fontsize=7)
            for lbl in self.ax_top.get_xticklabels(): lbl.set_visible(False)
        if self.ax_right:
            self.ax_right.clear(); self.ax_right.set_facecolor(T['ax_bg'])
            self.ax_right.set_xlabel('Count', color=T['fg'], fontsize=7)
            for lbl in self.ax_right.get_yticklabels(): lbl.set_visible(False)

        total_cells = 0
        # In gated mode we build a legend entry per file (not per region)
        gated_legend_handles = []
        # Accumulators for "Fit axes to data" and GMM overlay (reused below)
        _fit_x_all: list = []
        _fit_y_all: list = []
        # Always accumulate valid raw parts — reused by the GMM overlay block
        # so it doesn't need a second pass through display files.
        _raw_x_parts: list = []
        _raw_y_parts: list = []

        for path, df in display.items():
            if self.x_channel not in df.columns or \
               self.y_channel not in df.columns: continue
            color  = self.file_colors[path]
            lbl    = os.path.basename(path)
            lbl_s  = (lbl[:28] + '…') if len(lbl) > 30 else lbl
            x_raw  = df[self.x_channel].to_numpy(dtype=float, copy=False)
            y_raw  = df[self.y_channel].to_numpy(dtype=float, copy=False)
            xt, yt, valid = self._transform_xy_cached(path, x_raw, y_raw)
            n_cells = int(valid.sum())
            total_cells += n_cells
            if valid.any():
                _raw_x_parts.append(x_raw[valid])
                _raw_y_parts.append(y_raw[valid])
            # Accumulate finite raw values for "Fit axes to data"
            if self.fit_axes_var.get() and valid.any():
                _fit_x_all.append(x_raw[valid])
                _fit_y_all.append(y_raw[valid])

            if eff_gate:
                # Render base visualization as chosen (density/contour/dot)
                # then overlay gate membership coloring on top
                if plot_type == 'Density':
                    self._plot_density(x_raw, y_raw, xt, yt, valid,
                                       dot_size, alpha * 0.5, lbl_s)
                elif plot_type == 'Contour Plot':
                    self._plot_contour(x_raw, y_raw, xt, yt, valid,
                                       color, lbl_s, dot_size, alpha * 0.4, prob)
                else:
                    # Dot mode: use full gated coloring (outside faded, IN colored)
                    pass  # handled by _plot_gated_multi below

                # Gated overlay: color IN cells by their gate membership
                self._plot_gated_multi(x_raw, y_raw, dot_size,
                                       alpha if plot_type == 'Dot Plot' else alpha * 0.85,
                                       applied_gates, color, path=path,
                                       overlay=(plot_type != 'Dot Plot'))
                h = mlines.Line2D([], [], color=color, marker='o',
                                  linestyle='None', markersize=4,
                                  label=f'{lbl_s}  (n={n_cells:,})')
                gated_legend_handles.append(h)
            elif plot_type == 'Density':
                self._plot_density(x_raw, y_raw, xt, yt, valid,
                                   dot_size, alpha, lbl_s)
            elif plot_type == 'Contour Plot':
                self._plot_contour(x_raw, y_raw, xt, yt, valid,
                                   color, lbl_s, dot_size, alpha, prob)
            else:
                self._plot_dot(x_raw, y_raw, valid, color, lbl_s,
                               dot_size, alpha)

            if self.ax_top and self.ax_right:
                xr_full, yr_full, x_edges, y_edges = self._plot_marginals(
                    x_raw, y_raw, xt, yt, valid, color)

        # ── GMM overlay on marginal histograms ───────────────────────────────
        # Drawn once, after all files' histograms, using the first applied GMM
        # gate (gmm_multi).  Controlled by show_legend_var so the user can
        # toggle it off together with the rest of the plot legend.
        if (self.ax_top and self.ax_right
                and self.show_legend_var.get()):
            gmm_gate = next(
                (g for g in self.gates
                 if g.get('applied') and g.get('auto_method') == 'gmm_multi'),
                None)
            if gmm_gate is not None and _raw_x_parts:
                # Reuse the raw parts already gathered in the main render loop
                # — no second pass through display files needed.
                x_all_raw = np.concatenate(_raw_x_parts)
                y_all_raw = np.concatenate(_raw_y_parts)
                x_t_all = self._fwd(x_all_raw, self.x_scale)
                y_t_all = self._fwd(y_all_raw, self.y_scale)
                xv_all  = x_t_all[np.isfinite(x_t_all)]
                yv_all  = y_t_all[np.isfinite(y_t_all)]
                if len(xv_all) > 1:
                    _bt_x = np.linspace(xv_all.min(), xv_all.max(), 121)
                    _be_x = self._inv(_bt_x, self.x_scale)
                else:
                    _be_x = None
                if len(yv_all) > 1:
                    _bt_y = np.linspace(yv_all.min(), yv_all.max(), 121)
                    _be_y = self._inv(_bt_y, self.y_scale)
                else:
                    _be_y = None
                gxp = gmm_gate.get('gmm_x_params')
                gyp = gmm_gate.get('gmm_y_params')
                try:
                    if gxp is not None and _be_x is not None:
                        self._plot_gmm_overlay(
                            self.ax_top, gxp,
                            'horizontal', x_all_raw, _be_x)
                except Exception:
                    pass
                try:
                    if gyp is not None and _be_y is not None:
                        self._plot_gmm_overlay(
                            self.ax_right, gyp,
                            'vertical', y_all_raw, _be_y)
                except Exception:
                    pass

        # ── Population shading on marginals for KDE / Otsu gates ──────────────
        # If a KDE Valley or Otsu crosshair gate is applied and marginals are
        # visible, shade each population band between threshold lines so the
        # user can see which region is positive / negative — the same visual
        # cue that GMM Multi provides via its Gaussian component curves.
        if self.ax_top and self.ax_right:
            _shading_gate = next(
                (g for g in self.gates
                 if g.get('applied')
                 and g.get('type', 'crosshair') == 'crosshair'
                 and g.get('auto_method') in ('kde', 'otsu')),
                None)
            if _shading_gate is not None:
                self._plot_threshold_shading(
                    _shading_gate,
                    self.ax_top, 'horizontal',
                    self.ax_right, 'vertical')

        # Draw ALL applied gate outlines + handles for selected gate.
        # _clear_preview no longer calls draw_idle(); refresh_plot owns the
        # full draw lifecycle and issues one unconditional flush at the end.
        self._preview_gate()

        fg = T['fg']
        self.fig.suptitle(f'{self.x_channel}  ×  {self.y_channel}',
                          color=fg, fontsize=10, y=0.97)
        self.ax.set_xlabel(self.x_channel, color=fg, fontsize=9)
        self.ax.set_ylabel(self.y_channel, color=fg, fontsize=9)
        if self.show_grid_var.get():
            self.ax.grid(True, alpha=0.25, color=T['grid'])
        self.ax.tick_params(colors=fg, labelsize=8)
        if self.ax_top:
            self.ax_top.tick_params(colors=fg, labelsize=6)
        if self.ax_right:
            self.ax_right.tick_params(colors=fg, labelsize=6)

        # Apply the custom axis scale BEFORE drawing region labels so that
        # the full axis transform (asinh / biexp / logicle) is in place when
        # _label_centroid() resolves text positions.  Labels placed before
        # set_xscale() can be clipped or repositioned when the axis
        # autoscale range is recalculated for the new scale type.
        self._set_axis_scale()

        # ── Fit axes to data (FlowJo-style "zoom to data") ────────────────────
        # After _set_axis_scale so the scale type is already applied.
        # Uses p0.5 / p99.5 of all valid raw values with a 5 % margin so the
        # population is centred with a small breathing room on each side.
        if self.fit_axes_var.get() and _fit_x_all:
            all_x = np.concatenate(_fit_x_all)
            all_y = np.concatenate(_fit_y_all)
            xlo_r, xhi_r = np.nanpercentile(all_x, [0.5, 99.5])
            ylo_r, yhi_r = np.nanpercentile(all_y, [0.5, 99.5])
            # Add 5 % breathing room in transform space to avoid edge clipping
            xt_lo = self._fwd(np.array([xlo_r]), self.x_scale)[0]
            xt_hi = self._fwd(np.array([xhi_r]), self.x_scale)[0]
            yt_lo = self._fwd(np.array([ylo_r]), self.y_scale)[0]
            yt_hi = self._fwd(np.array([yhi_r]), self.y_scale)[0]
            x_pad = (xt_hi - xt_lo) * 0.05
            y_pad = (yt_hi - yt_lo) * 0.05
            x_margin_lo = float(self._inv(np.array([xt_lo - x_pad]), self.x_scale)[0])
            x_margin_hi = float(self._inv(np.array([xt_hi + x_pad]), self.x_scale)[0])
            y_margin_lo = float(self._inv(np.array([yt_lo - y_pad]), self.y_scale)[0])
            y_margin_hi = float(self._inv(np.array([yt_hi + y_pad]), self.y_scale)[0])
            try:
                self.ax.set_xlim(x_margin_lo, x_margin_hi)
                self.ax.set_ylim(y_margin_lo, y_margin_hi)
            except Exception:
                pass   # non-finite limits (e.g. log of negative) → keep auto

        # ── Region % labels ───────────────────────────────────────────────────
        # Drawn AFTER _set_axis_scale() + fit-axes so that:
        #   • _label_centroid uses the correct axis transform space
        #   • axis limits are finalised before text positions are resolved
        if eff_gate and self.show_labels_var.get():
            try:
                self._draw_region_labels(applied_gates)
            except Exception:
                pass   # never let a label error crash the full refresh

        if self.show_legend_var.get():
            if eff_gate and gated_legend_handles:
                self.ax.legend(handles=gated_legend_handles,
                               fontsize=7, loc='lower left',
                               framealpha=0.6, facecolor=T['legend_bg'],
                               labelcolor=fg)
            else:
                handles, _ = self.ax.get_legend_handles_labels()
                if handles:
                    self.ax.legend(fontsize=7, markerscale=3, loc='lower left',
                                   framealpha=0.6, facecolor=T['legend_bg'],
                                   labelcolor=fg)

        self.status_var.set(
            f"Shown: {len(display)}/{len(active)} files  │  "
            f"Cells: {total_cells:,}  │  "
            f"{self.x_channel} vs {self.y_channel}  │  "
            f"Scale: {self.x_scale}/{self.y_scale}"
            + (f"  │  {len(applied_gates)} gate(s) ON" if eff_gate else ""))

        # Single unconditional flush — renders scatter + gate outlines +
        # labels + axis styling all at once, avoiding partial repaints.
        self.canvas.draw_idle()

    # ── Plot helpers ──────────────────────────────────────────────────────────

    def _plot_dot(self, x_raw, y_raw, valid, color, label, dot_size, alpha):
        xv = x_raw[valid]; yv = y_raw[valid]
        n  = len(xv)
        if n > RENDER_CAP:
            idx = _get_rng(2).choice(n, RENDER_CAP, replace=False)
            xv, yv = xv[idx], yv[idx]
        self.ax.scatter(xv, yv, s=dot_size, alpha=alpha, color=color,
                        label=f'{label} (n={valid.sum():,})',
                        rasterized=True, linewidths=0)

    def _plot_density(self, x_raw, y_raw, xt, yt, valid,
                      dot_size, alpha, label):
        xv = xt[valid]; yv = yt[valid]
        # Clip to [1st, 99th] percentile in transform space to prevent extreme
        # outliers from inflating KDE bandwidth and flattening the density map
        xlo, xhi = np.nanpercentile(xv, [1, 99])
        ylo, yhi = np.nanpercentile(yv, [1, 99])
        core = (xv >= xlo) & (xv <= xhi) & (yv >= ylo) & (yv <= yhi)
        xc = xv[core]; yc = yv[core]
        n  = len(xc)
        if n < 2: return

        # ── Fit KDE on subsample ──────────────────────────────────────────
        if n > KDE_SUBSAMPLE:
            idx  = _get_rng(0).choice(n, KDE_SUBSAMPLE, replace=False)
            kern = gaussian_kde(np.vstack([xc[idx], yc[idx]]))
        else:
            kern = gaussian_kde(np.vstack([xc, yc]))

        # ── Evaluate on a 128×128 grid (fast) then interpolate per-cell ──
        # This replaces kern(all_points) which is O(n×k) → now O(grid + n·log·grid)
        GRID = 96
        xg = np.linspace(xlo, xhi, GRID)
        yg = np.linspace(ylo, yhi, GRID)
        xmg, ymg = np.meshgrid(xg, yg, indexing='ij')
        Z = kern(np.vstack([xmg.ravel(), ymg.ravel()])).reshape(GRID, GRID)
        interp  = RegularGridInterpolator(
            (xg, yg), Z, method='linear',
            bounds_error=False, fill_value=float(Z.min()))
        density = interp(np.column_stack([xv, yv]))

        # ── Render cap: random subsample to preserve full spatial coverage ──
        # Do NOT bias toward high-density — that drops all sparse scatter,
        # showing only the dense cluster. Random sampling keeps every region
        # of the plot represented; sorting by density gives painter's order.
        xr = x_raw[valid]; yr = y_raw[valid]
        n_valid = len(xr)
        if n_valid > RENDER_CAP:
            rng  = _get_rng(3)
            keep = rng.choice(n_valid, RENDER_CAP, replace=False)
            xr   = xr[keep]; yr = yr[keep]
            dens_plot = density[keep]
        else:
            dens_plot = density
        order = np.argsort(dens_plot)           # painter's order: dense on top
        vlo   = float(np.nanpercentile(density, 1))    # vmin/vmax from ALL data
        vhi   = float(np.nanpercentile(density, 99))
        self.ax.scatter(xr[order], yr[order],
                        c=dens_plot[order], cmap='jet',
                        s=dot_size, alpha=alpha, rasterized=True, linewidths=0,
                        vmin=vlo, vmax=vhi,
                        label=f'{label} (n={valid.sum():,})')

    def _plot_contour(self, x_raw, y_raw, xt, yt, valid,
                      color, label, dot_size, alpha, prob_level):
        xv = xt[valid]; yv = yt[valid]
        n  = len(xv)
        if n < 20:
            return self._plot_dot(x_raw, y_raw, valid, color, label,
                                  dot_size, alpha)
        if n > KDE_SUBSAMPLE:
            idx  = _get_rng(0).choice(n, KDE_SUBSAMPLE, replace=False)
            kern = gaussian_kde(np.vstack([xv[idx], yv[idx]]))
        else:
            kern = gaussian_kde(np.vstack([xv, yv]))

        # Grid evaluation for contour surface (fast; no per-point KDE call)
        GRID = 96
        xg_t = np.linspace(xv.min(), xv.max(), GRID)
        yg_t = np.linspace(yv.min(), yv.max(), GRID)
        xmg, ymg = np.meshgrid(xg_t, yg_t, indexing='ij')
        Z = kern(np.vstack([xmg.ravel(), ymg.ravel()])).reshape(GRID, GRID)

        xg_raw = self._inv(xmg, self.x_scale)
        yg_raw = self._inv(ymg, self.y_scale)
        s_z    = np.sort(Z.ravel())
        cum    = np.cumsum(s_z) / s_z.sum()
        lv     = float(np.interp(prob_level, cum, s_z))

        # Classify per-point inside/outside via grid interpolation (not kern eval)
        interp   = RegularGridInterpolator(
            (xg_t, yg_t), Z, method='linear',
            bounds_error=False, fill_value=float(Z.min()))
        pt_dens  = interp(np.column_stack([xv, yv]))
        outside  = pt_dens < lv

        self.ax.contourf(xg_raw, yg_raw, Z, levels=12,
                         cmap='viridis', alpha=0.35)
        c = self.ax.contour(xg_raw, yg_raw, Z, levels=[lv],
                             colors=[color], linewidths=0.5)
        self.ax.clabel(c, fmt={lv: f'{prob_level*100:.0f}%'},
                        fontsize=8, colors=[color])

        # Render cap on outlier scatter (random subsample preserves coverage)
        xo = x_raw[valid][outside]; yo = y_raw[valid][outside]
        if len(xo) > RENDER_CAP:
            idx2 = _get_rng(4).choice(len(xo), RENDER_CAP, replace=False)
            xo, yo = xo[idx2], yo[idx2]
        self.ax.scatter(xo, yo,
                        s=dot_size, color=color, alpha=alpha, linewidths=0,
                        label=f'{label} outliers ({outside.sum():,})',
                        rasterized=True)

    def _plot_gated_multi(self, x_raw, y_raw, dot_size, alpha,
                          applied_gates: list, file_color: str, path: str = None,
                          overlay: bool = False):
        """
        Color cells by gate membership — single scatter() call via RGBA array.

        One scatter call regardless of gate/region count eliminates the N×scatter
        overhead that dominated render time for large files.  Outside cells are
        faded (or invisible when overlay=True); IN cells use their gate color.

        When n > RENDER_CAP the display is subsampled:
          • ALL IN-region cells are always kept (gate boundaries stay sharp).
          • Outside/faded cells are randomly thinned to fill the remaining budget.
        Gate stats are NOT affected — they run on the full array elsewhere.
        """
        xa = np.asarray(x_raw, float)
        ya = np.asarray(y_raw, float)
        n  = len(xa)

        out_alpha = 0.0 if overlay else max(alpha * 0.25, 0.05)

        # ── Build per-cell RGBA array ─────────────────────────────────────
        rgba    = np.empty((n, 4), dtype=np.float32)
        rgba[:] = _hex_to_rgba(file_color, out_alpha)
        in_any  = np.zeros(n, bool)

        for gate in applied_gates:
            regions, colors = self._gate_mask_for(gate, xa, ya,
                                                   _cache_path=path)
            gt = gate.get('type', 'crosshair')
            if gt == 'crosshair':
                for (rname, mask), c in zip(regions.items(), colors):
                    rgba[mask] = _hex_to_rgba(c, alpha)
                    in_any[mask] = True
            else:
                in_mask = regions.get('IN', np.zeros(n, bool))
                c = gate.get('color', colors[0] if colors else file_color)
                rgba[in_mask] = _hex_to_rgba(c, alpha)
                in_any[in_mask] = True

        # ── Render-cap subsampling ────────────────────────────────────────
        # Always keep all IN cells; thin outside cells to stay under cap.
        if n > RENDER_CAP:
            in_idx  = np.where(in_any)[0]
            out_idx = np.where(~in_any)[0]
            budget  = max(0, RENDER_CAP - len(in_idx))
            if budget < len(out_idx):
                rng     = _get_rng(1)
                out_idx = rng.choice(out_idx, budget, replace=False)
            keep    = np.concatenate([in_idx, out_idx])
            xa, ya, rgba = xa[keep], ya[keep], rgba[keep]

        # ── Single scatter call ───────────────────────────────────────────
        visible = rgba[:, 3] > 0
        if visible.any():
            self.ax.scatter(xa[visible], ya[visible],
                            c=rgba[visible], s=dot_size,
                            rasterized=True, linewidths=0)

    def _plot_marginals(self, x_raw, y_raw, xt, yt, valid, color):
        xv = xt[valid]; yv = yt[valid]
        xr = x_raw[valid]; yr = y_raw[valid]
        # Subsample raw values for histogram binning — distributions are
        # visually identical above ~30k points, but hist() slows with 100k+
        MARG_MAX = 30_000
        if len(xr) > MARG_MAX:
            idx = _get_rng(5).choice(len(xr), MARG_MAX, replace=False)
            xr_h = xr[idx]; yr_h = yr[idx]
            xv_h = xv[idx]; yv_h = yv[idx]
        else:
            xr_h = xr; yr_h = yr; xv_h = xv; yv_h = yv
        x_edges = y_edges = None
        if len(xv_h) > 1 and self.ax_top:
            bt = np.linspace(xv.min(), xv.max(), 121)   # bins from full range
            br = self._inv(bt, self.x_scale)
            _, x_edges, _ = self.ax_top.hist(
                xr_h, bins=br, color=color, alpha=0.55,
                histtype='stepfilled', linewidth=0.5)
        if len(yv_h) > 1 and self.ax_right:
            bt = np.linspace(yv.min(), yv.max(), 121)
            br = self._inv(bt, self.y_scale)
            _, y_edges, _ = self.ax_right.hist(
                yr_h, bins=br, color=color, alpha=0.55,
                histtype='stepfilled',
                orientation='horizontal', linewidth=0.5)
        return xr, yr, x_edges, y_edges

    def _plot_gmm_overlay(self, ax, gmm_params: dict,
                          orientation: str, hist_data_raw: np.ndarray,
                          bin_edges_raw: np.ndarray):
        """
        Draw per-component Gaussian curves on a marginal histogram axis,
        scaled to match the histogram counts.

        Strategy: the GMM was fitted in transform space where bins are
        *uniform* (linspace).  The scale factor is therefore simple:
            counts = pdf_transform(x_t) × n_total × bin_width_transform
        The curve is evaluated on a dense transform-space grid, then
        back-transformed to raw space for plotting (matching the x-axis
        already used by the histogram).  No Jacobian needed.

        The legend is placed outside the histogram bars — anchored to the
        top-right corner of the axes bounding box via bbox_to_anchor so it
        never overlaps the data.
        """
        from scipy.stats import norm as _norm

        means_t   = gmm_params['means_t']
        means_raw = gmm_params['means_raw']
        weights   = gmm_params['weights']
        stds_t    = gmm_params['stds_t']
        scale     = gmm_params['scale']
        lo_t, hi_t = gmm_params['data_range_t']
        n_comp    = len(means_t)

        # Dense grid in transform space (where the GMM lives) → raw for x-axis
        x_t   = np.linspace(lo_t, hi_t, 1024)
        x_raw = self._inv(x_t, scale)

        # Scale factor: transform-space bin width (bins were linspace → uniform)
        # The histogram used 120 bins over [lo_t, hi_t], so:
        n_bins   = 120
        bw_t     = (hi_t - lo_t) / n_bins          # uniform bin width in transform space
        n_total  = len(hist_data_raw)
        scale_f  = n_total * bw_t                   # pdf_t × scale_f → counts

        component_colors = [
            '#ff6b6b', '#74d7e8', '#ffd93d', '#6bcb77', '#c77dff',
            '#ff9a3c', '#4d96ff', '#ff6bcd', '#4ecdc4', '#a3e048',
        ]
        legend_handles = []

        for i in range(n_comp):
            pdf_t     = weights[i] * _norm.pdf(x_t, means_t[i], stds_t[i])
            pdf_count = pdf_t * scale_f

            col = component_colors[i % len(component_colors)]
            mu_r = means_raw[i]
            lbl  = f'C{i+1}  μ={mu_r:,.0f}  w={weights[i]:.2f}'

            if orientation == 'horizontal':
                ax.plot(x_raw, pdf_count, color=col, lw=1.0, ls='--', zorder=5)
            else:
                ax.plot(pdf_count, x_raw, color=col, lw=1.0, ls='--', zorder=5)
            legend_handles.append(
                mlines.Line2D([], [], color=col, lw=1.0, ls='--', label=lbl))

        T   = self.T
        ncol = 2 if n_comp > 3 else 1

        # Anchor legend to the top-left corner of the axes (outside the tallest
        # histogram bars which tend to be on the right for flow data).
        # bbox_to_anchor=(0, 1) = top-left corner of axes in axes coordinates;
        # loc='upper left' makes the legend box grow downward from that corner.
        # For the vertical (right) histogram, bars grow leftward from the y-axis,
        # so the empty space is at the bottom — anchor there instead.
        if orientation == 'horizontal':
            bbox  = (0.0, 1.0)
            loc   = 'upper left'
        else:
            bbox  = (1.0, 0.0)
            loc   = 'lower right'

        ax.legend(
            handles=legend_handles,
            fontsize=5.5,
            loc=loc,
            bbox_to_anchor=bbox,
            bbox_transform=ax.transAxes,
            framealpha=0.75,
            facecolor=T['legend_bg'],
            labelcolor=T['fg'],
            handlelength=1.6,
            borderpad=0.5,
            labelspacing=0.25,
            ncol=ncol,
        )

    def _plot_threshold_shading(self, gate: dict,
                                ax_h, orient_h: str,
                                ax_v, orient_v: str):
        """
        Shade population bands on marginal histograms for KDE/Otsu gates.

        For the horizontal (top) histogram (X axis) and the vertical (right)
        histogram (Y axis), each band between consecutive threshold lines is
        filled with a semi-transparent colour matching the REGION_COLORS palette
        and labelled with the population name (e.g. TH+, VGLUT1-).

        This gives the same visual population feedback that GMM Multi provides
        via Gaussian curve overlays, but for the simpler single-threshold methods.
        """
        T = self.T

        xbs = self._active_xbs_for(gate)   # list of active X threshold raw values
        ybs = self._active_ybs_for(gate)   # list of active Y threshold raw values

        def _shade_axis(ax, thresholds_raw, scale_name, channel, orientation):
            """Draw region bands on one marginal histogram axis."""
            if not thresholds_raw:
                return
            thresholds_raw = sorted(thresholds_raw)

            # Axis limits from the histogram bars already drawn
            try:
                if orientation == 'horizontal':
                    lo_raw, hi_raw = ax.get_xlim()
                else:
                    lo_raw, hi_raw = ax.get_ylim()
            except Exception:
                return

            # Build band boundaries: [lo, t1, t2, ..., hi]
            boundaries = [lo_raw] + list(thresholds_raw) + [hi_raw]
            n_bands    = len(boundaries) - 1

            # Band label suffixes: first band is "-", last is "+", middle "m"
            fluor = self._fluor(channel or '')
            if n_bands == 2:
                labels = [f'{fluor}−', f'{fluor}+']
            elif n_bands == 3:
                labels = [f'{fluor}−', f'{fluor}(m)', f'{fluor}+']
            else:
                mids   = [f'{fluor}(m{i})' for i in range(1, n_bands - 1)]
                labels = [f'{fluor}−'] + mids + [f'{fluor}+']

            for i in range(n_bands):
                b0 = boundaries[i]
                b1 = boundaries[i + 1]
                col = REGION_COLORS[i % len(REGION_COLORS)]
                try:
                    if orientation == 'horizontal':
                        ax.axvspan(b0, b1, alpha=0.13, color=col,
                                   linewidth=0, zorder=1)
                        mid = (b0 + b1) / 2.0
                        y_top = ax.get_ylim()[1]
                        ax.text(mid, y_top * 0.88, labels[i],
                                ha='center', va='top', fontsize=6,
                                color=col, fontweight='bold',
                                clip_on=True, zorder=6)
                    else:
                        ax.axhspan(b0, b1, alpha=0.13, color=col,
                                   linewidth=0, zorder=1)
                        mid = (b0 + b1) / 2.0
                        x_right = ax.get_xlim()[1]
                        ax.text(x_right * 0.96, mid, labels[i],
                                ha='right', va='center', fontsize=6,
                                color=col, fontweight='bold',
                                rotation=90, clip_on=True, zorder=6)
                except Exception:
                    pass

            # Draw threshold lines on the marginal axis
            for thresh in thresholds_raw:
                try:
                    if orientation == 'horizontal':
                        ax.axvline(thresh, color=T['gate_line'],
                                   lw=0.8, ls='--', alpha=0.7, zorder=4)
                    else:
                        ax.axhline(thresh, color=T['gate_line'],
                                   lw=0.8, ls='--', alpha=0.7, zorder=4)
                except Exception:
                    pass

        _shade_axis(ax_h, xbs, self.x_scale, self.x_channel, 'horizontal')
        _shade_axis(ax_v, ybs, self.y_scale, self.y_channel, 'vertical')

    # ── Fluorophore / population naming ─────────────────────────────────────────

    @staticmethod
    @functools.lru_cache(maxsize=64)
    def _fluor(channel: str) -> str:
        """Extract fluorophore from last _-separated segment.
        e.g. 'Bkgd_Corr_Intensity_TH' → 'TH'
             'CD3' → 'CD3' (no underscore → use whole name)
        Cached: channel names are fixed per session.
        """
        parts = channel.rsplit('_', 1)
        return parts[-1] if parts[-1] else channel

    def _region_masks(self, xa, ya, x_boundaries, y_boundary,
                      y_boundaries=None):
        """
        Returns (regions_dict, colors_list).

        y_boundaries (list, optional): if provided, creates a full X×Y grid.
        y_boundary   (scalar, optional): classic single-Y threshold (backward compat).
        """
        xa  = np.asarray(xa, float)
        ya  = np.asarray(ya, float)
        xbs = sorted(x_boundaries) if x_boundaries else []

        # Resolve Y boundaries into a sorted list
        if y_boundaries is not None and len(y_boundaries) > 0:
            ybs = sorted(float(v) for v in y_boundaries)
        elif y_boundary is not None:
            ybs = [float(y_boundary)]
        else:
            ybs = []

        n_x = len(xbs)
        n_y = len(ybs)
        has_x = n_x > 0
        has_y = n_y > 0

        xf = self._fluor(self.x_channel or 'X')
        yf = self._fluor(self.y_channel or 'Y')

        if not has_x and not has_y:
            return {}, []

        # ── X band labels ──
        if n_x == 0:
            x_band_labels = []
        elif n_x == 1:
            x_band_labels = [f'{xf}-', f'{xf}+']
        elif n_x == 2:
            x_band_labels = [f'{xf}-', f'{xf}(m)', f'{xf}+']
        else:
            mid = [f'{xf}(m{i})' for i in range(1, n_x)]
            x_band_labels = [f'{xf}-'] + mid + [f'{xf}+']

        # ── Y band labels ──
        if n_y == 0:
            y_band_labels = []
        elif n_y == 1:
            y_band_labels = [f'{yf}-', f'{yf}+']
        elif n_y == 2:
            y_band_labels = [f'{yf}-', f'{yf}(m)', f'{yf}+']
        else:
            mid = [f'{yf}(m{i})' for i in range(1, n_y)]
            y_band_labels = [f'{yf}-'] + mid + [f'{yf}+']

        # ── Compute X and Y membership masks ──
        if has_x:
            x_edges = [-np.inf] + xbs + [np.inf]
            x_masks = [(xa > x_edges[i]) & (xa <= x_edges[i+1])
                       for i in range(len(x_edges) - 1)]
        else:
            x_masks = [np.ones(len(xa), bool)]
            x_band_labels = ['All']

        if has_y:
            y_edges = [-np.inf] + ybs + [np.inf]
            y_masks = [(ya > y_edges[i]) & (ya <= y_edges[i+1])
                       for i in range(len(y_edges) - 1)]
        else:
            y_masks = [np.ones(len(ya), bool)]
            y_band_labels = ['All']

        if not has_x:
            # Y-only gate
            regions = {}; colors = []
            # Reverse so positive (highest) band comes first
            for i, (ylbl, ym) in enumerate(
                    zip(reversed(y_band_labels), reversed(y_masks))):
                regions[ylbl] = ym
                colors.append(REGION_COLORS[i % len(REGION_COLORS)])
            return regions, colors

        if not has_y:
            # X-only gate
            regions = {}; colors = []
            for i, (xlbl, xm) in enumerate(zip(x_band_labels, x_masks)):
                regions[xlbl] = xm
                colors.append(REGION_COLORS[i % len(REGION_COLORS)])
            return regions, colors

        # Both axes: full Y×X grid (Y positive first in legend)
        regions = {}; colors = []; ci = 0
        for yi in range(len(y_band_labels) - 1, -1, -1):   # Y high → low
            ylbl = y_band_labels[yi]
            ym   = y_masks[yi]
            for xi, (xlbl, xm) in enumerate(zip(x_band_labels, x_masks)):
                lbl = f'{ylbl}/{xlbl}'
                regions[lbl] = xm & ym
                colors.append(REGION_COLORS[ci % len(REGION_COLORS)])
                ci += 1
        return regions, colors

    def _on_gate_mode_change(self):
        """Called when user switches Off / Draw mode."""
        mode = self.gate_mode_var.get()
        self.gate_var.set(mode == 'draw')

        if mode == 'none':
            self._gate_hint_var.set('Off — double-click region to open sub-gate')
            self._poly_active = False
            self._poly_cursor = None
            self._update_poly_close_btn()
        elif mode == 'draw':
            self._on_gate_type_change()

        self.refresh_plot()

    def _on_gate_type_change(self):
        """Update hint text only — does NOT clear existing gates."""
        if self.gate_mode_var.get() != 'draw':
            return
        hints = {
            'crosshair': 'Draw: click & drag to place H/V lines',
            'rectangle': 'Draw: click & drag to draw a rectangle',
            'ellipse':   'Draw: click & drag to draw an ellipse',
            'polygon':   'Draw: click vertices  |  ✓ Close Polygon or dbl-click',
        }
        self._gate_hint_var.set(hints.get(self.gate_type_var.get(), ''))

    # ── Gate manager helpers ──────────────────────────────────────────────────

    def _sel_gate(self):
        """Return the currently selected gate dict or None."""
        return next((g for g in self.gates if g['id'] == self._sel_gate_id), None)

    def _draw_gate_obj(self):
        """Return the gate currently being drawn, or None."""
        return next((g for g in self.gates if g['id'] == self._draw_gate_id), None)

    def _gate_color(self, idx):
        return GATE_PALETTE[idx % len(GATE_PALETTE)]

    def _add_gate(self, auto_type: str = None, auto_apply: dict = None,
                  auto_method: str = None):
        """
        Create a new (empty) gate of the current type and select it.
        auto_type / auto_apply are used by auto-gate methods to inject geometry.
        auto_method: string tag identifying which auto-gate created this gate
                     (e.g. 'gmm', 'kde', 'otsu').  None = manual gate.
        When called interactively (no auto_apply), also enables Draw mode.
        """
        # Switch to Draw mode automatically so the user can immediately draw
        if auto_apply is None and self.gate_mode_var.get() == 'none':
            self.gate_mode_var.set('draw')
            self.gate_var.set(True)
            self._on_gate_type_change()
        gid   = self._next_gate_id
        self._next_gate_id += 1
        color = self._gate_color(len(self.gates))
        gt    = auto_type or self.gate_type_var.get()
        gate  = {
            'id': gid, 'name': f'Gate {gid + 1}',
            'type': gt, 'applied': False,
            'auto_method': auto_method,          # None = manual; str = auto tag
            'color': color,
            'linestyle': '-',    # '-' | '--' | ':'
            'linewidth': 0.5,    # float
            # crosshair
            'x_boundaries': [], 'y_boundary': None,
            'x_thresh_vars': [], 'y_thresh_var': None,
            # multi-valley crosshair (Y can also have multiple thresholds)
            'y_boundaries': None, 'y_thresh_vars': [],
            # rect / ellipse
            'x0': 0.0, 'y0': 0.0, 'x1': 0.0, 'y1': 0.0,
            # polygon
            'vertices': [],
        }
        if auto_apply:
            gate.update(auto_apply)
            gate['applied'] = True
        self.gates.append(gate)
        self._sel_gate_id  = gid
        self._draw_gate_id = gid if not auto_apply else None
        self._rebuild_gate_manager()
        self._rebuild_thresh_panel()
        return gate

    def _del_gate(self, gid: int):
        """Delete gate by id; select nearest remaining gate."""
        # Find index before removing so we can select a neighbour
        idx_before = next((i for i, g in enumerate(self.gates) if g['id'] == gid), None)
        self.gates = [g for g in self.gates if g['id'] != gid]
        if self._hover_gate_id == gid:
            self._hover_gate_id = None
        if self._pinned_gate_id == gid:
            self._pinned_gate_id = None
        self._handle_px_cache.pop(gid, None)
        if self._sel_gate_id == gid:
            if self.gates:
                # Select the gate at the same position, or the last one
                sel_idx = min(idx_before, len(self.gates) - 1) if idx_before is not None else -1
                self._sel_gate_id = self.gates[sel_idx]['id']
            else:
                self._sel_gate_id = None
        if self._draw_gate_id == gid:
            self._draw_gate_id = None
            self.moving_gate   = False
            self._poly_active  = False
        if gid in self.gate_stats:
            del self.gate_stats[gid]
        self._rebuild_gate_manager()
        self._rebuild_thresh_panel()
        self._update_stats_display()
        self.refresh_plot()

    def _select_gate(self, gid: int):
        """Select a gate for stats / editing."""
        self._sel_gate_id = gid
        self._rebuild_thresh_panel()
        self._update_stats_display()
        self.refresh_plot()

    def _rename_gate(self, gid: int):
        """Open a simple rename dialog."""
        gate = next((g for g in self.gates if g['id'] == gid), None)
        if not gate: return
        dlg = tk.Toplevel(self.root)
        dlg.title("Rename gate")
        dlg.geometry("280x90")
        dlg.resizable(False, False)
        T = self.T
        dlg.configure(bg=T['sidebar_bg'])
        ttk.Label(dlg, text="New name:").pack(pady=(12, 2))
        var = tk.StringVar(value=gate['name'])
        ent = ttk.Entry(dlg, textvariable=var, width=28)
        ent.pack(padx=10); ent.select_range(0, tk.END); ent.focus()
        def _ok(*_):
            name = var.get().strip()
            if name: gate['name'] = name
            dlg.destroy()
            self._rebuild_gate_manager()
            self._update_stats_display()
            self.refresh_plot()
        ent.bind('<Return>', _ok)
        ttk.Button(dlg, text='OK', command=_ok).pack(pady=4)
        dlg.grab_set()
        dlg.wait_window()

    def _rebuild_gate_manager(self):
        """Rebuild the gate list rows inside gate_manager_frame."""
        for w in self.gate_manager_frame.winfo_children():
            w.destroy()
        if not self.gates:
            ttk.Label(self.gate_manager_frame, text="(no gates)",
                      style='Dim.TLabel').pack(anchor='w')
            return
        for gate in self.gates:
            row = ttk.Frame(self.gate_manager_frame, style='TFrame')
            row.pack(fill=tk.X, pady=1)
            # Coloured square
            tk.Label(row, bg=gate['color'], width=2,
                     relief='raised').pack(side=tk.LEFT, padx=(0, 4))
            # Selection indicator
            prefix = '▸ ' if gate['id'] == self._sel_gate_id else '   '
            name_lbl = ttk.Label(
                row, text=f"{prefix}{gate['name']}",
                style='TLabel')
            name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            name_lbl.bind('<Button-1>',
                          lambda e, gid=gate['id']: self._select_gate(gid))
            # Rename button
            ttk.Button(row, text='✎',
                       command=lambda gid=gate['id']: self._rename_gate(gid),
                       style='TButton', width=2).pack(side=tk.RIGHT, padx=1)
            # Delete button
            ttk.Button(row, text='✗',
                       command=lambda gid=gate['id']: self._del_gate(gid),
                       style='Red.TButton', width=2).pack(side=tk.RIGHT, padx=1)
            # ── Style row: linestyle + linewidth ──
            style_row = ttk.Frame(self.gate_manager_frame, style='TFrame')
            style_row.pack(fill=tk.X, pady=(0, 3), padx=(20, 4))
            # Linestyle
            ls_var = tk.StringVar(value=gate.get('linestyle', '-'))
            ls_cb  = ttk.Combobox(style_row, textvariable=ls_var,
                                   values=['─── Solid', '- - Dashed', '··· Dotted'],
                                   state='readonly', width=11,
                                   font=('Arial', 7))
            ls_cb.pack(side=tk.LEFT, padx=(0, 4))
            # Map display value → mpl linestyle
            _LS_MAP = {'─── Solid': '-', '- - Dashed': '--', '··· Dotted': ':'}
            _LS_INV = {v: k for k, v in _LS_MAP.items()}
            ls_var.set(_LS_INV.get(gate.get('linestyle', '-'), '─── Solid'))
            def _on_ls(*_args, g=gate, v=ls_var):
                g['linestyle'] = _LS_MAP.get(v.get(), '-')
                self._preview_gate()
                self.canvas.draw_idle()
                self.schedule_refresh(120)   # redraws colored cells with new outline
            ls_var.trace_add('write', _on_ls)
            # Linewidth
            lw_var = tk.DoubleVar(value=gate.get('linewidth', 0.5))
            ttk.Label(style_row, text='w:', style='Dim.TLabel').pack(side=tk.LEFT)
            lw_sb  = ttk.Spinbox(style_row, from_=0.5, to=5.0, increment=0.5,
                                  textvariable=lw_var, width=4,
                                  font=('Arial', 7))
            lw_sb.pack(side=tk.LEFT)
            def _on_lw(*_args, g=gate, v=lw_var):
                try:
                    g['linewidth'] = float(v.get())
                except (ValueError, tk.TclError):
                    pass
                self._preview_gate()
                self.canvas.draw_idle()
                self.schedule_refresh(200)   # spinbox fires many events; debounce
            lw_var.trace_add('write', _on_lw)

    def _update_poly_close_btn(self):
        """Show/hide the Close Polygon button based on polygon draw state."""
        try:
            if self._poly_active:
                self._poly_close_btn.pack(fill=tk.X, padx=16, pady=(0, 4))
            else:
                self._poly_close_btn.pack_forget()
        except Exception:
            pass

    # ── Unified gate mask ─────────────────────────────────────────────────────

    def _gate_mask_for(self, gate: dict, xa, ya, _cache_path: str = None):
        """
        Unified gate-inclusion test for one gate dict.
        Returns (regions_dict, colors_list).

        crosshair → delegates to _region_masks (multi-quadrant, fluorophore labels)
        rectangle/ellipse/polygon → {'IN': mask_in, 'OUT': mask_out}

        _cache_path: when provided, the result is stored in self._gmc keyed by
        (path, x_ch, y_ch, gate_id, gate_sig) and reused on subsequent calls
        without recomputation as long as the gate geometry hasn't changed.
        """
        if not gate or not gate.get('applied'):
            return {}, []

        # Callers in the hot render path (_plot_gated_multi, _compute_gate_stats_for)
        # always pass float64 ndarrays.  np.asarray is a no-op on those but still
        # takes ~1µs to check the dtype.  We guard the rare case (e.g. list input
        # from a test or _open_subgate) with a fast isinstance check instead.
        if not isinstance(xa, np.ndarray) or xa.dtype != np.float64:
            xa = np.asarray(xa, float)
        if not isinstance(ya, np.ndarray) or ya.dtype != np.float64:
            ya = np.asarray(ya, float)

        # ── Persistent cache lookup ───────────────────────────────────────
        if _cache_path is not None:
            sig = _gate_sig(gate)
            ck  = (_cache_path, self.x_channel, self.y_channel,
                   gate['id'], sig)
            if ck in self._gmc:
                cached_regions, cached_colors = self._gmc[ck]
                # Safety: verify mask length matches current input to guard
                # against stale cache entries (e.g. from a differently-sized
                # filtered DataFrame in the Polar window or sub-gate tabs).
                if cached_regions:
                    first_mask = next(iter(cached_regions.values()))
                    if len(first_mask) == len(xa):
                        return cached_regions, cached_colors
                    # Length mismatch → fall through and recompute

        gt = gate.get('type', 'crosshair')
        c  = gate.get('color', GATE_PALETTE[0])

        if gt == 'crosshair':
            xbs  = self._active_xbs_for(gate)
            yb   = self._active_yb_for(gate)
            ybs  = gate.get('y_boundaries')   # multi-Y list if present
            if ybs:
                active_ybs = self._active_ybs_for(gate)
                result = self._region_masks(xa, ya, xbs, None,
                                            y_boundaries=active_ybs)
            else:
                result = self._region_masks(xa, ya, xbs, yb)

        elif gt == 'rectangle':
            xlo = min(gate['x0'], gate['x1']); xhi = max(gate['x0'], gate['x1'])
            ylo = min(gate['y0'], gate['y1']); yhi = max(gate['y0'], gate['y1'])
            mask = (xa >= xlo) & (xa <= xhi) & (ya >= ylo) & (ya <= yhi)
            result = {'IN': mask, 'OUT': ~mask}, [c, REGION_COLORS[1]]

        elif gt == 'ellipse':
            cx = (gate['x0'] + gate['x1']) / 2.0
            cy = (gate['y0'] + gate['y1']) / 2.0
            a  = abs(gate['x1'] - gate['x0']) / 2.0
            b  = abs(gate['y1'] - gate['y0']) / 2.0
            if a < 1e-12 or b < 1e-12:
                return {}, []
            fin  = np.isfinite(xa) & np.isfinite(ya)
            mask = np.zeros(len(xa), bool)
            mask[fin] = (((xa[fin]-cx)**2/a**2 + (ya[fin]-cy)**2/b**2) <= 1.0)
            result = {'IN': mask, 'OUT': ~mask}, [c, REGION_COLORS[1]]

        elif gt == 'polygon':
            verts = gate.get('vertices', [])
            if len(verts) < 3:
                return {}, []
            mpl_path = MplPath(verts + [verts[0]])
            fin  = np.isfinite(xa) & np.isfinite(ya)
            mask = np.zeros(len(xa), bool)
            if fin.any():
                mask[fin] = mpl_path.contains_points(
                    np.column_stack([xa[fin], ya[fin]]))
            result = {'IN': mask, 'OUT': ~mask}, [c, REGION_COLORS[1]]

        else:
            return {}, []

        # ── Store in persistent cache ─────────────────────────────────────
        if _cache_path is not None:
            if len(self._gmc) >= _GMC_MAX:
                # Partial eviction: drop oldest 50 % so hot entries survive.
                # Avoids the cold-cache cliff where a full .clear() forces
                # every gate mask to be recomputed on the very next render.
                evict = list(self._gmc)[: _GMC_MAX // 2]
                for k in evict:
                    del self._gmc[k]
            self._gmc[ck] = result

        return result

    def _label_centroid(self, xa, ya, mask):
        """Return (mx, my) data-space centroid for mask, using transform-median."""
        xt = self._fwd(xa[mask], self.x_scale)
        yt = self._fwd(ya[mask], self.y_scale)
        fx = xt[np.isfinite(xt)]; fy = yt[np.isfinite(yt)]
        if len(fx) == 0 or len(fy) == 0:
            return None, None
        mx = float(self._inv(np.array([float(np.median(fx))]), self.x_scale)[0])
        my = float(self._inv(np.array([float(np.median(fy))]), self.y_scale)[0])
        return mx, my

    @staticmethod
    def _crosshair_corner(rname: str):
        """Map a two-sign crosshair quadrant name (e.g. 'TH+/D1R-') to an
        axes-space corner position so the label is pinned to the matching
        corner of the plot instead of being placed on top of the data cloud.

        Returns (x_ax, y_ax, ha, va) for use with ax.transAxes, or None when
        the name does not encode a simple ± quadrant (e.g. mid-band names
        like 'TH(m)/D1R+' fall back to the centroid path).
        """
        if '/' not in rname:
            return None
        y_part, x_part = rname.split('/', 1)
        y_plus  = y_part.endswith('+')
        y_minus = y_part.endswith('-')
        x_plus  = x_part.endswith('+')
        x_minus = x_part.endswith('-')
        if not ((y_plus or y_minus) and (x_plus or x_minus)):
            return None
        x_ax = 0.98 if x_plus  else 0.02
        y_ax = 0.97 if y_plus  else 0.03
        ha   = 'right' if x_plus  else 'left'
        va   = 'top'   if y_plus  else 'bottom'
        return x_ax, y_ax, ha, va

    def _draw_region_labels(self, applied_gates: list = None):
        """
        Draw population labels on the scatter plot.

        Single gate  → IN label + OUT label (classic view).
        Multi-gate   → Venn partition: one label per non-empty zone
                       (exclusive regions, overlaps, and "Outside all").
                       Percentages match what is shown in the stats panel.
                       No generic OUT label that would flood the canvas.
        """
        if applied_gates is None:
            applied_gates = [g for g in self.gates if g.get('applied')]
        if not applied_gates: return
        display = self._display_files()
        if not display: return
        T = self.T

        x_parts, y_parts = [], []
        for path, df in display.items():
            if self.x_channel not in df.columns or \
               self.y_channel not in df.columns: continue
            x_parts.append(df[self.x_channel].to_numpy(dtype=float, copy=False))
            y_parts.append(df[self.y_channel].to_numpy(dtype=float, copy=False))
        if not x_parts: return
        xa = np.concatenate(x_parts)
        ya = np.concatenate(y_parts)
        total = len(xa)
        if total == 0: return

        # ── Single gate: classic IN / OUT labels ─────────────────────────
        if len(applied_gates) == 1:
            gate         = applied_gates[0]
            c            = gate.get('color', GATE_PALETTE[0])
            is_crosshair = gate['type'] == 'crosshair'
            regions, _ = self._gate_mask_for(gate, xa, ya)
            for rname, mask in regions.items():
                cnt = int(mask.sum())
                if cnt == 0 or (rname == 'OUT' and cnt == total): continue
                pct       = cnt / total * 100
                hint      = ' ⤵' if self.manager and rname != 'OUT' else ''
                label_txt = f'{rname}{hint}\n{pct:.1f}%\n({cnt:,})'

                # Crosshair quadrants: pin label to the matching plot corner so
                # it never obscures the data cloud.  Non-simple quadrant names
                # (mid-bands with '(m)') fall back to the centroid path.
                corner = self._crosshair_corner(rname) if is_crosshair else None
                if corner is not None:
                    cx, cy, ha, va = corner
                    self.ax.text(cx, cy, label_txt,
                                 ha=ha, va=va, fontsize=7.5,
                                 fontweight='bold', color=T['label_txt'],
                                 linespacing=1.4,
                                 transform=self.ax.transAxes,
                                 bbox=dict(boxstyle='round,pad=0.3',
                                           facecolor=T['label_box'],
                                           alpha=0.65, linewidth=0))
                else:
                    mx, my = self._label_centroid(xa, ya, mask)
                    if mx is None: continue
                    self.ax.text(mx, my, label_txt,
                                 ha='center', va='center', fontsize=7.5,
                                 fontweight='bold', color=T['label_txt'],
                                 linespacing=1.4,
                                 bbox=dict(boxstyle='round,pad=0.35',
                                           facecolor=c if not is_crosshair
                                                      else T['label_box'],
                                           alpha=0.82, linewidth=0))
            return

        # ── Multiple gates: Venn partition labels ────────────────────────
        # Build one boolean "in" mask per gate
        n = len(xa)
        in_masks = []
        for gate in applied_gates:
            regions, _ = self._gate_mask_for(gate, xa, ya)
            gt = gate.get('type', 'crosshair')
            if gt == 'crosshair':
                in_m = np.zeros(n, bool)
                for rname, m in regions.items():
                    if rname != 'OUT':
                        in_m |= m
            else:
                in_m = regions.get('IN', np.zeros(n, bool))
            in_masks.append(in_m)

        # Iterate over all 2^N combinations
        for combo in range(2 ** len(applied_gates)):
            flags      = [bool((combo >> i) & 1) for i in range(len(applied_gates))]
            combo_mask = np.ones(n, bool)
            for i, flag in enumerate(flags):
                combo_mask &= (in_masks[i] if flag else ~in_masks[i])
            cnt = int(combo_mask.sum())
            if cnt == 0:
                continue
            pct  = cnt / total * 100
            mx, my = self._label_centroid(xa, ya, combo_mask)
            if mx is None:
                continue

            in_gates = [applied_gates[i] for i, f in enumerate(flags) if f]
            if not in_gates:
                # Outside all gates
                label_text = f'Outside all\n{pct:.1f}%\n({cnt:,})'
                fc = T['label_box']
            elif len(in_gates) == 1:
                g    = in_gates[0]
                hint = ' ⤵' if self.manager else ''
                label_text = f'{g["name"]}{hint}\n{pct:.1f}%\n({cnt:,})'
                fc   = g.get('color', GATE_PALETTE[0])
            else:
                names      = ' ∩ '.join(g['name'] for g in in_gates)
                hint       = ' ⤵' if self.manager else ''
                label_text = f'{names}{hint}\n{pct:.1f}%\n({cnt:,})'
                # Blend: use first gate's color at reduced alpha
                fc = in_gates[0].get('color', GATE_PALETTE[0])

            self.ax.text(mx, my, label_text,
                         ha='center', va='center', fontsize=7.5,
                         fontweight='bold', color=T['label_txt'],
                         linespacing=1.4,
                         bbox=dict(boxstyle='round,pad=0.35',
                                   facecolor=fc,
                                   alpha=0.82, linewidth=0))

    # ── Gate interactions ─────────────────────────────────────────────────────

    def _on_click(self, event):
        if event.inaxes != self.ax:
            return

        mode = self.gate_mode_var.get()

        # ── DOUBLE-CLICK: close polygon or sub-gate ──
        if event.dblclick:
            if self._poly_active and mode == 'draw':
                self._poly_finish(); return
            if mode == 'none':
                sel = self._sel_gate()
                if sel and sel.get('applied') and self.manager:
                    self._open_subgate(event.xdata, event.ydata)
            return

        # ── RIGHT-CLICK: grab handle, pin gate outline, or close polygon ──
        if event.button == 3:
            if self._poly_active:
                self._poly_finish()
                return
            # Try handle drag first (must be within HANDLE_PX)
            hit = self._hit_test_handles(event)
            if hit:
                self._handle_drag = hit
                if hit['gate_id'] != self._sel_gate_id:
                    self._sel_gate_id = hit['gate_id']
                    self._rebuild_gate_manager()
                    self._rebuild_thresh_panel()
                return
            # Try line hit: right-click on a gate line pins/unpins handles
            line_gid = self._hit_test_gate_line(event, threshold_px=10)
            if line_gid is not None:
                if self._pinned_gate_id == line_gid:
                    self._pinned_gate_id = None   # toggle off
                else:
                    self._pinned_gate_id = line_gid
                    self._sel_gate_id    = line_gid
                    self._rebuild_gate_manager()
                    self._rebuild_thresh_panel()
                self._preview_gate()
                self.canvas.draw_idle()
            else:
                # Right-click on empty space — unpin
                if self._pinned_gate_id is not None:
                    self._pinned_gate_id = None
                    self._preview_gate()
                    self.canvas.draw_idle()
            return

        # ── LEFT-CLICK: draw mode only ────────────────────────────────────
        if mode != 'draw':
            return

        x, y = event.xdata, event.ydata
        gt   = self.gate_type_var.get()

        draw = self._draw_gate_obj()

        if gt == 'polygon':
            if not self._poly_active or draw is None:
                gate = self._add_gate()
                self._draw_gate_id = gate['id']
                gate['vertices'] = [(x, y)]
                self._poly_active = True
            else:
                draw['vertices'].append((x, y))
            self._update_poly_close_btn()
            self._preview_gate()
            self.canvas.draw_idle()
            return

        if draw is None or draw.get('applied'):
            # ── Crosshair special rule: only one manual crosshair allowed ──
            # If a manual crosshair (auto_method=None) already exists, reuse it
            # in-place rather than stacking up duplicates.  The user can always
            # adjust position by right-drag on the handles.
            if gt == 'crosshair':
                existing = next(
                    (g for g in self.gates
                     if g.get('type') == 'crosshair'
                     and g.get('auto_method') is None),
                    None)
                if existing:
                    gate = existing
                    self._draw_gate_id = gate['id']
                    self._sel_gate_id  = gate['id']
                else:
                    gate = self._add_gate()
                    self._draw_gate_id = gate['id']
            else:
                gate = self._add_gate()
                self._draw_gate_id = gate['id']
        else:
            gate = draw

        gate['type'] = gt

        if gt == 'crosshair':
            gate['x_boundaries'] = [x]; gate['y_boundary'] = y
        elif gt in ('rectangle', 'ellipse'):
            gate['x0'] = x; gate['y0'] = y
            gate['x1'] = x; gate['y1'] = y

        self.moving_gate = True
        self._preview_gate()
        self.canvas.draw_idle()

    def _on_motion(self, event):
        # ── Handle drag: must work even when cursor moves outside axes ──
        if self._handle_drag:
            # event.x/y are mpl display coords (y=0 bottom); invert to data coords
            try:
                x, y = self.ax.transData.inverted().transform((event.x, event.y))
            except Exception:
                return
            self._drag_handle_update(x, y)
            return

        # ── Hover detection: show/hide handles — skip when actively drawing ──
        if not self.moving_gate and not self._poly_active:
            if event.inaxes == self.ax:
                # Handle-proximity test first (pure arithmetic on cached coords — fast)
                new_hover = self._hover_test_handles(event)
                # If no handle nearby, test line proximity only when hover state needs update
                # (line test calls transData.transform per segment — limit to state changes)
                if new_hover is None and self._hover_gate_id is not None:
                    # Leaving a gate — check if still near its line before hiding
                    new_hover = self._hit_test_gate_line(event, threshold_px=8)
                elif new_hover is None and self._hover_gate_id is None:
                    # Not currently over anything: only run line test every ~10px of movement
                    # by checking if cursor moved enough since last line test
                    ex, ey = event.x, event.y
                    lx, ly = getattr(self, '_last_line_test_pos', (ex-99, ey))
                    if abs(ex-lx) + abs(ey-ly) > 10:
                        self._last_line_test_pos = (ex, ey)
                        new_hover = self._hit_test_gate_line(event, threshold_px=8)
                # Update Tk cursor
                try:
                    self.canvas.get_tk_widget().config(
                        cursor=self._cursor_for_hover(event) if (
                            new_hover or self._pinned_gate_id) else '')
                except Exception:
                    pass
                if new_hover != self._hover_gate_id:
                    self._hover_gate_id = new_hover
                    self._preview_gate()
                    self.canvas.draw_idle()
                    return
            elif self._hover_gate_id is not None:
                self._hover_gate_id = None
                try:
                    self.canvas.get_tk_widget().config(cursor='')
                except Exception:
                    pass
                self._preview_gate()
                self.canvas.draw_idle()
                return

        if event.inaxes != self.ax:
            return
        x, y = event.xdata, event.ydata

        mode = self.gate_mode_var.get()
        gt   = self.gate_type_var.get()

        # Polygon rubber-band
        if gt == 'polygon' and self._poly_active and mode == 'draw':
            self._poly_cursor = (x, y)
            self._preview_gate()
            self.canvas.draw_idle()
            return

        if not self.moving_gate:
            return
        gate = self._draw_gate_obj()
        if not gate:
            return

        if gate['type'] == 'crosshair':
            gate['x_boundaries'] = [x]; gate['y_boundary'] = y
        elif gate['type'] in ('rectangle', 'ellipse'):
            gate['x1'] = x; gate['y1'] = y

        self._preview_gate()
        self.canvas.draw_idle()

    def _on_release(self, event):
        # ── Finish handle drag (any button) ──
        if self._handle_drag:
            gate = next((g for g in self.gates
                         if g['id'] == self._handle_drag['gate_id']), None)
            self._handle_drag   = None
            self._hover_gate_id = None   # hide handles after release
            if gate:
                self._finish_gate(gate)
            return

        if not self.moving_gate:
            return
        self.moving_gate = False

        gate = self._draw_gate_obj()
        # Guard: released outside axes or None coords
        if not gate or event.xdata is None or event.ydata is None:
            if gate and not gate.get('applied'):
                self._del_gate(gate['id'])
            return

        x, y = event.xdata, event.ydata
        gt   = gate.get('type', 'crosshair')

        if gt == 'crosshair':
            gate['x_boundaries'] = [x]; gate['y_boundary'] = y
            gate['x_thresh_vars'] = [tk.BooleanVar(value=True)]
            gate['y_thresh_var']  = tk.BooleanVar(value=True)
            gate['applied']       = True
        elif gt in ('rectangle', 'ellipse'):
            gate['x1'] = x; gate['y1'] = y
            if (abs(gate['x1'] - gate['x0']) < 1e-10 or
                    abs(gate['y1'] - gate['y0']) < 1e-10):
                self._del_gate(gate['id']); return
            gate['applied'] = True
        else:
            return  # polygon finishes via _poly_finish

        self._draw_gate_id = None
        self._finish_gate(gate)

    def _poly_finish(self):
        """Close and apply the current polygon gate."""
        draw = self._draw_gate_obj()
        if not draw or len(draw.get('vertices', [])) < 3:
            return
        draw['applied']    = True
        self._poly_active  = False
        self._poly_cursor  = None
        self._draw_gate_id = None
        self._update_poly_close_btn()
        self._finish_gate(draw)

    def _finish_gate(self, gate: dict):
        """After gate geometry is finalised: recompute stats, rebuild UI.
        Automatically switches to Edit mode so the user can immediately
        adjust the gate without accidentally creating another one."""
        self._sel_gate_id = gate['id']
        # Keep Draw mode active so user can add more gates,
        # but update hint to remind right-click reshapes handles.
        if self.gate_mode_var.get() == 'draw':
            self._gate_hint_var.set('Gate placed  |  Right-drag handles to reshape')
        self._compute_gate_stats_for(gate)
        self._rebuild_gate_manager()
        self._rebuild_thresh_panel()
        self.refresh_plot()
        self._update_stats_display()

    def _commit_gate(self):
        sel = self._sel_gate()
        if sel:
            self._finish_gate(sel)

    # ── Gate handle system ────────────────────────────────────────────────────

    def _get_handles(self, gate: dict) -> list:
        """
        Return list of handle dicts for editing this gate.
        Each: {'x', 'y', 'handle', 'idx'}  — coordinates in data space.
        """
        handles = []
        gt = gate.get('type', 'crosshair')
        if gt in ('rectangle', 'ellipse'):
            x0, y0 = gate['x0'], gate['y0']
            x1, y1 = gate['x1'], gate['y1']
            cx, cy = (x0+x1)/2, (y0+y1)/2
            for i, (hx, hy, nm) in enumerate([
                (x0, y0, 'nw'), (x1, y0, 'ne'),
                (x1, y1, 'se'), (x0, y1, 'sw'),
                (cx, cy, 'center'),
            ]):
                handles.append({'x': hx, 'y': hy, 'handle': nm, 'idx': i})
        elif gt == 'polygon':
            for i, (vx, vy) in enumerate(gate.get('vertices', [])):
                handles.append({'x': vx, 'y': vy, 'handle': 'vertex', 'idx': i})
        return handles

    def _draw_handles(self):
        """
        Draw handle markers for:
        - The gate being dragged (filled square on active handle)
        - The hovered gate (open circles on all handles)
        - The pinned gate (open circles, slightly larger — persists after right-click)
        """
        self._handle_artists = []
        drag_gid   = self._handle_drag['gate_id'] if self._handle_drag else None
        # Collect all gate ids that need handles drawn
        show_gids = set()
        if drag_gid:     show_gids.add(drag_gid)
        if self._hover_gate_id:   show_gids.add(self._hover_gate_id)
        if self._pinned_gate_id:  show_gids.add(self._pinned_gate_id)
        if not show_gids:
            return

        for gate in self.gates:
            if not gate.get('applied') or gate['id'] not in show_gids:
                continue
            handles = self._get_handles(gate)
            color   = gate.get('color', GATE_PALETTE[0])
            pinned  = (gate['id'] == self._pinned_gate_id and
                       gate['id'] != drag_gid)
            for h in handles:
                is_dragged = (drag_gid == gate['id'] and
                              h['handle'] == self._handle_drag.get('handle') and
                              h['idx']    == self._handle_drag.get('idx'))
                marker = 's' if is_dragged else 'o'
                ms     = 9  if is_dragged else (8 if pinned else 7)
                mfc    = color if is_dragged else ('none' if not pinned else color+'55')
                mew    = 2.0 if pinned else 0.5
                a, = self.ax.plot(h['x'], h['y'],
                                  marker=marker, ms=ms,
                                  markerfacecolor=mfc,
                                  markeredgecolor=color,
                                  markeredgewidth=mew,
                                  linestyle='none', zorder=20)
                a._flowjo_handle = {'gate_id': gate['id'],
                                    'handle':  h['handle'],
                                    'idx':     h['idx']}
                self._handle_artists.append(a)

    def _hit_test_handles(self, event) -> dict:
        """
        Return handle drag info if the click is within HANDLE_PX pixels of
        any handle on any applied gate.

        Computed directly from gate geometry (not from artists) so that
        handles do not need to be visible to be draggable.
        """
        best, best_dist = None, float('inf')
        for gate in self.gates:
            if not gate.get('applied'):
                continue
            for h in self._get_handles(gate):
                try:
                    px, py = self.ax.transData.transform((h['x'], h['y']))
                except Exception:
                    continue
                dist = ((px - event.x)**2 + (py - event.y)**2)**0.5
                if dist < HANDLE_PX and dist < best_dist:
                    best_dist = dist
                    best = {'gate_id': gate['id'],
                            'gate':    gate,
                            'handle':  h['handle'],
                            'idx':     h['idx'],
                            'orig':    copy.deepcopy(gate)}
        return best

    def _rebuild_handle_px_cache(self):
        """Cache all handle positions in display pixels after a full redraw.
        Avoids calling transData.transform() on every mouse-move event."""
        self._handle_px_cache = {}
        for gate in self.gates:
            if not gate.get('applied'):
                continue
            entries = []
            for h in self._get_handles(gate):
                try:
                    px, py = self.ax.transData.transform((h['x'], h['y']))
                    entries.append((px, py, h['handle'], h['idx']))
                except Exception:
                    pass
            if entries:
                self._handle_px_cache[gate['id']] = entries

    def _hit_test_gate_line(self, event, threshold_px: int = 8) -> int:
        """
        Return gate_id if the cursor is within threshold_px of any drawn gate
        outline (axvline, axhline, rectangle edge, ellipse perimeter, polygon edge).
        Returns None if no line is close.
        Used for right-click pinning and extended hover detection.
        """
        ex, ey = event.x, event.y   # display pixels, y=0 at bottom

        def _data_to_px(dx, dy):
            try:
                return self.ax.transData.transform((dx, dy))
            except Exception:
                return None

        def _seg_dist(px, py, ax2, ay2, bx, by):
            """Pixel distance from point (px,py) to segment (ax2,ay2)-(bx,by)."""
            dx, dy = bx - ax2, by - ay2
            if dx == 0 and dy == 0:
                return ((px-ax2)**2 + (py-ay2)**2)**0.5
            t = max(0.0, min(1.0, ((px-ax2)*dx + (py-ay2)*dy) / (dx*dx+dy*dy)))
            return ((px - (ax2+t*dx))**2 + (py - (ay2+t*dy))**2)**0.5

        # Get axes bounding box in display pixels for clamping infinite lines
        try:
            axb  = self.ax.get_window_extent()
            x_lo, x_hi = axb.x0, axb.x1
            y_lo, y_hi = axb.y0, axb.y1
        except Exception:
            return None

        best_gid, best_dist = None, float('inf')

        for gate in self.gates:
            if not gate.get('applied'):
                continue
            gid = gate['id']
            gt  = gate.get('type', 'crosshair')

            if gt == 'crosshair':
                # axvlines and axhline span the full axes
                for xb in self._active_xbs_for(gate):
                    p = _data_to_px(xb, 0)
                    if p is None: continue
                    vx = p[0]
                    d  = abs(ex - vx) if y_lo <= ey <= y_hi else float('inf')
                    if d < threshold_px and d < best_dist:
                        best_dist, best_gid = d, gid
                for yb_val in self._active_ybs_for(gate):
                    p = _data_to_px(0, yb_val)
                    if p is not None:
                        hy = p[1]
                        d  = abs(ey - hy) if x_lo <= ex <= x_hi else float('inf')
                        if d < threshold_px and d < best_dist:
                            best_dist, best_gid = d, gid

            elif gt == 'rectangle':
                x0, y0, x1, y1 = gate.get('x0',0), gate.get('y0',0), gate.get('x1',0), gate.get('y1',0)
                corners = [
                    (_data_to_px(x0,y0), _data_to_px(x1,y0)),
                    (_data_to_px(x1,y0), _data_to_px(x1,y1)),
                    (_data_to_px(x1,y1), _data_to_px(x0,y1)),
                    (_data_to_px(x0,y1), _data_to_px(x0,y0)),
                ]
                for (pa, pb) in corners:
                    if pa is None or pb is None: continue
                    d = _seg_dist(ex, ey, pa[0], pa[1], pb[0], pb[1])
                    if d < threshold_px and d < best_dist:
                        best_dist, best_gid = d, gid

            elif gt == 'ellipse':
                x0, y0 = gate.get('x0',0), gate.get('y0',0)
                x1, y1 = gate.get('x1',0), gate.get('y1',0)
                cx, cy = (x0+x1)/2, (y0+y1)/2
                # Sample 64 points on the ellipse perimeter (in data space) and
                # check segment distances to cursor
                N = 64
                ts = np.linspace(0, 2*np.pi, N, endpoint=False)
                rx, ry = abs(x1-x0)/2, abs(y1-y0)/2
                pts = [_data_to_px(cx + rx*np.cos(t), cy + ry*np.sin(t)) for t in ts]
                pts = [p for p in pts if p is not None]
                for i in range(len(pts)):
                    pa, pb = pts[i], pts[(i+1) % len(pts)]
                    d = _seg_dist(ex, ey, pa[0], pa[1], pb[0], pb[1])
                    if d < threshold_px and d < best_dist:
                        best_dist, best_gid = d, gid

            elif gt == 'polygon':
                verts = gate.get('vertices', [])
                if len(verts) < 2: continue
                closed = list(verts) + [verts[0]]
                for i in range(len(closed)-1):
                    pa = _data_to_px(*closed[i])
                    pb = _data_to_px(*closed[i+1])
                    if pa is None or pb is None: continue
                    d = _seg_dist(ex, ey, pa[0], pa[1], pb[0], pb[1])
                    if d < threshold_px and d < best_dist:
                        best_dist, best_gid = d, gid

        return best_gid

    def _hover_test_handles(self, event) -> int:
        """Return gate_id if cursor is within HANDLE_PX*2.5 of any handle (uses cache).
        Returns None if no handle is close. Does NOT fall back to line testing —
        that is done separately in _on_motion to avoid per-pixel transform calls."""
        best_gid, best_dist = None, float('inf')
        threshold = HANDLE_PX * 2.5
        for gid, entries in self._handle_px_cache.items():
            for (px, py, handle, idx) in entries:
                dist = ((px - event.x)**2 + (py - event.y)**2)**0.5
                if dist < threshold and dist < best_dist:
                    best_dist = dist
                    best_gid  = gid
        return best_gid

    def _cursor_for_hover(self, event) -> str:
        """Return Tk cursor name appropriate for the current hover state."""
        if self._handle_drag or self._hover_gate_id or self._pinned_gate_id:
            # Check if we're specifically over a corner handle → sizing cursor
            threshold = HANDLE_PX * 2.5
            gid = self._handle_drag['gate_id'] if self._handle_drag else (
                  self._hover_gate_id or self._pinned_gate_id)
            entries = self._handle_px_cache.get(gid, [])
            for (px, py, handle, idx) in entries:
                dist = ((px - event.x)**2 + (py - event.y)**2)**0.5
                if dist < threshold:
                    if handle == 'center':
                        return 'fleur'
                    return 'sizing'
            # Near a line but not a corner handle
            return 'hand2'
        return ''

    def _drag_handle_update(self, x: float, y: float):
        """Update gate geometry as a handle is dragged to (x, y)."""
        info = self._handle_drag
        if not info:
            return
        gate   = info['gate']
        handle = info['handle']
        idx    = info['idx']
        orig   = info['orig']
        gt     = gate.get('type', 'crosshair')

        if gt in ('rectangle', 'ellipse'):
            # Move corners
            if handle == 'nw':   gate['x0'], gate['y0'] = x, y
            elif handle == 'ne': gate['x1'], gate['y0'] = x, y
            elif handle == 'se': gate['x1'], gate['y1'] = x, y
            elif handle == 'sw': gate['x0'], gate['y1'] = x, y
            elif handle == 'center':
                dx = x - (orig['x0'] + orig['x1']) / 2
                dy = y - (orig['y0'] + orig['y1']) / 2
                gate['x0'] = orig['x0'] + dx; gate['x1'] = orig['x1'] + dx
                gate['y0'] = orig['y0'] + dy; gate['y1'] = orig['y1'] + dy

        elif gt == 'polygon' and handle == 'vertex':
            verts = list(gate.get('vertices', []))
            if 0 <= idx < len(verts):
                verts[idx] = (x, y)
                gate['vertices'] = verts

        self._preview_gate()
        self.canvas.draw_idle()

    def _clear_handles(self):
        for art in self._handle_artists:
            try: art.remove()
            except Exception: pass
        self._handle_artists = []

    def _clear_preview(self):
        for art in self._preview_artists:
            try: art.remove()
            except Exception: pass
        self._preview_artists = []
        self._clear_handles()
        # NOTE: draw_idle() intentionally removed here.
        # refresh_plot calls _preview_gate() as part of a larger redraw
        # sequence; a premature flush here would render an incomplete state
        # (scatter drawn, gate artists not yet added, labels not yet added).
        # Each interactive caller (_on_click, _on_motion etc.) issues its own
        # explicit canvas.draw_idle() after _preview_gate() returns.

    def _preview_gate(self):
        """
        Redraw ALL gate outlines (applied + in-progress) and handle dots.
        Called both during drag preview and after ax.clear() in refresh_plot.
        """
        self._clear_preview()

        for gate in self.gates:
            if not gate.get('vertices', []) and not gate.get('applied', False)                and gate.get('type') not in ('crosshair', 'rectangle', 'ellipse'):
                continue  # skip empty polygon gate
            c    = gate.get('color', GATE_PALETTE[0])
            sel  = (gate['id'] == self._sel_gate_id)
            ls   = gate.get('linestyle', '-') if gate.get('applied') else '--'
            base_lw = gate.get('linewidth', 0.5)
            lw   = base_lw + 0.8 if sel else base_lw
            gt   = gate.get('type', 'crosshair')

            if gt == 'crosshair':
                if gate.get('applied'):
                    xbs  = self._active_xbs_for(gate)
                    ybs  = self._active_ybs_for(gate)   # works for both single and multi-Y
                else:
                    xbs = gate.get('x_boundaries', [])
                    yb  = gate.get('y_boundary')
                    ybs = gate.get('y_boundaries') or ([yb] if yb is not None else [])
                for xb in xbs:
                    a = self.ax.axvline(xb, color=c, ls=ls, lw=lw, zorder=10)
                    self._preview_artists.append(a)
                for yb_val in ybs:
                    a = self.ax.axhline(yb_val, color=c, ls=ls, lw=lw, zorder=10)
                    self._preview_artists.append(a)

            elif gt in ('rectangle', 'ellipse'):
                x0, y0 = gate.get('x0', 0), gate.get('y0', 0)
                x1, y1 = gate.get('x1', 0), gate.get('y1', 0)
                if gt == 'rectangle':
                    rx, ry = min(x0,x1), min(y0,y1)
                    rw, rh = abs(x1-x0), abs(y1-y0)
                    patch = MplRect((rx, ry), rw, rh,
                                    lw=lw, ls=ls, edgecolor=c, facecolor='none', zorder=10)
                else:
                    cx, cy = (x0+x1)/2, (y0+y1)/2
                    patch = MplEllipse((cx,cy), abs(x1-x0), abs(y1-y0),
                                       lw=lw, ls=ls, edgecolor=c, facecolor='none', zorder=10)
                self.ax.add_patch(patch)
                self._preview_artists.append(patch)

            elif gt == 'polygon':
                verts = gate.get('vertices', [])
                if verts:
                    xs = [v[0] for v in verts]
                    ys = [v[1] for v in verts]
                    if gate.get('applied'):
                        xs = xs + [xs[0]]; ys = ys + [ys[0]]
                    ln, = self.ax.plot(xs, ys, color=c, ls=ls, lw=lw,
                                       marker='o' if not gate.get('applied') else 'none',
                                       markersize=3, zorder=10)
                    self._preview_artists.append(ln)
                    # Rubber-band line to cursor while drawing
                    if self._poly_active and self._poly_cursor is not None                             and gate['id'] == self._draw_gate_id:
                        rb, = self.ax.plot(
                            [xs[-1], self._poly_cursor[0]],
                            [ys[-1], self._poly_cursor[1]],
                            color=c, ls=':', lw=1.0, zorder=10)
                        self._preview_artists.append(rb)

        # Draw handles
        self._draw_handles()
        # Refresh pixel-coord cache so hover hit-testing needs no per-event transform
        self._rebuild_handle_px_cache()
        # Caller is responsible for draw_idle to avoid duplicate flushes

    # ── Sub-gate (double-click) ───────────────────────────────────────────────

    def _open_subgate(self, click_x, click_y):
        """
        Determine which applied gate's region contains (click_x, click_y),
        filter all active files to cells in that region, open a sub-gate tab.

        Search order:
          1. The currently selected gate (most likely intention).
          2. All other applied gates (handles multi-polygon case: user clicked
             inside Gate2 while Gate1 is selected).
        For shape gates (rect/ellipse/polygon) only an IN click is meaningful.
        For crosshair gates any quadrant is valid.
        """
        if not self.x_channel or not self.y_channel:
            return

        px = np.array([click_x], dtype=float)
        py = np.array([click_y], dtype=float)

        # Build candidate list: selected gate first, then the rest
        sel = self._sel_gate()
        ordered = ([sel] if sel else []) + [
            g for g in self.gates
            if g.get('applied') and g is not sel
        ]

        target_gate    = None
        clicked_region = None

        for gate in ordered:
            if not gate or not gate.get('applied'):
                continue
            regions_pt, _ = self._gate_mask_for(gate, px, py)
            for rname, mask in regions_pt.items():
                if not mask.any():
                    continue
                gt = gate.get('type', 'crosshair')
                # For shape gates, only accept IN (not OUT — that's "everywhere else")
                if gt != 'crosshair' and rname == 'OUT':
                    continue
                target_gate    = gate
                clicked_region = rname
                break
            if target_gate is not None:
                break

        if target_gate is None or clicked_region is None:
            return

        filtered = {}
        for path, df in self._active().items():
            if self.x_channel not in df.columns or \
               self.y_channel not in df.columns:
                continue
            xa = df[self.x_channel].to_numpy(dtype=float, copy=False)
            ya = df[self.y_channel].to_numpy(dtype=float, copy=False)
            reg, _ = self._gate_mask_for(target_gate, xa, ya)
            if clicked_region in reg:
                sub_df = df[reg[clicked_region]].reset_index(drop=True)
                if len(sub_df) > 0:
                    filtered[path] = sub_df

        if not filtered:
            messagebox.showinfo("Sub-gate",
                f"No cells in '{clicked_region}'."); return

        total = sum(len(d) for d in filtered.values())
        self.manager.open_subgate_tab(
            label=clicked_region, filtered_data=filtered,
            parent_x=self.x_channel, parent_y=self.y_channel,
            total_cells=total,
            parent_gate=target_gate, parent_region=clicked_region,
            excluded_files=dict(self.excluded_files))

    def clear_gate(self):
        """Clear the currently selected gate."""
        sel = self._sel_gate()
        if sel:
            self._del_gate(sel['id'])
        else:
            self.refresh_plot()

    def clear_all_gates(self):
        """Clear all gates."""
        self.gates          = []
        self.gate_stats     = {}
        self._sel_gate_id   = None
        self._draw_gate_id  = None
        self.moving_gate    = False
        self._poly_active   = False
        self._poly_cursor   = None
        self._handle_drag      = None
        self._hover_gate_id    = None
        self._pinned_gate_id   = None
        self._handle_px_cache  = {}
        self._clear_preview()
        self._rebuild_gate_manager()
        self._rebuild_thresh_panel()
        self._update_stats_display()
        self.refresh_plot()

        # ── Auto-gating ───────────────────────────────────────────────────────────

    def _sens_params(self) -> dict:
        """
        Convert the single sensitivity slider (1–10) into per-method parameters.

        Uses exponential interpolation so the slider feels linear in effect:
          s=1  → very conservative (only the most obvious gaps)
          s=5  → balanced (roughly equivalent to previous hard-coded defaults)
          s=10 → very sensitive (finds subtle shoulders and weak separations)

        Ranges are intentionally wide — the user can always clear and re-gate.
        """
        s = float(self.auto_sensitivity_var.get())   # 1.0–10.0
        # Normalise to t ∈ [0, 1]
        t = (s - 1.0) / 9.0

        # ── GMM max components ───────────────────────────────────────────────
        # 2 (conservative) → 8 (sensitive)
        gmm_max_comp = max(2, min(8, round(2 + t * 6)))

        # ── KDE valley prominence (exponential decay) ────────────────────────
        # s=1: 200  (only unmistakable, very deep valleys)
        # s=7: ~5   (typical bimodal flow data)
        # s=10: 1.001 (any local dip qualifies)
        kde_prominence = 200.0 * (1.001 / 200.0) ** t   # 200 → 1.001

        # ── Multi-valley prominence ──────────────────────────────────────────
        # Same philosophy, slightly lower ceiling
        mv_prominence  = 100.0 * (1.0 / 100.0) ** t     # 100 → 1.0

        # ── KDE bandwidth factor ─────────────────────────────────────────────
        # Most impactful parameter: narrows KDE to resolve closely-spaced peaks.
        # s=1: bw_factor=5.0  (very smooth — only obvious bimodal gaps)
        # s=7: bw_factor≈0.4
        # s=10: bw_factor=0.05 (very sharp — resolves tight populations)
        bw_factor = 5.0 * (0.05 / 5.0) ** t             # 5.0 → 0.05

        # ── Min peak fraction (peak must be ≥ this × global max) ────────────
        # High sensitivity lets tiny minority peaks participate in valley search.
        # s=1: 15% (only substantial peaks)
        # s=7: ~1%
        # s=10: 0.1%
        min_peak_frac = 0.15 * (0.001 / 0.15) ** t      # 0.15 → 0.001

        # ── Otsu min class fraction ──────────────────────────────────────────
        # s=1: 25%  s=10: 0.05%
        otsu_min_frac = 0.25 * (0.0005 / 0.25) ** t     # 0.25 → 0.0005

        return {
            'gmm_max_comp':   gmm_max_comp,
            'kde_prominence': max(1.001, kde_prominence),
            'mv_prominence':  max(1.0,   mv_prominence),
            'bw_factor':      max(0.05,  bw_factor),
            'min_peak_frac':  max(0.001, min_peak_frac),
            'otsu_min_frac':  max(0.0005, otsu_min_frac),
        }

    def _rerun_last_auto_gate(self):
        """Called after debounce when sensitivity slider changes.
        Re-runs the most recently used auto-gate method with the new parameters."""
        self._sens_rerun_pending = None
        if self._last_auto_gate_fn is not None:
            try:
                self._last_auto_gate_fn()
            except Exception:
                pass   # silently ignore — user can still click the button manually

    def _collect_x_transform(self):
        parts = []
        for df in self._active().values():
            if self.x_channel not in df.columns: continue
            x = df[self.x_channel].to_numpy(dtype=float, copy=False)
            xt = self._fwd(x, self.x_scale)
            parts.append(xt[np.isfinite(xt)])
        return np.concatenate(parts) if parts else np.array([])

    def _collect_y_transform(self):
        parts = []
        for df in self._active().values():
            if self.y_channel not in df.columns: continue
            y = df[self.y_channel].to_numpy(dtype=float, copy=False)
            yt = self._fwd(y, self.y_scale)
            parts.append(yt[np.isfinite(yt)])
        return np.concatenate(parts) if parts else np.array([])

    def _apply_gate_and_refresh(self, xbs_raw, yb_raw, auto_method: str = None):
        """
        Store an auto-gate result as a crosshair gate, then refresh everything.

        If auto_method is given and a gate with that same auto_method already
        exists, it is reused in-place (geometry updated, no new gate created).
        This means re-running or slider-scrubbing never accumulates duplicate
        gates.  Manual gates (auto_method=None) are never touched.
        """
        # ── Find an existing gate to reuse ───────────────────────────────────
        target = None
        if auto_method:
            # Prefer the currently selected gate if it matches
            sel = self._sel_gate()
            if sel and sel.get('auto_method') == auto_method:
                target = sel
            else:
                # Otherwise take the first matching gate in the list
                for g in self.gates:
                    if g.get('auto_method') == auto_method:
                        target = g
                        break

        # ── Fall back: use selected crosshair or create new ──────────────────
        if target is None:
            sel = self._sel_gate()
            if sel and sel.get('type') == 'crosshair' and not sel.get('auto_method'):
                # Selected gate is a manual crosshair — don't overwrite it
                target = None
            elif sel and sel.get('type') == 'crosshair' and sel.get('auto_method') == auto_method:
                target = sel
            if target is None:
                target = self._add_gate(auto_type='crosshair',
                                        auto_method=auto_method)

        # ── Write geometry ────────────────────────────────────────────────────
        target['auto_method']   = auto_method   # ensure tag is set
        target['type']          = 'crosshair'
        target['x_boundaries']  = list(xbs_raw)
        target['y_boundary']    = yb_raw
        target['y_boundaries']  = None
        target['x_thresh_vars'] = [tk.BooleanVar(value=True) for _ in xbs_raw]
        target['y_thresh_var']  = tk.BooleanVar(value=True)
        target['y_thresh_vars'] = []
        target['applied']       = True
        self._sel_gate_id       = target['id']

        # Gate geometry changed → _gmc self-invalidates via _gate_sig() on next render
        self._gate_hint_var.set('Auto-gate placed  |  Right-drag handles to reshape')
        self._compute_gate_stats_for(target)
        self._rebuild_gate_manager()
        self._rebuild_thresh_panel()
        self.refresh_plot()
        self._update_stats_display()

    def auto_gate_derivative(self):
        """
        Run Derivative (first-valley KDE) on BOTH axes:
          X → single threshold (x_boundaries = [val])
          Y → single threshold (y_boundary)
        """
        active = self._active()
        if not active or not self.x_channel or not self.y_channel:
            messagebox.showwarning("Auto-Gate",
                "Load data and select axes first."); return

        self._last_auto_gate_fn = self.auto_gate_derivative
        sp = self._sens_params()

        # ── X: Derivative ──
        all_xt = self._collect_x_transform()
        all_xt = all_xt[np.isfinite(all_xt)]
        try:
            xb_t = derivative_threshold(all_xt, min_prominence=sp['kde_prominence'], bw_factor=sp['bw_factor'], min_peak_frac=sp['min_peak_frac'])
        except Exception as e:
            messagebox.showerror("Derivative Error (X)", str(e)); return
        xb_raw = float(self._inv(np.array([xb_t]), self.x_scale)[0])

        # ── Y: Derivative ──
        all_yt = self._collect_y_transform()
        all_yt = all_yt[np.isfinite(all_yt)]
        try:
            yb_t = derivative_threshold(all_yt, min_prominence=sp['kde_prominence'], bw_factor=sp['bw_factor'], min_peak_frac=sp['min_peak_frac'])
        except Exception as e:
            messagebox.showerror("Derivative Error (Y)", str(e)); return
        yb_raw = float(self._inv(np.array([yb_t]), self.y_scale)[0])

        self._apply_gate_and_refresh([xb_raw], yb_raw, auto_method='kde')

        all_x_raw = np.concatenate([df[self.x_channel].dropna().values
                                    for df in active.values()])
        all_y_raw = np.concatenate([df[self.y_channel].dropna().values
                                    for df in active.values()])
        pct_x = float(np.mean(all_x_raw < xb_raw)) * 100
        pct_y = float(np.mean(all_y_raw < yb_raw)) * 100
        self.status_var.set(
            f"✓ KDE Valley: X @ {xb_raw:,.0f} ({pct_x:.1f}% below)"
            f"  |  Y @ {yb_raw:,.0f} ({pct_y:.1f}% below)")

    def auto_gate_otsu(self):
        """
        Otsu threshold on each axis independently, using ALL selected files merged.

        Otsu's method maximises between-class variance across all binary splits
        of the histogram — equivalent to minimising within-class variance.
        No distributional assumptions: works for any histogram shape.

        Fastest of all methods (O(n_bins) after one histogram).  Particularly
        reliable for clearly bimodal data with 20/80 to 80/20 splits.
        For very unequal populations (5/95) prefer KDE Valley or 2D GMM.
        """
        active = self._active()
        if not active or not self.x_channel or not self.y_channel:
            messagebox.showwarning("Auto-Gate",
                "Load data and select axes first."); return

        self._last_auto_gate_fn = self.auto_gate_otsu
        sp = self._sens_params()

        all_xt = self._collect_x_transform()
        all_xt = all_xt[np.isfinite(all_xt)]
        all_yt = self._collect_y_transform()
        all_yt = all_yt[np.isfinite(all_yt)]

        try:
            xb_t = otsu_threshold(all_xt, min_class_fraction=sp['otsu_min_frac'])
            yb_t = otsu_threshold(all_yt, min_class_fraction=sp['otsu_min_frac'])
        except Exception as e:
            messagebox.showerror("Otsu Error", str(e)); return

        xb_raw = float(self._inv(np.array([xb_t]), self.x_scale)[0])
        yb_raw = float(self._inv(np.array([yb_t]), self.y_scale)[0])

        self._apply_gate_and_refresh([xb_raw], yb_raw, auto_method='otsu')

        all_x_raw = np.concatenate([df[self.x_channel].dropna().values
                                    for df in active.values()])
        all_y_raw = np.concatenate([df[self.y_channel].dropna().values
                                    for df in active.values()])
        pct_x = float(np.mean(all_x_raw < xb_raw)) * 100
        pct_y = float(np.mean(all_y_raw < yb_raw)) * 100
        self.status_var.set(
            f"✓ Otsu: X @ {xb_raw:,.0f} ({pct_x:.1f}% below)"
            f"  |  Y @ {yb_raw:,.0f} ({pct_y:.1f}% below)")

    def auto_gate_gmm_multi(self):
        """
        GMM Multi (v3.9.7) — fit independent 1-D GMMs on X and Y with
        user-specified component counts, then place ALL equal-density
        thresholds into the existing multi-threshold crosshair system.

        Workflow
        --------
        1.  Read 'GMM pops — X' and 'Y' spinboxes (set independently).
        2.  Fit a GaussianMixture with exactly that many components on
            each axis in transform space (no BIC selection — user decides).
        3.  Compute every equal-density crossing between adjacent
            components (N-1 crossings for N components).
        4.  Store ALL crossings as x_thresh_vars / y_thresh_vars so they
            appear as individual checkboxes in the Threshold panel.
        5.  User unchecks any crossings they do not want.

        Why 'exact N' instead of BIC-best up to N
        ------------------------------------------
        BIC penalises complexity — it almost always prefers fewer
        components than the user can visually identify (e.g. it merges
        a small negative cloud into the dominant positive population).
        Giving the user direct control over the component count makes
        the negative sub-populations discoverable by simply increasing
        the spinbox and observing where new crossings appear.

        Negative population detection tip
        ----------------------------------
        Increase the X or Y spinbox by 1 at a time.  Each extra
        component adds one more crossing.  Start with the value that
        produces crossings that match the visible histogram peaks, then
        uncheck any crossings that sit inside a population (not between
        populations).
        """
        if not HAS_SKLEARN:
            messagebox.showerror(
                "GMM Multi",
                "scikit-learn is required:\n  pip install scikit-learn")
            return
        active = self._active()
        if not active or not self.x_channel or not self.y_channel:
            messagebox.showwarning(
                "GMM Multi", "Load data and select axes first.")
            return

        self._last_auto_gate_fn = self.auto_gate_gmm_multi

        n_x = max(1, min(8, int(self.gmm_max_x_var.get())))
        n_y = max(1, min(8, int(self.gmm_max_y_var.get())))

        from scipy.stats import norm as _norm

        def _fit_and_cross(data_t, n_comp, scale_name):
            """
            Fit exactly n_comp Gaussian components, return
            (thresholds_raw, component_summary_str, gmm_params).

            gmm_params is a dict with keys 'means_t', 'weights', 'stds_t',
            'scale', 'data_range_t' suitable for overlay curve rendering.

            Uses multiple random seeds (n_init=15) to avoid local
            minima — especially important when one component is small
            (negative cloud) and the default kmeans init may miss it.
            """
            data_t = data_t[np.isfinite(data_t)]
            if len(data_t) < max(10, n_comp * 3):
                return [], "not enough data", None

            # Subsample for speed; GMM is stable well above 10k points
            _MAX = 30_000
            rng  = _get_rng(42)
            if len(data_t) > _MAX:
                data_t = data_t[rng.choice(len(data_t), _MAX, replace=False)]

            d2 = data_t.reshape(-1, 1)
            # Try both kmeans and random inits and keep the best log-likelihood
            best_ll, best_gmm = -np.inf, None
            for seed in range(5):          # 5 seeds × n_init=3 each = 15 fits
                for init in ('kmeans', 'random'):
                    try:
                        g = GaussianMixture(
                            n_components=n_comp,
                            covariance_type='full',
                            n_init=3,
                            init_params=init,
                            random_state=seed)
                        g.fit(d2)
                        ll = g.score(d2)   # mean log-likelihood
                        if ll > best_ll:
                            best_ll, best_gmm = ll, g
                    except Exception:
                        pass

            if best_gmm is None:
                return [], "fit failed", None

            order   = np.argsort(best_gmm.means_.flatten())
            means   = best_gmm.means_.flatten()[order]
            weights = best_gmm.weights_[order]
            stds    = np.sqrt(
                best_gmm.covariances_.reshape(n_comp, -1)[:, 0][order])

            # Equal-density crossing between every pair of adjacent components
            thresh_raw = []
            for i in range(n_comp - 1):
                xs  = np.linspace(means[i], means[i + 1], 5000)
                d1  = weights[i]     * _norm.pdf(xs, means[i],     stds[i])
                d2_ = weights[i + 1] * _norm.pdf(xs, means[i + 1], stds[i + 1])
                t_t = float(xs[np.argmin(np.abs(d1 - d2_))])
                t_r = float(self._inv(np.array([t_t]), scale_name)[0])
                thresh_raw.append(t_r)

            summary = "  |  ".join(
                f"C{i+1} μ≈{float(self._inv(np.array([means[i]]), scale_name)[0]):,.0f}"
                f" w={weights[i]:.0%}"
                for i in range(n_comp))

            # Build params needed to reconstruct PDF curves during plot rendering.
            # Means are stored as back-transformed raw values so the renderer can
            # build legend labels without knowing the scale; stds remain in
            # transform space because the histogram bins are in raw space and the
            # PDF is evaluated in transform space then mapped back.
            gmm_params = {
                'means_t':      [float(m) for m in means],
                'means_raw':    [float(self._inv(np.array([m]), scale_name)[0])
                                 for m in means],
                'weights':      [float(w) for w in weights],
                'stds_t':       [float(s) for s in stds],
                'scale':        scale_name,
                'data_range_t': (float(data_t.min()), float(data_t.max())),
                'n_data':       len(data_t),
            }
            return thresh_raw, summary, gmm_params

        # ── X axis ────────────────────────────────────────────────────────────
        all_xt = self._collect_x_transform()
        xbs_raw, x_summary, gmm_x_params = _fit_and_cross(all_xt, n_x, self.x_scale)

        # ── Y axis ────────────────────────────────────────────────────────────
        all_yt = self._collect_y_transform()
        ybs_raw, y_summary, gmm_y_params = _fit_and_cross(all_yt, n_y, self.y_scale)

        if not xbs_raw and not ybs_raw:
            messagebox.showwarning(
                "GMM Multi",
                "Could not fit GMM on either axis.\n"
                "Check that enough data is loaded.")
            return

        # ── Reuse or create gate (same pattern as multi_valley) ───────────────
        target = None
        for g in self.gates:
            if g.get('auto_method') == 'gmm_multi':
                target = g
                break
        if target is None:
            target = self._add_gate(auto_type='crosshair',
                                    auto_method='gmm_multi')

        target['auto_method']   = 'gmm_multi'
        target['type']          = 'crosshair'
        target['x_boundaries']  = xbs_raw
        target['x_thresh_vars'] = [tk.BooleanVar(value=True) for _ in xbs_raw]

        if ybs_raw:
            target['y_boundaries']  = ybs_raw
            target['y_thresh_vars'] = [tk.BooleanVar(value=True)
                                        for _ in ybs_raw]
            target['y_boundary']    = None
            target['y_thresh_var']  = None
        else:
            target['y_boundaries']  = None
            target['y_thresh_vars'] = []
            target['y_boundary']    = None
            target['y_thresh_var']  = None

        target['applied']     = True
        target['gmm_x_params'] = gmm_x_params   # None if fit failed
        target['gmm_y_params'] = gmm_y_params   # None if fit failed
        self._sel_gate_id     = target['id']
        self._gate_hint_var.set(
            f'GMM Multi placed — uncheck crossings you do not want')
        self._compute_gate_stats_for(target)
        self._rebuild_gate_manager()
        self._rebuild_thresh_panel()
        self.refresh_plot()
        self._update_stats_display()

        nx = len(xbs_raw); ny = len(ybs_raw)
        self.status_var.set(
            f"✓ GMM Multi — X: {n_x} comp → {nx} crossing(s)  "
            f"|  Y: {n_y} comp → {ny} crossing(s)  "
            f"|  Uncheck unwanted thresholds in the Threshold panel")

    def auto_gate_cluster_polygons(self):
        """
        HDBSCAN Cluster Polygons — identifies discrete 2D cell populations and
        draws a tight convex-hull polygon gate around each one.

        Why HDBSCAN over DBSCAN:
        - DBSCAN requires eps (neighbourhood radius), which must be manually
          tuned and breaks down for variable-density clusters (typical in flow).
        - HDBSCAN builds a cluster hierarchy and extracts stable clusters
          automatically — no eps needed.  It handles flow cytometry populations
          well because it works at the density scale of each cluster, not a
          single global scale.

        Sensitivity → min_cluster_size:
          s=1:  large mcs (10% of cells) — only the most dominant blobs
          s=7:  ~1.5% of cells — default, finds typical flow populations
          s=10: 0.3% of cells — finds subtle sub-populations

        Algorithm:
          1. Transform both axes (biexp/asinh/etc.) → uniform scale.
          2. Normalise to [0, 1] × [0, 1] so clustering is scale-independent.
          3. Run HDBSCAN with sensitivity-driven min_cluster_size.
          4. For each surviving cluster, compute CONVEX HULL in RAW data space.
          5. Each cluster becomes a polygon gate with a unique color.
        """
        try:
            from sklearn.cluster import HDBSCAN as _HDBSCAN
        except ImportError:
            # sklearn < 1.3 fallback: use DBSCAN with proper normalization
            try:
                from sklearn.cluster import DBSCAN as _DBSCAN
                _HDBSCAN = None
            except ImportError:
                messagebox.showerror("Missing library",
                    "Cluster Polygons requires scikit-learn ≥ 1.3.\n"
                    "Install with: pip install -U scikit-learn")
                return
        try:
            from scipy.spatial import ConvexHull
        except ImportError:
            messagebox.showerror("Missing library",
                "Cluster Polygons requires scipy.\n"
                "Install with: pip install scipy")
            return

        active = self._active()
        if not active or not self.x_channel or not self.y_channel:
            messagebox.showwarning("Auto-Gate",
                "Load data and select axes first."); return

        self._last_auto_gate_fn = self.auto_gate_cluster_polygons

        # ── Sensitivity → min_cluster_size (fraction of total cells) ─────────
        # s=1: 10%   s=7≈1.5%   s=10: 0.3%  (exponential)
        t_s          = (float(self.auto_sensitivity_var.get()) - 1.0) / 9.0
        min_frac     = 0.10 * (0.003 / 0.10) ** t_s   # 10% → 0.3% exponentially

        # ── Collect data ──────────────────────────────────────────────────────
        all_xt = self._collect_x_transform()
        all_yt = self._collect_y_transform()
        all_xr = np.concatenate([df[self.x_channel].dropna().values
                                  for df in active.values()])
        all_yr = np.concatenate([df[self.y_channel].dropna().values
                                  for df in active.values()])

        valid  = np.isfinite(all_xt) & np.isfinite(all_yt)
        xt, yt = all_xt[valid], all_yt[valid]
        xr, yr = all_xr[valid], all_yr[valid]
        n_total = len(xt)
        if n_total < 20:
            messagebox.showwarning("Cluster Polygons", "Not enough data."); return

        # ── Subsample for speed (HDBSCAN is fast, but cap at 10k) ────────────
        MAX_PTS = 10_000
        rng = _get_rng(42)
        if n_total > MAX_PTS:
            idx    = rng.choice(n_total, MAX_PTS, replace=False)
            xt_s, yt_s = xt[idx], yt[idx]
            xr_s, yr_s = xr[idx], yr[idx]
        else:
            xt_s, yt_s = xt, yt
            xr_s, yr_s = xr, yr

        # ── Normalise to [0,1]×[0,1] (proper min-subtraction) ───────────────
        pts = np.column_stack([xt_s, yt_s])
        mins_p = pts.min(axis=0); maxs_p = pts.max(axis=0)
        rng_p  = np.where(maxs_p > mins_p, maxs_p - mins_p, 1.0)
        pts_n  = (pts - mins_p) / rng_p

        min_cluster_size = max(5, int(min_frac * len(xt_s)))
        min_samples      = max(3, min_cluster_size // 5)

        self.status_var.set("Running HDBSCAN…  please wait")
        self.root.update_idletasks()

        try:
            if _HDBSCAN is not None:
                clust  = _HDBSCAN(min_cluster_size=min_cluster_size,
                                   min_samples=min_samples,
                                   cluster_selection_method='eom').fit(pts_n)
            else:
                # DBSCAN fallback with proper normalization and auto eps
                from sklearn.neighbors import NearestNeighbors
                nbrs  = NearestNeighbors(n_neighbors=2).fit(pts_n)
                dists, _ = nbrs.kneighbors(pts_n)
                # Use 10th-pctile of NN distances as eps (more robust than 5th)
                eps = float(np.percentile(dists[:, 1], 10)) * 2.0
                eps = max(eps, 0.01)
                clust = _DBSCAN(eps=eps, min_samples=min_samples).fit(pts_n)
        except Exception as e:
            messagebox.showerror("Cluster Error", str(e)); return

        labels      = clust.labels_
        unique_lbls = [l for l in set(labels) if l != -1]
        if not unique_lbls:
            self.status_var.set(
                "✗ No clusters found — try increasing sensitivity or checking axes/scale")
            return

        # ── Remove previous HDBSCAN gates ────────────────────────────────────
        old_ids = {g['id'] for g in self.gates if g.get('auto_method') == 'dbscan'}
        if old_ids:
            self.gates = [g for g in self.gates if g['id'] not in old_ids]
            # Evict removed gate ids from persistent mask cache
            stale = [k for k in self._gmc if k[3] in old_ids]
            for k in stale:
                self._gmc.pop(k, None)
            if self._sel_gate_id in old_ids:
                self._sel_gate_id = self.gates[-1]['id'] if self.gates else None

        # ── Build convex-hull polygon gate for each cluster ──────────────────
        n_created = 0
        for cluster_label in sorted(unique_lbls):
            mask    = labels == cluster_label
            cxr     = xr_s[mask]; cyr = yr_s[mask]
            pts_raw = np.column_stack([cxr, cyr])
            if len(pts_raw) < 3:
                continue
            try:
                hull  = ConvexHull(pts_raw)
                verts = pts_raw[hull.vertices].tolist()
            except Exception:
                bx0, bx1 = float(cxr.min()), float(cxr.max())
                by0, by1 = float(cyr.min()), float(cyr.max())
                verts = [[bx0,by0],[bx1,by0],[bx1,by1],[bx0,by1]]

            gate             = self._add_gate(auto_method='dbscan')
            gate['type']     = 'polygon'
            gate['vertices'] = [(float(v[0]), float(v[1])) for v in verts]
            gate['applied']  = True
            self._compute_gate_stats_for(gate)
            n_created += 1

        self._rebuild_gate_manager()
        self._rebuild_thresh_panel()
        self.refresh_plot()
        self._update_stats_display()
        noise_n   = int((labels == -1).sum())
        noise_pct = noise_n / len(labels) * 100
        algo      = "HDBSCAN" if _HDBSCAN is not None else "DBSCAN"
        self.status_var.set(
            f"✓ Cluster Polygons ({algo}): {n_created} gate(s)"
            + (f"  |  {noise_pct:.1f}% noise points" if noise_n > 0 else ""))

    # ── Threshold panel ───────────────────────────────────────────────────────

    def _rebuild_thresh_panel(self):
        """Show gate info / crosshair threshold toggles for selected gate."""
        for w in self.thresh_panel.winfo_children():
            w.destroy()
        gate = self._sel_gate()
        if not gate:
            ttk.Label(self.thresh_panel, text="(no gate selected)",
                      style='Dim.TLabel').pack(anchor='w')
            return

        gt = gate.get('type', 'crosshair')
        ttk.Label(self.thresh_panel,
                  text=f"{gate['name']}  [{gt}]",
                  style='Dim.TLabel').pack(anchor='w')

        if gt == 'crosshair':
            xbs  = gate.get('x_boundaries', [])
            yb   = gate.get('y_boundary')
            ybs  = gate.get('y_boundaries')   # multi-Y list

            # ── Y first ──────────────────────────────────────────────────
            # Multi-Y (from multi-valley gate)
            if ybs:
                ttk.Label(self.thresh_panel, text="Y thresholds:",
                          style='Dim.TLabel').pack(anchor='w')
                y_tvs = gate.get('y_thresh_vars', [])
                for i, yb_val in enumerate(ybs):
                    var = y_tvs[i] if i < len(y_tvs) else tk.BooleanVar(value=True)
                    row = ttk.Frame(self.thresh_panel, style='TFrame')
                    row.pack(fill=tk.X, pady=1)
                    ttk.Checkbutton(row, variable=var,
                                    command=self._on_thresh_toggle,
                                    style='TCheckbutton').pack(side=tk.LEFT)
                    ttk.Label(row, text=f'Y{i+1}:  {yb_val:>12,.1f}',
                              style='Mono.TLabel').pack(side=tk.LEFT)
            elif yb is not None:
                ttk.Label(self.thresh_panel, text="Y threshold:",
                          style='Dim.TLabel').pack(anchor='w')
                ytv = gate.get('y_thresh_var') or tk.BooleanVar(value=True)
                row = ttk.Frame(self.thresh_panel, style='TFrame')
                row.pack(fill=tk.X, pady=1)
                ttk.Checkbutton(row, variable=ytv,
                                command=self._on_thresh_toggle,
                                style='TCheckbutton').pack(side=tk.LEFT)
                ttk.Label(row, text=f'Y  :  {yb:>12,.1f}',
                          style='Mono.TLabel').pack(side=tk.LEFT)

            # ── X second ─────────────────────────────────────────────────
            if xbs:
                ttk.Label(self.thresh_panel, text="X thresholds:",
                          style='Dim.TLabel').pack(anchor='w', pady=(6, 0))
                tvs = gate.get('x_thresh_vars', [])
                for i, xb in enumerate(xbs):
                    var = tvs[i] if i < len(tvs) else tk.BooleanVar(value=True)
                    row = ttk.Frame(self.thresh_panel, style='TFrame')
                    row.pack(fill=tk.X, pady=1)
                    ttk.Checkbutton(row, variable=var,
                                    command=self._on_thresh_toggle,
                                    style='TCheckbutton').pack(side=tk.LEFT)
                    ttk.Label(row, text=f'X{i+1}:  {xb:>12,.1f}',
                              style='Mono.TLabel').pack(side=tk.LEFT)

        elif gt == 'rectangle':
            x0,y0 = gate.get('x0',0), gate.get('y0',0)
            x1,y1 = gate.get('x1',0), gate.get('y1',0)
            ttk.Label(self.thresh_panel,
                      text=f"  X: {min(x0,x1):,.1f} → {max(x0,x1):,.1f}",
                      style='Mono.TLabel').pack(anchor='w')
            ttk.Label(self.thresh_panel,
                      text=f"  Y: {min(y0,y1):,.1f} → {max(y0,y1):,.1f}",
                      style='Mono.TLabel').pack(anchor='w')

        elif gt == 'ellipse':
            x0,y0 = gate.get('x0',0), gate.get('y0',0)
            x1,y1 = gate.get('x1',0), gate.get('y1',0)
            ttk.Label(self.thresh_panel,
                      text=f"  Centre: ({(x0+x1)/2:,.1f}, {(y0+y1)/2:,.1f})",
                      style='Mono.TLabel').pack(anchor='w')
            ttk.Label(self.thresh_panel,
                      text=f"  a={abs(x1-x0)/2:,.1f}  b={abs(y1-y0)/2:,.1f}",
                      style='Mono.TLabel').pack(anchor='w')

        elif gt == 'polygon':
            n = len(gate.get('vertices', []))
            s = 'drawing…' if self._poly_active else 'closed'
            ttk.Label(self.thresh_panel, text=f"  {n} vertices  ({s})",
                      style='Mono.TLabel').pack(anchor='w')
            if self._poly_active:
                ttk.Label(self.thresh_panel,
                          text="  Click ✓ Close Polygon or dbl-click",
                          style='Dim.TLabel').pack(anchor='w')

        # Drag-handle hint
        if gate.get('applied') and gt in ('rectangle', 'ellipse', 'polygon'):
            ttk.Label(self.thresh_panel,
                      text="  Drag ◼ handles to reshape",
                      style='Dim.TLabel').pack(anchor='w', pady=(4,0))


    def _on_thresh_toggle(self):
        sel = self._sel_gate()
        if sel:
            self._compute_gate_stats_for(sel)
        self.refresh_plot()
        self._update_stats_display()

    # ── Stats ─────────────────────────────────────────────────────────────────

    def _compute_gate_stats_for(self, gate: dict):
        """Compute stats for a single gate dict, store in self.gate_stats[gate_id]."""
        if not gate or not gate.get('applied'): return
        gid = gate['id']
        self.gate_stats[gid] = {}
        for path, df in self._active().items():
            if self.x_channel not in df.columns or \
               self.y_channel not in df.columns: continue
            xa    = df[self.x_channel].to_numpy(dtype=float, copy=False)
            ya    = df[self.y_channel].to_numpy(dtype=float, copy=False)
            total = len(xa)
            regions, _ = self._gate_mask_for(gate, xa, ya, _cache_path=path)
            self.gate_stats[gid][path] = {
                'stats': {
                    rname: {'count': (c := int(m.sum())), 'pct': c/total*100 if total else 0.0}
                    for rname, m in regions.items()},
                'total': total}

    def _merged_stats_from(self, gate_data: dict) -> dict:
        """Merge per-file stats from a {path: {stats, total}} dict."""
        if not gate_data: return {}
        first_stats  = next(iter(gate_data.values()))['stats']
        region_names = list(first_stats.keys())
        counts = {r: 0 for r in region_names}
        total  = 0
        for info in gate_data.values():
            total += info['total']
            for r in region_names:
                counts[r] += info['stats'].get(r, {}).get('count', 0)
        return {'stats': {r: {'count': counts[r],
                               'pct': counts[r]/total*100 if total else 0.0}
                          for r in region_names},
                'total': total}

    def _merged_stats(self) -> dict:
        """Convenience wrapper used by export_stats."""
        return self._merged_stats_from(
            self.gate_stats.get(self._sel_gate_id, {}))

    def _update_stats_display(self):
        """
        Show a combined gate partition.

        Single gate:  IN / OUT rows as before.

        Multiple gates: compute a Venn-like partition across ALL files:
          - Each gate's exclusive IN cells
          - Cells IN multiple gates (overlap regions)
          - Outside all gates

        This gives percentages that sum to 100%% and are directly comparable.
        """
        for item in self.stats_tree.get_children():
            self.stats_tree.delete(item)

        applied = [g for g in self.gates if g.get('applied')]
        if not applied: return

        mode = self.stats_mode_var.get()

        # ── Single gate: show per-gate IN/OUT breakdown ───────────────────
        if len(applied) == 1:
            gate       = applied[0]
            gid        = gate['id']
            gate_stats = self.gate_stats.get(gid, {})
            if not gate_stats: return
            star = ' ▸' if gid == self._sel_gate_id else ''
            lbl  = f'{gate["name"]}{star}  [{gate["type"]}]'
            if mode == 'merged':
                merged = self._merged_stats_from(gate_stats)
                if not merged: return
                root_id = self.stats_tree.insert(
                    '', 'end', text=f'  {lbl}',
                    values=(f"{merged['total']:,}", ''), open=True)
                for ri, (q, d) in enumerate(merged['stats'].items()):
                    self.stats_tree.insert(
                        root_id, 'end', text=f'    {q}',
                        values=(f"{d['count']:,}", f"{d['pct']:.1f}%"),
                        tags=(f'rc{ri % len(REGION_COLORS)}',))
            else:
                for path, info in gate_stats.items():
                    name  = os.path.basename(path)
                    short = (name[:26] + '…') if len(name) > 27 else name
                    fid   = self.stats_tree.insert(
                        '', 'end', text=f'  {lbl}  ·  {short}',
                        values=(f"{info['total']:,}", ''), open=True)
                    for ri, (q, d) in enumerate(info['stats'].items()):
                        self.stats_tree.insert(
                            fid, 'end', text=f'    {q}',
                            values=(f"{d['count']:,}", f"{d['pct']:.1f}%"),
                            tags=(f'rc{ri % len(REGION_COLORS)}',))
            return

        # ── Multiple gates: Venn partition ───────────────────────────────
        # Compute partition using all active file data merged together,
        # or per-file depending on mode.
        active = self._active()
        if not active: return

        def _partition_data(xa, ya):
            """Return {region_label: count} for a Venn partition."""
            n    = len(xa)
            # in_masks[i] = boolean array of cells in gate i's IN region
            in_masks = []
            for gate in applied:
                regions, _ = self._gate_mask_for(gate, xa, ya)
                gt = gate.get('type', 'crosshair')
                if gt == 'crosshair':
                    # crosshair: a cell is "in" if not in any named OUT quadrant
                    # We combine all non-OUT quadrant masks
                    in_m = np.zeros(n, bool)
                    for rname, m in regions.items():
                        in_m |= m   # all quadrants are "in" for crosshair gates
                    # Actually for crosshair each quadrant is a separate region.
                    # We treat the gate as "applied" to the cell if it falls in
                    # any non-trivial quadrant (i.e. not pure background).
                    # Simpler: use the first non-OUT region as "in this gate's area"
                    in_m = np.zeros(n, bool)
                    for rname, m in regions.items():
                        if rname != 'OUT':
                            in_m |= m
                else:
                    in_m = regions.get('IN', np.zeros(n, bool))
                in_masks.append(in_m)

            parts  = {}
            for mask_combo in _all_combos(len(applied)):
                combo_mask = np.ones(n, bool)
                labels     = []
                for i, flag in enumerate(mask_combo):
                    if flag:
                        combo_mask &= in_masks[i]
                        labels.append(applied[i]['name'])
                    else:
                        combo_mask &= ~in_masks[i]
                cnt = int(combo_mask.sum())
                if cnt == 0:
                    continue
                region_name = (' ∩ '.join(labels)) if labels else 'Outside all'
                parts[region_name] = parts.get(region_name, 0) + cnt
            return parts

        def _all_combos(n_gates):
            """Generate all 2^n binary combos as tuples of bool."""
            for i in range(2 ** n_gates):
                yield tuple(bool((i >> j) & 1) for j in range(n_gates))

        if mode == 'merged':
            total = 0
            merged_parts = {}
            for df in active.values():
                if self.x_channel not in df.columns or                    self.y_channel not in df.columns: continue
                xa = df[self.x_channel].to_numpy(dtype=float, copy=False)
                ya = df[self.y_channel].to_numpy(dtype=float, copy=False)
                total += len(xa)
                for k, v in _partition_data(xa, ya).items():
                    merged_parts[k] = merged_parts.get(k, 0) + v

            # Sort: IN-only regions first, overlaps next, Outside last
            def _sort_key(k):
                if k == 'Outside all': return (2, k)
                if '∩' in k:          return (1, k)
                return (0, k)

            root_id = self.stats_tree.insert(
                '', 'end',
                text=f'  Combined ({len(applied)} gates, {len(active)} files)',
                values=(f"{total:,}", ''), open=True)
            for ri, (region, cnt) in enumerate(
                    sorted(merged_parts.items(), key=lambda x: _sort_key(x[0]))):
                pct = cnt / total * 100 if total else 0.0
                self.stats_tree.insert(
                    root_id, 'end', text=f'    {region}',
                    values=(f"{cnt:,}", f"{pct:.1f}%"),
                    tags=(f'rc{ri % len(REGION_COLORS)}',))
        else:
            for path, df in active.items():
                if self.x_channel not in df.columns or                    self.y_channel not in df.columns: continue
                xa    = df[self.x_channel].to_numpy(dtype=float, copy=False)
                ya    = df[self.y_channel].to_numpy(dtype=float, copy=False)
                total = len(xa)
                parts = _partition_data(xa, ya)
                name  = os.path.basename(path)
                short = (name[:26] + '…') if len(name) > 27 else name
                fid   = self.stats_tree.insert(
                    '', 'end', text=f'  {short}',
                    values=(f"{total:,}", ''), open=True)

                def _sort_key(k):
                    if k == 'Outside all': return (2, k)
                    if '∩' in k:          return (1, k)
                    return (0, k)

                for ri, (region, cnt) in enumerate(
                        sorted(parts.items(), key=lambda x: _sort_key(x[0]))):
                    pct = cnt / total * 100 if total else 0.0
                    self.stats_tree.insert(
                        fid, 'end', text=f'    {region}',
                        values=(f"{cnt:,}", f"{pct:.1f}%"),
                        tags=(f'rc{ri % len(REGION_COLORS)}',))

    # ── Export ────────────────────────────────────────────────────────────────

    def _auto_stem(self) -> str:
        active = self._active()
        if active:
            return os.path.splitext(os.path.basename(next(iter(active))))[0]
        return 'flowjo_export'

    def save_gates(self):
        """
        Serialise all current gates to a JSON file.

        JSON schema (v1):
          version       : int   — format version for forward-compat
          x_channel     : str   — X axis column name at save time
          y_channel     : str   — Y axis column name at save time
          gates         : list of gate objects (see below)

        Each gate object:
          id, name, type, auto_method
          color, linestyle, linewidth
          x_boundaries, y_boundary
          x_thresh_active   : list[bool]   (replaces tkinter BooleanVars)
          y_thresh_active   : bool
          y_boundaries, y_thresh_actives : list[bool]
          x0, y0, x1, y1
          vertices          : list[[x,y]]
        """
        import json
        if not self.gates:
            messagebox.showwarning("Save Gates", "No gates to save."); return

        stem = self._auto_stem()
        path = filedialog.asksaveasfilename(
            defaultextension='.json',
            initialfile=f'{stem}_gates.json',
            filetypes=[("Gate file (JSON)", "*.json"), ("All files", "*.*")])
        if not path: return

        def _gate_to_dict(g: dict) -> dict:
            return {
                'id':         g.get('id'),
                'name':       g.get('name', ''),
                'type':       g.get('type', 'crosshair'),
                'auto_method':g.get('auto_method'),
                'applied':    g.get('applied', False),
                'color':      g.get('color', '#e74c3c'),
                'linestyle':  g.get('linestyle', '-'),
                'linewidth':  g.get('linewidth', 0.5),
                # crosshair thresholds
                'x_boundaries':     g.get('x_boundaries', []),
                'y_boundary':       g.get('y_boundary'),
                'x_thresh_active':  [bool(v.get()) for v in g.get('x_thresh_vars', [])],
                'y_thresh_active':  bool(g['y_thresh_var'].get())
                                    if g.get('y_thresh_var') else True,
                # multi-Y
                'y_boundaries':     g.get('y_boundaries'),
                'y_thresh_actives': [bool(v.get()) for v in g.get('y_thresh_vars', [])],
                # rect / ellipse
                'x0': g.get('x0', 0.0), 'y0': g.get('y0', 0.0),
                'x1': g.get('x1', 0.0), 'y1': g.get('y1', 0.0),
                # polygon
                'vertices': list(g.get('vertices', [])),
            }

        payload = {
            'version':   1,
            'x_channel': self.x_channel or '',
            'y_channel': self.y_channel or '',
            'gates':     [_gate_to_dict(g) for g in self.gates],
        }

        with open(path, 'w') as fh:
            json.dump(payload, fh, indent=2)

        n = len(self.gates)
        self.status_var.set(f"✓ {n} gate(s) saved → {os.path.basename(path)}")
        messagebox.showinfo("Save Gates",
            f"{n} gate(s) saved to:\n{path}\n\n"
            f"Channels at save time:\n"
            f"  X: {self.x_channel}\n  Y: {self.y_channel}")

    def load_gates(self):
        """
        Load gates from a previously saved JSON file.

        The current gates are replaced.  Channels in the file are matched to
        the currently loaded data; a warning is shown if they differ so the
        user can switch axes before loading.
        """
        import json
        path = filedialog.askopenfilename(
            filetypes=[("Gate file (JSON)", "*.json"), ("All files", "*.*")])
        if not path: return

        try:
            with open(path) as fh:
                payload = json.load(fh)
        except Exception as e:
            messagebox.showerror("Load Gates", f"Could not read file:\n{e}"); return

        if payload.get('version', 0) != 1:
            messagebox.showwarning("Load Gates",
                "Unknown gate file version. Attempting to load anyway.")

        saved_x = payload.get('x_channel', '')
        saved_y = payload.get('y_channel', '')
        if saved_x != (self.x_channel or '') or saved_y != (self.y_channel or ''):
            if not messagebox.askyesno("Load Gates",
                f"Channel mismatch!\n\n"
                f"Saved with:   X={saved_x!r}  Y={saved_y!r}\n"
                f"Current axes: X={self.x_channel!r}  Y={self.y_channel!r}\n\n"
                "Load anyway? (Gate positions will be wrong if channels differ.)"):
                return

        def _dict_to_gate(d: dict) -> dict:
            xta  = d.get('x_thresh_active', [])
            yta  = d.get('y_thresh_actives', [])
            xbs  = d.get('x_boundaries', [])
            ybs  = d.get('y_boundaries')
            return {
                'id':          d.get('id', self._next_gate_id),
                'name':        d.get('name', 'Gate'),
                'type':        d.get('type', 'crosshair'),
                'auto_method': d.get('auto_method'),
                'applied':     d.get('applied', False),
                'color':       d.get('color', '#e74c3c'),
                'linestyle':   d.get('linestyle', '-'),
                'linewidth':   float(d.get('linewidth', 0.5)),
                'x_boundaries':  list(xbs),
                'y_boundary':    d.get('y_boundary'),
                'x_thresh_vars': [tk.BooleanVar(value=bool(a)) for a in xta],
                'y_thresh_var':  tk.BooleanVar(value=bool(d.get('y_thresh_active', True))),
                'y_boundaries':  ybs,
                'y_thresh_vars': [tk.BooleanVar(value=bool(a)) for a in yta],
                'x0': float(d.get('x0', 0.0)), 'y0': float(d.get('y0', 0.0)),
                'x1': float(d.get('x1', 0.0)), 'y1': float(d.get('y1', 0.0)),
                'vertices': [tuple(v) for v in d.get('vertices', [])],
            }

        # Replace current gates
        raw_gates = payload.get('gates', [])
        new_gates = []
        max_id = -1
        for d in raw_gates:
            g = _dict_to_gate(d)
            new_gates.append(g)
            max_id = max(max_id, g['id'])
        if not new_gates:
            messagebox.showwarning("Load Gates", "No gates found in file."); return

        self.clear_all_gates()
        self.gates = new_gates
        self._next_gate_id = max_id + 1
        self._sel_gate_id  = new_gates[-1]['id']

        # Recompute stats for applied gates
        for g in self.gates:
            if g.get('applied') and self._active():
                self._compute_gate_stats_for(g)

        self._rebuild_gate_manager()
        self._rebuild_thresh_panel()
        self._update_stats_display()
        self.refresh_plot()

        n = len(new_gates)
        self.status_var.set(f"✓ {n} gate(s) loaded from {os.path.basename(path)}")
        messagebox.showinfo("Load Gates",
            f"{n} gate(s) loaded from:\n{path}")

    def export_stats(self):
        if not self.gate_stats.get(self._sel_gate_id):
            messagebox.showwarning("Export", "Apply a gate first."); return
        stem = self._auto_stem()
        xn   = (self.x_channel or 'X').replace(' ', '_')
        yn   = (self.y_channel or 'Y').replace(' ', '_')
        path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            initialfile=f'{stem}_{xn}_vs_{yn}_stats.csv',
            filetypes=[("CSV", "*.csv")])
        if not path: return

        rows = []
        xbs  = self._active_xbs()
        yb   = self._active_yb()
        mode = self.stats_mode_var.get()
        gate_stats_for = self.gate_stats.get(self._sel_gate_id, {})

        if mode == 'merged':
            merged = self._merged_stats()
            if merged:
                for q, d in merged['stats'].items():
                    rows.append({
                        'File': 'MERGED',
                        'X Channel': self.x_channel,
                        'Y Channel': self.y_channel,
                        'X Gates': '; '.join(f'{v:.4f}' for v in xbs),
                        'Y Gate': round(yb, 4) if yb else '',
                        'Population': q,
                        'Count': d['count'],
                        'Total': merged['total'],
                        'Percentage': round(d['pct'], 2),
                    })
        else:
            for fp, info in gate_stats_for.items():
                for q, d in info['stats'].items():
                    rows.append({
                        'File': os.path.basename(fp),
                        'X Channel': self.x_channel,
                        'Y Channel': self.y_channel,
                        'X Gates': '; '.join(f'{v:.4f}' for v in xbs),
                        'Y Gate': round(yb, 4) if yb else '',
                        'Population': q,
                        'Count': d['count'],
                        'Total': info['total'],
                        'Percentage': round(d['pct'], 2),
                    })
        pd.DataFrame(rows).to_csv(path, index=False)
        messagebox.showinfo("Export", f"Stats saved:\n{path}")

    # ── Batch stats export ────────────────────────────────────────────────────

    def batch_export_stats(self):
        """
        Apply the current gates to every matching file in the source folder
        (and sub-folders) and write one summary CSV — one row per file.

        Workflow:
          1. Detect the root folder from currently loaded files (or let the
             user pick one manually).
          2. User sets a filename suffix pattern (default '___CytoFile') and
             file type (CSV / FCS / both).
          3. The tool scans the folder tree for matching files.
          4. Each file is loaded in memory, the current gates are applied,
             and per-region counts + percentages are computed.
          5. A wide-format CSV is saved: one row per file, columns for each
             gate × region combination.

        The row label is the filename stem (without extension), so e.g.
        '20241122_DA-FASS_..._1___CytoFile' → that string as the Sample column.
        """
        applied = [g for g in self.gates if g.get('applied')]
        if not applied:
            messagebox.showwarning("Batch Stats",
                "Apply at least one gate first."); return
        if not self.x_channel or not self.y_channel:
            messagebox.showwarning("Batch Stats",
                "Select X and Y channels first."); return

        # Auto-detect root folders from loaded files
        auto_folders = sorted({os.path.dirname(p) for p in self.loaded_files})

        dlg = BatchStatsDialog(self.root, self.T, auto_folders,
                               self.x_channel, self.y_channel)
        self.root.wait_window(dlg)
        if not dlg.result:
            return

        folder, suffix, file_types, save_path = dlg.result

        # ── Build exclusion set from excluded_files ───────────────────────
        # Two levels:
        #   1. Direct: the exact file path (or stem) is in excluded_files
        #   2. Family: the file shares a long experiment prefix with an
        #              excluded file (e.g. exclud. "…_Pooled_CytoFile" also
        #              blocks "…_1___CytoFile", "…_2___CytoFile", etc.)
        #
        # Family prefix = os.path.commonprefix([excl_stem, target_stem])
        # trimmed to the last `_` boundary, requiring ≥ 10 chars so that
        # coincidental short matches ("TH_") don't trigger false exclusions.

        excl_stems = {
            os.path.splitext(os.path.basename(p))[0].lower(): p
            for p in self.excluded_files
        }
        excl_paths = {p.lower() for p in self.excluded_files}

        def _family_exclusion_prefix(target_stem: str):
            """Return the shared prefix and the matched excluded stem,
            or (None, None) if no family match is found.

            Rule: common character-level prefix (trimmed to the last `_`
            boundary) must cover ≥ 70 % of the shorter of the two stems.
            This means only files that share almost their entire name are
            treated as the same family — e.g. the same experiment, same
            animal, same channel combination — differing only in the file
            number vs 'Pooled' at the end.
            """
            ts = target_stem.lower()
            for es in excl_stems:
                cp = os.path.commonprefix([es, ts])
                # Trim to last underscore boundary (avoids partial token matches)
                if '_' in cp:
                    cp = cp[:cp.rfind('_') + 1]
                if not cp:
                    continue
                min_len = min(len(es), len(ts))
                if min_len > 0 and len(cp) / min_len >= 0.70:
                    return cp, es
            return None, None


        exts = []
        if file_types in ('csv', 'both'):  exts.append('.csv')
        if file_types in ('fcs', 'both'):  exts += ['.fcs', '.FCS']

        target_files  = []
        skipped_excl  = []   # (fname, reason) — excluded by rule
        suffix_lower  = suffix.strip().lower()
        for root_d, _, files in os.walk(folder):
            for fname in sorted(files):
                base, ext = os.path.splitext(fname)
                if ext.lower() not in [e.lower() for e in exts]:
                    continue
                if suffix_lower and suffix_lower not in fname.lower():
                    continue
                fpath = os.path.join(root_d, fname)

                # ── Exclusion check 1: direct path match ─────────────────
                if fpath.lower() in excl_paths:
                    skipped_excl.append(
                        (fname, "directly excluded from analysis"))
                    continue

                # ── Exclusion check 2: family prefix match ────────────────
                prefix, matched_excl = _family_exclusion_prefix(base)
                if prefix is not None:
                    skipped_excl.append(
                        (fname, f"family of excluded '{matched_excl}' "
                                f"(shared prefix '{prefix}')"))
                    continue

                target_files.append(fpath)

        if not target_files and not skipped_excl:
            messagebox.showwarning("Batch Stats",
                f"No matching files found in:\n{folder}\n\n"
                f"Pattern: '{suffix}', types: {file_types}")
            return
        if not target_files:
            excl_summary = "\n".join(f"  {f}  ← {r}" for f, r in skipped_excl[:10])
            messagebox.showwarning("Batch Stats",
                f"All matching files were excluded ({len(skipped_excl)} total).\n\n"
                f"{excl_summary}")
            return

        # ── Process each file ─────────────────────────────────────────────
        self.status_var.set(f"Batch stats: processing 0 / {len(target_files)} files…")
        self.root.update_idletasks()

        # Determine all region names from currently applied gates
        # (we need consistent columns even if a file has no cells in a region)
        region_cols = []   # list of (gate_name, region_name) tuples
        for gate in applied:
            gname = gate['name']
            # Use a tiny dummy array to discover region labels
            dummy_xa = np.array([0.0]); dummy_ya = np.array([0.0])
            regions, _ = self._gate_mask_for(gate, dummy_xa, dummy_ya)
            for rname in regions:
                region_cols.append((gname, rname))

        all_rows = []
        errors   = []

        # Sub-gate context: if this FlowApp was opened by double-clicking a
        # gate region in the parent tab, batch stats must first filter each
        # raw file through that parent gate/region before applying the
        # sub-gate's own gates — otherwise we'd be computing stats against
        # the full unfiltered population instead of the sub-gate population.
        is_subgate    = self.parent_gate is not None
        p_gate        = self.parent_gate
        p_region      = self.parent_region

        for fi, fpath in enumerate(target_files):
            self.status_var.set(
                f"Batch stats: {fi+1} / {len(target_files)} — {os.path.basename(fpath)}")
            self.root.update_idletasks()
            try:
                df = self._read_data_file(fpath)
            except Exception as e:
                errors.append(f"{os.path.basename(fpath)}: load error — {e}")
                continue

            if self.x_channel not in df.columns or self.y_channel not in df.columns:
                errors.append(
                    f"{os.path.basename(fpath)}: missing channel "
                    f"'{self.x_channel}' or '{self.y_channel}'")
                continue

            # ── Sub-gate pre-filter ───────────────────────────────────────
            # Restrict to the same parent-gate region that was double-clicked
            # so the percentages are relative to that sub-population, not to
            # all cells in the file.
            if is_subgate:
                xa_all = df[self.x_channel].to_numpy(dtype=float, copy=False)
                ya_all = df[self.y_channel].to_numpy(dtype=float, copy=False)
                p_regions, _ = self._gate_mask_for(p_gate, xa_all, ya_all,
                                                    _cache_path=fpath)
                p_mask = p_regions.get(p_region)
                if p_mask is None or not p_mask.any():
                    errors.append(
                        f"{os.path.basename(fpath)}: no cells in parent region "
                        f"'{p_region}' — skipped")
                    continue
                df = df[p_mask].reset_index(drop=True)

            xa    = df[self.x_channel].to_numpy(dtype=float, copy=False)
            ya    = df[self.y_channel].to_numpy(dtype=float, copy=False)
            total = len(xa)
            stem  = os.path.splitext(os.path.basename(fpath))[0]

            row = {'Sample': stem, 'Total_Cells': total,
                   'Source_File': fpath}

            for gate in applied:
                gname   = gate['name']
                regions, _ = self._gate_mask_for(gate, xa, ya,
                                                  _cache_path=fpath)
                for rname, mask in regions.items():
                    cnt = int(mask.sum())
                    pct = round(cnt / total * 100, 3) if total else 0.0
                    safe = rname.replace('/', '_').replace(' ', '_')
                    row[f'{gname}__{safe}__N']   = cnt
                    row[f'{gname}__{safe}__pct'] = pct

            all_rows.append(row)

        if not all_rows:
            msg = "No files could be processed."
            if errors:
                msg += "\n\nErrors:\n" + "\n".join(errors[:10])
            messagebox.showerror("Batch Stats", msg)
            return

        # ── Write CSV ─────────────────────────────────────────────────────
        result_df = pd.DataFrame(all_rows)
        # Reorder: Sample, Total_Cells, then all gate columns, then Source_File
        gate_cols = [c for c in result_df.columns
                     if c not in ('Sample', 'Total_Cells', 'Source_File')]
        result_df = result_df[['Sample', 'Total_Cells'] + sorted(gate_cols) + ['Source_File']]
        result_df.to_csv(save_path, index=False)

        # ── Write excluded-files log (always, even if empty) ─────────────
        log_path = os.path.splitext(save_path)[0] + '_excluded.csv'
        log_rows = []
        for fname, reason in skipped_excl:
            log_rows.append({'Filename': fname, 'Full_Path': '',
                             'Reason': reason})
        for err_msg in errors:
            # err_msg format: "basename: description"
            parts = err_msg.split(': ', 1)
            log_rows.append({'Filename': parts[0],
                             'Full_Path': '',
                             'Reason': parts[1] if len(parts) > 1 else err_msg})
        pd.DataFrame(log_rows, columns=['Filename', 'Full_Path', 'Reason']
                     ).to_csv(log_path, index=False)

        status_msg = (f"✓ Batch stats: {len(all_rows)} files → "
                      f"{os.path.basename(save_path)}")
        if skipped_excl:
            status_msg += f"  |  {len(skipped_excl)} excluded"
        if errors:
            status_msg += f"  |  {len(errors)} errors"
        self.status_var.set(status_msg)

        msg = (f"Batch stats exported:\n{save_path}\n\n"
               f"  Files processed:          {len(all_rows)}\n"
               f"  Gates applied:            {len(applied)}\n"
               f"  Excluded (family/direct): {len(skipped_excl)}")
        if errors:
            msg += f"\n  Skipped (load errors):    {len(errors)}"
        msg += f"\n\nExclusion log:\n{log_path}"

        show_details = (skipped_excl or errors) and messagebox.askyesno(
            "Batch Stats", msg + "\n\nShow skipped/error details?")
        if show_details:
            lines = []
            if skipped_excl:
                lines.append("=== Excluded by family/direct rule ===")
                lines += [f"  {f}  ← {r}" for f, r in skipped_excl]
            if errors:
                lines.append("\n=== Load errors ===")
                lines += [f"  {e}" for e in errors]
            messagebox.showinfo("Skipped Files", "\n".join(lines))
        elif not (skipped_excl or errors):
            messagebox.showinfo("Batch Stats", msg)

    def export_gated_data(self):
        """
        Export the raw cell-level data for all gated populations to a single CSV.

        For every active file × every applied gate, each cell that falls inside
        at least one gate region is included once (assigned to the region of the
        FIRST matching gate in gate-manager order).

        Extra columns added:
          Source_File  — basename of the originating CSV
          Gate_Name    — name of the gate the cell belongs to
          Gate_Region  — region label (IN / TH+/VGLUT1- / TH+/VGLUT1+ / etc.)
          Gate_Type    — crosshair | rectangle | ellipse | polygon

        Cells that fall outside all gates are excluded by default (they are not
        interesting to the user in this context).

        If NO gates are applied, all cells from active files are exported with
        Source_File column only (plain dump).
        """
        active = self._active()
        if not active:
            messagebox.showwarning("Export", "Load data first."); return

        applied_gates = [g for g in self.gates if g.get('applied')]

        stem = self._auto_stem()
        xn   = (self.x_channel or 'X').replace(' ', '_')
        yn   = (self.y_channel or 'Y').replace(' ', '_')
        default_name = f'{stem}_{xn}_vs_{yn}_gated_cells.csv'

        save_path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            initialfile=default_name,
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not save_path:
            return

        self.status_var.set("Exporting gated data…")
        self.root.update_idletasks()

        all_frames = []

        for file_path, df in active.items():
            file_base = os.path.basename(file_path)

            # ── No gates: export everything with just Source_File ──────────
            if not applied_gates:
                out = df.copy()
                out.insert(0, 'Source_File', file_base)
                all_frames.append(out)
                continue

            # ── Build per-gate masks ────────────────────────────────────────
            xa = df[self.x_channel].to_numpy(dtype=float, copy=False) \
                 if self.x_channel and self.x_channel in df.columns else None
            ya = df[self.y_channel].to_numpy(dtype=float, copy=False) \
                 if self.y_channel and self.y_channel in df.columns else None

            if xa is None or ya is None:
                # Can't gate this file — export raw
                out = df.copy()
                out.insert(0, 'Source_File', file_base)
                out['Gate_Name']   = '(no matching axes)'
                out['Gate_Region'] = ''
                out['Gate_Type']   = ''
                all_frames.append(out)
                continue

            n = len(df)
            assigned_gate   = np.full(n, '', dtype=object)
            assigned_region = np.full(n, '', dtype=object)
            assigned_type   = np.full(n, '', dtype=object)
            in_any          = np.zeros(n, bool)

            for gate in applied_gates:
                regions, _ = self._gate_mask_for(gate, xa, ya,
                                                  _cache_path=file_path)
                gt    = gate.get('type', 'crosshair')
                gname = gate.get('name', '')

                for rname, mask in regions.items():
                    # For shape gates skip OUT region (not an interesting gate)
                    if gt != 'crosshair' and rname == 'OUT':
                        continue
                    # Only assign cells not yet claimed by an earlier gate
                    new_cells = mask & ~in_any
                    if new_cells.any():
                        assigned_gate[new_cells]   = gname
                        assigned_region[new_cells] = rname
                        assigned_type[new_cells]   = gt
                        in_any[new_cells] = True

            # Keep only gated cells
            gated_mask = in_any
            if not gated_mask.any():
                continue   # skip file with no cells in any gate

            out = df[gated_mask].copy().reset_index(drop=True)
            out.insert(0, 'Source_File',  [file_base] * int(gated_mask.sum()))
            out['Gate_Name']   = assigned_gate[gated_mask]
            out['Gate_Region'] = assigned_region[gated_mask]
            out['Gate_Type']   = assigned_type[gated_mask]
            all_frames.append(out)

        if not all_frames:
            messagebox.showwarning("Export",
                "No gated cells found. Apply a gate first."); return

        combined = pd.concat(all_frames, ignore_index=True)
        combined.to_csv(save_path, index=False)

        n_cells = len(combined)
        n_files = combined['Source_File'].nunique()
        self.status_var.set(
            f"✓ Exported {n_cells:,} cells from {n_files} file(s) → "
            + os.path.basename(save_path))
        messagebox.showinfo("Export",
            f"Gated data saved:\n{save_path}\n\n"
            f"{n_cells:,} cells · {n_files} file(s)\n"
            f"Gates: {', '.join(g['name'] for g in applied_gates)}")

    def open_polar_analysis(self):
        """
        Open the Polar / Vector Analysis window.

        The window inherits the currently active files and applied gates
        from this FlowApp instance, but manages its own display independently.
        """
        if not self.loaded_files:
            messagebox.showwarning(
                "Polar Analysis",
                "Load at least one data file first.")
            return
        win = PolarAnalysisWindow(self.root, self.T, self)
        win.focus_set()

    def open_batch_plots(self):
        """Open the Batch Plots window (violin distributions + gate % bars)."""
        if not self.loaded_files:
            messagebox.showwarning(
                "Batch Plots",
                "Load at least one data file first.")
            return
        win = BatchPlotWindow(self.root, self.T, self)
        win.focus_set()

    def export_figure(self):
        stem = self._auto_stem()
        xn   = (self.x_channel or 'X').replace(' ', '_')
        yn   = (self.y_channel or 'Y').replace(' ', '_')
        path = filedialog.asksaveasfilename(
            defaultextension='.pdf',
            initialfile=f'{stem}_{xn}_vs_{yn}.pdf',
            filetypes=[("PDF", "*.pdf"), ("PNG", "*.png"),
                       ("SVG", "*.svg"), ("All", "*.*")])
        if not path: return

        # For vector formats (PDF / SVG) un-rasterize every scatter collection
        # so dots are drawn as true vectors (crisp at any zoom level).
        # For PNG/raster formats, keep rasterized=True for performance.
        ext = os.path.splitext(path)[1].lower()
        is_vector = ext in ('.pdf', '.svg', '.eps')

        # Snapshot current rasterized state of all collections in all axes
        collections_state = []
        if is_vector:
            for ax in self.fig.get_axes():
                for coll in ax.collections:
                    collections_state.append((coll, coll.get_rasterized()))
                    coll.set_rasterized(False)
        try:
            self.fig.savefig(path, dpi=300, bbox_inches='tight',
                             facecolor=self.fig.get_facecolor())
            messagebox.showinfo("Saved", f"Figure saved:\n{path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))
        finally:
            # Always restore rasterized state (even if save failed)
            for coll, state in collections_state:
                coll.set_rasterized(state)



# ─────────────────────────────────────────────────────────────────────────────
#  Rotated x-label helper for dense categorical axes
# ─────────────────────────────────────────────────────────────────────────────

def _set_rotated_xlabels(ax, labels: list, fontsize: int = 7) -> None:
    """
    Apply 45 ° rotated x-tick labels using standard matplotlib tick machinery.

    ha='right' pins the top-right corner of each label exactly at its tick
    mark so every label — regardless of length — aligns consistently with
    its bar/violin.  This is the canonical matplotlib approach and avoids
    the coordinate-mixing issues of the previous annotate-based helper.
    """
    ax.set_xticklabels(labels, rotation=45, ha='right',
                       fontsize=fontsize, rotation_mode='anchor')


# ─────────────────────────────────────────────────────────────────────────────
#  Batch Plot Window
# ─────────────────────────────────────────────────────────────────────────────

class BatchPlotWindow(tk.Toplevel):
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
        self.after(180, self._compute_and_plot)

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
        stem = os.path.splitext(os.path.basename(str(source_file_value)))[0]
        # Order matters: longest / most-specific tails first
        _TAILS = (
            '_TH-488_Pooled_CytoFile',
            '_TH-488_Pooled',
            '_Pooled_CytoFile',
            '___Results', '___CytoFile',
            '__Results',  '__CytoFile',
            '_Results',   '_CytoFile',
        )
        for tail in _TAILS:
            if stem.endswith(tail):
                stem = stem[: -len(tail)]
                break
        return stem

    def _shorten_labels(self, raw_labels: list) -> list:
        """
        Strip the longest common underscore-delimited prefix so labels are
        as short as possible while still being unique.  No newlines, no
        truncation — staggered rendering handles visual separation.
        """
        if len(raw_labels) <= 1:
            return list(raw_labels)
        prefix = os.path.commonprefix(raw_labels)
        if '_' in prefix:
            prefix = prefix[:prefix.rfind('_') + 1]
        if len(prefix) > 4:
            return [lbl[len(prefix):] or lbl for lbl in raw_labels]
        return list(raw_labels)

    def _is_concat_mode(self) -> bool:
        """True if any active file has a Source_File column."""
        for p, v in self._file_vars.items():
            if not v.get():
                continue
            df = self.app.loaded_files.get(p)
            if df is not None and 'Source_File' in df.columns:
                return True
        return False

    def _get_samples(self) -> 'list[tuple[str, pd.DataFrame, str]]':
        """
        Return [(display_label, sub_df, color), ...] in current sort order.

        In concat mode: sub_df is the rows for that Source_File value.
        In file mode:   sub_df is the full per-file DataFrame.
        """
        active_paths = [p for p, v in self._file_vars.items() if v.get()]
        if not active_paths:
            return []

        concat_mode = self._is_concat_mode()

        if concat_mode:
            # Merge all active files into one frame, group by Source_File
            frames = []
            for p in sorted(active_paths):
                df = self.app.loaded_files.get(p)
                if df is not None:
                    frames.append(df)
            if not frames:
                return []
            combined = pd.concat(frames, ignore_index=True)
            if 'Source_File' not in combined.columns:
                return []

            raw_labels = [self._make_sample_label(sf)
                          for sf in combined['Source_File'].unique()]
            short_labels = self._shorten_labels(raw_labels)
            label_map = dict(zip(
                combined['Source_File'].unique(), short_labels))

            samples = []
            for fi, (sf, grp) in enumerate(combined.groupby('Source_File',
                                                              sort=True)):
                lbl   = label_map.get(sf, str(sf))
                color = self._SAMPLE_COLORS[fi % len(self._SAMPLE_COLORS)]
                samples.append((lbl, grp.reset_index(drop=True), color))
        else:
            raw_labels = [self._make_sample_label(p)
                          for p in sorted(active_paths)]
            short_labels = self._shorten_labels(raw_labels)
            samples = []
            for fi, p in enumerate(sorted(active_paths)):
                df    = self.app.loaded_files.get(p)
                if df is None:
                    continue
                lbl   = short_labels[fi]
                color = self.app.file_colors.get(
                    p, self._SAMPLE_COLORS[fi % len(self._SAMPLE_COLORS)])
                samples.append((lbl, df, color))

        if self._sample_order_var.get() == 'alpha':
            samples.sort(key=lambda t: t[0])

        return samples

    def _get_population_mask(self, df: pd.DataFrame) -> np.ndarray:
        """
        Boolean row-mask for the selected gate + region.
        Fresh computation — same pattern as PolarAnalysisWindow.
        """
        n    = len(df)
        name = self._gate_var.get()
        if name == 'All cells':
            return np.ones(n, bool)
        gate = next((g for g in self.app.gates
                     if g['name'] == name and g.get('applied')), None)
        if gate is None:
            return np.ones(n, bool)
        xch = self.app.x_channel
        ych = self.app.y_channel
        if (not xch or not ych
                or xch not in df.columns or ych not in df.columns):
            return np.ones(n, bool)
        xa = df[xch].to_numpy(dtype=float, copy=False)
        ya = df[ych].to_numpy(dtype=float, copy=False)
        try:
            regions, _ = self.app._gate_mask_for(gate, xa, ya)
        except Exception:
            return np.ones(n, bool)
        region_sel = self._region_var.get()
        if region_sel == 'All regions':
            combined = np.zeros(n, bool)
            for rname, mask in regions.items():
                if gate.get('type', 'crosshair') != 'crosshair' \
                        and rname == 'OUT':
                    continue
                combined |= mask
            return combined
        return regions.get(region_sel, np.ones(n, bool))

    def _get_region_pcts_and_n(self, df: pd.DataFrame) -> 'dict[str, tuple]':
        """
        Return {region_name: (pct, n_total)} for the selected gate on one
        sample's DataFrame.  n_total is the total cell count for that sample
        and is needed to compute the per-sample binomial SEM.
        Returns {} if no gate is selected or gate cannot be applied.
        """
        name = self._gate_var.get()
        if name == 'All cells':
            return {}
        gate = next((g for g in self.app.gates
                     if g['name'] == name and g.get('applied')), None)
        if gate is None:
            return {}
        xch = self.app.x_channel
        ych = self.app.y_channel
        if (not xch or not ych
                or xch not in df.columns or ych not in df.columns):
            return {}
        xa    = df[xch].to_numpy(dtype=float, copy=False)
        ya    = df[ych].to_numpy(dtype=float, copy=False)
        total = len(xa)
        if total == 0:
            return {}
        try:
            regions, _ = self.app._gate_mask_for(gate, xa, ya)
        except Exception:
            return {}
        return {rname: (float(mask.sum()) / total * 100.0, total)
                for rname, mask in regions.items()}

    def _get_region_pcts(self, df: pd.DataFrame) -> 'dict[str, float]':
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
            var = tk.BooleanVar(value=self.app.file_vars.get(
                path, tk.BooleanVar(value=True)).get())
            self._file_vars[path] = var
            color = self.app.file_colors.get(
                path, FILE_COLORS[fi % len(FILE_COLORS)])
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
        applied = [g for g in self.app.gates if g.get('applied')]
        gate_names = ['All cells'] + [g['name'] for g in applied]
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
            preferred = next(
                (c for c in cols if 'distance' in c.lower() or 'dist' in c.lower()),
                next((c for c in cols if 'intensity' in c.lower()),
                     cols[0] if cols else ''))
            self._dist_col_var.set(preferred)

    def _numeric_columns(self) -> list:
        """Return all numeric columns common to all active files.
        Only exclude columns that are pure row indices (named 'label' or
        'index'). All intensity, distance, coordinate and background columns
        are included so the user can choose freely."""
        dfs = [self.app.loaded_files[p] for p, v in self._file_vars.items()
               if v.get() and p in self.app.loaded_files]
        if not dfs:
            dfs = list(self.app.loaded_files.values())
        sets = [set(df.select_dtypes(include='number').columns) for df in dfs]
        common = sorted(set.intersection(*sets)) if sets else []
        # Only skip pure integer-index columns named 'label' / 'index'
        return [c for c in common if c.lower() not in ('label', 'index')]

    def _on_gate_changed(self, event=None):
        name = self._gate_var.get()
        if name == 'All cells':
            self._region_combo['values'] = ['All regions']
            self._region_var.set('All regions')
            self._schedule_replot()
            return
        gate = next((g for g in self.app.gates
                     if g['name'] == name and g.get('applied')), None)
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
        hit = next((c for c in cols if 'intensity' in c.lower()), None)
        if hit:
            self._dist_col_var.set(hit)
            self._schedule_replot()

    def _auto_distance(self):
        cols = self._dist_combo['values']
        hit = next((c for c in cols
                    if 'distance' in c.lower() or 'dist' in c.lower()), None)
        if hit:
            self._dist_col_var.set(hit)
            self._schedule_replot()

    # ── compute ───────────────────────────────────────────────────────────────

    def _compute_and_plot(self):
        self._populate_dropdowns()
        samples = self._get_samples()
        if not samples:
            self._status_var.set("No data — check file selection.")
            return

        dist_col     = self._dist_col_var.get()
        gate_name    = self._gate_var.get()
        region_sel   = self._region_var.get()
        gate         = next((g for g in self.app.gates
                             if g['name'] == gate_name and g.get('applied')), None)
        xch          = self.app.x_channel
        ych          = self.app.y_channel

        self._dist_cache     = {}
        self._pop_cache      = {}
        self._pop_sem_cache  = {}

        for lbl, df, color in samples:
            n_total = len(df)

            # ── Single _gate_mask_for call per sample ─────────────────────
            regions: dict = {}
            if (gate is not None and gate_name != 'All cells'
                    and xch and ych
                    and xch in df.columns and ych in df.columns):
                xa = df[xch].to_numpy(dtype=float, copy=False)
                ya = df[ych].to_numpy(dtype=float, copy=False)
                try:
                    regions, _ = self.app._gate_mask_for(gate, xa, ya)
                except Exception:
                    regions = {}

            # ── Population mask for distribution filtering ────────────────
            if not regions:
                pop_mask = np.ones(n_total, bool)
            elif region_sel == 'All regions':
                pop_mask = np.zeros(n_total, bool)
                for rname, mask in regions.items():
                    if gate.get('type', 'crosshair') != 'crosshair' and rname == 'OUT':
                        continue
                    pop_mask |= mask
            else:
                pop_mask = regions.get(region_sel, np.ones(n_total, bool))

            # ── Distribution values ───────────────────────────────────────
            if dist_col and dist_col in df.columns:
                vals = df[dist_col].to_numpy(dtype=float, copy=False)[pop_mask]
                vals = vals[np.isfinite(vals)]
            else:
                vals = np.array([])
            self._dist_cache[lbl] = (vals, color)

            # ── Population percentages + binomial SEM ─────────────────────
            if regions and n_total > 0:
                pct_map = {rname: float(mask.sum()) / n_total * 100.0
                           for rname, mask in regions.items()}
                self._pop_cache[lbl] = pct_map
                for rname, pct in pct_map.items():
                    p = pct / 100.0
                    self._pop_sem_cache[(lbl, rname)] = float(
                        np.sqrt(p * (1.0 - p) / n_total) * 100.0)
            else:
                self._pop_cache[lbl] = {}

        self._sample_labels = [lbl for lbl, _, _ in samples]

        self._render_figure()
        self._update_stats()

        mode = 'concat-mode' if self._is_concat_mode() else 'file-mode'
        self._status_var.set(
            f"{len(samples)} sample(s)  ·  {mode}  ·  gate: {gate_name}"
            + (f"  ·  col: {dist_col}" if dist_col else ""))

    # ── render ────────────────────────────────────────────────────────────────

    def _render_figure(self):
        T     = self.T
        labels = self._sample_labels
        if not labels:
            return

        # Resize figure using zoom factors
        n_samples     = len(labels)
        zoom_x        = getattr(self, '_zoom_x', tk.DoubleVar(value=1.0)).get()
        zoom_y        = getattr(self, '_zoom_y', tk.DoubleVar(value=1.0)).get()
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
            for sp in ax.spines.values():
                sp.set_color(T['spine'])
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
                col_bar = REGION_COLORS[ri % len(REGION_COLORS)]
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
            ax_bar.set_title(f'Gate Population % — Per Sample  [{gate_lbl}]',
                              color=T['fg'], fontsize=9)

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

        def _f(v):
            if not np.isfinite(v):
                return '—'
            if abs(v) >= 1e6:
                return f'{v:.3e}'
            if abs(v) >= 100:
                return f'{v:,.1f}'
            return f'{v:.3f}'

        for lbl in self._sample_labels:
            vals, _ = self._dist_cache.get(lbl, (np.array([]), None))
            n = len(vals)
            if n == 0:
                med = mean = iqr = float('nan')
            else:
                med        = float(np.median(vals))
                mean       = float(np.mean(vals))
                q25, q75   = np.percentile(vals, [25, 75])
                iqr        = float(q75 - q25)
            short = (lbl[:24] + '…') if len(lbl) > 25 else lbl
            self._stats_tree.insert(
                '', 'end', text=f'  {short}',
                values=(f'{n:,}', _f(med), _f(mean), _f(iqr)))

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
            self._fig.savefig(path, dpi=300, bbox_inches='tight',
                              facecolor=self._fig.get_facecolor())
            messagebox.showinfo("Saved", f"Figure saved:\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("Save Error", str(e), parent=self)

    def _export_stats(self):
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
            n    = len(vals)
            if n:
                _q5, _q25, _q75, _q95 = np.percentile(vals, [5, 25, 75, 95])
            base = {
                'Sample':  lbl,
                'Col':     self._dist_col_var.get(),
                'Gate':    self._gate_var.get(),
                'Region':  self._region_var.get(),
                'N':       n,
                'Mean':    round(float(np.mean(vals)),        4) if n else '',
                'Median':  round(float(np.median(vals)),      4) if n else '',
                'Std':     round(float(np.std(vals, ddof=1)), 4) if n > 1 else '',
                'IQR':     round(float(_q75 - _q25),          4) if n else '',
                'p5':      round(float(_q5),                  4) if n else '',
                'p95':     round(float(_q95),                 4) if n else '',
            }
            pops = self._pop_cache.get(lbl, {})
            for rname, pct in pops.items():
                safe = rname.replace('/', '_').replace(' ', '_')
                base[f'Pop_{safe}_pct'] = round(pct, 3)
            rows.append(base)
        try:
            pd.DataFrame(rows).to_csv(path, index=False)
            messagebox.showinfo("Export",
                f"Stats saved ({len(rows)} rows):\n{path}", parent=self)
        except Exception as e:
            messagebox.showerror("Export", str(e), parent=self)



# ─────────────────────────────────────────────────────────────────────────────
#  Tab manager
# ─────────────────────────────────────────────────────────────────────────────

class FlowTabManager:
    """
    Owns a ttk.Notebook.  Each tab is a full, independent FlowApp instance.

    Sub-gate workflow
    ─────────────────
    1. User applies a gate in any tab.
    2. User double-clicks a region label on the plot (gate mode must be OFF).
    3. FlowApp calls self.manager.open_subgate_tab(…).
    4. Manager creates a new Notebook tab pre-loaded with the filtered cells.
    5. The new tab is a complete FlowApp — it can have its own gate type,
       auto-gate, axes selection, stats, and export.
    6. Right-click a sub-gate tab header → Close Tab (Main tab is permanent).
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("vFlow 4.0.12")
        root.geometry("1500x960")

        self._theme_name = 'dark'
        self.T = THEMES['dark']
        _apply_ttk_style(self.T)
        root.configure(bg=self.T['sidebar_bg'])

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self._apps: list = []  # list of FlowApp instances, in tab order

        # Create the permanent Main tab
        self._new_tab(title=' ✦ Main ', parent_label=None,
                      filtered_data=None, default_x=None, default_y=None)

        # Right-click tab header → Close Tab menu
        self.notebook.bind('<Button-3>', self._on_tab_rclick)

    # ── Tab lifecycle ─────────────────────────────────────────────────────────

    def _new_tab(self, title, parent_label, filtered_data,
                 default_x, default_y,
                 parent_gate=None, parent_region=None, excluded_files=None):
        frame = ttk.Frame(self.notebook, style='TFrame')
        self.notebook.add(frame, text=title)

        # Sub-gate tabs get a thin header bar with a close ✕ button
        if parent_label is not None:
            hdr = tk.Frame(frame, bg=self.T['header_bg'], height=24)
            hdr.pack(fill=tk.X, side=tk.TOP)
            hdr.pack_propagate(False)
            def _close_this():
                idx = self.notebook.index(frame)
                self._close_tab(idx)

            tk.Label(hdr, text=f'  ↳ {parent_label}',
                     bg=self.T['header_bg'], fg=self.T['fg'],
                     font=('Arial', 8)).pack(side=tk.LEFT, padx=4)
            close_btn = tk.Button(
                hdr, text=' ✕ ', command=_close_this,
                bg=self.T['header_bg'], fg=self.T['fg_dim'],
                activebackground='#c33', activeforeground='white',
                relief='flat', font=('Arial', 9, 'bold'), bd=0, padx=4)
            close_btn.pack(side=tk.RIGHT, padx=4)
            inner = ttk.Frame(frame, style='TFrame')
            inner.pack(fill=tk.BOTH, expand=True)
        else:
            inner = frame

        app = FlowApp(self.root, container=inner,
                      parent_label=parent_label, manager=self)
        if filtered_data:
            self._load_filtered(app, filtered_data, default_x, default_y,
                                parent_gate=parent_gate,
                                parent_region=parent_region,
                                excluded_files=excluded_files or {})
        self._apps.append(app)
        self.notebook.select(frame)
        return app

    @staticmethod
    def _load_filtered(app, filtered_data, default_x, default_y,
                       parent_gate=None, parent_region=None, excluded_files=None):
        """Pre-load filtered DataFrames into a FlowApp and select axes.

        Sub-gate tabs contain only the cells that passed the parent gate,
        so there is no meaningful data outside that cluster.  We enable
        fit_axes_var so every render (including after placing a new gate)
        automatically zooms to the data range instead of showing the full
        scale which would leave the population as a tiny speck in one corner.
        The user can still uncheck 'Fit axes to data' in the sidebar.

        parent_gate / parent_region are stored on the app so that
        batch_export_stats can re-apply the parent filter to each raw file
        before computing sub-gate statistics.

        excluded_files is a snapshot of the parent's exclusion dict;
        it is copied into the child so batch_export_stats excludes the same
        files as the parent analysis did.
        """
        # Propagate parent-gate context for batch stats
        app.parent_gate   = parent_gate    # gate dict (or None for main tab)
        app.parent_region = parent_region  # region name (or None)

        # Inherit exclusion list from parent tab
        if excluded_files:
            app.excluded_files = dict(excluded_files)
            # Refresh the EXCLUDED FILES panel so it shows the inherited list
            # instead of the default "(none)" label.
            app._rebuild_excluded_list()

        for path, df in filtered_data.items():
            if path in app.loaded_files:
                continue
            cidx = len(app.loaded_files)
            app.loaded_files[path] = df
            app.file_colors[path]  = FILE_COLORS[cidx % len(FILE_COLORS)]
            app._add_file_row(path)

        if not app.loaded_files:
            return
        sample = next(iter(app.loaded_files.values()))
        cols   = list(sample.columns)
        app.x_menu['values'] = cols
        app.y_menu['values'] = cols

        if default_x and default_x in cols:
            app.x_var.set(default_x); app.x_channel = default_x
        elif cols:
            app.x_var.set(cols[0]);   app.x_channel = cols[0]

        if default_y and default_y in cols:
            app.y_var.set(default_y); app.y_channel = default_y
        elif len(cols) > 1:
            app.y_var.set(cols[1]);   app.y_channel = cols[1]

        # Sub-gate tabs: always fit the view to the actual data range.
        # The parent gate filtered out everything outside the selection,
        # so showing the full instrument scale would be misleading.
        app.fit_axes_var.set(True)

        app.refresh_plot()

    def open_subgate_tab(self, label: str, filtered_data: dict,
                         parent_x: str, parent_y: str, total_cells: int,
                         parent_gate: dict = None, parent_region: str = None,
                         excluded_files: dict = None):
        """Called by a FlowApp when the user double-clicks a gated region."""
        short     = label[:22]
        tab_title = f' ↳ {short}  ({total_cells:,}) '
        self._new_tab(title=tab_title, parent_label=label,
                      filtered_data=filtered_data,
                      default_x=parent_x, default_y=parent_y,
                      parent_gate=parent_gate, parent_region=parent_region,
                      excluded_files=excluded_files or {})

    # ── Tab closure ───────────────────────────────────────────────────────────

    def _on_tab_rclick(self, event):
        try:
            idx = self.notebook.index(f'@{event.x},{event.y}')
        except tk.TclError:
            return
        if idx == 0:
            return  # Main tab is permanent
        menu  = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f'✕  Close tab', command=lambda i=idx: self._close_tab(i))
        menu.tk_popup(event.x_root, event.y_root)

    def _close_tab(self, idx: int):
        """Close sub-gate tab by notebook index. Maintains _apps list integrity."""
        tabs = self.notebook.tabs()
        if idx <= 0 or idx >= len(tabs):
            return  # Main tab (idx=0) is permanent
        # Remove from _apps using the same index (Main is _apps[0])
        if 0 < idx < len(self._apps):
            self._apps.pop(idx)
        # Remove from notebook last so index is still valid above
        self.notebook.forget(tabs[idx])


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Heavy imports above already advanced the splash through 5 steps.
    # Two final steps for the UI build, then finish and launch.
    if _splash:
        try:
            _splash.step("vFlow UI")
            _splash.step("ready")
            _splash.finish()
        except Exception:
            pass

    # ── Main application ──────────────────────────────────────────────────────
    root = tk.Tk()
    mgr  = FlowTabManager(root)

    def _on_close():
        try:
            import matplotlib.pyplot as _plt
            _plt.close('all')
        except Exception:
            pass
        root.quit()
        root.destroy()
        sys.exit(0)

    root.protocol('WM_DELETE_WINDOW', _on_close)
    root.mainloop()
    sys.exit(0)