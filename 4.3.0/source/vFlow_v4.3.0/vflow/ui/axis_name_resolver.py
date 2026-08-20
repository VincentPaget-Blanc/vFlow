"""Dialogs for explicit channel/axis nomenclature reconciliation.

The dialogs only collect user-confirmed mappings and delegate all mutation to
FlowApp controller methods. Fuzzy similarity is advisory only.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, ttk

from vflow.nomenclature.channel_names import (
    axis_name_similarity as _axis_name_similarity,
    channel_relation as _channel_relation,
    summarise_names as _summarise_names,
)

class ExactAxisNameResolverDialog(tk.Toplevel):
    """Advanced explicit resolver for heterogeneous individual column labels.

    The dialog never touches numeric data.  It delegates the actual rename to
    FlowApp._apply_axis_mapping(), which contains collision guards and updates
    all downstream caches/menus after a successful label mapping.
    """

    CLOSE_MATCH_THRESHOLD = 0.60
    PRESELECT_THRESHOLD    = 0.97

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Resolve Axis / Channel Names")
        self.geometry("820x590")
        self.minsize(700, 500)
        self.transient(parent)

        self.main_var = tk.StringVar()
        self.close_only_var = tk.BooleanVar(value=True)
        self.summary_var = tk.StringVar()
        self.detail_var = tk.StringVar()
        self._iid_to_name = {}

        outer = ttk.Frame(self, style='TFrame', padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            outer,
            text=("Axis menus require an exact column-name match in every loaded file. "
                  "Choose the correct Main Axis Name, then select all discovered names "
                  "that represent that same measurement. Only labels are renamed; "
                  "numeric values are never modified."),
            style='TLabel', wraplength=780, justify='left'
        ).pack(fill=tk.X, pady=(0, 8))

        ttk.Label(outer, textvariable=self.summary_var,
                  style='Dim.TLabel', wraplength=780,
                  justify='left').pack(fill=tk.X, pady=(0, 10))

        choose = ttk.Frame(outer, style='TFrame')
        choose.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(choose, text="Main Axis Name:", style='TLabel').pack(side=tk.LEFT)
        self.main_combo = ttk.Combobox(
            choose, textvariable=self.main_var, state='readonly', width=48,
            font=('Arial', 9))
        self.main_combo.pack(side=tk.LEFT, padx=(8, 8), fill=tk.X, expand=True)
        self.main_combo.bind('<<ComboboxSelected>>', lambda _e: self._refresh_variants())
        ttk.Checkbutton(
            choose, text="Show close names only", variable=self.close_only_var,
            command=self._refresh_variants, style='TCheckbutton'
        ).pack(side=tk.RIGHT)

        ttk.Label(
            outer,
            text=("Select variants to map → Main Axis Name. “Present” is the number of "
                  "loaded files containing that exact spelling. “Conflict” means both names "
                  "occur in the same file; those files are protected from ambiguous renaming."),
            style='Dim.TLabel', wraplength=780, justify='left'
        ).pack(fill=tk.X, pady=(0, 4))

        tree_frame = ttk.Frame(outer, style='TFrame')
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(
            tree_frame, columns=('name', 'present', 'similarity', 'conflict'),
            show='headings', selectmode='extended', height=14)
        self.tree.heading('name', text='Discovered variant')
        self.tree.heading('present', text='Present')
        self.tree.heading('similarity', text='Name similarity')
        self.tree.heading('conflict', text='Conflict')
        self.tree.column('name', width=390, anchor='w')
        self.tree.column('present', width=90, anchor='center')
        self.tree.column('similarity', width=120, anchor='center')
        self.tree.column('conflict', width=90, anchor='center')
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(outer, textvariable=self.detail_var,
                  style='Dim.TLabel', wraplength=780,
                  justify='left').pack(fill=tk.X, pady=(8, 4))

        btns = ttk.Frame(outer, style='TFrame')
        btns.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(btns, text='Apply selected variants → Main',
                   command=self._apply, style='Green.TButton').pack(side=tk.LEFT)
        ttk.Button(btns, text='Select suggested',
                   command=self._select_suggested,
                   style='Gray.TButton').pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text='Close', command=self.destroy,
                   style='Gray.TButton').pack(side=tk.RIGHT)

        self._reload_inventory(select_suggestion=True)
        try:
            self.grab_set()
        except Exception:
            pass

    def _reload_inventory(self, select_suggestion=False):
        inventory = self.app._axis_name_inventory()
        n_files = len(self.app.loaded_files)
        names = sorted(inventory, key=lambda n: (-len(inventory[n]), str(n).casefold()))
        self.main_combo['values'] = names

        shared = sum(1 for n in names if len(inventory[n]) == n_files) if n_files else 0
        hidden = len(names) - shared
        self.summary_var.set(
            f"Loaded files: {n_files}   •   exact names discovered: {len(names)}   •   "
            f"shared by every file: {shared}   •   not shared by every file: {hidden}")

        current = self.main_var.get()
        if current not in names:
            current = ''
        if select_suggestion or not current:
            suggestion = self.app._first_axis_resolution_candidate()
            current = suggestion or (names[0] if names else '')
        self.main_var.set(current)
        self._refresh_variants()

    def _variant_rows(self):
        inventory = self.app._axis_name_inventory()
        canonical = self.main_var.get()
        if not canonical or canonical not in inventory:
            return []
        canonical_files = inventory[canonical]
        rows = []
        for name, paths in inventory.items():
            if name == canonical:
                continue
            score = _axis_name_similarity(canonical, name)
            if self.close_only_var.get() and score < self.CLOSE_MATCH_THRESHOLD:
                continue
            conflict = len(canonical_files & paths)
            rows.append((name, len(paths), score, conflict))
        rows.sort(key=lambda r: (-r[2], -r[1], str(r[0]).casefold()))
        return rows

    def _refresh_variants(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._iid_to_name.clear()

        inventory = self.app._axis_name_inventory()
        n_files = max(1, len(self.app.loaded_files))
        canonical = self.main_var.get()
        if not canonical or canonical not in inventory:
            self.detail_var.set("No axis names are available.")
            return

        for i, (name, count, score, conflict) in enumerate(self._variant_rows()):
            iid = f'v{i}'
            self._iid_to_name[iid] = name
            self.tree.insert('', 'end', iid=iid,
                             values=(name, f'{count}/{n_files}',
                                     f'{score * 100:.1f}%',
                                     str(conflict) if conflict else ''))
        self._select_suggested()
        self.detail_var.set(
            f"'{canonical}' is present in {len(inventory[canonical])}/{n_files} loaded file(s). "
            "Close-name ranking is only a suggestion; verify marker/measurement identity before applying.")

    def _select_suggested(self):
        canonical = self.main_var.get()
        if not canonical:
            return
        inventory = self.app._axis_name_inventory()
        canonical_files = inventory.get(canonical, set())
        selection = []
        for iid, name in self._iid_to_name.items():
            score = _axis_name_similarity(canonical, name)
            conflict = len(canonical_files & inventory.get(name, set()))
            if score >= self.PRESELECT_THRESHOLD and conflict == 0:
                selection.append(iid)
        self.tree.selection_set(selection)

    def _apply(self):
        canonical = self.main_var.get()
        variants = [self._iid_to_name[i]
                    for i in self.tree.selection()
                    if i in self._iid_to_name]
        if not canonical:
            messagebox.showwarning("Axis Resolver", "Choose a Main Axis Name.", parent=self)
            return
        if not variants:
            messagebox.showinfo("Axis Resolver", "Select at least one variant to map.", parent=self)
            return

        result = self.app._apply_axis_mapping(canonical, variants)
        renamed = result.get('renamed_columns', 0)
        changed_files = result.get('changed_files', 0)
        skipped = result.get('ambiguous_files', [])

        msg = (f"Mapped {len(variants)} variant name(s) to '{canonical}'.\n\n"
               f"Column labels renamed: {renamed} across {changed_files} loaded/excluded file(s).\n"
               "Numeric values and row counts were not changed.")
        if skipped:
            sample = '\n'.join(f"  • {os.path.basename(p)}: {why}" for p, why in skipped[:8])
            more = f"\n  … +{len(skipped)-8} more" if len(skipped) > 8 else ''
            msg += ("\n\nProtected ambiguous files (left unchanged for the conflicting names):\n"
                    + sample + more)
        messagebox.showinfo("Axis Resolver", msg, parent=self)
        self._reload_inventory(select_suggestion=False)


class UnresolvedFilesDialog(tk.Toplevel):
    """Review files whose exact post-resolution schema differs from consensus."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title('Unresolved File Schemas')
        self.geometry('980x560')
        self.minsize(760, 420)
        self.transient(parent)

        outer = ttk.Frame(self, style='TFrame', padding=10)
        outer.pack(fill=tk.BOTH, expand=True)
        self.summary_var = tk.StringVar()
        ttk.Label(outer, textvariable=self.summary_var, style='TLabel',
                  wraplength=940, justify='left').pack(fill=tk.X, pady=(0, 8))

        tree_frame = ttk.Frame(outer, style='TFrame')
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(
            tree_frame, columns=('file', 'missing', 'extra'), show='headings',
            selectmode='extended', height=16)
        self.tree.heading('file', text='Unresolved file')
        self.tree.heading('missing', text='Missing vs reference schema')
        self.tree.heading('extra', text='Extra vs reference schema')
        self.tree.column('file', width=250, anchor='w')
        self.tree.column('missing', width=330, anchor='w')
        self.tree.column('extra', width=330, anchor='w')
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        ttk.Label(
            outer,
            text=('“Unresolved” means the exact column-name set still differs from the most '
                  'common loaded schema. This can represent an unresolved channel name, a '
                  'missing measurement, or an unexpected extra measurement. Source files are '
                  'never modified or deleted.'),
            style='Dim.TLabel', wraplength=940, justify='left'
        ).pack(fill=tk.X, pady=(8, 6))

        btns = ttk.Frame(outer, style='TFrame')
        btns.pack(fill=tk.X)
        ttk.Button(btns, text='Reveal selected', command=self._reveal_selected,
                   style='Gray.TButton').pack(side=tk.LEFT)
        ttk.Button(btns, text='Reveal all unresolved', command=self._reveal_all,
                   style='Gray.TButton').pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text='Unload selected', command=self._unload_selected,
                   style='Gray.TButton').pack(side=tk.LEFT, padx=(12, 6))
        ttk.Button(btns, text='Unload + Reveal all unresolved',
                   command=self._unload_reveal_all,
                   style='Green.TButton').pack(side=tk.LEFT)
        ttk.Button(btns, text='Close', command=self.destroy,
                   style='Gray.TButton').pack(side=tk.RIGHT)

        self._iid_to_path = {}
        self._reload()

    def _reload(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._iid_to_path.clear()
        report = self.app._schema_resolution_report()
        ref = report.get('reference_path')
        unresolved = report.get('unresolved', [])
        ref_name = os.path.basename(ref) if ref else '(none)'
        tie_note = (
            f"  •  WARNING: {report.get('dominant_tie_count', 0)} schemas are tied for most common"
            if not report.get('reference_unique', True) else '')
        self.summary_var.set(
            f"Reference schema: {ref_name}  •  files using that exact schema: "
            f"{report.get('reference_count', 0)}/{report.get('n_files', 0)}  •  "
            f"unresolved: {len(unresolved)}" + tie_note)
        for i, item in enumerate(unresolved):
            iid = f'u{i}'
            path = item['path']
            self._iid_to_path[iid] = path
            self.tree.insert('', 'end', iid=iid, values=(
                os.path.basename(path),
                _summarise_names(item['missing'], 6),
                _summarise_names(item['extra'], 6)))

    def _selected_paths(self):
        return [self._iid_to_path[i] for i in self.tree.selection()
                if i in self._iid_to_path]

    def _all_paths(self):
        return [x['path'] for x in
                self.app._schema_resolution_report().get('unresolved', [])]

    def _reveal_selected(self):
        paths = self._selected_paths()
        if not paths:
            messagebox.showinfo('Unresolved Files', 'Select at least one file.', parent=self)
            return
        self.app._reveal_paths_in_file_manager(paths, parent=self)

    def _reveal_all(self):
        paths = self._all_paths()
        if not paths:
            messagebox.showinfo('Unresolved Files', 'No unresolved files remain.', parent=self)
            return
        self.app._reveal_paths_in_file_manager(paths, parent=self)

    def _unload_selected(self):
        paths = self._selected_paths()
        if not paths:
            messagebox.showinfo('Unresolved Files', 'Select at least one file.', parent=self)
            return
        if messagebox.askyesno(
                'Unload unresolved files',
                f'Unload {len(paths)} selected file(s) from this analysis?\n\n'
                'The source files will not be changed or deleted.', parent=self):
            self.app._unload_paths(paths)
            self._reload()

    def _unload_reveal_all(self):
        report = self.app._schema_resolution_report()
        paths = [x['path'] for x in report.get('unresolved', [])]
        if not paths:
            messagebox.showinfo('Unresolved Files', 'No unresolved files remain.', parent=self)
            return
        if not report.get('reference_unique', True):
            messagebox.showwarning(
                'Unresolved Files',
                'There is no unique dominant schema yet, so bulk-unload is disabled to avoid '
                'choosing an arbitrary reference. Resolve more channel names first, or unload '
                'specific files manually from this list.', parent=self)
            return
        if not messagebox.askyesno(
                'Unload unresolved files',
                f'Unload all {len(paths)} unresolved file(s) from this analysis and reveal '
                'their locations?\n\nThe source files will not be changed or deleted.',
                parent=self):
            return
        self.app._reveal_paths_in_file_manager(paths, parent=self, quiet=True)
        self.app._unload_paths(paths)
        self._reload()


class AxisNameResolverDialog(tk.Toplevel):
    """Channel-aware nomenclature resolver with exact structural matching."""

    PRESELECT_NAME_THRESHOLD = 0.97

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title('Resolve Channel / Axis Names')
        self.geometry('1020x650')
        self.minsize(820, 540)
        self.transient(parent)

        self.main_var = tk.StringVar()
        self.summary_var = tk.StringVar()
        self.detail_var = tk.StringVar()
        self.schema_var = tk.StringVar()
        self.show_conflicts_var = tk.BooleanVar(value=False)
        self._iid_to_name = {}

        outer = ttk.Frame(self, style='TFrame', padding=10)
        outer.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            outer,
            text=('Recommended mode: resolve the channel name once while requiring the rest '
                  'of every column name to match exactly. Example: vGAT → VGAT can reconcile '
                  'Intensity_vGAT, Bkgd_Corr_Intensity_vGAT, X_vGAT_microns and '
                  'Y_vGAT_microns together, but it will NOT fuzzy-match a changed measurement '
                  'prefix or suffix.'),
            style='TLabel', wraplength=880, justify='left'
        ).pack(fill=tk.X, pady=(0, 8))
        ttk.Label(outer, textvariable=self.summary_var, style='Dim.TLabel',
                  wraplength=880, justify='left').pack(fill=tk.X, pady=(0, 10))

        choose = ttk.Frame(outer, style='TFrame')
        choose.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(choose, text='Main channel name:', style='TLabel').pack(side=tk.LEFT)
        self.main_combo = ttk.Combobox(choose, textvariable=self.main_var,
                                       state='readonly', width=44,
                                       font=('Arial', 9))
        self.main_combo.pack(side=tk.LEFT, padx=(8, 8), fill=tk.X, expand=True)
        self.main_combo.bind('<<ComboboxSelected>>',
                             lambda _e: self._refresh_variants())
        ttk.Button(choose, text='Advanced: individual columns…',
                   command=self._open_advanced,
                   style='Gray.TButton').pack(side=tk.RIGHT)

        explain = ttk.Frame(outer, style='TFrame')
        explain.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(
            explain,
            text=('Candidates are extracted from the selected Main channel’s exact measurement '
                  'slots. The non-channel prefix/suffix must remain exact. By default, channels '
                  'that coexist with the Main channel are hidden because they are separate real '
                  'channels, not aliases.'),
            style='Dim.TLabel', wraplength=760, justify='left'
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Checkbutton(
            explain, text='Show coexisting channels',
            variable=self.show_conflicts_var, command=self._refresh_variants,
            style='TCheckbutton'
        ).pack(side=tk.RIGHT, padx=(10, 0))

        tree_frame = ttk.Frame(outer, style='TFrame')
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(
            tree_frame,
            columns=('name', 'present', 'structures', 'coverage',
                     'relation', 'similarity', 'conflict'),
            show='headings', selectmode='extended', height=14)
        headings = [
            ('name', 'Channel-name variant', 250),
            ('present', 'Present', 75),
            ('structures', 'Exact structures', 105),
            ('coverage', 'Coverage', 80),
            ('relation', 'Relation', 100),
            ('similarity', 'Name similarity', 100),
            ('conflict', 'Coexists', 70),
        ]
        for key, text, width in headings:
            self.tree.heading(key, text=text)
            self.tree.column(key, width=width,
                             anchor='w' if key == 'name' else 'center')
        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(outer, textvariable=self.detail_var, style='Dim.TLabel',
                  wraplength=880, justify='left').pack(fill=tk.X, pady=(8, 4))

        btns = ttk.Frame(outer, style='TFrame')
        btns.pack(fill=tk.X, pady=(2, 8))
        ttk.Button(btns, text='Apply selected channel variants → Main',
                   command=self._apply,
                   style='Green.TButton').pack(side=tk.LEFT)
        ttk.Button(btns, text='Select strong suggestions',
                   command=self._select_suggested,
                   style='Gray.TButton').pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text='Close', command=self.destroy,
                   style='Gray.TButton').pack(side=tk.RIGHT)

        schema_box = ttk.Frame(outer, style='TFrame')
        schema_box.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(schema_box, textvariable=self.schema_var, style='Dim.TLabel',
                  wraplength=600, justify='left').pack(side=tk.LEFT,
                                                      fill=tk.X, expand=True)
        ttk.Button(schema_box, text='Review unresolved files…',
                   command=self._review_unresolved,
                   style='Gray.TButton').pack(side=tk.RIGHT)
        ttk.Button(schema_box, text='Unload + Reveal unresolved',
                   command=self._unload_reveal_unresolved,
                   style='Gray.TButton').pack(side=tk.RIGHT, padx=6)

        self._reload_inventory(select_suggestion=True)
        try:
            self.grab_set()
        except Exception:
            pass

    def _channel_inventory(self):
        return self.app._channel_family_inventory()

    def _reload_inventory(self, select_suggestion=False):
        inv = self._channel_inventory()
        n_files = len(self.app.loaded_files)
        names = sorted(inv,
                       key=lambda n: (-len(inv[n]['files']), str(n).casefold()))
        self.main_combo['values'] = names
        current = self.main_var.get()
        if current not in names:
            current = ''
        if select_suggestion or not current:
            current = (self.app._first_channel_resolution_candidate()
                       or (names[0] if names else ''))
        self.main_var.set(current)
        self.summary_var.set(
            f'Loaded files: {n_files}   •   channel names discovered: {len(names)}   •   '
            'non-channel label structure is compared exactly')
        self._refresh_variants()
        self._refresh_schema_summary()

    def _variant_rows(self):
        canonical = self.main_var.get()
        base_inv = self._channel_inventory()
        if canonical not in base_inv:
            return []
        candidates = self.app._channel_variants_for_canonical(canonical)
        templates = self.app._channel_templates_for_name(canonical)
        can_files = set(candidates.get(canonical, {}).get(
            'files', base_inv[canonical]['files']))
        rows = []
        for name, info in candidates.items():
            if name == canonical:
                continue
            files = set(info['files'])
            conflict = len(can_files & files)
            coverage = len(can_files | files)
            # Normal mode is intentionally conservative: a real channel that
            # coexists with the Main channel is not an alias candidate.
            if conflict:
                if not self.show_conflicts_var.get():
                    continue
            elif coverage <= len(can_files):
                continue
            structure_n = len(info['templates'])
            structure_ratio = structure_n / max(1, len(templates))
            similarity = _axis_name_similarity(canonical, name)
            relation = _channel_relation(canonical, name)
            rows.append((name, len(files), structure_n, structure_ratio,
                         coverage, relation, similarity, conflict))
        relation_rank = {'case only': 4, 'separator only': 4,
                         'partial/suffix': 2, 'manual': 1}
        rows.sort(key=lambda r: (bool(r[7]), -relation_rank.get(r[5], 0),
                                 -r[3], -r[2], -r[4], -r[6],
                                 str(r[0]).casefold()))
        return rows

    def _refresh_variants(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._iid_to_name.clear()
        inv = self._channel_inventory()
        canonical = self.main_var.get()
        n_files = max(1, len(self.app.loaded_files))
        if canonical not in inv:
            self.detail_var.set('No channel-family names were discovered.')
            return
        rows = self._variant_rows()
        for i, (name, present, structure_n, structure_ratio,
                coverage, relation, similarity, conflict) in enumerate(rows):
            iid = f'c{i}'
            self._iid_to_name[iid] = name
            self.tree.insert('', 'end', iid=iid, values=(
                name, f'{present}/{n_files}',
                f'{structure_n} ({structure_ratio*100:.0f}%)',
                f'{coverage}/{n_files}', relation,
                f'{similarity*100:.1f}%',
                str(conflict) if conflict else ''))
        self._select_suggested()
        templates = sorted(self.app._channel_templates_for_name(canonical))
        candidates = self.app._channel_variants_for_canonical(canonical)
        can_files = candidates.get(canonical, {}).get('files', inv[canonical]['files'])
        hidden_note = ('' if self.show_conflicts_var.get() else
                       ' Coexisting real channels are hidden from the normal list.')
        self.detail_var.set(
            f"'{canonical}' appears in {len(can_files)}/{n_files} file(s) across "
            f"{len(templates)} exact Main-channel structure(s): "
            f"{_summarise_names(templates, 5)}.{hidden_note}")

    def _select_suggested(self):
        rows_by_name = {r[0]: r for r in self._variant_rows()}
        selection = []
        for iid, name in self._iid_to_name.items():
            row = rows_by_name.get(name)
            if not row:
                continue
            (_name, _present, structure_n, structure_ratio,
             _coverage, relation, similarity, conflict) = row
            # Only near-exact spelling differences are auto-selected. A
            # partial alias such as Venus -> VGLUT1-Venus remains a deliberate
            # user choice even when it occupies the correct exact templates.
            if (conflict == 0 and structure_n >= 1 and structure_ratio >= 0.50
                    and relation in ('case only', 'separator only')
                    and similarity >= self.PRESELECT_NAME_THRESHOLD):
                selection.append(iid)
        self.tree.selection_set(selection)

    def _apply(self):
        canonical = self.main_var.get()
        variants = [self._iid_to_name[i] for i in self.tree.selection()
                    if i in self._iid_to_name]
        if not canonical:
            messagebox.showwarning('Channel Resolver',
                                   'Choose a Main channel name.', parent=self)
            return
        if not variants:
            messagebox.showinfo('Channel Resolver',
                                'Select at least one channel-name variant.',
                                parent=self)
            return

        rows_by_name = {r[0]: r for r in self._variant_rows()}
        coexisting = [v for v in variants
                      if rows_by_name.get(v) and rows_by_name[v][7] > 0]
        if coexisting:
            messagebox.showwarning(
                'Channel Resolver',
                'The following selected name(s) coexist with the Main channel in at least '
                'one loaded file and are therefore treated as separate real channels:\n\n  • '
                + '\n  • '.join(coexisting)
                + '\n\nThey cannot be mapped in the safe channel resolver. Use the Advanced '
                  'individual-column resolver only if you intentionally need a more manual '
                  'exception.',
                parent=self)
            return

        result = self.app._apply_channel_mapping(canonical, variants)
        pairs = result.get('axis_pairs', [])
        skipped = result.get('ambiguous_files', [])
        if not pairs:
            messagebox.showwarning(
                'Channel Resolver',
                'No exact Main-channel measurement slots could be mapped for the selected '
                'variant(s). Nothing was changed.', parent=self)
            return
        msg = (f"Mapped {len(variants)} channel-name variant(s) → '{canonical}'.\n\n"
               f"Exact structural column mappings created: {len(pairs)}\n"
               f"Column labels renamed: {result.get('renamed_columns', 0)} across "
               f"{result.get('changed_files', 0)} loaded/excluded file(s).\n"
               'Numeric values and row counts were not changed.')
        if pairs:
            sample = '\n'.join(f'  • {a} → {b}' for a, b in pairs[:8])
            more = f"\n  … +{len(pairs)-8} more" if len(pairs) > 8 else ''
            msg += '\n\nExamples:\n' + sample + more
        if skipped:
            msg += (f"\n\n{len(skipped)} ambiguous file mapping(s) were protected "
                    'and left unchanged.')
        messagebox.showinfo('Channel Resolver', msg, parent=self)
        self._reload_inventory(select_suggestion=False)

    def _refresh_schema_summary(self):
        report = self.app._schema_resolution_report()
        unresolved = report.get('unresolved', [])
        if not report.get('n_files'):
            self.schema_var.set('No files loaded.')
            return
        ref = os.path.basename(report.get('reference_path') or '')
        if unresolved:
            if report.get('reference_unique', True):
                self.schema_var.set(
                    f"Exact-schema check: {len(unresolved)} unresolved file(s). Reference is the "
                    f"most common schema ({report.get('reference_count', 0)}/"
                    f"{report.get('n_files', 0)} files; example: {ref}).")
            else:
                self.schema_var.set(
                    f"Exact-schema check: {len(unresolved)} file(s) differ, but there is no unique "
                    f"dominant schema ({report.get('dominant_tie_count', 0)} schemas tie at "
                    f"{report.get('reference_count', 0)} file(s) each). Bulk unload is disabled "
                    "until a dominant schema exists.")
        else:
            self.schema_var.set(
                f"Exact-schema check: all {report.get('n_files', 0)} loaded files "
                'now share the same column names.')

    def _review_unresolved(self):
        report = self.app._schema_resolution_report()
        if not report.get('unresolved'):
            messagebox.showinfo('Channel Resolver',
                                'All loaded files share the same exact schema.',
                                parent=self)
            return
        UnresolvedFilesDialog(self, self.app)

    def _unload_reveal_unresolved(self):
        report = self.app._schema_resolution_report()
        paths = [x['path'] for x in report.get('unresolved', [])]
        if not paths:
            messagebox.showinfo('Channel Resolver',
                                'No unresolved files remain.', parent=self)
            return
        if not report.get('reference_unique', True):
            messagebox.showwarning(
                'Channel Resolver',
                'There is no unique dominant schema yet, so bulk-unload is disabled to avoid '
                'choosing an arbitrary reference. Resolve more channel names first, or use '
                'Review unresolved files to unload specific files.', parent=self)
            return
        if not messagebox.askyesno(
                'Unload unresolved files',
                f'Unload all {len(paths)} unresolved file(s) from this analysis and reveal '
                'their locations?\n\nThe source files will not be changed or deleted.',
                parent=self):
            return
        self.app._reveal_paths_in_file_manager(paths, parent=self, quiet=True)
        self.app._unload_paths(paths)
        self._reload_inventory(select_suggestion=False)

    def _open_advanced(self):
        ExactAxisNameResolverDialog(self, self.app)

__all__ = [
    "AxisNameResolverDialog",
    "ExactAxisNameResolverDialog",
    "UnresolvedFilesDialog",
]
