#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlowJo-like Flow Cytometry Visualization Tool - v3.9.4
@author: vincentpb

Changelog v3.9.3 → v3.9.4
──────────────────────────
BUG FIX — Stats panel empty + gate coloring not applied after drawing a gate

  Root cause: _gate_sig() had two bugs introduced with the persistent
  gate-mask cache (_gmc) in v3.9.2:

  BUG A — TypeError crash (primary cause of empty stats & blank plot):
    _gate_sig read  gate.get('y_boundaries', [])  then called tuple() on the
    result.  For every manually drawn crosshair gate, 'y_boundaries' is
    initialised to None in _add_gate() — so .get() returns None (the stored
    value, not the [] default), and tuple(None) raises TypeError.
    That exception propagated silently through tkinter's event loop, aborting
    _finish_gate() immediately after _compute_gate_stats_for() — before
    _rebuild_gate_manager(), refresh_plot(), and _update_stats_display()
    could run.  The stats panel stayed empty and cell coloring was never
    applied after gate placement.

  BUG B — Wrong cache-key keys (stale mask after threshold toggle):
    _gate_sig read 'x_thresh_active', 'y_thresh_active', 'y_thresh_actives'
    — the serialised JSON key names used in save/load.  Live gate dicts
    store toggle state in BooleanVar objects under 'x_thresh_vars',
    'y_thresh_var', 'y_thresh_vars'.  Because those keys are absent in live
    dicts, the defaults ([] / True / []) were always returned, so the hash
    never changed when the user toggled a threshold checkbox.  The _gmc
    cache returned the stale mask (wrong threshold state) and stats/colors
    did not update.

  Fix: _gate_sig now reads BooleanVar.get() values for live gates and falls
  back to plain bool values for loaded/serialised gates.  All tuple() calls
  are guarded against None inputs with `or []`.

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
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

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

import copy
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde
from scipy.signal import savgol_filter
from scipy.interpolate import RegularGridInterpolator

try:
    from sklearn.mixture import GaussianMixture
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

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
    """Convert a '#rrggbb' hex string to a (4,) float32 RGBA array."""
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return np.array([r, g, b, float(alpha)], dtype=np.float32)


def _gate_sig(gate: dict) -> int:
    """
    Return a stable integer hash of the gate's geometric parameters.
    Changes whenever thresholds, vertices, or active-flags change.
    Used as part of the persistent gate-mask cache key so stale entries
    are naturally bypassed without explicit invalidation.

    BUG FIXED (v3.9.3 → v3.9.4):
    The original implementation read  gate.get('x_thresh_active', []),
    gate.get('y_thresh_active', True) and gate.get('y_thresh_actives', []).
    Those keys are the *serialised* names used in save/load JSON.  Live gate
    dicts store threshold toggle state in BooleanVar objects under the keys
    x_thresh_vars, y_thresh_var and y_thresh_vars — meaning the toggle state
    was NEVER included in the cache key.

    Two consequences:
      1. tuple(gate.get('y_boundaries', [])) crashed with TypeError when
         y_boundaries=None (its initial value for every manually-drawn
         crosshair gate), because the key exists in the dict with value None
         so .get() returns None rather than the [] default.  That TypeError
         silently aborted _finish_gate() at _compute_gate_stats_for(), so
         the stats panel stayed empty, the plot was never refreshed after gate
         placement, and the gate-manager row was never rebuilt.
      2. Toggling a threshold checkbox left the stale cached mask in _gmc
         (same hash) so stats and cell colours did not update.

    The fix reads BooleanVar values when present (live gate) and falls back
    to plain bool values for loaded/serialised gates.  It also guards every
    tuple() call against None values.
    """
    gt = gate.get('type', 'crosshair')
    if gt == 'crosshair':
        # ── X threshold active-state ──────────────────────────────────────
        x_tvs = gate.get('x_thresh_vars') or []
        if x_tvs:
            # Live gate: BooleanVar objects
            try:
                x_ta = tuple(bool(v.get()) for v in x_tvs)
            except AttributeError:
                x_ta = tuple(bool(v) for v in x_tvs)
        else:
            # Loaded/serialised gate: plain bool list
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
        rng = np.random.default_rng(42)
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
        data = data[np.random.default_rng(7).choice(len(data), _KDE_MAX, replace=False)]

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


def all_kde_valleys(data: np.ndarray,
                    min_peak_fraction: float = 0.05,
                    min_prominence: float = 4.0,
                    bw_factor: float = 1.0,
                    min_peak_frac: float = 0.01) -> list:
    """
    Find ALL significant KDE valleys in a 1D distribution.

    Used by the Multi-Valley Crosshair auto-gate to place thresholds at
    every real gap between population peaks on a given axis.

    Parameters
    ----------
    data              : 1D array in transform (display) space
    min_peak_fraction : a peak must be at least this fraction of the
                        global maximum to count (filters tiny noise humps)
    min_prominence    : both flanking peaks must be ≥ this × valley depth
                        (filters shoulders, not true gaps)

    Returns
    -------
    Sorted list of threshold values (may be empty for unimodal distributions).
    """
    data = data[np.isfinite(data)]
    if len(data) < 10:
        return []

    # Subsample for speed — KDE valley positions are stable above ~10k points
    _KDE_MAX = 30_000
    if len(data) > _KDE_MAX:
        data = data[np.random.default_rng(7).choice(len(data), _KDE_MAX, replace=False)]

    kde = gaussian_kde(data, bw_method='scott')
    if bw_factor != 1.0:
        kde.set_bandwidth(bw_method=kde.factor * bw_factor)
    x   = np.linspace(data.min(), data.max(), 2048)
    y   = kde(x)
    win = min(51, max(5, (len(y) // 10) | 1))
    y_s = savgol_filter(y, window_length=win, polyorder=3)
    dy  = np.gradient(y_s, x)
    peak_val = float(np.max(y_s))

    peak_idx   = np.where(np.diff(np.sign(dy)) < 0)[0]
    valley_idx = np.where(np.diff(np.sign(dy)) > 0)[0]

    # Filter peaks that are too small (noise) — controlled by min_peak_frac
    sig_peaks = peak_idx[y_s[peak_idx] >= min_peak_frac * peak_val]

    thresholds = []
    for vi in valley_idx:
        left_peaks  = sig_peaks[sig_peaks < vi]
        right_peaks = sig_peaks[sig_peaks > vi]
        if len(left_peaks) == 0 or len(right_peaks) == 0:
            continue
        vdepth = max(float(y_s[vi]), 1e-12)
        lbest  = float(y_s[left_peaks [np.argmax(y_s[left_peaks ])]])
        rbest  = float(y_s[right_peaks[np.argmax(y_s[right_peaks])]])
        if lbest >= min_prominence * vdepth and rbest >= min_prominence * vdepth:
            thresholds.append(float(x[vi]))

    return sorted(thresholds)


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
        self._folder            = tk.StringVar()
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
        d = filedialog.askdirectory(parent=self, title="Select root folder")
        if not d:
            return
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
        d = filedialog.askdirectory(parent=self, title="Select root folder")
        if d:
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
    Polar / Vector Analysis window  (v3.9.3 simplified design)

    Shows ONE polar axes per "Compute & Plot" call.
    When multiple files are active, each file's rose histogram is overlaid on
    the same axes using FILE_COLORS — mirroring the behaviour of the main
    scatter plot.

    The axes is rendered without rasterization so that PDF / SVG exports are
    true vector graphics.

    What is displayed
    -----------------
    • A polar rose histogram (bar chart of angles) for each file / population.
    • A mean-direction arrow when MRL ≥ mrl_threshold.
    • A per-file statistics annotation (n, MRL, Rayleigh p).

    Sidebar controls
    ----------------
    POPULATION  : gate selector + region selector
    CHANNEL MAP : X Ch1, Y Ch1, X Ch2, Y Ch2 centroid column combos
    SETTINGS    : histogram bins, bar alpha, MRL threshold (for arrow)
    ACTIONS     : Compute & Plot, Export figure, Export stats CSV
    """

    # ── construction ─────────────────────────────────────────────────────────

    def __init__(self, parent_root, T: dict, app: 'FlowApp'):
        super().__init__(parent_root)
        self.T   = T
        self.app = app
        self.title("Vector / Polar Analysis")
        self.geometry("1000x720")
        self.configure(bg=T['sidebar_bg'])
        self.resizable(True, True)

        # ── tk variables ─────────────────────────────────────────────────
        self._mrl_thresh_var = tk.StringVar(value='0.3')
        self._n_bins_var     = tk.StringVar(value='36')
        self._alpha_var      = tk.StringVar(value='0.55')

        self._cx1_var = tk.StringVar()
        self._cy1_var = tk.StringVar()
        self._cx2_var = tk.StringVar()
        self._cy2_var = tk.StringVar()

        self._gate_var   = tk.StringVar(value='All cells')
        self._region_var = tk.StringVar(value='All regions')

        self._build_ui()
        self._auto_detect_channels()
        self._populate_gate_dropdown()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        T = self.T

        # ── Scrollable sidebar ────────────────────────────────────────────
        sb_outer = tk.Frame(self, bg=T['sidebar_bg'], width=260)
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
                                       anchor='nw', width=244)
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

        # ── CHANNEL MAPPING ───────────────────────────────────────────────
        _sec("CHANNEL MAPPING")
        cols = self._get_columns()
        _lbl("X  Ch1 (centroid):")
        self._cx1_combo = _combo(self._cx1_var, cols)
        _lbl("Y  Ch1 (centroid):")
        self._cy1_combo = _combo(self._cy1_var, cols)
        _lbl("X  Ch2 (centroid):")
        self._cx2_combo = _combo(self._cx2_var, cols)
        _lbl("Y  Ch2 (centroid):")
        self._cy2_combo = _combo(self._cy2_var, cols)
        _btn("⟳  Auto-detect columns", self._auto_detect_channels, 'Gray.TButton')

        # ── SETTINGS ──────────────────────────────────────────────────────
        _sec("SETTINGS")
        _lbl("Histogram bins (rose):")
        _entry(self._n_bins_var)
        _lbl("Bar alpha (0–1):")
        _entry(self._alpha_var)
        _lbl("MRL threshold for arrow:")
        _entry(self._mrl_thresh_var)
        ttk.Label(p,
            text="  Arrow drawn when MRL ≥ threshold",
            style='Dim.TLabel').pack(anchor='w', padx=8, pady=(0, 6))

        # ── ACTIONS ───────────────────────────────────────────────────────
        _sec("ACTIONS")
        _btn("🔄  Compute & Plot",     self._compute_and_plot, 'Accent.TButton')
        _btn("💾  Export figure",      self._export_current,   'Green.TButton')
        _btn("📋  Export stats → CSV", self._export_stats,     'Blue2.TButton')

        ttk.Frame(p, style='TFrame', height=20).pack()

        # ── Plot area ─────────────────────────────────────────────────────
        self._plot_frame = tk.Frame(self, bg=T['plot_bg'])
        self._plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._fig = Figure(figsize=(8.5, 7), facecolor=T['fig_bg'])
        self._canvas = FigureCanvasTkAgg(self._fig, master=self._plot_frame)
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        tf = tk.Frame(self._plot_frame, bg=T['sidebar_bg'])
        tf.pack(fill=tk.X)
        tb = NavigationToolbar2Tk(self._canvas, tf)
        tb.config(background=T['sidebar_bg'])
        tb.update()

        self._status_var = tk.StringVar(
            value="Select coordinate columns, then press  🔄 Compute & Plot")
        tk.Label(self._plot_frame, textvariable=self._status_var,
                 bg=T['header_bg'], fg=T['fg_dim'],
                 anchor='w', font=('Arial', 8), padx=6
                 ).pack(side=tk.BOTTOM, fill=tk.X)

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
        Prefers columns matching X_{ch}_microns / Y_{ch}_microns (vSynApp).
        Falls back to any X_*/Y_* prefix or centroid_x/centroid_y naming.
        Clears StringVars first so stale values from a previous session
        do not survive when detection finds nothing.
        """
        cols = self._get_columns()

        # Update combo lists before setting vars (avoids readonly-combo glitch)
        for cb in (self._cx1_combo, self._cy1_combo,
                   self._cx2_combo, self._cy2_combo):
            cb['values'] = cols

        # Clear stale values
        for v in (self._cx1_var, self._cy1_var, self._cx2_var, self._cy2_var):
            v.set('')

        # Build candidate lists (case-insensitive)
        x_cols = [c for c in cols
                  if c.lower().startswith('x_') or 'centroid_x' in c.lower()
                  or ('centroid' in c.lower() and 'x' in c.lower().split('_'))]
        y_cols = [c for c in cols
                  if c.lower().startswith('y_') or 'centroid_y' in c.lower()
                  or ('centroid' in c.lower() and 'y' in c.lower().split('_'))]

        # Deduplicate while preserving order
        seen = set(); x_cols_u = []
        for c in x_cols:
            if c not in seen: seen.add(c); x_cols_u.append(c)
        seen = set(); y_cols_u = []
        for c in y_cols:
            if c not in seen: seen.add(c); y_cols_u.append(c)
        x_cols, y_cols = x_cols_u, y_cols_u

        # Prefer columns containing 'microns' (vSynApp convention)
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
            return
        gate = next((g for g in self.app.gates
                     if g['name'] == name and g.get('applied')), None)
        if gate is None:
            return
        xch = self.app.x_channel
        ych = self.app.y_channel
        if not xch or not ych:
            self._region_combo['values'] = ['All regions']
            self._region_var.set('All regions')
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

    # ── data retrieval ────────────────────────────────────────────────────────

    def _get_population_mask(self, df: pd.DataFrame, path: str) -> np.ndarray:
        """
        Boolean row-mask for the selected gate + region (all-True if none).

        Important: does NOT pass _cache_path to _gate_mask_for.
        The gate-mask cache is keyed to the full-file DataFrame.  Here the df
        may be a filtered subset (sub-gate tab), so we always compute fresh to
        avoid wrong-length mask errors that would silently fall back to
        'all cells'.
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
        xa = df[xch].values.astype(float)
        ya = df[ych].values.astype(float)
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

    def _get_vectors_for_df(self, df: pd.DataFrame,
                            mask: np.ndarray):
        """
        Return (angles_rad, magnitudes) for gated rows, or (None, None).
        Uses the four centroid column variables set in the sidebar.
        """
        cx1 = self._cx1_var.get(); cy1 = self._cy1_var.get()
        cx2 = self._cx2_var.get(); cy2 = self._cy2_var.get()
        for col in (cx1, cy1, cx2, cy2):
            if not col or col not in df.columns:
                return None, None
        sub = df[mask]
        if len(sub) == 0:
            return np.array([]), np.array([])
        dx = sub[cx2].values.astype(float) - sub[cx1].values.astype(float)
        dy = sub[cy2].values.astype(float) - sub[cy1].values.astype(float)
        return np.arctan2(dy, dx), np.sqrt(dx**2 + dy**2)

    # ── circular statistics ───────────────────────────────────────────────────

    @staticmethod
    def _mrl(angles: np.ndarray) -> float:
        """Mean Resultant Length — circular analogue of mean absolute deviation."""
        n = len(angles)
        if n == 0:
            return 0.0
        return float(np.sqrt(np.sum(np.cos(angles))**2 +
                              np.sum(np.sin(angles))**2) / n)

    @staticmethod
    def _mean_dir(angles: np.ndarray) -> float:
        """Circular mean direction in radians."""
        return float(np.arctan2(np.mean(np.sin(angles)),
                                 np.mean(np.cos(angles))))

    @staticmethod
    def _rayleigh_p(angles: np.ndarray) -> float:
        """
        Rayleigh test p-value.
        Uses the standard approximation  p ≈ exp(-n · R̄²).
        Returns 1.0 for n < 2.
        """
        n = len(angles)
        if n < 2:
            return 1.0
        R_bar = PolarAnalysisWindow._mrl(angles)
        return float(np.clip(np.exp(-n * R_bar**2), 0.0, 1.0))

    # ── plotting ──────────────────────────────────────────────────────────────

    def _compute_and_plot(self):
        """
        Read parameters, gather per-file vector data, render the polar figure.

        One polar axes is produced.  Every active file (filtered by the chosen
        gate / region) is drawn as a semi-transparent rose histogram using the
        same FILE_COLORS palette as the main scatter plot.  The mean-direction
        arrow and per-file statistics are overlaid.
        All artists are left non-rasterized so PDF / SVG exports are
        true vector graphics.
        """
        # ── Parse parameters ──────────────────────────────────────────────
        try:
            mrl_thresh = float(self._mrl_thresh_var.get())
            n_bins     = max(4, int(self._n_bins_var.get()))
            bar_alpha  = float(np.clip(float(self._alpha_var.get()), 0.05, 1.0))
        except ValueError:
            messagebox.showerror("Polar Analysis",
                "Invalid parameter value(s).", parent=self)
            return

        # ── Validate column selection ─────────────────────────────────────
        if not all([self._cx1_var.get(), self._cy1_var.get(),
                    self._cx2_var.get(), self._cy2_var.get()]):
            messagebox.showerror("Polar Analysis",
                "Please select all four coordinate columns.", parent=self)
            return

        active = self.app._active()
        if not active:
            messagebox.showwarning("Polar Analysis",
                "No data loaded.", parent=self)
            return

        # ── Collect per-file data ─────────────────────────────────────────
        file_keys   = sorted(active.keys())
        datasets    = []   # list of (angles, mags, short_label, color)
        for fi, path in enumerate(file_keys):
            df    = active[path]
            mask  = self._get_population_mask(df, path)
            angles, mags = self._get_vectors_for_df(df, mask)
            if angles is None:
                continue
            color = FILE_COLORS[fi % len(FILE_COLORS)]
            label = os.path.basename(path)
            datasets.append((angles, mags, label, color))

        if not datasets or not any(len(a) > 0 for a, _, _, _ in datasets):
            messagebox.showwarning(
                "Polar Analysis",
                "No valid vector data found.\n"
                "Check that the coordinate columns exist and that the "
                "selected gate / region contains cells.",
                parent=self)
            return

        # ── Build figure ──────────────────────────────────────────────────
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

        # Normalise bar heights across all files so they are visually
        # comparable: each bar shows the fraction of vectors in that bin.
        stats_lines = []   # collected for the annotation text

        for angles, mags, label, color in datasets:
            if len(angles) == 0:
                continue

            counts, _ = np.histogram(angles, bins=bin_edges)
            # Normalise to fraction so multi-file overlay is comparable
            fracs = counts / len(angles)

            # Rose bars — non-rasterized (vector PDF)
            ax.bar(bin_centers, fracs,
                   width=bin_width, bottom=0.0,
                   color=color, alpha=bar_alpha,
                   edgecolor=T['spine'], linewidth=0.5,
                   label=f'{os.path.splitext(label)[0][:28]}  (n={len(angles):,})',
                   zorder=2)

            # Statistics
            mrl   = self._mrl(angles)
            p_val = self._rayleigh_p(angles)

            # Mean-direction arrow when MRL meets threshold
            if mrl >= mrl_thresh and fracs.max() > 0:
                mean_dir = self._mean_dir(angles)
                # Arrow length scaled to 80 % of the tallest bar
                arrow_r  = fracs.max() * 0.82
                ax.annotate(
                    '', xy=(mean_dir, arrow_r), xytext=(0, 0),
                    arrowprops=dict(arrowstyle='->', color=color,
                                    lw=2.0, shrinkA=0, shrinkB=0),
                    zorder=5)

            p_fmt = f'{p_val:.4f}' if p_val >= 0.0001 else '< 0.0001'
            sig   = '✓ sig.' if p_val < 0.05 else 'n.s.'
            short = os.path.splitext(label)[0]
            short = (short[:30] + '…') if len(short) > 31 else short
            stats_lines.append(
                f'{short}\n'
                f'  n={len(angles):,}   MRL={mrl:.3f}   p={p_fmt}   {sig}')

        # ── Statistics annotation ─────────────────────────────────────────
        if stats_lines:
            stats_txt = '\n'.join(stats_lines)
            ax.text(0.01, 0.01, stats_txt,
                    transform=ax.transAxes,
                    fontsize=7, ha='left', va='bottom',
                    color=T['fg'],
                    bbox=dict(boxstyle='round,pad=0.4',
                              facecolor=T['label_box'],
                              alpha=0.82, linewidth=0),
                    zorder=10)

        # ── Legend ────────────────────────────────────────────────────────
        if len(datasets) > 1 or datasets:
            ax.legend(fontsize=7, loc='upper right',
                      facecolor=T['legend_bg'], labelcolor=T['fg'],
                      framealpha=0.75)

        # ── Title ─────────────────────────────────────────────────────────
        gate_lbl   = self._gate_var.get()
        region_lbl = self._region_var.get()
        pop_info   = (f'{gate_lbl} / {region_lbl}'
                      if gate_lbl != 'All cells' else 'All cells')
        self._fig.suptitle(
            f'Vector directionality  —  {pop_info}',
            color=T['fg'], fontsize=10, y=1.01)

        self._fig.tight_layout()
        self._canvas.draw()

        # ── Status bar ────────────────────────────────────────────────────
        total_vecs = sum(len(a) for a, _, _, _ in datasets)
        self._status_var.set(
            f"{total_vecs:,} vectors  ·  {len(datasets)} file(s)  "
            f"·  population: {pop_info}  "
            f"·  bins: {n_bins}  ·  MRL-arrow threshold: {mrl_thresh}")

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
        Columns: File, Gate, Region, N_vectors, MRL, Rayleigh_p,
                 Mean_dir_deg, Significant, X_Ch1, Y_Ch1, X_Ch2, Y_Ch2
        """
        try:
            mrl_thresh = float(self._mrl_thresh_var.get())
        except ValueError:
            mrl_thresh = 0.3

        active = self.app._active()
        if not active:
            messagebox.showwarning("Export Stats",
                "No data loaded.", parent=self)
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
                    'N_vectors': 0, 'MRL': None, 'Rayleigh_p': None,
                    'Mean_dir_deg': None, 'Significant': None,
                    'X_Ch1': self._cx1_var.get(), 'Y_Ch1': self._cy1_var.get(),
                    'X_Ch2': self._cx2_var.get(), 'Y_Ch2': self._cy2_var.get(),
                })
                continue

            mrl      = self._mrl(angles)
            p_val    = self._rayleigh_p(angles)
            mean_dir = float(np.degrees(self._mean_dir(angles)))
            sig      = p_val < 0.05 and mrl >= mrl_thresh

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
            messagebox.showwarning("Export Stats",
                "No vector data found.", parent=self)
            return

        try:
            pd.DataFrame(rows).to_csv(path_out, index=False)
            messagebox.showinfo("Export Stats",
                f"Stats saved ({len(rows)} file(s)):\n{path_out}",
                parent=self)
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
            root.title("Flow Cytometry Tool v39")
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
        side_outer = ttk.Frame(C, style='TFrame', width=305)
        side_outer.pack(side=tk.LEFT, fill=tk.Y)
        side_outer.pack_propagate(False)

        self._side_canvas = tk.Canvas(side_outer, bg=T['sidebar_bg'],
                                       highlightthickness=0, width=303)
        vsb = ttk.Scrollbar(side_outer, orient='vertical',
                             command=self._side_canvas.yview)
        self._side_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._side_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.sidebar = ttk.Frame(self._side_canvas, style='TFrame')
        self._side_canvas.create_window(
            (0, 0), window=self.sidebar, anchor='nw', width=288)
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
        self.file_list_frame = ttk.Frame(p, style='TFrame')
        self.file_list_frame.pack(fill=tk.X, padx=8)

        # ── EXCLUDED FILES ──
        self._section("EXCLUDED FILES")
        self.excluded_list_frame = ttk.Frame(p, style='TFrame')
        self.excluded_list_frame.pack(fill=tk.X, padx=8)
        ttk.Label(self.excluded_list_frame, text="(none)", style='Dim.TLabel').pack(anchor='w')

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
        self._lbl("X Axis:")
        self.x_var = tk.StringVar()
        self.x_menu = ttk.Combobox(p, textvariable=self.x_var,
                                    state='readonly', font=('Arial', 8))
        self.x_menu.pack(fill=tk.X, padx=8, pady=(0, 4))
        self._lbl("Y Axis:")
        self.y_var = tk.StringVar()
        self.y_menu = ttk.Combobox(p, textvariable=self.y_var,
                                    state='readonly', font=('Arial', 8))
        self.y_menu.pack(fill=tk.X, padx=8, pady=(0, 4))
        self._btn("Apply Axes", self.apply_axes, 'Green.TButton')

        # ── SCALE ──
        self._section("SCALE")
        sf = ttk.Frame(p, style='TFrame')
        sf.pack(fill=tk.X, padx=8, pady=2)
        for row_i, (lbl_text, attr) in enumerate([("X:", 'x_scale_var'),
                                                   ("Y:", 'y_scale_var')]):
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
            style='Dim.TLabel').pack(anchor='w', padx=8, pady=(0, 4))

        # Auto-gate buttons
        self._btn("2D GMM  (joint X,Y space)",       self.auto_gate_2d_gmm,          'Indigo.TButton')
        self._btn("KDE Valley  (X + Y)",             self.auto_gate_derivative,      'Orange.TButton')
        self._btn("Multi-Valley Grid  (KDE X+Y)",    self.auto_gate_multi_valley,    'Cyan.TButton')
        self._btn("Otsu  (X + Y)",                   self.auto_gate_otsu,            'Teal.TButton')
        self._btn("Mixed  (GMM X + KDE Y)",          self.auto_gate_both,            'Brown.TButton')
        self._btn("Cluster Polygons  (HDBSCAN 2D)",   self.auto_gate_cluster_polygons,'Olive.TButton')
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
            text="  Requires X/Y centroid columns\n  for two channels in the data.",
            style='Dim.TLabel', justify='left'
        ).pack(anchor='w', padx=8, pady=(0, 4))
        self._btn("🧭 Polar / Vector Analysis…",
                  self.open_polar_analysis, 'Purple.TButton')

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
        paths = filedialog.askopenfilenames(
            title="Select CSV or FCS Files",
            filetypes=[("Flow data", "*.csv *.fcs *.FCS"),
                       ("CSV files", "*.csv"),
                       ("FCS files", "*.fcs *.FCS"),
                       ("All files", "*.*")])
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
                 ).pack(side=tk.LEFT, padx=(0, 4))
        # ✕ exclude button
        ttk.Button(row, text='✕', width=2,
                   command=lambda p=path: self._exclude_file(p),
                   style='Gray.TButton').pack(side=tk.RIGHT, padx=(2, 0))
        var  = tk.BooleanVar(value=True)
        self.file_vars[path] = var
        name = os.path.basename(path)
        disp = (name[:22] + '…') if len(name) > 23 else name
        ttk.Checkbutton(row, text=disp, variable=var,
                        command=self._on_active_files_changed,
                        style='TCheckbutton').pack(side=tk.LEFT)

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
        """Move a file from the excluded list back into the active list."""
        if path not in self.excluded_files:
            return
        self.loaded_files[path] = self.excluded_files.pop(path)
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
                       style='Green.TButton').pack(side=tk.LEFT, padx=(0, 4))
            name = os.path.basename(path)
            disp = (name[:22] + '…') if len(name) > 23 else name
            ttk.Label(row, text=disp,
                      style='Dim.TLabel').pack(side=tk.LEFT)

    def _active(self) -> dict:
        return {p: df for p, df in self.loaded_files.items()
                if self.file_vars[p].get()}

    def _display_files(self) -> dict:
        active = self._active()
        if self.view_mode_var.get() == 'cycle' and active:
            keys = list(active.keys())
            idx  = self.cycle_idx % len(keys)
            return {keys[idx]: active[keys[idx]]}
        return active

    def _update_cycle_label(self):
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
            self.x_var.set(cols[0]); self.y_var.set(cols[1])
            self.x_channel = cols[0]; self.y_channel = cols[1]

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
        self.x_channel, self.y_channel = x, y
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

    def _new_thresh_vars(self, n: int) -> list:
        """Create n fresh BooleanVar(True) for X thresholds."""
        return [tk.BooleanVar(value=True) for _ in range(n)]

    def _new_y_thresh_var(self) -> tk.BooleanVar:
        """Create a fresh BooleanVar(True) for the Y threshold."""
        return tk.BooleanVar(value=True)

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

        self._update_cycle_label()
        display = self._display_files()

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
        # Accumulators for "Fit axes to data" percentile computation
        _fit_x_all: list = []
        _fit_y_all: list = []

        for path, df in display.items():
            if self.x_channel not in df.columns or \
               self.y_channel not in df.columns: continue
            color  = self.file_colors[path]
            lbl    = os.path.basename(path)
            lbl_s  = (lbl[:28] + '…') if len(lbl) > 30 else lbl
            x_raw  = df[self.x_channel].values.astype(float)
            y_raw  = df[self.y_channel].values.astype(float)
            xt, yt, valid = self._transform_xy_cached(path, x_raw, y_raw)
            n_cells = int(valid.sum())
            total_cells += n_cells
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
                self._plot_marginals(x_raw, y_raw, xt, yt, valid, color)

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
            f"Shown: {len(display)}/{len(self._active())} files  │  "
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
            idx = np.random.default_rng(2).choice(n, RENDER_CAP, replace=False)
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
            idx  = np.random.default_rng(0).choice(n, KDE_SUBSAMPLE, replace=False)
            kern = gaussian_kde(np.vstack([xc[idx], yc[idx]]))
        else:
            kern = gaussian_kde(np.vstack([xc, yc]))

        # ── Evaluate on a 128×128 grid (fast) then interpolate per-cell ──
        # This replaces kern(all_points) which is O(n×k) → now O(grid + n·log·grid)
        GRID = 128
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
            rng  = np.random.default_rng(3)
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
            idx  = np.random.default_rng(0).choice(n, KDE_SUBSAMPLE, replace=False)
            kern = gaussian_kde(np.vstack([xv[idx], yv[idx]]))
        else:
            kern = gaussian_kde(np.vstack([xv, yv]))

        # Grid evaluation for contour surface (fast; no per-point KDE call)
        GRID = 128
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
                             colors=[color], linewidths=1.8)
        self.ax.clabel(c, fmt={lv: f'{prob_level*100:.0f}%'},
                        fontsize=8, colors=[color])

        # Render cap on outlier scatter (random subsample preserves coverage)
        xo = x_raw[valid][outside]; yo = y_raw[valid][outside]
        if len(xo) > RENDER_CAP:
            idx2 = np.random.default_rng(4).choice(len(xo), RENDER_CAP, replace=False)
            xo, yo = xo[idx2], yo[idx2]
        self.ax.scatter(xo, yo,
                        s=dot_size, color=color, alpha=alpha, linewidths=0,
                        label=f'{label} outliers ({outside.sum():,})',
                        rasterized=True)

    def _plot_gated(self, x_raw, y_raw, dot_size, alpha, gate=None):
        """Single-gate coloring — kept for backward compat."""
        xa = np.asarray(x_raw, float)
        ya = np.asarray(y_raw, float)
        regions, colors = self._gate_mask_for(gate or self._sel_gate(), xa, ya)
        for (_, mask), color in zip(regions.items(), colors):
            self.ax.scatter(xa[mask], ya[mask],
                            s=dot_size, alpha=alpha, color=color,
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
                rng     = np.random.default_rng(1)
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
            idx = np.random.default_rng(5).choice(len(xr), MARG_MAX, replace=False)
            xr_h = xr[idx]; yr_h = yr[idx]
            xv_h = xv[idx]; yv_h = yv[idx]
        else:
            xr_h = xr; yr_h = yr; xv_h = xv; yv_h = yv
        if len(xv_h) > 1 and self.ax_top:
            bt = np.linspace(xv.min(), xv.max(), 121)   # bins from full range
            br = self._inv(bt, self.x_scale)
            self.ax_top.hist(xr_h, bins=br, color=color, alpha=0.55,
                             histtype='stepfilled', linewidth=0.5)
        if len(yv_h) > 1 and self.ax_right:
            bt = np.linspace(yv.min(), yv.max(), 121)
            br = self._inv(bt, self.y_scale)
            self.ax_right.hist(yr_h, bins=br, color=color, alpha=0.55,
                               histtype='stepfilled',
                               orientation='horizontal', linewidth=0.5)

    # ── Fluorophore / population naming ─────────────────────────────────────────

    @staticmethod
    def _fluor(channel: str) -> str:
        """Extract fluorophore from last _-separated segment.
        e.g. 'Bkgd_Corr_Intensity_TH' → 'TH'
             'CD3' → 'CD3' (no underscore → use whole name)
        """
        parts = channel.rsplit('_', 1)
        return parts[-1] if parts[-1] else channel

    def _region_display_name(self, x_pos: bool, y_pos: bool,
                              has_x: bool, has_y: bool) -> str:
        """Build 'VGLUT1+/TH-' style label from axis sign booleans.

        has_x / has_y indicate whether that axis has an active threshold.
        If only one axis is gated, only that fluorophore is shown.
        """
        xf = self._fluor(self.x_channel or 'X')
        yf = self._fluor(self.y_channel or 'Y')
        xs = '+' if x_pos else '-'
        ys = '+' if y_pos else '-'
        if has_x and has_y:
            return f'{yf}{ys}/{xf}{xs}'
        if has_x:
            return f'{xf}{xs}'
        if has_y:
            return f'{yf}{ys}'
        return 'All'

    # ── Region masks ─────────────────────────────────────────────────────────

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
            'linewidth': 1.8,    # float
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
            lw_var = tk.DoubleVar(value=gate.get('linewidth', 1.8))
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

        xa = np.asarray(xa, float)
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
                self._gmc.clear()
            self._gmc[ck] = result

        return result

    def _gate_mask(self, xa, ya):
        """Convenience: gate mask for the currently selected gate."""
        return self._gate_mask_for(self._sel_gate(), xa, ya)

    # Backward-compat alias used in _open_subgate
    def _gate_mask_for_id(self, gid, xa, ya):
        gate = next((g for g in self.gates if g['id'] == gid), None)
        return self._gate_mask_for(gate, xa, ya)

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
            x_parts.append(df[self.x_channel].values.astype(float))
            y_parts.append(df[self.y_channel].values.astype(float))
        if not x_parts: return
        xa = np.concatenate(x_parts)
        ya = np.concatenate(y_parts)
        total = len(xa)
        if total == 0: return

        # ── Single gate: classic IN / OUT labels ─────────────────────────
        if len(applied_gates) == 1:
            gate = applied_gates[0]
            c    = gate.get('color', GATE_PALETTE[0])
            regions, _ = self._gate_mask_for(gate, xa, ya)
            for rname, mask in regions.items():
                cnt = int(mask.sum())
                if cnt == 0 or (rname == 'OUT' and cnt == total): continue
                pct = cnt / total * 100
                mx, my = self._label_centroid(xa, ya, mask)
                if mx is None: continue
                hint = ' ⤵' if self.manager and rname != 'OUT' else ''
                self.ax.text(mx, my,
                             f'{rname}{hint}\n{pct:.1f}%\n({cnt:,})',
                             ha='center', va='center', fontsize=7.5,
                             fontweight='bold', color=T['label_txt'],
                             linespacing=1.4,
                             bbox=dict(boxstyle='round,pad=0.35',
                                       facecolor=c if gate['type'] != 'crosshair'
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
                mew    = 2.0 if pinned else 1.8
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
            base_lw = gate.get('linewidth', 1.8)
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
            xa = df[self.x_channel].values.astype(float)
            ya = df[self.y_channel].values.astype(float)
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
            total_cells=total)

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
            x = df[self.x_channel].values.astype(float)
            xt = self._fwd(x, self.x_scale)
            parts.append(xt[np.isfinite(xt)])
        return np.concatenate(parts) if parts else np.array([])

    def _collect_y_transform(self):
        parts = []
        for df in self._active().values():
            if self.y_channel not in df.columns: continue
            y = df[self.y_channel].values.astype(float)
            yt = self._fwd(y, self.y_scale)
            parts.append(yt[np.isfinite(yt)])
        return np.concatenate(parts) if parts else np.array([])

    def _deepest_gmm_threshold(self, data_t: np.ndarray,
                                thresh_list: list) -> float:
        """
        Given a list of GMM inter-component thresholds (in transform space),
        return the one at which the KDE density is LOWEST (deepest valley).

        This selects the most prominent biological separation rather than
        the leftmost threshold — critical when a 3-component GMM finds
        [neg-background | neg-main | pos] and thresh_list[0] is the
        background/main boundary instead of the main/pos boundary.
        """
        if len(thresh_list) == 1:
            return thresh_list[0]
        from scipy.stats import gaussian_kde as _kde
        data_t = data_t[np.isfinite(data_t)]
        try:
            kde  = _kde(data_t, bw_method='scott')
            dens = kde(np.asarray(thresh_list, dtype=float))   # one vectorised call
            return float(thresh_list[int(np.argmin(dens))])
        except Exception:
            return thresh_list[0]

    def _collect_2d_transform(self) -> np.ndarray:
        """
        Return an (N, 2) array of [X_transformed, Y_transformed] for every
        cell in ALL currently active (checked) files, with NaN / inf removed.
        Rows are proper (X_i, Y_i) pairs from the same cell — required for 2D GMM.
        """
        x_parts, y_parts = [], []
        for df in self._active().values():
            if self.x_channel not in df.columns or                self.y_channel not in df.columns: continue
            x_raw = df[self.x_channel].values.astype(float)
            y_raw = df[self.y_channel].values.astype(float)
            # Keep only cells where BOTH channels are present
            valid = np.isfinite(x_raw) & np.isfinite(y_raw)
            xt = self._fwd(x_raw[valid], self.x_scale)
            yt = self._fwd(y_raw[valid], self.y_scale)
            valid2 = np.isfinite(xt) & np.isfinite(yt)
            x_parts.append(xt[valid2])
            y_parts.append(yt[valid2])
        if not x_parts:
            return np.empty((0, 2))
        return np.column_stack([np.concatenate(x_parts),
                                np.concatenate(y_parts)])

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

    def auto_gate_2d_gmm(self):
        """
        2D GMM: fit a multivariate Gaussian mixture on the JOINT (X, Y) transform
        space from all currently selected (overlaid) files merged together.

        Why this is better than 1D GMM for your data:
        - 1D GMM on Y marginal sees ALL cells projected onto Y, which can produce
          a confusing multi-modal marginal (e.g., TH- cells with background VGLUT,
          TH+ cells with no VGLUT, TH+ cells with VGLUT — three Y humps).
        - 2D GMM identifies the actual 2D clusters (e.g., the TH+/VGLUT1+ island
          in the upper-right quadrant) and then PROJECTS the cluster structure onto
          each axis to find the correct axis-aligned separation.

        Algorithm:
          1. Collect paired (X_t, Y_t) from every cell in all active files.
          2. Fit GMM with k=2..4 components in the 2D joint space (BIC selection).
          3. Project each 2D component onto the X axis: marginal is N(μ_xi, σ_xi).
             Find the deepest inter-component valley on X → x_boundaries.
          4. Same projection onto Y → y_boundary (single deepest valley).
          5. Convert transform-space thresholds back to raw coordinates.
        """
        if not HAS_SKLEARN:
            messagebox.showerror("2D GMM",
                "scikit-learn required: pip install scikit-learn"); return
        active = self._active()
        if not active or not self.x_channel or not self.y_channel:
            messagebox.showwarning("Auto-Gate",
                "Load data and select axes first."); return

        self._last_auto_gate_fn = self.auto_gate_2d_gmm
        sp = self._sens_params()
        # 2D GMM: k range 2..max_comp (sensitivity expands how many clusters to try)
        k_max = sp['gmm_max_comp'] + 1  # slightly wider range for 2D

        data_2d = self._collect_2d_transform()
        if len(data_2d) < 10:
            messagebox.showwarning("2D GMM", "Not enough valid data."); return

        # Subsample for speed — 50k points is statistically sufficient
        MAX_FIT = 50_000
        rng = np.random.default_rng(42)
        data_fit = (data_2d[rng.choice(len(data_2d), MAX_FIT, replace=False)]
                    if len(data_2d) > MAX_FIT else data_2d)

        # BIC-best 2D GMM with k = 2..k_max
        best_bic, best_gmm, best_n = np.inf, None, 2
        for n in range(2, k_max + 1):
            try:
                g = GaussianMixture(n_components=n, n_init=5,
                                    covariance_type='full', random_state=42)
                g.fit(data_fit)
                b = g.bic(data_fit)
                if b < best_bic:
                    best_bic, best_gmm, best_n = b, g, n
            except Exception:
                pass

        if best_gmm is None:
            messagebox.showerror("2D GMM", "GMM fitting failed."); return

        means   = best_gmm.means_        # (k, 2)
        weights = best_gmm.weights_      # (k,)
        covs    = best_gmm.covariances_  # (k, 2, 2)

        from scipy.stats import norm as _norm

        def _project_thresholds(ax_idx):
            """Project 2D components onto one axis and find valley thresholds."""
            ax_means = means[:, ax_idx]
            ax_stds  = np.sqrt(np.clip(covs[:, ax_idx, ax_idx], 1e-12, None))
            order    = np.argsort(ax_means)
            m_s = ax_means[order]; s_s = ax_stds[order]; w_s = weights[order]
            thresholds = []
            for i in range(best_n - 1):
                lo_x   = m_s[i]     - 3 * s_s[i]
                hi_x   = m_s[i + 1] + 3 * s_s[i + 1]
                x_grid = np.linspace(lo_x, hi_x, 2000)
                dens   = sum(w_s[j] * _norm.pdf(x_grid, m_s[j], s_s[j])
                             for j in range(best_n))
                lo_idx = int(np.searchsorted(x_grid, m_s[i]))
                hi_idx = int(np.searchsorted(x_grid, m_s[i + 1]))
                if hi_idx > lo_idx:
                    thresholds.append(
                        float(x_grid[lo_idx + np.argmin(dens[lo_idx:hi_idx])]))
                else:
                    thresholds.append(float((m_s[i] + m_s[i + 1]) / 2.0))
            return thresholds

        x_thresh_t = _project_thresholds(0)
        y_thresh_t = _project_thresholds(1)

        # Convert thresholds from transform space back to raw data coordinates
        if x_thresh_t:
            xbs_raw = [float(self._inv(np.array([t]), self.x_scale)[0])
                       for t in x_thresh_t]
        else:
            # 2D GMM saw only one X cluster — use KDE valley
            all_xt = self._collect_x_transform()
            xbs_raw = [float(self._inv(
                np.array([derivative_threshold(all_xt[np.isfinite(all_xt)],
                                               bw_factor=sp['bw_factor'],
                                               min_peak_frac=sp['min_peak_frac'])]),
                self.x_scale)[0])]

        if y_thresh_t:
            # Deepest Y valley = most prominent biological Y separation
            yb_t   = self._deepest_gmm_threshold(data_2d[:, 1], y_thresh_t)
            yb_raw = float(self._inv(np.array([yb_t]), self.y_scale)[0])
        else:
            all_yt = self._collect_y_transform()
            yb_raw = float(self._inv(
                np.array([derivative_threshold(all_yt[np.isfinite(all_yt)],
                                               bw_factor=sp['bw_factor'],
                                               min_peak_frac=sp['min_peak_frac'])]),
                self.y_scale)[0])

        self._apply_gate_and_refresh(xbs_raw, yb_raw, auto_method='2d_gmm')

        all_y_raw = np.concatenate([df[self.y_channel].dropna().values
                                    for df in active.values()])
        pct_y = float(np.mean(all_y_raw < yb_raw)) * 100
        nx = len(xbs_raw)
        msg = (f"2D GMM found {best_n} populations in joint (X,Y) space.\n\n"
               f"X ({self.x_channel}): {nx} threshold(s)\n"
               + "\n".join(f"  T{i+1} = {t:,.1f}" for i, t in enumerate(xbs_raw))
               + f"\n\nY ({self.y_channel}): {yb_raw:,.2f}\n"
               f"  ({pct_y:.1f}% of cells below)")
        self.status_var.set(
            f"✓ 2D GMM gate applied  |  IN: {msg.split(chr(10))[0] if msg else ''}")

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

    def auto_gate_both(self):
        """
        Auto-Gate BOTH axes simultaneously:
          X axis → GMM population detection
          Y axis → Derivative first-valley detection
        """
        active = self._active()
        if not active or not self.x_channel or not self.y_channel:
            messagebox.showwarning("Auto-Gate",
                "Load data and select axes first."); return

        self._last_auto_gate_fn = self.auto_gate_both
        sp = self._sens_params()

        # ── X: GMM ──
        all_xt = self._collect_x_transform()
        all_xt = all_xt[np.isfinite(all_xt)]
        try:
            thresh_t = gmm_thresholds(all_xt, max_components=sp['gmm_max_comp'])
        except Exception as e:
            messagebox.showerror("GMM Error (X)", str(e)); return
        if thresh_t:
            xbs_raw = [float(self._inv(np.array([t]), self.x_scale)[0])
                       for t in thresh_t]
        else:
            xb_t    = derivative_threshold(all_xt, min_prominence=sp['kde_prominence'], bw_factor=sp['bw_factor'], min_peak_frac=sp['min_peak_frac'])
            xbs_raw = [float(self._inv(np.array([xb_t]), self.x_scale)[0])]

        # ── Y: Derivative ──
        all_yt = self._collect_y_transform()
        all_yt = all_yt[np.isfinite(all_yt)]
        try:
            yb_t = derivative_threshold(all_yt, min_prominence=sp['kde_prominence'], bw_factor=sp['bw_factor'], min_peak_frac=sp['min_peak_frac'])
        except Exception as e:
            messagebox.showerror("Derivative Error (Y)", str(e)); return
        yb_raw = float(self._inv(np.array([yb_t]), self.y_scale)[0])

        self._apply_gate_and_refresh(xbs_raw, yb_raw, auto_method='mixed')
        n_x = len(xbs_raw)
        self.status_var.set(
            f"✓ Mixed GMM+KDE: X={n_x} threshold(s)"
            + (f" @ {xbs_raw[0]:,.0f}" if n_x == 1 else "")
            + f"  |  Y @ {yb_raw:,.0f}")

    def auto_gate_multi_valley(self):
        """
        Multi-Valley Grid (KDE X+Y) — finds ALL significant KDE valleys on
        each axis independently and places threshold lines at each one.

        This is exactly what the user described: manually looking at the
        1D histogram on X, placing lines at every visible gap, then doing the
        same for Y — producing a full N×M grid of cell populations.

        - X: all_kde_valleys() finds every peak-to-peak gap
        - Y: all_kde_valleys() finds every peak-to-peak gap
        - Result: one crosshair gate with N x-lines and M y-lines
        - Each intersection zone gets its own population label in the stats

        If an axis is unimodal (no real valley), no threshold is placed for
        that axis (equivalent to an X-only or Y-only gate).
        """
        active = self._active()
        if not active or not self.x_channel or not self.y_channel:
            messagebox.showwarning("Auto-Gate",
                "Load data and select axes first."); return

        # Collect transform-space data for each axis
        all_xt = self._collect_x_transform()
        all_xt = all_xt[np.isfinite(all_xt)]
        all_yt = self._collect_y_transform()
        all_yt = all_yt[np.isfinite(all_yt)]

        if len(all_xt) < 10 or len(all_yt) < 10:
            messagebox.showwarning("Multi-Valley Grid", "Not enough data."); return

        self._last_auto_gate_fn = self.auto_gate_multi_valley
        sp = self._sens_params()

        # Find all valleys on each axis using sensitivity-controlled prominence
        x_thresh_t = all_kde_valleys(all_xt, min_prominence=sp['mv_prominence'], bw_factor=sp['bw_factor'], min_peak_frac=sp['min_peak_frac'])
        y_thresh_t = all_kde_valleys(all_yt, min_prominence=sp['mv_prominence'], bw_factor=sp['bw_factor'], min_peak_frac=sp['min_peak_frac'])

        if not x_thresh_t and not y_thresh_t:
            self.status_var.set(
                "✗ Multi-Valley Grid: no significant valleys found on either axis "
                "(data may be unimodal — try 1D GMM or KDE Valley instead)")
            return

        # Back-transform to raw data space
        xbs_raw = [float(self._inv(np.array([t]), self.x_scale)[0])
                   for t in x_thresh_t]
        ybs_raw = [float(self._inv(np.array([t]), self.y_scale)[0])
                   for t in y_thresh_t]

        # Apply to gate — reuse existing multi_valley gate or create new one
        target = None
        for g in self.gates:
            if g.get('auto_method') == 'multi_valley':
                target = g
                break
        if target is None:
            sel = self._sel_gate()
            if sel and sel.get('type') == 'crosshair' and not sel.get('auto_method'):
                target = None   # don't overwrite manual gate
            target = self._add_gate(auto_type='crosshair',
                                    auto_method='multi_valley')

        # Gate geometry will change → _gmc self-invalidates via _gate_sig()
        target['auto_method']   = 'multi_valley'
        target['type']          = 'crosshair'
        target['x_boundaries']  = xbs_raw
        target['x_thresh_vars'] = [tk.BooleanVar(value=True) for _ in xbs_raw]

        if ybs_raw:
            target['y_boundaries']  = ybs_raw
            target['y_thresh_vars'] = [tk.BooleanVar(value=True) for _ in ybs_raw]
            target['y_boundary']    = None
            target['y_thresh_var']  = None
        else:
            target['y_boundaries']  = None
            target['y_thresh_vars'] = []
            target['y_boundary']    = None
            target['y_thresh_var']  = None

        target['applied'] = True
        self._sel_gate_id = target['id']
        self._gate_hint_var.set('Multi-Valley Gate placed  |  Right-drag handles to reshape')
        self._compute_gate_stats_for(target)
        self._rebuild_gate_manager()
        self._rebuild_thresh_panel()
        self.refresh_plot()
        self._update_stats_display()

        # Status message
        nx = len(xbs_raw)
        ny = len(ybs_raw)
        x_msg = (f"{nx} X threshold(s): " +
                 ', '.join(f'{v:,.0f}' for v in xbs_raw)) if xbs_raw else "X: unimodal"
        y_msg = (f"{ny} Y threshold(s): " +
                 ', '.join(f'{v:,.0f}' for v in ybs_raw)) if ybs_raw else "Y: unimodal"
        self.status_var.set(f"✓ Multi-Valley Grid — {x_msg}  |  {y_msg}")

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
        rng = np.random.default_rng(42)
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
            if xbs:
                ttk.Label(self.thresh_panel, text="X thresholds:",
                          style='Dim.TLabel').pack(anchor='w')
                tvs = gate.get('x_thresh_vars', [])
                for i, xb in enumerate(xbs):
                    var = tvs[i] if i < len(tvs) else tk.BooleanVar(value=True)
                    row = ttk.Frame(self.thresh_panel, style='TFrame')
                    row.pack(fill=tk.X, pady=1)
                    ttk.Checkbutton(row, variable=var,
                                    command=self._on_thresh_toggle,
                                    style='TCheckbutton').pack(side=tk.LEFT)
                    ttk.Label(row, text=f'T{i+1}:  {xb:>12,.1f}',
                              style='Mono.TLabel').pack(side=tk.LEFT)
            # Multi-Y (from multi-valley gate)
            if ybs:
                ttk.Label(self.thresh_panel, text="Y thresholds:",
                          style='Dim.TLabel').pack(anchor='w', pady=(6,0))
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
                          style='Dim.TLabel').pack(anchor='w', pady=(6,0))
                ytv = gate.get('y_thresh_var') or tk.BooleanVar(value=True)
                row = ttk.Frame(self.thresh_panel, style='TFrame')
                row.pack(fill=tk.X, pady=1)
                ttk.Checkbutton(row, variable=ytv,
                                command=self._on_thresh_toggle,
                                style='TCheckbutton').pack(side=tk.LEFT)
                ttk.Label(row, text=f'Y  :  {yb:>12,.1f}',
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
            xa    = df[self.x_channel].values.astype(float)
            ya    = df[self.y_channel].values.astype(float)
            total = len(xa)
            regions, _ = self._gate_mask_for(gate, xa, ya, _cache_path=path)
            self.gate_stats[gid][path] = {
                'stats': {
                    rname: {'count': int(m.sum()),
                            'pct':   m.sum()/total*100 if total else 0.0}
                    for rname, m in regions.items()},
                'total': total}

    def _compute_gate_stats(self):
        """Recompute stats for the currently selected gate."""
        sel = self._sel_gate()
        if sel:
            self._compute_gate_stats_for(sel)

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

        for i, c in enumerate(REGION_COLORS):
            self.stats_tree.tag_configure(f'rc{i}', foreground=c)

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
                xa = df[self.x_channel].values.astype(float)
                ya = df[self.y_channel].values.astype(float)
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
                xa    = df[self.x_channel].values.astype(float)
                ya    = df[self.y_channel].values.astype(float)
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
                'linewidth':  g.get('linewidth', 1.8),
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
                'linewidth':   float(d.get('linewidth', 1.8)),
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

            xa    = df[self.x_channel].values.astype(float)
            ya    = df[self.y_channel].values.astype(float)
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
            xa = df[self.x_channel].values.astype(float) \
                 if self.x_channel and self.x_channel in df.columns else None
            ya = df[self.y_channel].values.astype(float) \
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
        root.title("Flow Cytometry Tool v39")
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
                 default_x, default_y):
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
            self._load_filtered(app, filtered_data, default_x, default_y)
        self._apps.append(app)
        self.notebook.select(frame)
        return app

    @staticmethod
    def _load_filtered(app, filtered_data, default_x, default_y):
        """Pre-load filtered DataFrames into a FlowApp and select axes."""
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

        app.refresh_plot()

    def open_subgate_tab(self, label: str, filtered_data: dict,
                         parent_x: str, parent_y: str, total_cells: int):
        """Called by a FlowApp when the user double-clicks a gated region."""
        short     = label[:22]
        tab_title = f' ↳ {short}  ({total_cells:,}) '
        self._new_tab(title=tab_title, parent_label=label,
                      filtered_data=filtered_data,
                      default_x=parent_x, default_y=parent_y)

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
    root = tk.Tk()
    mgr  = FlowTabManager(root)
    def _on_close():
        try: import matplotlib.pyplot as _plt; _plt.close('all')
        except Exception: pass
        root.quit()
        root.destroy()
        sys.exit(0)
    root.protocol('WM_DELETE_WINDOW', _on_close)
    root.mainloop()
    sys.exit(0)