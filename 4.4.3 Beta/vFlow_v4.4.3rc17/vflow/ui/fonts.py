"""Native semantic fonts shared by the shell and secondary windows."""
import tkinter.font as tkfont


def semantic_fonts(widget):
    root = widget._root()
    fonts = getattr(root, '_vflow_semantic_fonts', None)
    if fonts is None:
        family = tkfont.nametofont('TkDefaultFont', root=root).actual('family')
        fonts = {}
        for name in ('VFlowBody', 'VFlowSmall', 'VFlowSection', 'VFlowControl', 'VFlowStatus'):
            fonts[name] = tkfont.Font(root, name=name, family=family, size=11)
        root._vflow_semantic_fonts = fonts
    return fonts


def semantic_font(widget, role='VFlowControl'):
    semantic_fonts(widget)
    return role
