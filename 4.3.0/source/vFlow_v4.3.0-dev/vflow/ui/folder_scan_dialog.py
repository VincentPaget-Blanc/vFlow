"""FolderScanDialog for recursive folder loading and CSV concatenation."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from vflow.ui.folder_state import get_last_folder, set_last_folder


def matching_folder_scan_files(folder: str, pattern: str) -> list[str]:
    """Return CSV/FCS paths matching the FolderScanDialog filename pattern."""
    if not folder or not os.path.isdir(folder):
        return []

    pat = pattern.strip().lower()
    found = []
    for root, _, files in os.walk(folder):
        for f in sorted(files):
            if f.lower().endswith((".csv", ".fcs")):
                if not pat or pat in f.lower():
                    found.append(os.path.join(root, f))
    return found


def folder_scan_default_concat_filename(folder: str) -> str:
    """Return the default concatenate filename for a scanned folder."""
    folder_stem = os.path.basename(folder.rstrip("/\\")) or "data"
    return f"{folder_stem}_Concatenate.csv"


def folder_scan_count_text(paths: list[str]) -> str:
    """Return the FolderScanDialog count label for matched files."""
    return f"{len(paths)} file(s) found." if paths else "0 files found."


def folder_scan_relative_label(path: str, folder: str) -> str:
    """Return the file label shown in the FolderScanDialog checklist."""
    return os.path.relpath(path, folder)


class FolderScanDialog(tk.Toplevel):
    """
    Load-from-Folder dialog with an integrated Concatenate & Export section.

    result after closing:
      - list of individual file paths for the normal load workflow
      - [single_concat_path] for the Save & Load Concatenate workflow
    """

    def __init__(self, parent, T: dict):
        super().__init__(parent)
        self.T = T
        self.title("Load from Folder")
        self.geometry("700x660")
        self.configure(bg=T["sidebar_bg"])
        self.resizable(True, True)
        self.result = []
        self._folder = tk.StringVar(value=get_last_folder())
        self._pattern = tk.StringVar()
        self._vars = []
        self._concat_out_folder = tk.StringVar()
        self._concat_filename = tk.StringVar(value="Concatenate.csv")
        self._build()
        self.grab_set()

    def _build(self):
        T = self.T

        fr1 = ttk.Frame(self, style="TFrame")
        fr1.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(
            fr1,
            text="Filename must contain  (leave blank = all CSVs):",
            style="TLabel",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 2))
        self._pat_entry = ttk.Entry(
            fr1, textvariable=self._pattern, font=("Arial", 9), width=34
        )
        self._pat_entry.grid(row=1, column=0, columnspan=3, sticky="we", pady=(0, 6))
        self._pat_entry.focus_set()

        ttk.Label(fr1, text="Root folder:", style="TLabel").grid(
            row=2, column=0, sticky="w", pady=(4, 2)
        )
        ttk.Entry(fr1, textvariable=self._folder, font=("Arial", 8), width=36).grid(
            row=3, column=0, sticky="we", padx=(0, 4)
        )
        ttk.Button(
            fr1, text="Browse…", command=self._browse, style="Gray.TButton"
        ).grid(row=3, column=1, sticky="w")
        ttk.Button(
            fr1, text=" Scan ", command=self._scan, style="Accent.TButton"
        ).grid(row=3, column=2, sticky="w", padx=(6, 0))
        fr1.columnconfigure(0, weight=1)

        self._count_lbl = ttk.Label(self, text="No scan yet.", style="Dim.TLabel")
        self._count_lbl.pack(anchor="w", padx=10, pady=(2, 0))

        btn_fr = ttk.Frame(self, style="TFrame")
        btn_fr.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=6)
        ttk.Button(
            btn_fr, text="Select All", command=self._sel_all, style="Gray.TButton"
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            btn_fr, text="Unselect All", command=self._desel_all, style="Gray.TButton"
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            btn_fr,
            text="Load Selected",
            command=self._confirm,
            style="Accent.TButton",
        ).pack(side=tk.RIGHT, padx=2)
        ttk.Button(btn_fr, text="Cancel", command=self.destroy, style="Gray.TButton").pack(
            side=tk.RIGHT, padx=2
        )

        cat_outer = ttk.Frame(self, style="TFrame")
        cat_outer.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 2))

        hdr_fr = tk.Frame(cat_outer, bg=T["header_bg"])
        hdr_fr.pack(fill=tk.X, pady=(4, 4))
        tk.Label(
            hdr_fr,
            text="  ⊞  Concatenate & Export",
            bg=T["header_bg"],
            fg=T["fg"],
            font=("Arial", 8, "bold"),
        ).pack(side=tk.LEFT, padx=4, pady=3)

        row_folder = ttk.Frame(cat_outer, style="TFrame")
        row_folder.pack(fill=tk.X, pady=2)
        ttk.Label(row_folder, text="Output folder:", style="TLabel", width=13).pack(
            side=tk.LEFT
        )
        ttk.Entry(
            row_folder, textvariable=self._concat_out_folder, font=("Arial", 8)
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        ttk.Button(
            row_folder,
            text="Browse…",
            command=self._browse_concat_out,
            style="Gray.TButton",
        ).pack(side=tk.LEFT)

        row_file = ttk.Frame(cat_outer, style="TFrame")
        row_file.pack(fill=tk.X, pady=(2, 4))
        ttk.Label(row_file, text="Filename:", style="TLabel", width=13).pack(
            side=tk.LEFT
        )
        ttk.Entry(row_file, textvariable=self._concat_filename, font=("Arial", 8)).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4)
        )
        ttk.Button(
            row_file,
            text="Save & Load",
            command=self._do_concat_save_load,
            style="Green.TButton",
        ).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(
            row_file,
            text="Save Only",
            command=self._do_concat_save,
            style="Teal.TButton",
        ).pack(side=tk.RIGHT, padx=(4, 0))

        self._concat_status_var = tk.StringVar(value="")
        ttk.Label(
            cat_outer, textvariable=self._concat_status_var, style="Dim.TLabel"
        ).pack(anchor="w", pady=(0, 2))

        ttk.Separator(self, orient="horizontal").pack(
            side=tk.BOTTOM, fill=tk.X, padx=8, pady=0
        )

        list_fr = ttk.Frame(self, style="TFrame")
        list_fr.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        vsb = ttk.Scrollbar(list_fr, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._cv = tk.Canvas(
            list_fr, bg=T["plot_bg"], highlightthickness=0, yscrollcommand=vsb.set
        )
        self._cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.config(command=self._cv.yview)
        self._inner = ttk.Frame(self._cv, style="TFrame")
        self._cv.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind(
            "<Configure>",
            lambda _e: self._cv.configure(scrollregion=self._cv.bbox("all")),
        )

        self._pat_entry.bind("<Return>", lambda _e: self._scan())

    def _browse(self):
        init = self._folder.get().strip() or get_last_folder() or os.path.expanduser("~")
        d = filedialog.askdirectory(parent=self, title="Select root folder", initialdir=init)
        if not d:
            return
        set_last_folder(d)
        self._folder.set(d)
        if not self._concat_out_folder.get().strip():
            self._concat_out_folder.set(d)

    def _browse_concat_out(self):
        init = (
            self._concat_out_folder.get().strip()
            or self._folder.get().strip()
            or os.path.expanduser("~")
        )
        d = filedialog.askdirectory(
            parent=self,
            title="Select output folder for concatenated file",
            initialdir=init,
        )
        if d:
            self._concat_out_folder.set(d)

    def _scan(self):
        folder = self._folder.get().strip()
        if not folder or not os.path.isdir(folder):
            self._browse()
            folder = self._folder.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("Folder", "Please choose a valid folder.", parent=self)
            return

        if not self._concat_out_folder.get().strip():
            self._concat_out_folder.set(folder)

        self._concat_filename.set(folder_scan_default_concat_filename(folder))

        found = matching_folder_scan_files(folder, self._pattern.get())

        self._vars = []
        self._concat_status_var.set("")
        for w in self._inner.winfo_children():
            w.destroy()
        if not found:
            ttk.Label(
                self._inner, text="No matching files found.", style="Dim.TLabel"
            ).pack(padx=4, pady=4)
            self._count_lbl.config(text=folder_scan_count_text(found))
            return
        self._count_lbl.config(text=folder_scan_count_text(found))
        for path in found:
            var = tk.BooleanVar(value=True)
            self._vars.append((path, var))
            rel = folder_scan_relative_label(path, folder)
            ttk.Checkbutton(self._inner, text=rel, variable=var).pack(
                anchor="w", padx=4, pady=1
            )

    def _sel_all(self):
        for _, v in self._vars:
            v.set(True)

    def _desel_all(self):
        for _, v in self._vars:
            v.set(False)

    def _confirm(self):
        self.result = [p for p, v in self._vars if v.get()]
        self.destroy()

    def _selected_paths(self) -> list:
        """Return the currently checked file paths."""
        return [p for p, v in self._vars if v.get()]

    def _build_concat_save_path(self) -> str | None:
        """
        Validate concat output settings and return the full save path.
        """
        from vflow.services.concat_paths import concat_output_filename, concat_save_path

        out_folder = self._concat_out_folder.get().strip()
        filename = self._concat_filename.get().strip()

        if not out_folder:
            messagebox.showwarning(
                "Concatenate", "Please specify an output folder.", parent=self
            )
            return None
        if not os.path.isdir(out_folder):
            try:
                os.makedirs(out_folder, exist_ok=True)
            except OSError as e:
                messagebox.showerror(
                    "Concatenate", f"Cannot create output folder:\n{e}", parent=self
                )
                return None
        if not filename:
            messagebox.showwarning("Concatenate", "Please enter a filename.", parent=self)
            return None
        filename = concat_output_filename(filename)
        return concat_save_path(out_folder, filename)

    @staticmethod
    def _smart_read_csv(path: str):
        """Read CSV files while discarding an unnamed leading row-index column."""
        from vflow.core.data_io import smart_read_csv

        return smart_read_csv(path)

    def _run_concat(self, selected: list):
        """
        Read and concatenate selected CSV files.
        """
        from vflow.services.concat_export import (
            build_concatenated_csv,
            concat_no_csv_message,
            concat_no_selection_message,
            concat_read_error_message,
            concat_skipped_fcs_message,
        )

        if not selected:
            messagebox.showwarning(
                "Concatenate", concat_no_selection_message(), parent=self
            )
            return None

        result = build_concatenated_csv(selected)
        if result.error:
            filename, exc = result.error
            messagebox.showerror(
                "Concatenate", concat_read_error_message(filename, exc), parent=self
            )
            return None

        if result.skipped_fcs:
            messagebox.showwarning(
                "Concatenate",
                concat_skipped_fcs_message(result.skipped_fcs),
                parent=self,
            )

        if result.data is None:
            messagebox.showwarning("Concatenate", concat_no_csv_message(), parent=self)
            return None

        return result.data

    def _do_concat_save(self):
        """Save the concatenated file; keep the dialog open."""
        from vflow.services.concat_export import concat_success_message, concat_success_status

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
            messagebox.showerror(
                "Concatenate", f"Could not save file:\n{e}", parent=self
            )
            return

        n_cells = len(combined)
        n_files = len(selected)
        self._concat_status_var.set(
            concat_success_status(save_path, n_files=n_files, n_rows=n_cells)
        )
        messagebox.showinfo(
            "Concatenate",
            concat_success_message(save_path, n_files=n_files, n_rows=n_cells),
            parent=self,
        )

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
            messagebox.showerror(
                "Concatenate", f"Could not save file:\n{e}", parent=self
            )
            return

        self.result = [save_path]
        self.destroy()


__all__ = [
    "FolderScanDialog",
    "folder_scan_count_text",
    "folder_scan_default_concat_filename",
    "folder_scan_relative_label",
    "matching_folder_scan_files",
]
