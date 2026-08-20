"""ttk style configuration for vFlow."""

from __future__ import annotations

from tkinter import ttk


def _apply_ttk_style(T: dict):
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    BG = T["sidebar_bg"]
    FG = T["fg"]
    DIM = T["fg_dim"]
    SEL = T["sel_bg"]
    FLD = T["field_bg"]
    HDR = T["header_bg"]
    TRO = T["trough"]

    style.configure(
        ".",
        background=BG,
        foreground=FG,
        troughcolor=TRO,
        selectbackground=SEL,
        selectforeground=FG,
        fieldbackground=FLD,
        insertcolor=T["entry_ins"],
        relief="flat",
    )

    style.configure(
        "TButton",
        background=HDR,
        foreground=FG,
        padding=(6, 3),
        relief="flat",
        font=("Arial", 8),
    )
    style.map(
        "TButton",
        background=[("active", SEL), ("pressed", "#2a70b9")],
        foreground=[("active", FG)],
    )

    for name, bg, hover in [
        ("Accent.TButton", "#4a90d9", "#6aaaf9"),
        ("Green.TButton", "#3a7d3a", "#4a9d4a"),
        ("Blue2.TButton", "#3a5f8a", "#4a7faa"),
        ("Purple.TButton", "#7b5ea7", "#9b7ec7"),
        ("Orange.TButton", "#b05e3e", "#d07e5e"),
        ("Teal.TButton", "#2a7d7d", "#3a9d9d"),
        ("Cyan.TButton", "#1a6b7a", "#2a8b9a"),
        ("Indigo.TButton", "#3949ab", "#5c6bc0"),
        ("Brown.TButton", "#6d4c41", "#8d6e63"),
        ("Olive.TButton", "#5d7a2a", "#7a9d3a"),
        ("Gray.TButton", "#666666", "#888888"),
        ("DarkBlue.TButton", "#3a6fa8", "#5a8fc8"),
    ]:
        style.configure(
            name,
            background=bg,
            foreground="white",
            font=("Arial", 8),
            relief="flat",
            padding=(6, 3),
        )
        style.map(name, background=[("active", hover), ("pressed", bg)])

    style.configure(
        "TCombobox",
        background=FLD,
        foreground=FG,
        fieldbackground=FLD,
        selectbackground=SEL,
        selectforeground=FG,
        arrowcolor=FG,
        font=("Arial", 8),
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", FLD)],
        foreground=[("readonly", FG)],
        selectbackground=[("readonly", SEL)],
    )

    style.configure(
        "TScrollbar",
        background=HDR,
        troughcolor=BG,
        arrowcolor=FG,
        relief="flat",
    )

    tree_bg = T["plot_bg"]
    style.configure(
        "Treeview",
        background=tree_bg,
        foreground=FG,
        fieldbackground=tree_bg,
        rowheight=18,
        font=("Arial", 7),
    )
    style.configure(
        "Treeview.Heading",
        background=HDR,
        foreground=FG,
        font=("Arial", 7, "bold"),
    )
    style.map(
        "Treeview",
        background=[("selected", SEL)],
        foreground=[("selected", "white")],
    )

    for w in ("TCheckbutton", "TRadiobutton"):
        style.configure(w, background=BG, foreground=FG, font=("Arial", 8))
        style.map(w, background=[("active", BG)], foreground=[("active", FG)])

    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=FG, font=("Arial", 8))
    style.configure(
        "Section.TLabel",
        background=HDR,
        foreground=DIM,
        font=("Arial", 9, "bold"),
    )
    style.configure("Dim.TLabel", background=BG, foreground=DIM, font=("Arial", 7))
    style.configure("Mono.TLabel", background=BG, foreground=FG, font=("Courier", 8))

    style.configure("TNotebook", background=BG, tabmargins=[2, 4, 0, 0])
    style.configure(
        "TNotebook.Tab",
        background=HDR,
        foreground=FG,
        padding=[10, 4],
        font=("Arial", 8),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", BG), ("active", SEL)],
        foreground=[("selected", FG), ("active", FG)],
    )

    style.configure(
        "Close.TLabel",
        background=HDR,
        foreground=DIM,
        font=("Arial", 9, "bold"),
        padding=[4, 2],
    )
    style.map("Close.TLabel", foreground=[("active", "#ff6b6b")])

    style.configure(
        "Red.TButton",
        background="#922",
        foreground="white",
        font=("Arial", 8),
        relief="flat",
        padding=(6, 3),
    )
    style.map("Red.TButton", background=[("active", "#c33")])

    style.configure(
        "TEntry",
        fieldbackground=FLD,
        foreground=FG,
        insertcolor=T["entry_ins"],
        font=("Arial", 8),
    )
    return style

