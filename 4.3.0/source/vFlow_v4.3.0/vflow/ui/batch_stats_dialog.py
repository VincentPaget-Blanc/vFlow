"""BatchStatsDialog for configuring batch statistics exports."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from vflow.ui.folder_state import get_last_folder, set_last_folder


def matching_batch_preview_files(folder: str, suffix: str, file_type: str) -> list[str]:
    """Return filenames matching the Batch Stats dialog preview filters."""
    if not folder or not os.path.isdir(folder):
        return []

    suffix = suffix.strip().lower()
    exts = []
    if file_type in ("csv", "both"):
        exts.append(".csv")
    if file_type in ("fcs", "both"):
        exts += [".fcs", ".FCS"]

    found = []
    lowered_exts = [e.lower() for e in exts]
    for root_d, _, files in os.walk(folder):
        for fname in sorted(files):
            _, ext = os.path.splitext(fname)
            if ext.lower() not in lowered_exts:
                continue
            if suffix and suffix not in fname.lower():
                continue
            found.append(fname)
    return found


def batch_preview_message(files: list[str]) -> tuple[str, str]:
    """Return the Batch Stats preview text and foreground color."""
    n = len(files)
    if n == 0:
        return "No matching files found.", "#df4a4a"

    examples = files[:4]
    more = f"  … and {n - 4} more" if n > 4 else ""
    return f"{n} file(s) matched:\n  " + "\n  ".join(examples) + more, "#4adf8a"


def validate_batch_stats_selection(
    folder: str,
    suffix: str,
    file_type: str,
    save_path: str,
) -> tuple[tuple[str, str, str, str] | None, str | None]:
    """Return a Batch Stats dialog result tuple or a warning message."""
    folder = folder.strip()
    suffix = suffix.strip()
    file_type = file_type.strip()
    save_path = save_path.strip()

    if not folder or not os.path.isdir(folder):
        return None, "Select a valid root folder."
    if not save_path:
        return None, "Choose an output file path."
    return (folder, suffix, file_type, save_path), None


class BatchStatsDialog(tk.Toplevel):
    """
    Dialog for the Batch Stats → Folder feature.

    Returns result = (folder, suffix, file_types, save_path) or None if cancelled.
    """

    def __init__(
        self,
        parent,
        T: dict,
        auto_folders: list,
        x_channel: str,
        y_channel: str,
    ):
        super().__init__(parent)
        self.T = T
        self.x_channel = x_channel
        self.y_channel = y_channel
        self.result = None

        self.title("Batch Stats → Folder")
        self.geometry("600x460")
        self.configure(bg=T["sidebar_bg"])
        self.resizable(True, True)
        self.grab_set()

        self._folder_var = tk.StringVar(value=auto_folders[0] if auto_folders else "")
        self._suffix_var = tk.StringVar(value="___CytoFile")
        self._type_var = tk.StringVar(value="csv")
        self._preview_var = tk.StringVar(value="")
        self._save_var = tk.StringVar(value="")

        self._build(auto_folders)
        self._refresh_preview()

    def _build(self, auto_folders):
        T = self.T
        BG = T["sidebar_bg"]
        FG = T["fg"]
        pad = {"padx": 10, "pady": 4}

        ttk.Label(
            self, text="Root folder to scan:", foreground=FG, background=BG
        ).pack(anchor="w", **pad)
        fr1 = tk.Frame(self, bg=BG)
        fr1.pack(fill=tk.X, padx=10, pady=(0, 4))
        ttk.Entry(fr1, textvariable=self._folder_var, width=52).pack(
            side=tk.LEFT, expand=True, fill=tk.X
        )
        ttk.Button(fr1, text="Browse…", command=self._browse_folder).pack(
            side=tk.LEFT, padx=(4, 0)
        )

        if auto_folders:
            ttk.Label(
                self,
                text="Detected from loaded files:",
                foreground=T.get("dim_fg", FG),
                background=BG,
                font=("Arial", 8),
            ).pack(anchor="w", padx=10)
            for f in auto_folders[:3]:
                lbl = tk.Label(
                    self,
                    text=f"  {f}",
                    fg="#4a9aff",
                    bg=BG,
                    cursor="hand2",
                    font=("Arial", 8),
                    anchor="w",
                )
                lbl.pack(fill=tk.X, padx=10)
                lbl.bind(
                    "<Button-1>",
                    lambda _e, v=f: self._folder_var.set(v) or self._refresh_preview(),
                )

        ttk.Separator(self, orient="horizontal").pack(fill=tk.X, padx=10, pady=6)

        ttk.Label(
            self,
            text="Filename must contain (suffix pattern):",
            foreground=FG,
            background=BG,
        ).pack(anchor="w", **pad)
        fr2 = tk.Frame(self, bg=BG)
        fr2.pack(fill=tk.X, padx=10, pady=(0, 4))
        e = ttk.Entry(fr2, textvariable=self._suffix_var, width=36)
        e.pack(side=tk.LEFT)
        e.bind("<KeyRelease>", lambda _e: self._refresh_preview())
        ttk.Label(
            fr2,
            text="  (leave blank = all files)",
            foreground=T.get("dim_fg", FG),
            background=BG,
            font=("Arial", 8),
        ).pack(side=tk.LEFT)

        ttk.Label(self, text="File types:", foreground=FG, background=BG).pack(
            anchor="w", **pad
        )
        fr3 = tk.Frame(self, bg=BG)
        fr3.pack(fill=tk.X, padx=10, pady=(0, 4))
        for val, lbl in [("csv", "CSV"), ("fcs", "FCS"), ("both", "CSV + FCS")]:
            tk.Radiobutton(
                fr3,
                text=lbl,
                variable=self._type_var,
                value=val,
                bg=BG,
                fg=FG,
                selectcolor=BG,
                activebackground=BG,
                command=self._refresh_preview,
            ).pack(side=tk.LEFT, padx=8)

        ttk.Separator(self, orient="horizontal").pack(fill=tk.X, padx=10, pady=6)

        ttk.Label(
            self, text="Preview (matching files):", foreground=FG, background=BG
        ).pack(anchor="w", **pad)
        self._preview_lbl = tk.Label(
            self,
            textvariable=self._preview_var,
            fg="#4adf8a",
            bg=BG,
            font=("Arial", 9),
            justify="left",
            anchor="w",
            wraplength=560,
        )
        self._preview_lbl.pack(anchor="w", padx=14, pady=(0, 4))

        ttk.Separator(self, orient="horizontal").pack(fill=tk.X, padx=10, pady=6)

        ttk.Label(self, text="Save results to:", foreground=FG, background=BG).pack(
            anchor="w", **pad
        )
        fr4 = tk.Frame(self, bg=BG)
        fr4.pack(fill=tk.X, padx=10, pady=(0, 4))
        ttk.Entry(fr4, textvariable=self._save_var, width=46).pack(
            side=tk.LEFT, expand=True, fill=tk.X
        )
        ttk.Button(fr4, text="Browse…", command=self._browse_save).pack(
            side=tk.LEFT, padx=(4, 0)
        )

        fr5 = tk.Frame(self, bg=BG)
        fr5.pack(fill=tk.X, padx=10, pady=10, side=tk.BOTTOM)
        ttk.Button(fr5, text="Cancel", command=self.destroy).pack(
            side=tk.RIGHT, padx=(4, 0)
        )
        ttk.Button(
            fr5, text="Run Batch Export", command=self._confirm, style="Green.TButton"
        ).pack(side=tk.RIGHT)

        ttk.Label(
            self,
            text=f"Channels: X={self.x_channel}  Y={self.y_channel}",
            foreground=T.get("dim_fg", FG),
            background=BG,
            font=("Arial", 8),
        ).pack(side=tk.BOTTOM, padx=10, pady=(0, 2))

    def _browse_folder(self):
        init = (
            self._folder_var.get().strip()
            or get_last_folder()
            or os.path.expanduser("~")
        )
        d = filedialog.askdirectory(
            parent=self, title="Select root folder", initialdir=init
        )
        if d:
            set_last_folder(d)
            self._folder_var.set(d)
            self._refresh_preview()

    def _browse_save(self):
        path = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".csv",
            initialfile="batch_stats.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if path:
            self._save_var.set(path)

    def _refresh_preview(self):
        folder = self._folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            self._preview_var.set("(no valid folder selected)")
            return
        suffix = self._suffix_var.get().strip().lower()
        ftype = self._type_var.get()
        found = matching_batch_preview_files(folder, suffix, ftype)
        text, color = batch_preview_message(found)
        self._preview_var.set(text)
        self._preview_lbl.config(fg=color)

    def _confirm(self):
        result, warning = validate_batch_stats_selection(
            self._folder_var.get(),
            self._suffix_var.get(),
            self._type_var.get(),
            self._save_var.get(),
        )
        if warning:
            messagebox.showwarning("Batch Stats", warning, parent=self)
            return
        self.result = result
        self.destroy()


__all__ = [
    "BatchStatsDialog",
    "batch_preview_message",
    "matching_batch_preview_files",
    "validate_batch_stats_selection",
]
