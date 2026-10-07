"""Native layout helpers; no population or scientific calculations."""
import sys
import tkinter as tk
from tkinter import ttk


def reserve_footer(expanding, widgets):
    """Allocate action rows before a table can consume the available height."""
    for widget in reversed(widgets):
        widget.pack_configure(side='bottom', before=expanding, expand=False)


def wrap_on_resize(label):
    label.bind('<Configure>', lambda e: label.configure(wraplength=max(80, e.width)), add='+')
    return label


def attach_scroll_panel(canvas, content, window, *, resize_width=True):
    """Scroll over controls on all desktop platforms, without a global binding."""
    root = canvas._root()
    tag = 'VFlowPanelWheel' + str(id(canvas))
    callbacks = {}
    disposed = False
    def wheel(event, direction=None):
        if content.winfo_reqheight() <= canvas.winfo_height(): return 'break'
        if direction is not None: units = direction
        else:
            delta = getattr(event, 'delta', 0)
            units = -int(delta) if sys.platform == 'darwin' else -int(delta / 120)
            if not units and delta: units = -1 if delta > 0 else 1
        if units: canvas.yview_scroll(units, 'units')
        return 'break'
    callbacks['<MouseWheel>'] = root.bind_class(tag, '<MouseWheel>', wheel)
    # Bind direction explicitly: Tk 9 translates legacy X11 button numbers.
    for sequence, direction in (('<Button-4>', -1), ('<Button-5>', 1)):
        callbacks[sequence] = root.bind_class(tag, sequence, lambda e, d=direction: wheel(e, d))
    def bind(widget):
        if widget.winfo_class() not in ('Treeview', 'TCombobox', 'TSpinbox', 'Spinbox', 'Scale', 'Scrollbar', 'TScrollbar', 'Listbox', 'Text'):
            tags = widget.bindtags()
            if tag not in tags: widget.bindtags((tags[0], tag, *tags[1:]))
        for child in widget.winfo_children(): bind(child)
    def region(event=None):
        canvas.configure(scrollregion=canvas.bbox('all')); bind(content)
        if content.winfo_reqheight() <= canvas.winfo_height(): canvas.yview_moveto(0)
    def resize(event):
        if resize_width:canvas.itemconfigure(window, width=max(1, event.width))
        def wrap(widget):
            for child in widget.winfo_children():
                if 'wraplength' in child.keys() and 'text' in child.keys() and str(child.cget('text')):
                    child.configure(wraplength=max(80, event.width-32))
                wrap(child)
        wrap(content)
    def dispose(event):
        nonlocal disposed
        if disposed or event.widget is not canvas: return
        disposed = True
        for sequence, command in callbacks.items():
            root.unbind_class(tag, sequence)
            if command:
                try: root.deletecommand(command)
                except tk.TclError: pass
    content.bind('<Configure>', region, add='+'); canvas.bind('<Configure>', resize, add='+')
    canvas.bind('<Destroy>', dispose, add='+'); bind(canvas); bind(content)
    canvas._vflow_panel_wheel_tag = tag


def scrollable_body(parent, theme):
    outer = ttk.Frame(parent); outer.pack(fill='both', expand=True)
    canvas = tk.Canvas(outer, highlightthickness=0, bg=theme['sidebar_bg'])
    scroll = ttk.Scrollbar(outer, command=canvas.yview)
    canvas.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right', fill='y'); canvas.pack(side='left', fill='both', expand=True)
    content = ttk.Frame(canvas)
    window = canvas.create_window((0, 0), anchor='nw', window=content)
    attach_scroll_panel(canvas, content, window)
    return outer, content, canvas
