"""Gate-manager and threshold-panel presentation extracted during v4.2 refactor.

This mixin owns Tk presentation for gate rows, rename/style controls, and the
selected-gate threshold panel only. Gate geometry, threshold toggle semantics,
mask evaluation, statistics, context binding, serialization, and scientific
state transitions remain on the legacy-compatible ``FlowApp`` class.
"""

from __future__ import annotations

import tkinter as tk
import math
from tkinter import ttk

from vflow.config.constants import _LINESTYLE_INV, _LINESTYLE_MAP
from vflow.core.gates import gate_by_id, gate_geometry_summary_lines, active_x_boundaries, active_y_boundaries
from vflow.ui.tooltips import tooltip
from vflow.ui.layout_helpers import wrap_on_resize


class GateManagerPresentationMixin:
    """Tk-only gate-manager and threshold-panel presentation helpers."""

    def _rename_gate(self, gid: int):
        """Open a simple rename dialog."""
        gate = gate_by_id(self.gates, gid)
        if not gate: return
        dlg = tk.Toplevel(self.root)
        dlg.title("Rename gate")
        dlg.geometry("380x180")
        dlg.minsize(320,170)
        dlg.resizable(True, True)
        dlg.transient(self.root)
        T = self.T
        dlg.configure(bg=T['sidebar_bg'])
        ttk.Label(dlg, text="New name:").pack(pady=(12, 2))
        var = tk.StringVar(value=gate['name'])
        ent = ttk.Entry(dlg, textvariable=var, width=28)
        ent.pack(padx=10); ent.select_range(0, tk.END); ent.focus()
        error = tk.StringVar(dlg,value='')
        ttk.Label(dlg,textvariable=error,foreground='#b04040').pack(fill='x',padx=10,pady=3)
        def _ok(*_):
            name = var.get().strip()
            if not name:
                error.set('Enter a gate name.'); return
            gate['name'] = name
            dlg.destroy()
            self._rebuild_gate_manager()
            self._update_stats_display()
            self.refresh_plot()
        ent.bind('<Return>', _ok)
        actions = ttk.Frame(dlg); actions.pack(side='bottom',fill='x',padx=10,pady=10)
        ttk.Button(actions,text='Cancel',command=dlg.destroy).pack(side='right')
        ttk.Button(actions, text='Rename', command=_ok).pack(side='right',padx=6)
        dlg.bind('<Escape>',lambda e:dlg.destroy())
        dlg.grab_set()
        dlg.wait_window()

    def _rebuild_gate_manager(self):
        """Rebuild the gate list rows inside gate_manager_frame."""
        for w in self.gate_manager_frame.winfo_children():
            w.destroy()
        if not self.gates:
            ttk.Label(self.gate_manager_frame, text="No gates yet. Choose a gating tool or run Auto-Gating.", wraplength=280,
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
            if hasattr(self, '_workspace'):
                self._workspace_gate_row(row, name_lbl, gate)
            name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            from vflow.ui.layout_helpers import wrap_on_resize
            from vflow.ui.tooltips import tooltip
            wrap_on_resize(name_lbl); tooltip(name_lbl,gate['name'])
            name_lbl.bind('<Button-1>',
                          lambda e, gid=gate['id']: self._select_gate(gid))
            # Rename button
            actions = ttk.Frame(self.gate_manager_frame); actions.pack(fill='x',padx=(20,4),pady=(0,4))
            ttk.Button(actions, text='Rename',
                       command=lambda gid=gate['id']: self._rename_gate(gid),
                       style='TButton').pack(side=tk.LEFT,fill='x',expand=True,padx=1)
            # Delete button
            ttk.Button(actions, text='Delete',
                       command=lambda gid=gate['id']: self._del_gate(gid),
                       style='Red.TButton').pack(side=tk.LEFT,fill='x',expand=True,padx=1)
            if hasattr(self,'_task_notebook'):
                ttk.Button(actions,text='Info / thresholds',
                           command=lambda gid=gate['id']:self._show_gate_info(gid)).pack(side='left',fill='x',expand=True,padx=1)
            # ── Style row: linestyle + linewidth ──
            style_row = ttk.Frame(self.gate_manager_frame, style='TFrame')
            style_row.pack(fill=tk.X, pady=(0, 3), padx=(20, 4))
            # Linestyle
            ls_var = tk.StringVar(value=gate.get('linestyle', '-'))
            ls_cb  = ttk.Combobox(style_row, textvariable=ls_var,
                                   values=['─── Solid', '- - Dashed', '··· Dotted'],
                                   state='readonly', width=11,
                                   font='VFlowControl')
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
            ttk.Label(style_row, text='Width:', style='Dim.TLabel').pack(side=tk.LEFT)
            lw_sb  = ttk.Spinbox(style_row, from_=0.5, to=5.0, increment=0.5,
                                  textvariable=lw_var, width=4,
                                  font='VFlowControl')
            lw_sb.pack(side=tk.LEFT)
            def _on_lw(*_args, g=gate, v=lw_var):
                try:
                    value = float(v.get())
                    if not math.isfinite(value) or not 0.5 <= value <= 5.0:
                        return
                    g['linewidth'] = float(v.get())
                except (ValueError, tk.TclError):
                    return
                self._preview_gate()
                self.canvas.draw_idle()
                self.schedule_refresh(200)   # spinbox fires many events; debounce
            lw_var.trace_add('write', _on_lw)
            def _validate_lw(event=None, g=gate, v=lw_var):
                try: value = float(v.get())
                except (ValueError, tk.TclError): value = float('nan')
                if not math.isfinite(value) or not 0.5 <= value <= 5.0:
                    v.set(g.get('linewidth', 0.5))
                    self.status_var.set('Gate width must be between 0.5 and 5.0.')
                return 'break' if event is not None and event.keysym == 'Return' else None
            lw_sb.bind('<FocusOut>', _validate_lw)
            lw_sb.bind('<Return>', _validate_lw)

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
            if not hasattr(self, '_threshold_summary_var'):
                self._threshold_summary_var = tk.StringVar(self.root, value='')
            wrap_on_resize(ttk.Label(self.thresh_panel,textvariable=self._threshold_summary_var,
                      style='Dim.TLabel',wraplength=360)).pack(fill=tk.X,pady=(2,6))
            self._update_threshold_summary()
            owner = getattr(self,'_workspace',None)
            if owner is not None:
                ttk.Button(self.thresh_panel,text='Undo gate edit',
                    command=lambda gid=gate['id']:owner.gate_action(self,'undo',gid),
                    state='normal' if owner.stores[self._workspace_tab_id]._undo else 'disabled'
                ).pack(fill=tk.X,pady=(0,6))
            xbs  = gate.get('x_boundaries', [])
            yb   = gate.get('y_boundary')
            ybs  = gate.get('y_boundaries')   # multi-Y list

            # ── Y first ──────────────────────────────────────────────────
            # Multi-Y (from multi-valley gate)
            if ybs:
                ttk.Label(self.thresh_panel, text="Y thresholds:",
                          style='Dim.TLabel').pack(anchor='w')
                y_tvs = list(gate.get('y_thresh_vars') or [])[:len(ybs)]
                gate['y_thresh_vars'] = y_tvs
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
                    self._threshold_delete_button(row,gate['id'],'y',i,yb_val)
                    ttk.Checkbutton(row, variable=var,
                                    command=self._on_thresh_toggle,
                                    style='TCheckbutton').pack(side=tk.LEFT)
                    ttk.Label(row, text=f'Y{i+1}:  {yb_val:,.10g}',
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
                self._threshold_delete_button(row,gate['id'],'y',0,yb)
                ttk.Checkbutton(row, variable=ytv,
                                command=self._on_thresh_toggle,
                                style='TCheckbutton').pack(side=tk.LEFT)
                ttk.Label(row, text=f'Y  :  {yb:,.10g}',
                          style='Mono.TLabel').pack(side=tk.LEFT)

            # ── X second ─────────────────────────────────────────────────
            if xbs:
                ttk.Label(self.thresh_panel, text="X thresholds:",
                          style='Dim.TLabel').pack(anchor='w', pady=(6, 0))
                tvs = list(gate.get('x_thresh_vars') or [])[:len(xbs)]
                gate['x_thresh_vars'] = tvs
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
                    self._threshold_delete_button(row,gate['id'],'x',i,xb)
                    ttk.Checkbutton(row, variable=var,
                                    command=self._on_thresh_toggle,
                                    style='TCheckbutton').pack(side=tk.LEFT)
                    ttk.Label(row, text=f'X{i+1}:  {xb:,.10g}',
                              style='Mono.TLabel').pack(side=tk.LEFT)

            self._update_threshold_summary()

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

    def _threshold_delete_button(self, row, gid, axis, index, value):
        control = ttk.Button(row,text='Delete',style='Red.TButton',
            command=lambda:self._delete_threshold(gid,axis,index))
        tooltip(control,f'Delete {axis.upper()}{index+1}: {value:.17g}. Adjacent regions merge. Undo gate edit restores the boundary.')
        control.pack(side=tk.RIGHT,padx=(8,0))

    def _update_threshold_summary(self):
        if not hasattr(self,'_threshold_summary_var'):return
        gate = self._sel_gate()
        if not gate or gate.get('type') != 'crosshair':return
        total = len(gate.get('x_boundaries') or []) + (len(gate.get('y_boundaries') or []) or int(gate.get('y_boundary') is not None))
        active = len(active_x_boundaries(gate))+len(active_y_boundaries(gate))
        if not total:
            text = 'No thresholds remain. This gate defines no regions. Undo gate edit restores the last edit, or calculate a new gate.'
        elif not active:
            text = 'All thresholds are unticked. This gate currently defines no regions. Tick a threshold to enable it again.'
        else:
            text = f'{active}/{total} thresholds enabled. Untick to disable temporarily. Delete removes a boundary and merges adjacent regions.'
        self._threshold_summary_var.set(text)
