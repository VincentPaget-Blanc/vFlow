"""Measured sample allocation and scoped outer-sidebar navigation."""
from __future__ import annotations
import sys
import tkinter as tk
from tkinter import ttk


class AdaptiveSamplesMixin:
    def _build_adaptive_sidebar(self, parent):
        self._sample_layout_pending = None
        self._sample_layout_busy = False
        self._sample_layout_again = False
        self._sample_layout_disposed = False
        self._sidebar_outer_canvas = canvas = tk.Canvas(parent, bg=self.T['sidebar_bg'], highlightthickness=0)
        self._sidebar_outer_scrollbar = scroll = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y'); canvas.pack(side='left', fill='both', expand=True)
        self._sample_task_pane = pane = tk.PanedWindow(canvas, orient=tk.VERTICAL, bd=0,
            sashwidth=8, sashrelief='raised', sashcursor='sb_v_double_arrow',
            opaqueresize=True, bg=self.T['header_bg'])
        self._sidebar_outer_window = canvas.create_window((0, 0), window=pane, anchor='nw')
        sample_area = ttk.Frame(pane); task_area = ttk.Frame(pane)
        self._build_workspace_panel(sample_area); self._build_task_sidebar(task_area)
        pane.add(sample_area, minsize=1, stretch='never')
        pane.add(task_area, minsize=1, stretch='always')
        pane.bind('<ButtonRelease-1>', self._sample_pane_released)
        canvas.bind('<Configure>', self._sample_pane_configured)
        self._workspace_panel.bind('<Configure>', self._sample_pane_configured, add='+')
        self._task_notebook.bind('<Configure>', self._sample_pane_configured, add='+')
        self._sidebar_outer_wheel_tag = 'VFlowOuterSidebarWheel'+str(id(self))
        self._sidebar_outer_wheel_callbacks = {}
        callbacks = self._sidebar_outer_wheel_callbacks
        callbacks['<MouseWheel>'] = self.root.bind_class(self._sidebar_outer_wheel_tag, '<MouseWheel>', self._sidebar_outer_wheel)
        for sequence, direction in (('<Button-4>', -1), ('<Button-5>', 1)):
            callbacks[sequence] = self.root.bind_class(self._sidebar_outer_wheel_tag, sequence,
                lambda e, d=direction: self._sidebar_outer_wheel(e, d))
        self._bind_sidebar_outer_wheel(canvas)
        canvas.bind('<Destroy>', self._dispose_adaptive_sidebar, add='+')

    def _bind_sidebar_outer_wheel(self, widget):
        # Sample lists and task inputs retain their own native/inner scrolling.
        # The notebook itself (its tab strip) navigates the outer sidebar.
        if widget.winfo_class() not in ('Treeview', 'TCombobox', 'TSpinbox', 'Spinbox', 'Scale', 'Scrollbar', 'TScrollbar', 'Listbox', 'Text'):
            tags = widget.bindtags()
            if self._sidebar_outer_wheel_tag not in tags:
                widget.bindtags((tags[0], self._sidebar_outer_wheel_tag, *tags[1:]))
        if widget is self._task_notebook: return
        for child in widget.winfo_children(): self._bind_sidebar_outer_wheel(child)

    def _sidebar_outer_wheel(self, event, direction=None):
        canvas = self._sidebar_outer_canvas
        if direction is None:
            delta = getattr(event, 'delta', 0)
            direction = -int(delta) if sys.platform == 'darwin' else -int(delta/120)
            if not direction and delta: direction = -1 if delta > 0 else 1
        if direction: canvas.yview_scroll(direction, 'units')
        if not self._sidebar_restoring and not self._workspace.restoring: self._workspace.mark_dirty()
        return 'break'

    def _sample_pane_configured(self, event=None):
        if getattr(self, '_sample_layout_disposed', True): return
        if self._sample_layout_busy:
            self._sample_layout_again = True
            return
        if self._sample_layout_pending is None:
            self._sample_layout_pending = self.root.after_idle(self._layout_adaptive_samples)

    def _layout_adaptive_samples(self):
        # Task selection and workspace restoration can also request layout.
        # Never enter the geometry pass recursively through an event callback.
        if self._sample_layout_busy:
            self._sample_layout_again = True
            return
        if self._sample_layout_pending is not None:
            try: self.root.after_cancel(self._sample_layout_pending)
            except tk.TclError: pass
        self._sample_layout_pending = None
        if self._sample_layout_disposed: return
        canvas = self._sidebar_outer_canvas
        height, width = canvas.winfo_height(), canvas.winfo_width()
        if height < 2 or width < 2: return
        self._sample_layout_busy = True
        self._sample_layout_again = False
        try:
            # Read the geometry from this event-loop turn. Calling update here
            # would pump other layout callbacks inside the current pass, and
            # can prevent construction/mainloop from returning on some Tk
            # window systems. Configure events schedule the next measurement.
            tree = self._workspace_tree
            row = max(1, int(ttk.Style(self.root).lookup('Treeview', 'rowheight') or 24))
            count = len(tree.get_children())
            # Requested geometry includes actual fonts, padding, wrapped labels,
            # heading, action rows, scope, empty-state action and horizontal bar.
            overhead = max(0, self._workspace_panel.winfo_reqheight()-int(tree.cget('height'))*row)
            tab = max(1, self._task_pages[self._sidebar_task()]['page'].winfo_y())+2
            sash = int(self._sample_task_pane.cget('sashwidth'))
            available = max(1, height-tab-sash)
            minimum = min(available, overhead+row)
            if self._sample_panel_fraction is None:
                fit_rows = max(0, (available-overhead)//row)
                sample = min(available, overhead+min(max(1,count),fit_rows)*row)
                sample = max(minimum, sample)
            else:
                sample = max(minimum, min(available, round(height*self._sample_panel_fraction)))
            # Keep an ordinary scrollable task viewport below the initial fold.
            # With few samples it uses the remaining height, rather than whitespace.
            task = max(tab+3*row, min(height, max(round(height*.48), height-sample-sash)))
            total = sample+sash+task
            for area, floor in ((self._sample_task_pane.panes()[0], minimum),
                                (self._sample_task_pane.panes()[1], tab+row)):
                if int(self._sample_task_pane.panecget(area, 'minsize')) != floor:
                    self._sample_task_pane.paneconfigure(area, minsize=floor)
            # Avoid requesting geometry that is already in place: on platforms
            # that emit Configure again, unconditional writes sustain a loop.
            window = self._sidebar_outer_window
            if (int(float(canvas.itemcget(window, 'width'))),
                int(float(canvas.itemcget(window, 'height')))) != (width, total):
                canvas.itemconfigure(window, width=width, height=total)
            pane = self._sample_task_pane
            if (int(pane.cget('width') or 0), int(pane.cget('height') or 0)) != (width, total):
                pane.configure(width=width, height=total)
            # A later Configure pass corrects any sash clamping against the
            # previous bounds, without recursively processing idle callbacks.
            if abs(self._sample_task_pane.sash_coord(0)[1]-sample)>1:
                self._sample_task_pane.sash_place(0,0,sample)
            region = tuple(float(value) for value in canvas.cget('scrollregion').split())
            if region != (0, 0, width, total):
                canvas.configure(scrollregion=(0,0,width,total))
            if int(canvas.cget('yscrollincrement')) != row:
                canvas.configure(yscrollincrement=row)
            if total <= height: canvas.yview_moveto(0)
        finally:
            self._sample_layout_busy = False
            if self._sample_layout_again: self._sample_pane_configured()

    def _sample_pane_released(self, event=None):
        if event is not None and event.widget is not self._sample_task_pane: return
        height = self._sidebar_outer_canvas.winfo_height()
        if height > 1:
            self._sample_panel_fraction = max(0.,min(1.,self._sample_task_pane.sash_coord(0)[1]/height))
            self.sample_panel_mode_var.set('Manual')
            self._sample_pane_configured(); self._workspace.mark_dirty()

    def _set_sample_panel_mode(self):
        if self.sample_panel_mode_var.get()=='Automatic': self._sample_panel_fraction = None
        elif self._sample_panel_fraction is None:
            self._sample_panel_fraction = self._sample_task_pane.sash_coord(0)[1]/max(1,self._sidebar_outer_canvas.winfo_height())
        self._sample_pane_configured(); self._workspace.mark_dirty()

    def _reveal_sidebar_task(self):
        if self._sidebar_restoring or self._workspace.restoring: return
        self._layout_adaptive_samples()
        canvas = self._sidebar_outer_canvas
        # The target clamps naturally when the task is shorter than the window.
        region = canvas.cget('scrollregion').split()
        if len(region)==4:
            canvas.yview_moveto(self._sample_task_pane.sash_coord(0)[1]/max(1.,float(region[3])))

    def _dispose_adaptive_sidebar(self, event=None):
        if event is not None and event.widget is not self._sidebar_outer_canvas: return
        if self._sample_layout_disposed: return
        self._sample_layout_disposed = True
        if self._sample_layout_pending is not None:
            try: self.root.after_cancel(self._sample_layout_pending)
            except tk.TclError: pass
            self._sample_layout_pending = None
        for sequence, command in self._sidebar_outer_wheel_callbacks.items():
            self.root.unbind_class(self._sidebar_outer_wheel_tag, sequence)
            if command:
                try: self.root.deletecommand(command)
                except tk.TclError: pass
        self._sidebar_outer_wheel_callbacks.clear()
