"""Main-window file-list presentation ownership for the v4.2 refactor.

This module intentionally owns Tk/presentation-only state (selection variables and
file colors) separately from :class:`vflow.app.dataset.DatasetState`, which remains
the authoritative owner of loaded/excluded DataFrame mappings. The methods below
are relocated from the frozen legacy FlowApp without behavioral edits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import tkinter as tk
from tkinter import ttk


@dataclass
class FileListUIState:
    """UI-only mutable state for the main loaded-file list."""

    file_vars: dict = field(default_factory=dict)
    file_colors: dict = field(default_factory=dict)


class FileListPresentationMixin:
    """Tk presentation helpers for loaded/excluded file lists and cycle view."""

    def _add_file_row(self, path: str):
        color = self.file_colors[path]
        row   = ttk.Frame(self.file_list_frame, style='TFrame')
        row.pack(fill=tk.X, pady=1)
        swatch = tk.Label(row, bg=color, width=2, relief='raised')
        swatch.pack(side=tk.LEFT, padx=(0, 4), anchor='n', pady=2)
        # ✕ exclude button
        exclude_btn = ttk.Button(row, text='✕', width=2,
                                 command=lambda p=path: self._exclude_file(p),
                                 style='Gray.TButton')
        exclude_btn.pack(side=tk.RIGHT, padx=(2, 0), anchor='n')
        # Preserve existing checkbox state; create new var only for genuinely new files.
        # Without this guard _exclude_file → re-builds all rows → each rebuild called
        # BooleanVar(value=True), silently reselecting every surviving file.
        if path not in self.file_vars:
            self.file_vars[path] = tk.BooleanVar(value=True)
        var  = self.file_vars[path]
        name = os.path.basename(path)
        check = ttk.Checkbutton(row, text=name, variable=var,
                                command=self._on_active_files_changed,
                                style='TCheckbutton')
        check.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Tk events do not bubble to parent frames, so bind the source-file
        # context menu to every visible part of the row.
        for widget in (row, swatch, check, exclude_btn):
            self._bind_file_context_menu(widget, path)
    def _select_all(self):
        """Check all file checkboxes."""
        for v in self.file_vars.values():
            v.set(True)
        self._on_active_files_changed()
    def _unselect_all(self):
        """Uncheck all file checkboxes."""
        for v in self.file_vars.values():
            v.set(False)
        self._on_active_files_changed()
    def _rebuild_excluded_list(self):
        """Rebuild the excluded-files UI section."""
        for w in self.excluded_list_frame.winfo_children():
            w.destroy()
        if not self.excluded_files:
            ttk.Label(self.excluded_list_frame,
                      text="(none)", style='Dim.TLabel').pack(anchor='w')
            return
        for path in self.excluded_files:
            row = ttk.Frame(self.excluded_list_frame, style='TFrame')
            row.pack(fill=tk.X, pady=1)
            # Restore button
            restore_btn = ttk.Button(row, text='↩', width=2,
                                     command=lambda p=path: self._restore_file(p),
                                     style='Green.TButton')
            restore_btn.pack(side=tk.LEFT, padx=(0, 4), anchor='n')
            name = os.path.basename(path)
            label = ttk.Label(row, text=name,
                              style='Dim.TLabel', wraplength=220,
                              justify='left')
            label.pack(side=tk.LEFT, fill=tk.X, expand=True)
            for widget in (row, restore_btn, label):
                self._bind_file_context_menu(widget, path)
    def _active(self) -> dict:
        return {p: df for p, df in self.loaded_files.items()
                if self.file_vars[p].get()}
    def _display_files(self, active: dict = None) -> dict:
        if active is None:
            active = self._active()
        if self.view_mode_var.get() == 'cycle' and active:
            keys = list(active.keys())
            idx  = self.cycle_idx % len(keys)
            return {keys[idx]: active[keys[idx]]}
        return active
    def _update_cycle_label(self, active: dict = None):
        if active is None:
            active = self._active()
        if self.view_mode_var.get() == 'cycle' and active:
            keys = list(active.keys())
            idx  = self.cycle_idx % len(keys)
            self.cycle_label_var.set(
                f'{idx+1}/{len(keys)}  {os.path.basename(keys[idx])[:20]}')
        else:
            self.cycle_label_var.set('')
    def _on_view_mode_change(self):
        mode  = self.view_mode_var.get()
        state = tk.NORMAL if mode == 'cycle' else tk.DISABLED
        self._btn_prev.config(state=state)
        self._btn_next.config(state=state)
        self.cycle_idx = 0
        self._update_cycle_label()
        self.refresh_plot()
    def _cycle_prev(self):
        n = len(self._active())
        if n: self.cycle_idx = (self.cycle_idx - 1) % n
        self._update_cycle_label(); self.refresh_plot()
    def _cycle_next(self):
        n = len(self._active())
        if n: self.cycle_idx = (self.cycle_idx + 1) % n
        self._update_cycle_label(); self.refresh_plot()
