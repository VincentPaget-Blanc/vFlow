"""Gate-manager and threshold-panel presentation extracted during v4.2 refactor.

This mixin owns Tk presentation for gate rows, rename/style controls, and the
selected-gate threshold panel only. Gate geometry, threshold toggle semantics,
mask evaluation, statistics, context binding, serialization, and scientific
state transitions remain on the legacy-compatible ``FlowApp`` class.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from vflow.config.constants import _LINESTYLE_INV, _LINESTYLE_MAP
from vflow.core.gates import gate_by_id, gate_geometry_summary_lines


class GateManagerPresentationMixin:
    """Tk-only gate-manager and threshold-panel presentation helpers."""

    def _rename_gate(self, gid: int):
        """Open a simple rename dialog."""
        gate = gate_by_id(self.gates, gid)
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
            # BUG FIX (B28): use module-scope maps (built once at import).
            ls_var.set(_LINESTYLE_INV.get(gate.get('linestyle', '-'),
                                          '─── Solid'))
            def _on_ls(*_args, g=gate, v=ls_var):
                g['linestyle'] = _LINESTYLE_MAP.get(v.get(), '-')
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
                    # ── BUG FIX (B9 + B14): when y_thresh_vars is shorter than
                    # y_boundaries, the original code created an orphan
                    # BooleanVar that was never appended back to the gate.
                    # The checkbox toggle then had no effect — the var was
                    # disconnected from `_active_ybs_for`, which falls back
                    # to "all active" on length mismatch.  Also leaks a Tk
                    # variable per call (Tk vars are not GC'd).
                    # Fix: instantiate once and persist into the gate dict.
                    if i < len(y_tvs):
                        var = y_tvs[i]
                    else:
                        var = tk.BooleanVar(value=True)
                        y_tvs.append(var)
                        gate['y_thresh_vars'] = y_tvs  # ensure key present
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
                # BUG FIX (B14): persist y_thresh_var into the gate dict if
                # missing, so the checkbox state survives across rebuilds.
                ytv = gate.get('y_thresh_var')
                if ytv is None:
                    ytv = tk.BooleanVar(value=True)
                    gate['y_thresh_var'] = ytv
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
                    # Same fix as Y multi-threshold above.
                    if i < len(tvs):
                        var = tvs[i]
                    else:
                        var = tk.BooleanVar(value=True)
                        tvs.append(var)
                        gate['x_thresh_vars'] = tvs
                    row = ttk.Frame(self.thresh_panel, style='TFrame')
                    row.pack(fill=tk.X, pady=1)
                    ttk.Checkbutton(row, variable=var,
                                    command=self._on_thresh_toggle,
                                    style='TCheckbutton').pack(side=tk.LEFT)
                    ttk.Label(row, text=f'X{i+1}:  {xb:>12,.1f}',
                              style='Mono.TLabel').pack(side=tk.LEFT)

        elif gt in ('rectangle', 'ellipse', 'polygon'):
            mono_lines, dim_lines = gate_geometry_summary_lines(
                gate,
                polygon_active=self._poly_active,
            )
            for text in mono_lines:
                ttk.Label(self.thresh_panel, text=text,
                          style='Mono.TLabel').pack(anchor='w')
            for i, text in enumerate(dim_lines):
                pady = (4, 0) if text == "  Drag ◼ handles to reshape" else 0
                ttk.Label(self.thresh_panel, text=text,
                          style='Dim.TLabel').pack(anchor='w', pady=pady)
