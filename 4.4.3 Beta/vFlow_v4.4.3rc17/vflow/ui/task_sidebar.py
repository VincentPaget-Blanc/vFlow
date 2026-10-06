"""Task navigation and scrolling only; existing app callbacks own all analysis."""
from __future__ import annotations

import math
import sys
import tkinter as tk
from tkinter import ttk

TASKS = ('Data', 'Plot', 'Gates', 'Analysis')
SECTION_TASK = {
    'WORKSPACE': 'Data',
    'FILES': 'Data', 'EXCLUDED FILES': 'Data',
    'AXES': 'Plot', 'SCALE': 'Plot', 'DISPLAY': 'Plot', 'PLOT LIMITS': 'Plot',
    'TRANSFORM PARAMETERS': 'Plot', 'FIGURE EXPORT': 'Plot',
    'GATING': 'Gates', 'AUTO-GATE': 'Gates', 'GATE MANAGER': 'Gates',
    'GATE INFO': 'Gates', 'GATE SESSIONS': 'Gates',
    'STATISTICS': 'Analysis', 'STATISTICAL AUDITS': 'Analysis',
    'EXPORT': 'Analysis', 'VECTOR ANALYSIS': 'Analysis', 'BATCH PLOTS': 'Analysis',
}
SECTION_TITLES = {
    'WORKSPACE': 'Workspace',
    'FILES': 'Sources', 'EXCLUDED FILES': 'Excluded files',
    'AXES': 'Axes', 'SCALE': 'Scales', 'DISPLAY': 'Appearance',
    'PLOT LIMITS': 'Plot limits', 'TRANSFORM PARAMETERS': 'Transform parameters',
    'FIGURE EXPORT': 'Figure export', 'GATING': 'Drawing tools',
    'AUTO-GATE': 'Calculation settings', 'GATE MANAGER': 'Gate manager',
    'GATE INFO': 'Selected gate / thresholds', 'GATE SESSIONS': 'Gate sessions',
    'STATISTICS': 'Gate statistics', 'STATISTICAL AUDITS': 'Statistical audits',
    'EXPORT': 'Data and batch exports', 'VECTOR ANALYSIS': 'Vector analysis',
    'BATCH PLOTS': 'Batch plots',
}
OPEN_SECTIONS = {'WORKSPACE', 'FILES', 'AXES', 'SCALE', 'DISPLAY', 'PLOT LIMITS',
                 'GATING', 'AUTO-GATE', 'GATE MANAGER', 'STATISTICS',
                 'STATISTICAL AUDITS', 'FIGURE EXPORT', 'TRANSFORM PARAMETERS',
                 'GATE INFO', 'GATE SESSIONS', 'EXCLUDED FILES', 'EXPORT',
                 'VECTOR ANALYSIS', 'BATCH PLOTS'}
AUTO_METHODS = {
    'GMM Multi': 'auto_gate_gmm_multi', 'KDE Valley': 'auto_gate_derivative',
    'Otsu': 'auto_gate_otsu', 'Cluster Polygons': 'auto_gate_cluster_polygons',
}


class TaskSidebarMixin:
    def _build_task_sidebar(self, parent):
        self._sidebar_restoring = True
        self._task_pages = {}
        self._task_notebook = ttk.Notebook(parent, style='Sidebar.TNotebook')
        self._task_notebook.pack(fill='both', expand=True)
        self._sidebar_wheel_tag = 'VFlowSidebarWheel' + str(id(self))
        self._sidebar_wheel_callbacks = {}
        self._sidebar_wheel_callbacks['<MouseWheel>'] = self.root.bind_class(self._sidebar_wheel_tag, '<MouseWheel>', self._sidebar_mousewheel)
        for sequence, direction in (('<Button-4>', -1), ('<Button-5>', 1)):
            self._sidebar_wheel_callbacks[sequence] = self.root.bind_class(self._sidebar_wheel_tag, sequence, lambda e, d=direction: self._sidebar_mousewheel(e, d))
        for name in TASKS:
            page = ttk.Frame(self._task_notebook)
            self._task_notebook.add(page, text=name)
            canvas = tk.Canvas(page, bg=self.T['sidebar_bg'], highlightthickness=0, width=320)
            scroll = ttk.Scrollbar(page, orient='vertical', command=canvas.yview)
            canvas.configure(yscrollcommand=scroll.set)
            scroll.pack(side='right', fill='y'); canvas.pack(side='left', fill='both', expand=True)
            content = ttk.Frame(canvas)
            window = canvas.create_window((0, 0), window=content, anchor='nw', width=320)
            self._task_pages[name] = {'page': page, 'canvas': canvas, 'content': content, 'window': window}
            self._bind_sidebar_wheel(canvas)
            content.bind('<Configure>', lambda e, n=name: self._sidebar_region(n))
            canvas.bind('<Configure>', lambda e, n=name: self._sidebar_width(n, e.width))
        # Retain the original private aliases for integrations. They now identify
        # the Plot viewport, rather than one long frame containing every task.
        plot = self._task_pages['Plot']
        self.sidebar = plot['content']; self._side_canvas = plot['canvas']; self._sidebar_window = plot['window']
        self._task_notebook.select(plot['page'])
        self._task_notebook.bind('<<NotebookTabChanged>>', self._sidebar_task_changed)
        self._task_notebook.bind('<ButtonRelease-1>', self._sidebar_tab_clicked, add='+')

    def _sidebar_section_parent(self, name):
        if name in ('GATING', 'AUTO-GATE'):
            if not hasattr(self, '_gate_tools_notebook'):
                content = self._task_pages['Gates']['content']
                ttk.Label(content, text='Apply gates to:', style='TLabel').pack(anchor='w', padx=8, pady=(7, 0))
                self._gate_scope_menu = ttk.Combobox(content, textvariable=self.gate_scope_var,
                    values=['All samples (default)', 'Current sample', 'Selected samples'], state='readonly')
                self._gate_scope_menu.pack(fill='x', padx=8, pady=(2, 5))
                self._gate_scope_menu.bind('<<ComboboxSelected>>', lambda e: self._workspace.scope_changed(self))
                self._gate_tools_notebook = ttk.Notebook(content, style='Sidebar.TNotebook')
                self._gate_tools_notebook.pack(fill='x', padx=5, pady=(2, 4))
                self._gate_tool_pages = {}
                for key, label in (('GATING', 'Manual'), ('AUTO-GATE', 'Automatic')):
                    page = ttk.Frame(self._gate_tools_notebook)
                    self._gate_tool_pages[key] = page
                    self._gate_tools_notebook.add(page, text=label)
                    page.bind('<Configure>', lambda e: self._sidebar_gate_height())
                self._gate_tools_notebook.bind('<<NotebookTabChanged>>', self._sidebar_gate_changed)
            return self._gate_tool_pages[name]
        return self._task_pages[SECTION_TASK[name]]['content']

    def _sidebar_task(self):
        selected = self._task_notebook.select()
        return next((name for name, page in self._task_pages.items() if str(page['page']) == selected), 'Plot')

    def _select_sidebar_task(self, name):
        if isinstance(name, str) and name in self._task_pages:
            self._task_notebook.select(self._task_pages[name]['page'])
            if hasattr(self, '_sidebar_outer_canvas'): self._reveal_sidebar_task()

    def _show_sidebar_section(self, name):
        if name not in SECTION_TASK: return
        self._select_sidebar_task(SECTION_TASK[name])
        if name in ('GATING', 'AUTO-GATE'):
            self._gate_tools_notebook.select(self._gate_tool_pages[name])

    def _sidebar_task_changed(self, event=None):
        if not self._sidebar_restoring and hasattr(self, 'ax') and not self._workspace.restoring:
            self._reveal_sidebar_task()
            self._workspace.mark_dirty()

    def _sidebar_tab_clicked(self, event):
        try: self._task_notebook.index('@'+str(event.x)+','+str(event.y))
        except tk.TclError: return
        self._reveal_sidebar_task()
        if not self._sidebar_restoring and not self._workspace.restoring: self._workspace.mark_dirty()

    def _sidebar_gate_changed(self, event=None):
        self._sidebar_gate_height()
        self._sidebar_task_changed()

    def _sidebar_gate_height(self):
        if not hasattr(self, '_gate_tools_notebook'): return
        selected = self._gate_tools_notebook.select()
        if not selected: return
        page = self._gate_tools_notebook.nametowidget(selected)
        height = max(1, page.winfo_reqheight())
        if int(self._gate_tools_notebook.cget('height')) != height:
            self._gate_tools_notebook.configure(height=height)

    def _sidebar_region(self, name):
        page = self._task_pages[name]; canvas = page['canvas']
        canvas.configure(scrollregion=canvas.bbox('all'))
        if page['content'].winfo_reqheight() <= canvas.winfo_height(): canvas.yview_moveto(0)
        self._bind_sidebar_wheel(page['content'])

    def _sidebar_width(self, name, width):
        page = self._task_pages[name]
        page['canvas'].itemconfigure(page['window'], width=max(1, int(width)))
        def wrap(widget):
            for child in widget.winfo_children():
                if 'wraplength' in child.keys():
                    length = child.cget('wraplength')
                    if length and int(length) > 0: child.configure(wraplength=max(80, int(width) - 32))
                wrap(child)
        wrap(page['content']); self._workspace_fit_rows()

    def _bind_sidebar_wheel(self, widget):
        # Avoid bind_all: wheel events from the plot, dialogs and other population
        # tabs must not move this inspector. Native lists/inputs keep their wheel.
        if widget.winfo_class() not in ('Treeview', 'TCombobox', 'TSpinbox', 'Spinbox', 'Scale', 'Scrollbar', 'TScrollbar'):
            tags = widget.bindtags()
            if self._sidebar_wheel_tag not in tags:
                widget.bindtags((tags[0], self._sidebar_wheel_tag, *tags[1:]))
        for child in widget.winfo_children(): self._bind_sidebar_wheel(child)

    def _sidebar_mousewheel(self, event, direction=None):
        page = self._task_pages[self._sidebar_task()]
        if page['content'].winfo_reqheight() <= page['canvas'].winfo_height(): return 'break'
        if direction is not None: units = direction
        elif getattr(event, 'num', None) in (4, 5): units = -1 if event.num == 4 else 1
        else:
            delta = getattr(event, 'delta', 0)
            units = -int(delta) if sys.platform == 'darwin' else -int(delta / 120)
            if not units and delta: units = -1 if delta > 0 else 1
        if units: page['canvas'].yview_scroll(units, 'units')
        return 'break'

    def _sidebar_settings(self):
        menu = self._sidebar_settings_menu
        button = self._sidebar_settings_button
        try: menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())
        finally: menu.grab_release()

    def _build_sidebar_settings(self, parent):
        self._sidebar_settings_button = ttk.Button(parent, text='Settings', command=self._sidebar_settings)
        self._sidebar_settings_button.pack(side='right', padx=(4, 0))
        menu = self._sidebar_settings_menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label='Light mode' if self._theme_name == 'dark' else 'Dark mode', command=self.toggle_theme)
        menu.add_separator()
        for mode in ('Automatic', 'Compact', 'Comfortable', 'Large'):
            menu.add_radiobutton(label=mode, variable=self.interface_size_var, value=mode,
                command=lambda m=mode: self._workspace.set_interface_size(m))
        menu.add_separator()
        menu.add_separator()
        for mode in ('Automatic', 'Manual'):
            menu.add_radiobutton(label='Sample list: '+mode.lower(), variable=self.sample_panel_mode_var, value=mode,
                command=self._set_sample_panel_mode)
        menu.add_separator()
        menu.add_command(label='Expand all controls', command=lambda: self._set_all_sections(True))
        menu.add_command(label='Collapse all controls', command=lambda: self._set_all_sections(False))

    def _selected_sample_actions(self):
        selected = self._workspace_tree.selection()
        if selected: self._workspace.sample_menu(self, sid=selected[0])
        else:
            from tkinter import messagebox
            messagebox.showinfo('Sample actions', 'Select a sample in the pinned list first.', parent=self.root)

    def _show_gate_info(self, gid):
        self._select_gate(gid)
        self._sections['GATE INFO'][0].set(True); self._toggle_section('GATE INFO')
        self._scroll_to_gate_info()

    def _scroll_to_gate_info(self):
        self._task_notebook.update_idletasks()
        page = self._task_pages['Gates']; header = self._sections['GATE INFO'][1]._section_header
        page['canvas'].yview_moveto(header.winfo_y()/max(1,page['content'].winfo_height()))

    def _sample_icon(self, path):
        color = self.file_colors.get(path)
        if not color: return ''
        if color not in self._workspace_sample_icons:
            image = tk.PhotoImage(master=self.root, width=14, height=14)
            try: image.put(color, to=(0, 0, 14, 14))
            except tk.TclError: return ''
            self._workspace_sample_icons[color] = image
        return self._workspace_sample_icons[color]

    def _auto_method_changed(self, event=None):
        self._gmm_controls.pack_forget()
        if self.auto_gate_method_var.get() == 'GMM Multi':
            self._gmm_controls.pack(fill='x', padx=8, pady=(0, 6), before=self._auto_calculate_button)
        # Choosing a different method prepares a new explicit calculation, rather
        # than silently rerunning the previous method when sensitivity changes.
        token = getattr(self, '_sens_rerun_pending', None)
        if token:
            try: self.root.after_cancel(token)
            except tk.TclError: pass
        self._sens_rerun_pending = None; self._last_auto_gate_fn = None
        if not self._sidebar_restoring and not self._workspace.restoring: self._workspace.mark_dirty()

    def _run_selected_auto_gate(self):
        method = AUTO_METHODS.get(self.auto_gate_method_var.get())
        if method: getattr(self, method)()

    def _plot_mode_controls_changed(self):
        if self.plot_type_var.get() == 'Contour Plot':
            self._contour_controls.pack(fill='x', padx=8, pady=(0, 3), before=self._appearance_checks)
        else: self._contour_controls.pack_forget()
        self.refresh_plot()

    def _sidebar_state(self):
        gate_page = self._gate_tools_notebook.select()
        return {'sidebar_task': self._sidebar_task(),
                'sidebar_outer_scroll': self._sidebar_outer_canvas.yview()[0],
                'sample_panel_fraction': getattr(self, '_sample_panel_fraction', None),
                'sidebar_gate_tool': 'AUTO-GATE' if gate_page == str(self._gate_tool_pages['AUTO-GATE']) else 'GATING',
                'auto_gate_method': self.auto_gate_method_var.get(),
                'sidebar_scroll': {name: page['canvas'].yview()[0] for name, page in self._task_pages.items()}}

    def _restore_sidebar_state(self, state):
        self._sidebar_restoring = True
        try:
            fraction = state.get('sample_panel_fraction')
            self._sample_panel_fraction = fraction if isinstance(fraction, (int, float)) and not isinstance(fraction, bool) and math.isfinite(fraction) else None
            self.sample_panel_mode_var.set('Automatic' if self._sample_panel_fraction is None else 'Manual')
            self._sample_pane_configured()
            self._select_sidebar_task(state.get('sidebar_task', 'Plot'))
            tool = state.get('sidebar_gate_tool', 'GATING')
            if isinstance(tool, str) and tool in self._gate_tool_pages:
                self._gate_tools_notebook.select(self._gate_tool_pages[tool])
            method = state.get('auto_gate_method', 'GMM Multi')
            self.auto_gate_method_var.set(method if isinstance(method, str) and method in AUTO_METHODS else 'GMM Multi')
            self._auto_method_changed()
            # Do not let widget construction/restore generate delayed dirty events.
            self._task_notebook.update_idletasks(); self._gate_tools_notebook.update_idletasks()
            scroll = state.get('sidebar_scroll', {})
            if isinstance(scroll, dict):
                for name, page in self._task_pages.items():
                    fraction = scroll.get(name, 0)
                    if isinstance(fraction, (int, float)) and not isinstance(fraction, bool) and math.isfinite(fraction):
                        page['canvas'].yview_moveto(max(0., min(1., fraction)))
            self._layout_adaptive_samples()
            outer = state.get('sidebar_outer_scroll', 0)
            if not isinstance(outer, (int, float)) or isinstance(outer, bool) or not math.isfinite(outer): outer = 0
            self._sidebar_outer_canvas.yview_moveto(max(0., min(1., outer)))
        finally: self._sidebar_restoring = False

    def _dispose_sidebar(self):
        self._dispose_adaptive_sidebar()
        for event, command in self._sidebar_wheel_callbacks.items():
            self.root.unbind_class(self._sidebar_wheel_tag, event)
            if command:
                try: self.root.deletecommand(command)
                except tk.TclError: pass
        self._sidebar_wheel_callbacks.clear()
