"""Small, keyboard-dismissable help for compact controls."""
import tkinter as tk
from tkinter import ttk


def tooltip(widget, text):
    state = {'timer': None, 'window': None, 'pointer_focus': False}
    def hide(event=None):
        if state['timer']:
            try: widget.after_cancel(state['timer'])
            except tk.TclError: pass
            state['timer'] = None
        if state['window']:
            try: state['window'].destroy()
            except tk.TclError: pass
            state['window'] = None
    def show():
        state['timer'] = None
        if not widget.winfo_exists(): return
        value = text() if callable(text) else text
        if value is None or not str(value).strip():return
        window = tk.Toplevel(widget)
        window.wm_overrideredirect(True)
        ttk.Label(window, text=value, wraplength=360, padding=8).pack()
        window.update_idletasks()
        x = min(widget.winfo_rootx()+8,max(0,widget.winfo_screenwidth()-window.winfo_reqwidth()-8))
        y = widget.winfo_rooty()+widget.winfo_height()+4
        if y+window.winfo_reqheight()>widget.winfo_screenheight():
            y = max(0,widget.winfo_rooty()-window.winfo_reqheight()-4)
        window.wm_geometry(f'+{max(0,x)}+{y}')
        state['window'] = window
    def enter(event=None):
        if event is not None and event.type == tk.EventType.FocusIn and state['pointer_focus']: return
        if event is not None and event.type == tk.EventType.Motion and event.state & 0x700: return
        hide(); state['timer'] = widget.after(450, show)
    # Run dismissal before widget-specific handlers, including handlers that
    # return 'break'. A pointer-induced FocusIn must not immediately reopen help.
    root = widget._root()
    tag = 'VFlowTooltipInput' + str(id(widget))
    callbacks = {}
    def pointer(event):
        state['pointer_focus'] = True; hide()
    def key(event):
        state['pointer_focus'] = False; hide()
    callbacks['<ButtonPress>'] = root.bind_class(tag, '<ButtonPress>', pointer)
    callbacks['<KeyPress>'] = root.bind_class(tag, '<KeyPress>', key)
    widget.bindtags((tag, *widget.bindtags()))
    def leave(event=None):
        state['pointer_focus'] = False; hide()
    def dispose(event):
        if event.widget is not widget: return
        hide()
        for sequence, command in callbacks.items():
            root.unbind_class(tag, sequence)
            if command:
                try: root.deletecommand(command)
                except tk.TclError: pass
        callbacks.clear()
    widget.bind('<Enter>', enter, add='+')
    widget.bind('<FocusIn>', enter, add='+')
    if callable(text): widget.bind('<Motion>', enter, add='+')
    for event in ('<Leave>', '<FocusOut>'): widget.bind(event, leave, add='+')
    widget.bind('<Destroy>', dispose, add='+')
    widget._vflow_tooltip = state
    return widget
