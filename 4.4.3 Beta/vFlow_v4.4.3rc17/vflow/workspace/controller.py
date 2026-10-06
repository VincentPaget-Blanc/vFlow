"""Tk-facing workspace coordinator. Persistence and scientific ownership stay separate."""
from __future__ import annotations
import copy
import gc
import json
import re
import os
from pathlib import Path
import threading
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from dataclasses import asdict
from vflow.workspace.model import Workspace, FileReference, SampleReference, ViewState, atomic_json
from vflow.workspace.file_guard import check_revision
from vflow.workspace.gates import GateStore, decode_session, plain, filter_lineage, resolve_lineage_for_sample
from vflow.workspace.relink import scan_candidates
from vflow.app.state import AnalysisState
from vflow.services.gate_session import build_gate_session_payload


def live(gate, root):
    g = copy.deepcopy(gate)
    g['x_thresh_vars'] = [tk.BooleanVar(root, value=bool(v)) for v in g.get('x_thresh_active', g.get('x_thresh_vars', []))]
    g['y_thresh_var'] = tk.BooleanVar(root, value=bool(g.get('y_thresh_active', g.get('y_thresh_var', True))))
    g['y_thresh_vars'] = [tk.BooleanVar(root, value=bool(v)) for v in g.get('y_thresh_actives', g.get('y_thresh_vars', []))]
    return g


def session_payload(gates):
    state = AnalysisState()
    payload = build_gate_session_payload(gates, analysis_state=state, population_lineage=[])
    payload['workspace_auto_fit'] = {str(g['id']): copy.deepcopy(g['_auto_fit']) for g in gates if g.get('_auto_fit')}
    return payload


class WorkspaceController:
    def __init__(self, app):
        self.main = app
        self.document = Workspace()
        self.path = None
        self.dirty = False
        self.gates_dirty = False
        self.restoring = False
        self.apps = {}
        self.stores = {}
        self._loaded_lineages = {}
        self._unloaded_sample_ids = {}
        self.missing = {}
        self.errors = []
        self._autosave = None
        self._last_state = None
        self._scan_running = False
        self._scan_token = None
        self._scan_poll = None
        self._disposed = False
        self._default_gates_unavailable = False
        self.state_dir = Path.home() / '.vflow'
        self.recent_path = self.state_dir / 'recent_workspaces.json'
        self.recovery_path = None
        self._recovery_gate_path = None
        self._instance_id = uuid.uuid4().hex

    def register(self, app, tab_id=None):
        tab_id = tab_id or ('main' if not self.apps else str(uuid.uuid4()))
        self.apps[tab_id] = app
        self.stores.setdefault(tab_id, GateStore())
        app._workspace_tab_id = tab_id
        app._workspace_view_key = None
        app._workspace_display_signature = None
        app._workspace_materialized = False
        app._workspace_scope_sample = None
        app._workspace_selected_scope = ()
        app._workspace_gate_baseline = []
        return tab_id

    def sample_id(self, path):
        recorded=self._unloaded_sample_ids.get(path)
        if recorded in self.document.samples:return recorded
        absolute = str(Path(path).resolve())
        df = self.main.loaded_files.get(path, self.main.excluded_files.get(path))
        source = (df.attrs.get('vflow_source_path',absolute) if df is not None else absolute)
        member = df.attrs.get('vflow_source_member_id') if df is not None else None
        return next((sid for sid,s in self.document.samples.items()
                     if s.source.absolute_path == source and (member is None or s.source_member_id == member)),None)

    def path_for(self, sid):
        sample = self.document.samples.get(sid)
        if sample is None: return None
        for key,df in {**self.main.loaded_files,**self.main.excluded_files}.items():
            if df is not None and df.attrs.get('vflow_source_path',key)==sample.source.absolute_path and df.attrs.get('vflow_source_member_id')==sample.source_member_id:
                return key
            if df is None and sample.source_member_id is None and str(Path(key).resolve())==sample.source.absolute_path:return key
            if df is None and self._unloaded_sample_ids.get(key)==sid:return key
        # Restore removes the placeholder before unregistering its reference.
        key=next((key for key,value in self._unloaded_sample_ids.items() if value==sid),None)
        if key is not None:return key
        return sample.source.absolute_path

    def retain_unloaded_exclusion(self, sid):
        sample=self.document.samples[sid];key=sample.source.absolute_path
        if sample.source_member_id is not None:
            # Members need separate list keys. Their saved display filename is
            # only a UI key; the authoritative acquisition stays in the reference.
            key=str(Path(key).with_name(Path(sample.display_name).name))
            if key in {**self.main.loaded_files,**self.main.excluded_files} and self.sample_id(key)!=sid:
                key=str(Path(key).with_name(Path(key).stem+'_'+sid[:8]+Path(key).suffix))
        for stale,value in list(self._unloaded_sample_ids.items()):
            if value==sid and stale!=key:
                if self.main.excluded_files.get(stale) is None:self.main.excluded_files.pop(stale,None)
                self._unloaded_sample_ids.pop(stale,None)
        self.main.excluded_files.setdefault(key,None)
        self._unloaded_sample_ids[key]=sid

    def current_sid(self, app):
        active = list(app._active())
        return self.sample_id(active[app.cycle_idx % len(active)]) if active else None

    def auto_gate_data(self, app):
        """Full scientific populations, independent of plot/display subsampling."""
        self.refresh_child(app)
        mode = app.auto_gate_input_var.get()
        app._auto_fit_input_error = ''
        if mode == 'Active samples (pooled)': return app._active()
        if mode == 'Current sample':
            sid = self.current_sid(app)
            ids = [sid] if sid else []
        else: ids = list(app._workspace_tree.selection())
        frames = {}
        for sid in ids:
            path = self.path_for(sid)
            if path not in app.loaded_files:
                app._auto_fit_input_error = 'A fitting sample is unavailable in this population. Choose available samples.'
                return {}
            frames[path] = app.loaded_files[path]
        if not frames: app._auto_fit_input_error = 'Select fitting samples in the pinned Samples list, or choose Active samples (pooled).'
        return frames

    def auto_fit_signature(self, app):
        return (app.auto_gate_input_var.get(), tuple(self.auto_gate_data(app)),
                app.gate_scope_var.get(), app._workspace_scope_sample,
                app._data_generation,
                json.dumps(app._current_analysis_context(), sort_keys=True))

    def auto_fit_provenance(self, app):
        frames = self.auto_gate_data(app)
        return {'input_mode': app.auto_gate_input_var.get(),
                'sample_ids': [self.sample_id(p) for p in frames],
                'source_rows': {self.sample_id(p): len(df) for p, df in frames.items()},
                'application_scope': app.gate_scope_var.get()}

    def validate_gate_target(self, app, gate, target):
        path = self.path_for(target)
        df = self.main.loaded_files.get(path, self.main.excluded_files.get(path))
        if target not in self.document.samples or df is None:
            raise ValueError('Target sample is unavailable.')
        ctx = gate.get('_analysis_context') or {}
        from vflow.services.gate_session import validate_gate_context_payload
        valid, reason = validate_gate_context_payload(ctx)
        if not valid: raise ValueError('Gate context unavailable: ' + reason)
        missing = [ctx[k] for k in ('x_channel', 'y_channel') if ctx[k] not in df]
        if missing: raise ValueError(f"Gate unavailable for {Path(path).name}. Required channel: {', '.join(missing)}")
        if app.population_lineage:
            lineage = resolve_lineage_for_sample(target, app.population_lineage, self.stores)
            filter_lineage(df, lineage)

    def commit_gates(self, app):
        if not app._workspace_materialized: return False
        store = self.stores[app._workspace_tab_id]
        if self._default_gates_unavailable:
            if store.selected_changes(app.gates, app._workspace_gate_baseline):
                app.gates = [live(g, app.root) for g in app._workspace_gate_baseline]
                self.gate_editing_available(app)
            return False
        scope = app._workspace_scope_sample
        if isinstance(scope, tuple):
            changes = store.selected_changes(app.gates, app._workspace_gate_baseline)
            try:
                for gate in changes.values():
                    if gate is not None:
                        for sid in scope: self.validate_gate_target(app, gate, sid)
            except ValueError as exc:
                app.status_var.set('Selected-sample edit rejected: ' + str(exc))
                app.gates = [live(g, app.root) for g in app._workspace_gate_baseline]
                return False
            changed = store.commit_selected(app.gates, scope, app._workspace_gate_baseline)
            app._workspace_gate_baseline = [plain(g) for g in app.gates]
        else: changed = store.commit(app.gates, scope)
        if changed: self.gates_dirty = True
        return changed

    def capture_view(self, app):
        return ViewState(app.x_channel, app.y_channel, app.x_scale, app.y_scale, app.cofactor,
            copy.deepcopy(app.x_transform_params), copy.deepcopy(app.y_transform_params), app.plot_type_var.get(),
            {'x': app._locked_xlim, 'y': app._locked_ylim} if app.lock_scale_var.get() else None,
            'locked' if app.lock_scale_var.get() else ('fit' if app.fit_axes_var.get() else 'automatic')).validate()

    @staticmethod
    def lineage_references(lineage):
        # Gate snapshots live exclusively in the external gate bundle.
        return [{'workspace_tab_id': stage.get('workspace_tab_id'),
                 'gate_id': stage.get('gate', {}).get('id'), 'region': stage.get('region')}
                for stage in lineage]

    def tab_state(self, app):
        return self.document.tabs.setdefault(app._workspace_tab_id, {
            'title': app.parent_label or 'Main', 'lineage': self.lineage_references(app.population_lineage),
            'overlay_view': asdict(self.document.overlay_view), 'sample_views': {},
            'ui_state': {}, 'sections': {},
            'sample_ids': [self.sample_id(p) for p in app.loaded_files] if app is not self.main else None,
        })

    def sync_sources(self):
        app = self.main
        paths = {**app.loaded_files, **app.excluded_files}
        for path in paths:
            sid = self.sample_id(path)
            if sid is None:
                sid = str(uuid.uuid4())
                df = paths[path]
                source = df.attrs.get('vflow_source_path', path) if df is not None else str(Path(path).resolve())
                member = df.attrs.get('vflow_source_member_id') if df is not None else None
                if df is None and not Path(source).is_file():
                    ref=FileReference(str(Path(source).absolute()),filename=Path(source).name)
                    ref.rebase(self.path)
                    self.missing['sample:'+sid]=ref
                elif df is not None and df.attrs.get('vflow_source_identity') and df.attrs.get('vflow_source_size') is not None:
                    ref=FileReference(str(Path(source).resolve()),filename=Path(source).name,
                        size=df.attrs['vflow_source_size'],identity_fingerprint=df.attrs['vflow_source_identity'])
                    ref.rebase(self.path)
                else:ref=FileReference.create(source,self.path)
                self.document.samples[sid] = SampleReference(sid, Path(path).name, ref, source_member_id=member)
            sample = self.document.samples[sid]
            sample.excluded = path in app.excluded_files
            sample.active = bool(app.file_vars[path].get()) if path in app.file_vars else False
        # Missing references survive partial loading. Explicit remove uses remove_sample.
        for sid, sample in list(self.document.samples.items()):
            if self.path_for(sid) not in paths and 'sample:' + sid not in self.missing:
                del self.document.samples[sid]
        self.document.axis_aliases = dict(app.axis_aliases)

    def capture(self, app):
        if self.restoring: return
        self.sync_sources()
        self.refresh_child(app)
        tab = self.tab_state(app)
        key = app._workspace_view_key
        view = self.capture_view(app)
        if key and key != 'overlay':
            tab['sample_views'][key] = asdict(view)
            if app is self.main and key in self.document.samples: self.document.samples[key].view = view
        elif app.view_mode_var.get() != 'cycle':
            tab['overlay_view'] = asdict(view)
            if app is self.main: self.document.overlay_view = view
        ui = tab['ui_state']
        ui.update(view_mode=app.view_mode_var.get(), current_sample_id=self.current_sid(app),
                  gate_scope=app.gate_scope_var.get(), selected_gate_id=app._sel_gate_id,
                  interface_size=app.interface_size_var.get(),
                  auto_gate_input=app.auto_gate_input_var.get(),
                  selected_sample_ids=list(app._workspace_tree.selection()),
                  active_sample_ids=[self.sample_id(p) for p in app._active()],
                  active_tab_id=self.current_app()._workspace_tab_id,
                  sidebar_width=app._side_outer.winfo_width())
        if hasattr(app, '_sidebar_state'): ui.update(app._sidebar_state())
        if app is self.main:
            name = self.document.ui_state.get('workspace_name')
            self.document.ui_state = copy.deepcopy(ui)
            if name: self.document.ui_state['workspace_name'] = name
        if app.population_lineage or app is self.main or not tab.get('lineage'):
            tab['lineage'] = self.lineage_references(app.population_lineage)
        tab['sections'] = {name: bool(var.get()) for name, (var, frame) in getattr(app, '_sections', {}).items()}
        if app._workspace_materialized:
            changed = self.commit_gates(app)
            if changed: self.gates_dirty = True
        # Compare serialized state instead of marking every redraw dirty.
        state = json.dumps(self.document.payload(), sort_keys=True) + str([(k, s.revision) for k, s in self.stores.items()])
        if self._last_state is not None and state != self._last_state: self.mark_dirty()
        self._last_state = state
        self.update_tree(app)

    def mark_dirty(self):
        self.dirty = True
        self.title()
        if self._autosave:
            try: self.main.root.after_cancel(self._autosave)
            except tk.TclError: pass
        self._autosave = self.main.root.after(1500, self.autosave)

    def workspace_name(self):
        name = self.document.ui_state.get('workspace_name')
        return name.strip() if isinstance(name, str) and name.strip() else (Path(self.path).stem if self.path else 'Untitled Workspace')

    def rename(self, name):
        name = str(name).strip()
        if not name:
            self.title(force_name=True)
            return False
        if name != self.workspace_name():
            self.document.ui_state['workspace_name'] = name
            self.mark_dirty()
        self.title(force_name=True)
        return True

    def commit_focused_name(self):
        focused = self.main.root.focus_get()
        for app in self.apps.values():
            if focused is getattr(app, '_workspace_name_entry', None) and focused is not None:
                self.rename(app._workspace_name_var.get())
                break

    def title(self, force_name=False):
        name = self.workspace_name()
        self.main.root.title('vFlow — ' + name + (' *' if self.dirty or self.gates_dirty else ''))
        focused = self.main.root.focus_get()
        for app in self.apps.values():
            if hasattr(app, '_workspace_name_var') and (force_name or focused is not getattr(app, '_workspace_name_entry', None)):
                app._workspace_name_var.set(name)
            if hasattr(app, '_workspace_save_state_var'):
                app._workspace_save_state_var.set('Unsaved changes' if self.dirty or self.gates_dirty else ('Saved' if self.path else 'Not saved yet'))

    def autosave(self):
        if self._autosave:
            try:self.main.root.after_cancel(self._autosave)
            except tk.TclError:pass
        self._autosave = None
        if self.restoring or not self.dirty: return
        new_gate=None
        try:
            for app in list(self.apps.values()): self.capture(app)
            checkpoint=(Path(str(self.path)+'.recovery.'+self._instance_id+'.vflow') if self.path else
                self.state_dir/'recovery'/(self.document.workspace_id+'.'+self._instance_id+'.vflow'))
            staged=copy.deepcopy(self.document)
            if self.gates_dirty:
                if self._default_gates_unavailable:raise ValueError('Relink the unavailable gate session before checkpointing gate changes.')
                new_gate=Path(str(checkpoint)+'.gates.'+uuid.uuid4().hex+'.json')
                atomic_json(new_gate,self.gate_bundle())
                staged.default_gate_session=FileReference.create(new_gate,checkpoint,'gates')
            for _,ref in staged.references():ref.rebase(checkpoint)
            staged.ui_state.update(unsaved_gate_changes=self.gates_dirty,
                recovery_base_revision=getattr(self.document,'_disk_revision',None),recovery_origin_path=self.path)
            atomic_json(checkpoint,staged.payload())
            previous=self._recovery_gate_path
            self.recovery_path=checkpoint;self._recovery_gate_path=new_gate
            if previous and previous!=new_gate:previous.unlink(missing_ok=True)
        except (OSError, ValueError) as exc:
            if new_gate and new_gate.exists():
                # A directory-fsync error can occur after the snapshot committed.
                # Do not delete geometry that the committed checkpoint references.
                try:
                    committed=Workspace.load(checkpoint)
                    referenced=committed.default_gate_session and committed.default_gate_session.absolute_path==str(new_gate.resolve())
                except (OSError,ValueError,TypeError,KeyError):referenced=False
                if referenced:self.recovery_path=checkpoint;self._recovery_gate_path=new_gate
                else:
                    try:new_gate.unlink(missing_ok=True)
                    except OSError:pass
            self.main.status_var.set('Workspace recovery could not be saved: ' + str(exc))

    def confirm_close(self):
        self.commit_focused_name()
        for app in list(self.apps.values()): self.capture(app)
        if not (self.dirty or self.gates_dirty): return True
        answer = messagebox.askyesnocancel('Workspace', 'Save changes before closing?', parent=self.main.root)
        if answer is None: return False
        if answer: return self.save()
        self.discard_recovery()
        return True

    def dispose(self):
        self._disposed = True
        self.cancel_scan()
        for attr in ('_autosave', '_recovery_offer'):
            token = getattr(self, attr, None)
            if token:
                try: self.main.root.after_cancel(token)
                except tk.TclError: pass
                setattr(self, attr, None)
        for app in self.apps.values():
            if hasattr(app, '_dispose_sidebar'): app._dispose_sidebar()
            for attr in ('_refresh_pending', '_sens_rerun_pending'):
                token = getattr(app, attr, None)
                if token:
                    try: app.root.after_cancel(token)
                    except tk.TclError: pass
                    setattr(app, attr, None)
            canvas = getattr(app, 'canvas', None)
            token = getattr(canvas, '_idle_draw_id', None)
            if token:
                try: canvas.get_tk_widget().after_cancel(token)
                except tk.TclError: pass
                canvas._idle_draw_id = None

    def discard_recovery(self):
        if self.recovery_path:
            try: self.recovery_path.unlink(missing_ok=True)
            except OSError: pass
        if self._recovery_gate_path:
            try:self._recovery_gate_path.unlink(missing_ok=True)
            except OSError:pass
        self.recovery_path=None;self._recovery_gate_path=None

    def gate_bundle(self):
        return {'vflow_workspace_gates': 1, 'workspace_id': self.document.workspace_id,
            'tabs': {tab_id: {'population_lineage': copy.deepcopy(self.apps[tab_id].population_lineage) if tab_id in self.apps else self._loaded_lineages.get(tab_id, []),
                'global_session': session_payload(store.global_gates),
                'sample_sessions': {sid: session_payload([g for g in gates.values() if g is not None])
                    for sid, gates in store.sample_overrides.items()},
                'sample_deleted_gate_ids': {sid: [gid for gid, g in gates.items() if g is None]
                    for sid, gates in store.sample_overrides.items()}}
                for tab_id, store in self.stores.items()}}

    def save(self, save_as=False, path=None):
        self.commit_focused_name()
        for app in list(self.apps.values()): self.capture(app)
        document=self.document
        dest = path or self.path
        choose_destination=save_as or not dest
        if choose_destination:
            dest = path or filedialog.asksaveasfilename(parent=self.main.root, title='Save Workspace',
                initialfile=Path(self.path).name if self.path else self.suggested_filename(),
                defaultextension='.vflow', filetypes=[('vFlow workspace', '*.vflow')])
        if not dest or self._disposed or self.document is not document: return False
        if choose_destination:
            self.commit_focused_name()
            for app in list(self.apps.values()):self.capture(app)
        dest = str(Path(dest).absolute())
        staged=copy.deepcopy(self.document)
        try:
            if getattr(document,'_disk_nominal_path',None)==dest and getattr(document,'_disk_path',None)!=str(Path(dest).resolve()):
                raise ValueError('The saved workspace location changed outside this session. Your edits remain open; use Save As or reopen the file.')
            if getattr(document,'_disk_path',None)==str(Path(dest).resolve()):check_revision(dest,document._disk_revision)
            from vflow.io.export_safety import validate_export_destination,protected_app_paths
            validate_export_destination(dest,[p for p in protected_app_paths(self.main) if p!=self.path])
            if self.gates_dirty or (save_as and any(s.global_gates or s.sample_overrides for s in self.stores.values())):
                if self._default_gates_unavailable:
                    raise ValueError('The referenced all-samples gate session is unavailable. Relink it or explicitly assign a replacement before saving gate changes.')
                # A unique revision file keeps the last explicitly saved workspace usable
                # if the final workspace replace fails. Never overwrite an imported session.
                gate_path = Path(dest).with_name(Path(dest).stem + '_gates_' + uuid.uuid4().hex[:12] + '.json')
                atomic_json(gate_path, self.gate_bundle())
                staged.default_gate_session = FileReference.create(gate_path, dest, kind='gates')
            from vflow.statistics.audit_serialization import read_bundle,copy_bundle
            audit_folder=Path(dest).with_name(Path(dest).stem+'_audits')
            for audit in staged.audits.values():
                old=audit.result.resolve(self.path)
                target=audit_folder/(audit.audit_id+'.vflowaudit.json.gz')
                if old and Path(old).resolve()!=target.resolve():
                    read_bundle(audit,self.path)
                    if not target.exists():copy_bundle(old,target)
                    if not audit.result.matches(target):raise ValueError('Existing audit bundle destination has a different identity.')
                    audit.result=FileReference.create(target,dest,kind='audit')
            staged.save(dest)
        except (OSError, ValueError, TypeError) as exc:
            messagebox.showerror('Save Workspace', str(exc), parent=self.main.root)
            return False
        # Publish references only after the workspace itself was written. Keep
        # audit objects stable so open review dialogs remain attached.
        for sid,sample in self.document.samples.items():
            sample.source.relative_path=staged.samples[sid].source.relative_path
            if sample.gate_session:sample.gate_session.relative_path=staged.samples[sid].gate_session.relative_path
        self.document.default_gate_session=staged.default_gate_session
        for aid,audit in self.document.audits.items():audit.result=staged.audits[aid].result
        self.document._disk_path=staged._disk_path;self.document._disk_nominal_path=staged._disk_nominal_path;self.document._disk_revision=staged._disk_revision
        self.path = dest
        self.dirty = False; self.gates_dirty = False
        self.discard_recovery()
        self.recent_add(dest)
        self.title()
        self._last_state = None
        self.capture(self.main)
        self.main.status_var.set('Workspace saved: ' + Path(dest).name)
        return True

    def suggested_filename(self):
        # A display name may contain characters that cannot be used in filenames.
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', self.workspace_name()).strip(' .')
        return (name or 'Workspace') + '.vflow'

    def recent_add(self, path):
        try:
            recent = self.recents()
            atomic_json(self.recent_path, [path] + [p for p in recent if p != path][:9])
        except (OSError, ValueError): pass
        self.refresh_recent_menu()

    def recents(self):
        try:
            result = json.loads(self.recent_path.read_text())
            return result if isinstance(result, list) else []
        except (OSError, ValueError): return []

    def refresh_recent_menu(self):
        menu = getattr(self, '_recent_menu', None)
        if menu is not None: self.populate_recent_menu(menu)
        for app in self.apps.values():
            menu = getattr(app, '_workspace_recent_menu', None)
            if menu is not None: self.populate_recent_menu(menu)

    def populate_recent_menu(self, menu):
        menu.delete(0, 'end')
        for path in self.recents(): menu.add_command(label=path, command=lambda p=path: self.open(p))
        if not self.recents(): menu.add_command(label='No recent workspaces', state='disabled')

    def clear(self):
        self.cancel_scan()
        self.restoring = True
        try:
            manager = self.main.manager
            if manager:
                for i in range(len(manager._apps) - 1, 0, -1): manager._close_tab(i)
            h = self.main
            h.loaded_files.clear(); h.excluded_files.clear(); h.file_vars.clear(); h.file_colors.clear()
            h.gates = []; h.gate_stats.clear(); h.axis_aliases.clear()
            h.population_lineage = []; h.parent_gate = None; h.parent_region = None
            h.x_channel = h.y_channel = None
            h.x_var.set(''); h.y_var.set('')
            h._invalidate_analysis_caches(data_changed=True)
            for w in h.file_list_frame.winfo_children(): w.destroy()
            h._rebuild_excluded_list(); h._rebuild_gate_manager(); h._rebuild_thresh_panel(); h._update_stats_display()
            self.apps = {'main': h}; self.stores = {'main': GateStore()}; self._loaded_lineages = {}; self._unloaded_sample_ids = {}
            h._workspace_tab_id = 'main'; h._workspace_materialized = False; h._workspace_view_key = None
            h._workspace_scope_sample = None
            h._workspace_selected_scope = (); h._workspace_gate_baseline = []
            h.auto_gate_input_var.set('Active samples (pooled)')
            h._last_auto_fit_signature = None; h._last_auto_gate_fn = None
            h.gate_scope_var.set('All samples (default)'); h.view_mode_var.set('overlay')
            self.document = Workspace(); self.path = None; self.missing = {}; self.errors = []
            self.dirty = False; self.gates_dirty = False; self._last_state = None
            self._default_gates_unavailable = False
            self.recovery_path=None;self._recovery_gate_path=None
        finally: self.restoring = False
        self.update_tree(self.main); self.title(force_name=True); self.main.refresh_plot()

    def new(self):
        if self.confirm_close(): self.clear()

    def open_dialog(self):
        path = filedialog.askopenfilename(parent=self.main.root, title='Open Workspace', filetypes=[('vFlow workspace', '*.vflow')])
        if path: self.open(path)

    def open(self, path):
        try:
            doc = Workspace.load(path)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            messagebox.showerror('Open Workspace', str(exc), parent=self.main.root); return False
        document=self.document
        if not self.confirm_close() or self._disposed or self.document is not document:return False
        recovered=None;recovered_gate=None;recovery_gates=False
        try:
            # The close prompt may have saved this same target. Read it again.
            doc=Workspace.load(path)
            base=Path(path);candidates=[Path(str(path)+'.recovery')]+list(base.parent.glob(base.name+'.recovery.*.vflow'))
            candidates=sorted((p for p in candidates if p.is_file() and p.stat().st_mtime_ns>base.stat().st_mtime_ns),key=lambda p:p.stat().st_mtime_ns,reverse=True)
            for checkpoint in candidates:
                try:snapshot=Workspace.load(checkpoint)
                except (OSError,ValueError,TypeError,KeyError):continue
                if snapshot.workspace_id!=doc.workspace_id:continue
                legacy='recovery_base_revision' not in snapshot.ui_state
                text='A newer recovery checkpoint exists. Restore samples, exclusions, gates and review decisions?'
                if legacy:text+='\nThis older state-only checkpoint does not include unsaved gate geometry.'
                if messagebox.askyesno('Workspace recovery',text,parent=self.main.root):
                    snapshot._disk_path=doc._disk_path;snapshot._disk_nominal_path=doc._disk_nominal_path
                    snapshot._disk_revision=snapshot.ui_state.get('recovery_base_revision',doc._disk_revision)
                    doc=snapshot;recovered=checkpoint;recovery_gates=bool(doc.ui_state.get('unsaved_gate_changes'))
                    if doc.default_gate_session and doc.default_gate_session.absolute_path.startswith(str(checkpoint)+'.gates.'):
                        recovered_gate=Path(doc.default_gate_session.absolute_path)
                break
        except (OSError,ValueError,TypeError,KeyError) as exc:
            messagebox.showerror('Open Workspace',str(exc),parent=self.main.root);return False
        self.clear()
        self.document = doc; self.path = str(Path(path).absolute())
        self.recovery_path=recovered;self._recovery_gate_path=recovered_gate
        self.restoring = True
        try:
            self.reload_resources()
            self.restore_tabs()
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self.errors.append(str(exc))
        finally: self.restoring = False
        self.dirty = recovered is not None; self.gates_dirty = recovered is not None and recovery_gates; self._last_state = None
        for key in ('unsaved_gate_changes','recovery_base_revision','recovery_origin_path'):self.document.ui_state.pop(key,None)
        active_tab = self.document.ui_state.get('active_tab_id')
        self.restore_ui(self.main)
        self.main.refresh_plot()
        manager = self.main.manager
        if manager and active_tab in self.apps:
            manager.notebook.select(manager._apps.index(self.apps[active_tab]))
        self.title(force_name=True); self.recent_add(self.path)
        if self.missing or self.errors:
            self.main.status_var.set(f'{len(self.missing)} missing references · {len(self.errors)} errors · Find Missing Files…')
            messagebox.showwarning('Workspace opened with unavailable resources',
                '\n'.join([f'{len(self.missing)} references unavailable. Use Find Missing Files to recover them.'] + self.errors[:8]), parent=self.main.root)
        return True

    def reload_resources(self):
        from vflow.config.constants import FILE_COLORS
        self.missing = {}; self.errors = []
        resolved = {}
        for key, ref in self.document.references():
            path = ref.resolve(self.path)
            if path:
                ref.accept(path, self.path); resolved[key] = path
            else: self.missing[key] = ref
        h = self.main
        h.axis_aliases = dict(self.document.axis_aliases)
        # Relinking can move a still-loaded acquisition. Retire its old key
        # before reloading the verified source, preserving the recorded sample ID.
        identities={(s.source.absolute_path,s.source_member_id) for s in self.document.samples.values()}
        retired=[]
        for mapping in (h.loaded_files,h.excluded_files):
            for key,df in list(mapping.items()):
                source=df.attrs.get('vflow_source_path',key) if df is not None else str(Path(key).resolve())
                member=df.attrs.get('vflow_source_member_id') if df is not None else None
                unloaded=self.document.samples.get(self._unloaded_sample_ids.get(key)) if df is None else None
                if unloaded is not None:source,member=unloaded.source.absolute_path,unloaded.source_member_id
                if (source,member) not in identities:
                    mapping.pop(key);h.file_vars.pop(key,None);h.file_colors.pop(key,None);self._unloaded_sample_ids.pop(key,None);retired.append(key)
        if retired:
            for widget in h.file_list_frame.winfo_children():widget.destroy()
            for key in h.loaded_files:h._add_file_row(key)
        for sid, sample in self.document.samples.items():
            path = resolved.get('sample:' + sid)
            if not path:
                if sample.excluded:self.retain_unloaded_exclusion(sid)
                continue
            key=self.path_for(sid)
            if key in h.loaded_files or h.excluded_files.get(key) is not None: continue
            try:
                if sample.source_member_id:
                    from vflow.io.registry import read_flow_source
                    payload=read_flow_source(path)
                    member=next((m for m in payload.samples if m.source_member_id==sample.source_member_id),None)
                    if member is None: raise ValueError('Original source member is unavailable.')
                    df=member.dataframe
                    path=member.materialized_path if len(payload.samples)>1 else path
                else: df = h._read_data_file(path)
                df.attrs['vflow_sample_key'] = path
                df.attrs.setdefault('vflow_source_path', path)
                df, aliases = h._apply_axis_aliases_to_df(df, path)
                if aliases['ambiguous']: raise ValueError('Ambiguous confirmed channel aliases.')
                for stale,value in list(self._unloaded_sample_ids.items()):
                    if value==sid:
                        if h.excluded_files.get(stale) is None:h.excluded_files.pop(stale,None)
                        self._unloaded_sample_ids.pop(stale,None)
                h.file_colors[path] = FILE_COLORS[len(h.file_colors) % len(FILE_COLORS)]
                if sample.excluded: h.excluded_files[path] = df
                else:
                    h._add_file_row(path); h.loaded_files[path] = df; h.file_vars[path].set(sample.active)
            except Exception as exc:
                # Keep an unloaded exclusion visible even when its source exists
                # but decoding is unavailable. A later reload may retry it.
                if sample.excluded:self.retain_unloaded_exclusion(sid)
                self.errors.append(sample.display_name + ': ' + str(exc)); self.missing['sample:' + sid] = sample.source
        h._rebuild_excluded_list(); h._invalidate_analysis_caches(data_changed=True)
        managed_samples = set()
        default = resolved.get('gate:default')
        self._default_gates_unavailable = bool(self.document.default_gate_session and not default)
        if default:
            try:
                with open(default, encoding='utf-8') as f: payload = json.load(f)
                if 'vflow_workspace_gates' in payload:
                    if payload['vflow_workspace_gates'] != 1 or payload.get('workspace_id') != self.document.workspace_id:
                        raise ValueError('Unsupported or unrelated workspace gate bundle.')
                    staged = {}
                    for tab_id, item in payload['tabs'].items():
                        store = GateStore(decode_session(item['global_session']))
                        for sid, session in item.get('sample_sessions', {}).items():
                            store.sample_overrides[sid] = {g['id']: g for g in decode_session(session)}
                            managed_samples.add(sid)
                        for sid, ids in item.get('sample_deleted_gate_ids', {}).items():
                            store.sample_overrides.setdefault(sid, {}).update({int(gid): None for gid in ids})
                        staged[tab_id] = store
                        self._loaded_lineages[tab_id] = copy.deepcopy(item.get('population_lineage', []))
                    self.stores.update(staged)
                else:
                    view = self.document.overlay_view
                    state = AnalysisState(view.x_channel, view.y_channel, view.x_transform, view.y_transform, view.cofactor)
                    if payload.get('population_lineage'): raise ValueError('Sub-gate session must be assigned to its matching child tab.')
                    self.stores['main'] = GateStore(decode_session(payload, state.context_dict()))
            except Exception as exc:
                self._default_gates_unavailable = True
                self.errors.append('Default gate session: ' + str(exc))
        for sid, sample in self.document.samples.items():
            path = resolved.get('gate:' + sid)
            if not path or sid in managed_samples: continue
            try:
                with open(path, encoding='utf-8') as f: payload = json.load(f)
                view = sample.view or self.document.overlay_view
                state = AnalysisState(view.x_channel, view.y_channel, view.x_transform, view.y_transform, view.cofactor)
                if payload.get('population_lineage'): raise ValueError('Sample gate session contains unmatched parent lineage.')
                gates = decode_session(payload, state.context_dict())
                self.stores['main'].sample_overrides[sid] = {g['id']: g for g in gates}
            except Exception as exc: self.errors.append(sample.display_name + ' gate session: ' + str(exc))
        for app in self.apps.values(): app._workspace_materialized = False

    def restore_tabs(self):
        manager = self.main.manager
        if not manager: return
        for tab_id, tab in list(self.document.tabs.items()):
            if tab_id == 'main' or tab_id in self.apps: continue
            app = manager._new_tab(title=' ↳ ' + tab.get('title', 'Population'), parent_label=tab.get('title', 'Population'),
                filtered_data=None, default_x=None, default_y=None)
            old_id = app._workspace_tab_id
            self.apps.pop(old_id, None); self.stores.pop(old_id, None)
            self.document.tabs.pop(old_id,None)
            self.register(app, tab_id)
            app.population_lineage = copy.deepcopy(self._loaded_lineages.get(tab_id, []))
            if tab.get('lineage') and not app.population_lineage:
                self.errors.append(tab.get('title', 'Population') + ': parent gate session unavailable')
            self.refresh_child(app)
            self.restore_ui(app)
        if manager._apps: manager.notebook.select(0)

    def refresh_child(self, app):
        if app is self.main: return
        if self.document.tabs.get(app._workspace_tab_id, {}).get('lineage') and not app.population_lineage:
            stages=[]
            for ref in self.document.tabs[app._workspace_tab_id]['lineage']:
                store=self.stores.get(ref.get('workspace_tab_id'))
                gate=store.resolve_gate(None,ref.get('gate_id')) if store else None
                if not gate and store:
                    gate=next((store.resolve_gate(sid,ref.get('gate_id')) for sid in store.sample_overrides if store.resolve_gate(sid,ref.get('gate_id'))),None)
                if not gate: stages=[];break
                stages.append({'workspace_tab_id':ref['workspace_tab_id'],'gate':gate,
                               'context':copy.deepcopy(gate['_analysis_context']),'region':ref['region']})
            if stages: app.population_lineage=stages;app._workspace_display_signature=None
            else:
                app.loaded_files = {}; app._invalidate_analysis_caches(data_changed=True)
                app._workspace_parent_warning = 'Parent population unavailable: missing gate session'
                app.status_var.set(app._workspace_parent_warning)
                return
        sources = {**self.main.loaded_files, **self.main.excluded_files}
        tab = self.document.tabs.get(app._workspace_tab_id, {})
        membership = tab.get('sample_ids')
        if membership is None:
            membership = [self.sample_id(p) for p in app.loaded_files]
            tab['sample_ids'] = membership
        ancestor_ids = {stage.get('workspace_tab_id') for stage in app.population_lineage if stage.get('workspace_tab_id')}
        signature = tuple((k, self.stores[k].revision if k in self.stores else None) for k in sorted(ancestor_ids)) + (self.main._data_generation, tuple(self.main.loaded_files), tuple(self.main.excluded_files), tuple(membership))
        if signature == app._workspace_display_signature: return
        app._workspace_display_signature = signature
        frames = {}; failures = []
        for path, df in sources.items():
            sid = self.sample_id(path)
            if path in self.main.excluded_files or sid not in membership: continue
            try:
                lineage = resolve_lineage_for_sample(sid, app.population_lineage, self.stores)
                frames[path] = filter_lineage(df, lineage)
            except ValueError as exc: failures.append(Path(path).name + ': ' + str(exc))
        for w in app.file_list_frame.winfo_children(): w.destroy()
        old_vars = app.file_vars.copy()
        previous_keys=set(old_vars)
        app.loaded_files = frames; app.file_colors = dict(self.main.file_colors); app.file_vars = old_vars
        for path in frames: app._add_file_row(path)
        saved_active=tab.get('ui_state',{}).get('active_sample_ids')
        if saved_active is not None:
            for path in frames:
                if path not in previous_keys:app.file_vars[path].set(self.sample_id(path) in saved_active)
        app._invalidate_analysis_caches(data_changed=True)
        app._workspace_parent_warning = 'Parent population unavailable: ' + '; '.join(failures) if failures else ''
        if failures: app.status_var.set(app._workspace_parent_warning)

    def restore_ui(self, app):
        tab = self.tab_state(app); ui = tab.get('ui_state') or (self.document.ui_state if app is self.main else {})
        app.view_mode_var.set(ui.get('view_mode', 'overlay'))
        if app is not self.main and 'active_sample_ids' in ui:
            active_ids=set(ui['active_sample_ids'])
            for path,var in app.file_vars.items(): var.set(self.sample_id(path) in active_ids)
        active = list(app._active())
        path = self.path_for(ui.get('current_sample_id'))
        app.cycle_idx = active.index(path) if path in active else 0
        app.gate_scope_var.set('All samples (default)')  # editing scope always starts safely
        app.auto_gate_input_var.set(ui.get('auto_gate_input', 'Active samples (pooled)'))
        app.interface_size_var.set(ui.get('interface_size', 'Automatic')); app._apply_interface_size()
        if hasattr(app, '_sidebar_restoring'): app._sidebar_restoring = True
        try:
            for name, expanded in tab.get('sections', {}).items():
                if name in app._sections: app._sections[name][0].set(expanded); app._toggle_section(name)
        finally:
            if hasattr(app, '_sidebar_restoring'): app._sidebar_restoring = False
        width = ui.get('sidebar_width')
        if isinstance(width, (int, float)) and width > 0: app._main_pane.paneconfigure(app._side_outer, width=int(width))
        app._workspace_view_key = None; app._workspace_materialized = False
        self.before_render(app)
        app._workspace_tree.selection_set([sid for sid in ui.get('selected_sample_ids', []) if app._workspace_tree.exists(sid)])
        selected = ui.get('selected_gate_id')
        if any(g['id'] == selected for g in app.gates): app._sel_gate_id = selected
        if hasattr(app, '_restore_sidebar_state'): app._restore_sidebar_state(ui)

    def before_render(self, app):
        if self.restoring: return
        self.sync_sources()
        self.refresh_child(app)
        tab = self.tab_state(app)
        key = self.current_sid(app) if app.view_mode_var.get() == 'cycle' else 'overlay'
        if key != app._workspace_view_key:
            if app._workspace_view_key is not None: self.capture(app)
            old_view = self.capture_view(app)
            app._workspace_view_key = key
            data = tab.get('overlay_view') if key == 'overlay' else tab['sample_views'].get(key)
            if not data and key in self.document.samples and app is self.main:
                sample_view = self.document.samples[key].view
                data = asdict(sample_view) if sample_view else None
            self.apply_view(app, ViewState.from_dict(data) if data else old_view)
            app._workspace_materialized = False
        scope = self.current_sid(app) if app.gate_scope_var.get() == 'Current sample' else None
        if app.gate_scope_var.get() == 'Selected samples': scope = app._workspace_selected_scope
        if app.view_mode_var.get() == 'overlay' and scope is not None:
            app.gate_scope_var.set('All samples (default)'); scope = None
        if not app._workspace_materialized or scope != app._workspace_scope_sample:
            self.materialize(app, scope)
        if self.commit_gates(app): app._recompute_all_gate_stats()
        self.update_tree(app)

    def materialize(self, app, sample_scope=None):
        store = self.stores[app._workspace_tab_id]
        representative = sample_scope[0] if isinstance(sample_scope, tuple) and sample_scope else sample_scope
        gates = store.resolve_gate_set(representative) if representative else copy.deepcopy(store.global_gates)
        app.gates = [live(g, app.root) for g in gates]
        app._workspace_gate_baseline = copy.deepcopy(gates)
        app._workspace_scope_sample = sample_scope
        app._workspace_materialized = True
        app._next_gate_id = max([g['id'] for g in store.global_gates] + [gid for m in store.sample_overrides.values() for gid in m], default=-1) + 1
        if not any(g['id'] == app._sel_gate_id for g in gates): app._sel_gate_id = gates[-1]['id'] if gates else None
        app._invalidate_analysis_caches()
        app._rebuild_gate_manager(); app._rebuild_thresh_panel()
        app._recompute_all_gate_stats()

    def apply_view(self, app, view):
        view.validate()
        app._workspace_applying_view = True
        try:
            app.x_channel = view.x_channel; app.y_channel = view.y_channel
            app.x_scale = view.x_transform; app.y_scale = view.y_transform; app.cofactor = view.cofactor
            app.x_transform_params = copy.deepcopy(view.x_transform_params); app.y_transform_params = copy.deepcopy(view.y_transform_params)
            app.x_var.set(view.x_channel or ''); app.y_var.set(view.y_channel or '')
            app.x_scale_var.set(view.x_transform); app.y_scale_var.set(view.y_transform)
            app.cofactor_str.set(str(view.cofactor)); app.plot_type_var.set(view.plot_mode)
            app.lock_scale_var.set(view.axis_fit_mode == 'locked'); app.fit_axes_var.set(view.axis_fit_mode == 'fit')
            app._locked_xlim = copy.deepcopy((view.axis_limits or {}).get('x'))
            app._locked_ylim = copy.deepcopy((view.axis_limits or {}).get('y'))
            # Exact union in Cycle, exact intersection in Overlay. Never pick replacement axes.
            frames = list(app._display_files().values())
            cols = set(frames[0].columns) if frames else set()
            for df in frames[1:]: cols.intersection_update(df.columns)
            app.x_menu['values'] = sorted(cols); app.y_menu['values'] = sorted(cols)
            missing = view.missing_channels(cols)
            app._workspace_view_warning = ('Saved view unavailable. Required channel: ' + ', '.join(missing)) if missing else ''
            app._invalidate_analysis_caches()
        finally: app._workspace_applying_view = False

    def navigate(self, app, delta=None):
        self.capture(app)
        if delta is not None:
            n = len(app._active())
            if n: app.cycle_idx = (app.cycle_idx + delta) % n
        if app.view_mode_var.get() == 'overlay': app.gate_scope_var.set('All samples (default)')
        state = tk.NORMAL if app.view_mode_var.get() == 'cycle' else tk.DISABLED
        app._btn_prev.config(state=state); app._btn_next.config(state=state)
        app._workspace_materialized = False
        app.refresh_plot()
        self.mark_dirty()

    def scope_changed(self, app):
        self.capture(app)
        if app.gate_scope_var.get() == 'Selected samples':
            targets = tuple(app._workspace_tree.selection())
            available = all(self.path_for(sid) in app.loaded_files for sid in targets)
            active = list(app._active())
            if not targets or not available or any(self.path_for(sid) not in active for sid in targets):
                app.gate_scope_var.set('All samples (default)')
                self.navigate(app)
                app.status_var.set('Select active target samples first. Use Apply to selected samples to copy to inactive targets.')
                return
            app._workspace_selected_scope = targets
            app.view_mode_var.set('cycle')
            path = self.path_for(targets[0])
            app.cycle_idx = active.index(path)
        if app.gate_scope_var.get() == 'Current sample':
            if not app._active():
                app.gate_scope_var.set('All samples (default)'); return
            if app.view_mode_var.get() == 'overlay': app.view_mode_var.set('cycle')
        self.navigate(app)
        target_label = (f'{len(app._workspace_selected_scope)} selected samples' if app.gate_scope_var.get() == 'Selected samples' else
            self.document.samples[self.current_sid(app)].display_name if app.gate_scope_var.get() == 'Current sample' else 'All samples')
        app.status_var.set('Editing gates for: ' + target_label)

    def resolved_gate(self, app, path, gate):
        sid = self.sample_id(path)
        resolved = self.stores[app._workspace_tab_id].resolve_gate(sid, gate['id'])
        if resolved is None: return None
        return resolved

    def gate_action(self, app, action, gid, targets=None):
        if not self.gate_editing_available(app): return
        self.capture(app)
        store = self.stores[app._workspace_tab_id]
        sid = self.current_sid(app)
        source = next((plain(g) for g in app.gates if g['id'] == gid), None)
        if action == 'copy' and app.view_mode_var.get() == 'cycle': source = store.resolve_gate(sid, gid)
        if source is None: source = store.resolve_gate(sid if app.view_mode_var.get() == 'cycle' else None, gid)
        try:
            if action == 'undo':
                if not store.undo(): app.status_var.set('No gate changes to undo.'); return
            elif action == 'reset': store.reset(sid, gid)
            elif action == 'promote': store.promote(sid, gid)
            elif action == 'workspace':
                if source is None: raise ValueError('Source gate unavailable.')
                # The shared gate is inherited even by inactive/missing samples.
                # Incompatible populations remain unavailable; no channel mapping is invented.
                store.apply_workspace(source)
            elif action == 'copy':
                if source is None: raise ValueError('Source gate unavailable.')
                # Validate every target before changing any target.
                targets = list(dict.fromkeys(targets or []))
                if not targets: raise ValueError('Select target samples in the Samples list first.')
                for target in targets: self.validate_gate_target(app, source, target)
                store.checkpoint()
                for target in targets: store.sample_overrides.setdefault(target, {})[gid] = plain(source)
                store.revision += 1
            self.gates_dirty = True; self.mark_dirty()
            app._workspace_materialized = False; app.refresh_plot()
            app.status_var.set('Gate change applied · Undo available in Edit menu')
            if action == 'workspace': app.status_var.set('Gate applied to entire workspace; its sample overrides cleared. Undo available.')
        except ValueError as exc: messagebox.showwarning('Gate operation', str(exc), parent=app.root)

    def copy_dialog(self, app, gid):
        dlg = tk.Toplevel(app.root); dlg.title('Copy gate to samples')
        tree = ttk.Treeview(dlg, show='tree', selectmode='extended', height=12)
        tree.pack(fill='both', expand=True, padx=12, pady=12)
        for sid, sample in self.document.samples.items():
            if self.path_for(sid) in self.main.loaded_files: tree.insert('', 'end', iid=sid, text=sample.display_name)
        def apply():
            targets = list(tree.selection())
            if targets: self.gate_action(app, 'copy', gid, targets); dlg.destroy()
        ttk.Button(dlg, text='Copy to selected samples', command=apply).pack(pady=8)

    def assign_session(self, sid=None):
        path = filedialog.askopenfilename(parent=self.main.root, title='Assign gate session', filetypes=[('Gate session', '*.json')])
        if not path: return
        try:
            with open(path, encoding='utf-8') as f: payload = json.load(f)
            view = self.document.samples[sid].view if sid else self.document.overlay_view
            view = view or self.document.overlay_view
            ctx = AnalysisState(view.x_channel, view.y_channel, view.x_transform, view.y_transform, view.cofactor).context_dict()
            if payload.get('population_lineage'): raise ValueError('Assign this session in its matching child population tab.')
            gates = decode_session(payload, ctx)
            ref = FileReference.create(path, self.path, 'gates')
            store = self.stores['main']; store.checkpoint()
            if sid:
                self.document.samples[sid].gate_session = ref
                store.sample_overrides[sid] = {g['id']: g for g in gates}
            else:
                self.document.default_gate_session = ref; store.global_gates = gates
                self._default_gates_unavailable = False; self.missing.pop('gate:default',None)
            store.revision += 1
            self.gates_dirty = True; self.mark_dirty()
            for app in self.apps.values(): app._workspace_materialized = False
            self.main.refresh_plot()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            messagebox.showerror('Assign gate session', str(exc), parent=self.main.root)

    def gate_editing_available(self, app):
        if not self._default_gates_unavailable: return True
        app.status_var.set('Gate editing unavailable. Relink the missing all-samples gate session or explicitly assign a replacement.')
        return False

    def remember_native_session(self, app, path):
        ref = FileReference.create(path, self.path, 'gates')
        scope = app._workspace_scope_sample
        if app is self.main:
            if scope is None:
                self.document.default_gate_session = ref
                self._default_gates_unavailable = False; self.missing.pop('gate:default',None)
            else:
                for sid in scope if isinstance(scope, tuple) else (scope,):
                    self.document.samples[sid].gate_session = copy.deepcopy(ref)
        # Child-session saves/loads must not replace the workspace's root gate reference.
        # Workspace Save checkpoints the child's current gates in its referenced tab bundle.
        self.gates_dirty = True; self.mark_dirty()

    def update_tree(self, app):
        tree = getattr(app, '_workspace_tree', None)
        if tree is None: return
        selected = tree.selection()
        wanted = set(self.document.samples)
        for iid in tree.get_children():
            if iid not in wanted: tree.delete(iid)
        for sid, sample in self.document.samples.items():
            path=self.path_for(sid)
            active=bool(app.file_vars[path].get()) if path in app.loaded_files and path in app.file_vars else False
            status = ('Missing source' if 'sample:' + sid in self.missing else
                ('Excluded' if sample.excluded else ('' if app is self.main or path in app.loaded_files else 'Outside population')))
            custom = any(sid in s.sample_overrides and s.sample_overrides[sid] for s in self.stores.values())
            if 'gate:' + sid in self.missing: status = 'Gate file missing'
            elif custom or sample.gate_session: status = status or 'Custom gates'
            df = self.main.loaded_files.get(self.path_for(sid), self.main.excluded_files.get(self.path_for(sid)))
            if df is not None:
                gates = self.stores[app._workspace_tab_id].resolve_gate_set(sid)
                if any(g.get('applied') and any(g.get('_analysis_context', {}).get(k) not in df for k in ('x_channel','y_channel')) for g in gates):
                    status = 'Gate unavailable'
            values = ('[x]' if active else '[ ]' if path in app.loaded_files else '--',status)
            label=sample.display_name
            if status and 'state' not in tuple(tree.cget('displaycolumns')):
                label += ' [' + ('Custom' if status=='Custom gates' else status) + ']'
            icon = app._sample_icon(path) if hasattr(app, '_sample_icon') else ''
            if tree.exists(sid): tree.item(sid, text=label, values=values, image=icon)
            else: tree.insert('', 'end', iid=sid, text=label, values=values, image=icon)
        for sid in selected:
            if tree.exists(sid): tree.selection_add(sid)
        if hasattr(app, '_workspace_scope_label'):
            scope = ('This sample only' if app.gate_scope_var.get() == 'Current sample' else 'All samples')
            if app.gate_scope_var.get() == 'Selected samples': scope = f'{len(app._workspace_selected_scope)} selected samples'
            current = self.current_sid(app)
            name = self.document.samples[current].display_name if current in self.document.samples else 'No sample'
            active_count = len(app._active())
            name = name if len(name)<=40 else name[:37]+'…'
            cycle = f'{app.cycle_idx % active_count + 1}/{active_count} ' if active_count else ''
            app._workspace_scope_label.set(f'{cycle + name + " · " if app.view_mode_var.get() == "cycle" else ""}Gates apply to: {scope}')
        if hasattr(app, '_workspace_summary_var'):
            count = len(self.stores[app._workspace_tab_id].global_gates)
            app._workspace_summary_var.set(f'{len(self.document.samples)} samples · {len(app._active())} active · {count} shared gates')
        if hasattr(app,'_sample_exclude_button'): app._update_sample_action_buttons()
        if hasattr(app,'_sample_pane_configured'): app._sample_pane_configured()

    def sample_menu(self, app, event=None, sid=None):
        tree = app._workspace_tree
        if event is not None and tree.identify_region(event.x, event.y) not in ('tree', 'cell'): return 'break'
        if sid is None: sid = tree.identify_row(event.y)
        if not sid or not tree.exists(sid): return 'break'
        if sid not in tree.selection(): tree.selection_set(sid)
        tree.focus(sid)
        previous=getattr(app,'_workspace_sample_menu',None)
        if previous is not None: previous.destroy()
        menu = tk.Menu(app.root, tearoff=False)
        menu.add_command(label='Show only this sample', command=lambda: self.show_sample(app, sid))
        path = self.path_for(sid)
        menu.add_command(label='Toggle active', command=lambda: self.toggle_sample(sid,app),
                         state='normal' if path in app.loaded_files else 'disabled')
        menu.entryconfigure(0, state='normal' if path in app.loaded_files else 'disabled')
        menu.add_command(label='Exclude from analysis', command=lambda: app._exclude_file(path),
                         state='normal' if path in app.loaded_files else 'disabled')
        menu.add_command(label='Restore to analysis', command=lambda: app._restore_file(path),
                         state='normal' if path in app.excluded_files else 'disabled')
        menu.add_command(label=app._file_manager_menu_label(), command=lambda: app._show_single_file_in_manager(path))
        menu.add_command(label='Assign gate session…', command=lambda: self.assign_session(sid))
        menu.add_command(label='Sample details…', command=lambda: self.sample_details(app, sid))
        menu.add_command(label='Reset saved view', command=lambda: self.reset_view(app, sid))
        menu.add_command(label='Locate source file…', command=lambda: self.locate_reference('sample:' + sid))
        menu.add_command(label='Find Missing Files…', command=self.find_missing)
        menu.add_command(label='Clear sample-specific gate session', command=lambda: self.clear_sample_session(sid))
        menu.add_separator(); menu.add_command(label='Remove from workspace', command=lambda: self.remove_sample(sid))
        app._workspace_sample_menu = menu
        x = event.x_root if event is not None else tree.winfo_rootx() + 15
        y = event.y_root if event is not None else tree.winfo_rooty() + tree.winfo_height()
        try: menu.tk_popup(x, y)
        finally: menu.grab_release()
        return 'break'

    def sample_hover_text(self, app, sid):
        if sid not in self.document.samples:
            return 'Activate samples with [x]. Select rows to choose fitting or gate-copy targets.'
        sample=self.document.samples[sid]
        values=app._workspace_tree.item(sid,'values')
        state=values[-1] if values and values[-1] else 'Inherited gates'
        view=sample.view or self.document.overlay_view
        return f'{sample.display_name}\n{state}\nSaved axes: {view.x_channel} × {view.y_channel}\nRight-click for source and gate-session details.'

    def sample_details(self, app, sid):
        sample = self.document.samples[sid]
        view = sample.view or self.document.overlay_view
        session = sample.gate_session or self.document.default_gate_session
        gates = self.stores[app._workspace_tab_id].resolve_gate_set(sid)
        df = self.main.loaded_files.get(self.path_for(sid), self.main.excluded_files.get(self.path_for(sid)))
        missing = sorted({g.get('_analysis_context', {}).get(k) for g in gates for k in ('x_channel','y_channel')
                          if df is not None and g.get('_analysis_context', {}).get(k) not in df} - {None})
        message = f'{sample.display_name}\nSource file: {sample.source.absolute_path}\n\nSaved axes: {view.x_channel} × {view.y_channel}\nTransforms: {view.x_transform} / {view.y_transform}\n'
        message += '\nGate session: ' + (session.absolute_path if session else 'None')
        if missing: message += '\nUnavailable gates require: ' + ', '.join(missing)
        messagebox.showinfo('Sample details', message, parent=app.root)

    def show_sample(self, app, sid):
        path = self.path_for(sid)
        if path not in app.loaded_files: return
        self.capture(app)
        app.file_vars[path].set(True); active = list(app._active())
        app.cycle_idx = active.index(path); app.view_mode_var.set('cycle')
        self.navigate(app)

    def toggle_sample(self, sid, app=None):
        app = app or self.main
        path = self.path_for(sid)
        if path in app.loaded_files and path in app.file_vars:
            self.set_sample_activity(app, {path: not app.file_vars[path].get()})

    def set_sample_activity(self, app, updates):
        """Change checkboxes without moving a still-active Cycle sample."""
        self.capture(app)
        previous = list(app._active())
        current = previous[app.cycle_idx % len(previous)] if previous else None
        for path, value in updates.items():
            if path in app.loaded_files and path in app.file_vars:
                app.file_vars[path].set(value)
        active = list(app._active())
        if current in active: app.cycle_idx = active.index(current)
        elif active: app.cycle_idx %= len(active)
        else: app.cycle_idx = 0
        app._on_active_files_changed()

    def reset_view(self, app, sid):
        self.tab_state(app)['sample_views'].pop(sid, None)
        if app is self.main: self.document.samples[sid].view = None
        if app.view_mode_var.get() == 'cycle' and self.current_sid(app) == sid:
            self.apply_view(app, ViewState.from_dict(self.tab_state(app).get('overlay_view')))
            app._workspace_view_key = None
            app.refresh_plot()
        self.mark_dirty()

    def remove_sample(self, sid):
        path = self.path_for(sid)
        sample = self.document.samples.pop(sid)
        for key,value in list(self._unloaded_sample_ids.items()):
            if value==sid:self._unloaded_sample_ids.pop(key,None)
        self.missing.pop('sample:' + sid, None); self.missing.pop('gate:' + sid, None)
        self.main.loaded_files.pop(path, None); self.main.excluded_files.pop(path, None); self.main.file_vars.pop(path, None)
        for store in self.stores.values(): store.sample_overrides.pop(sid, None)
        self.main._invalidate_analysis_caches(data_changed=True)
        for w in self.main.file_list_frame.winfo_children(): w.destroy()
        for p in self.main.loaded_files: self.main._add_file_row(p)
        self.main._rebuild_excluded_list(); self.main.refresh_plot(); self.mark_dirty()

    def clear_sample_session(self, sid):
        self.document.samples[sid].gate_session = None
        for store in self.stores.values():
            if sid in store.sample_overrides:
                store.checkpoint(); store.sample_overrides.pop(sid); store.revision += 1
        self.missing.pop('gate:' + sid, None)
        self.gates_dirty = True; self.mark_dirty()
        for app in self.apps.values(): app._workspace_materialized = False
        self.main.refresh_plot()

    def locate_reference(self, key):
        ref = dict(self.document.references()).get(key)
        if ref is None: return
        document=self.document
        path = filedialog.askopenfilename(parent=self.main.root, title='Locate ' + ref.filename)
        if not path or self._disposed or self.document is not document or dict(self.document.references()).get(key) is not ref:return
        # Capture under the old identity before changing its source path.
        for app in list(self.apps.values()): self.capture(app)
        try:
            ref.accept(path, self.path)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Locate file', str(exc), parent=self.main.root); return
        pending = self.stores.copy() if self.gates_dirty else None
        self.restoring = True
        try:
            self.reload_resources()
            if pending: self.stores.update(pending)
            self.restore_tabs()
        finally: self.restoring = False
        self.restore_ui(self.main); self.main.refresh_plot(); self.mark_dirty()

    def offer_unsaved_recovery(self):
        folder = self.state_dir / 'recovery'
        try: candidates = sorted(folder.glob('*.vflow'), key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError: return
        if not candidates or self.dirty: return
        snapshot=None
        for path in candidates:
            try:snapshot=Workspace.load(path);break
            except (OSError,ValueError,TypeError,KeyError):continue
        if snapshot is None:
            self.main.status_var.set('Unsaved recovery files are unavailable or invalid. Original saved workspaces were not changed.')
            return
        text='An unsaved workspace recovery is available. Restore samples, exclusions, gates and review decisions?'
        if 'recovery_base_revision' not in snapshot.ui_state:text+='\nThis older checkpoint does not include unsaved gate geometry.'
        if messagebox.askyesno('Workspace recovery', text, parent=self.main.root):
            gate=snapshot.default_gate_session
            if self.open(str(path)):
                self.path = None; self.recovery_path = path; self.dirty = True
                self.gates_dirty=bool(snapshot.ui_state.get('unsaved_gate_changes'))
                self._recovery_gate_path=Path(gate.absolute_path) if gate and gate.absolute_path.startswith(str(path)+'.gates.') else None
                for key in ('unsaved_gate_changes','recovery_base_revision','recovery_origin_path'):self.document.ui_state.pop(key,None)
                self.title()

    def cancel_scan(self):
        token=self._scan_poll
        self._scan_poll=None;self._scan_token=None;self._scan_running=False
        if token:
            try:self.main.root.after_cancel(token)
            except tk.TclError:pass

    def find_missing(self):
        if self._scan_running or self._disposed: return
        if not self.missing:
            self.missing = {k: r for k, r in self.document.references() if not r.resolve(self.path)}
        if not self.missing:
            messagebox.showinfo('Find Missing Files', 'All references are available.', parent=self.main.root); return
        for app in list(self.apps.values()): self.capture(app)
        document=self.document
        folder = filedialog.askdirectory(parent=self.main.root, title='Find Missing Files — search subfolders')
        if not folder or self.document is not document or self._disposed: return
        refs = list(self.missing.items()); result = {}; errors = []
        token=object();self._scan_token=token
        self._scan_running = True
        self.main.status_var.set('Scanning folders for identity-verified matches…')
        def work():
            try: result.update(scan_candidates(refs, folder, recursive=True))
            except OSError as exc: errors.append(str(exc))
        gc.collect()  # Retired Tk interpreters must be finalized on the GUI thread.
        thread = threading.Thread(target=work, daemon=True); thread.start()
        def current():
            return self._scan_token is token and not self._disposed and self.document is document
        def finish():
            if not current():return
            self._scan_poll=None
            if thread.is_alive(): self._scan_poll=self.main.root.after(100, finish); return
            if errors:
                self.cancel_scan();messagebox.showerror('Find Missing Files', '\n'.join(errors), parent=self.main.root);return
            if any(dict(self.document.references()).get(key) is not ref for key,ref in refs):
                self.cancel_scan();self.main.status_var.set('Workspace references changed; start Find Missing Files again.');return
            uniquely_found = [(key, candidates[0]) for key, candidates in result.items() if len(candidates) == 1]
            if len(uniquely_found) >= 2:
                from vflow.workspace.relink import bulk_remap
                ref_map = dict(refs)
                try:
                    old_root = os.path.commonpath([str(Path(ref_map[k].absolute_path).parent) for k, _ in uniquely_found])
                    new_root = os.path.commonpath([str(Path(p).parent) for _, p in uniquely_found])
                    remapped = bulk_remap(refs, old_root, new_root)
                    for key, candidate in remapped.items():
                        if not result.get(key): result[key] = [candidate]
                except ValueError: pass
            selected=[]
            for key, ref in refs:
                matches = result.get(key, [])
                chosen = matches[0] if len(matches) == 1 and ref.identity_fingerprint else None
                if len(matches) > 1 or (matches and not ref.identity_fingerprint):
                    dlg = tk.Toplevel(self.main.root); dlg.title('Choose matching file — ' + ref.filename)
                    listing = tk.Listbox(dlg, width=90, height=min(12, len(matches)), exportselection=False)
                    listing.pack(fill='both', expand=True)
                    for candidate in matches: listing.insert('end', candidate)
                    picked = []
                    def choose():
                        if listing.curselection(): picked.append(matches[listing.curselection()[0]]); dlg.destroy()
                    ttk.Button(dlg, text='Use selected match', command=choose).pack(pady=8)
                    ttk.Button(dlg, text='Leave unavailable', command=dlg.destroy).pack()
                    dlg.grab_set(); self.main.root.wait_window(dlg)
                    chosen = picked[0] if picked else None
                if not current():return
                if chosen:selected.append((ref,chosen))
            # Capture gate edits made while the worker/dialog was open, not a
            # stale copy from the start of the scan. Capture before rebasing sources.
            for app in list(self.apps.values()):self.capture(app)
            pending_stores=self.stores.copy() if self.gates_dirty else None
            for ref,chosen in selected:
                try:ref.accept(chosen,self.path)
                except (OSError,ValueError) as exc:errors.append(str(exc))
            self.restoring = True
            try:
                self.reload_resources()
                if pending_stores is not None: self.stores.update(pending_stores)
                self.restore_tabs()
            finally: self.restoring = False
            self.restore_ui(self.main); self.main.refresh_plot(); self.mark_dirty()
            self.cancel_scan()
            self.main.status_var.set(f'Relocation complete · {len(self.missing)} references still unavailable')
            if errors:messagebox.showerror('Find Missing Files','\n'.join(errors),parent=self.main.root)
        self._scan_poll=self.main.root.after(100, finish)

    def install_menu(self):
        root = self.main.root; bar = tk.Menu(root)
        file = tk.Menu(bar, tearoff=False)
        for label, command, shortcut in [('New Workspace', self.new, 'Ctrl+N'), ('Open Workspace…', self.open_dialog, 'Ctrl+O'),
            ('Save Workspace', self.save, 'Ctrl+S'), ('Save Workspace As…', lambda: self.save(True), 'Ctrl+Shift+S'),
            ('Close Workspace', self.new, '')]: file.add_command(label=label, command=command, accelerator=shortcut)
        self._recent_menu = tk.Menu(file, tearoff=False)
        file.add_cascade(label='Open Recent', menu=self._recent_menu); self.refresh_recent_menu()
        file.add_separator(); file.add_command(label='Find Missing Files…', command=self.find_missing)
        file.add_command(label='Assign all-samples gate session…', command=self.assign_session)
        bar.add_cascade(label='File', menu=file)
        from vflow.ui.statistical_audit_dialog import StatisticalAuditDialog, AuditListDialog
        audits = tk.Menu(bar, tearoff=False)
        audits.add_command(label='Statistical Audit…', command=lambda: StatisticalAuditDialog(self,self.current_app()))
        audits.add_command(label='Review saved audits…', command=lambda: AuditListDialog(self))
        bar.add_cascade(label='Statistical audits',menu=audits)
        edit = tk.Menu(bar, tearoff=False)
        def undo():
            app = self.current_app(); self.gate_action(app, 'undo', app._sel_gate_id)
        edit.add_command(label='Undo gate change', command=undo, accelerator='Ctrl+Z'); bar.add_cascade(label='Edit', menu=edit)
        view = tk.Menu(bar, tearoff=False)
        for mode in ('Automatic', 'Compact', 'Comfortable', 'Large'):
            view.add_command(label=mode, command=lambda m=mode: self.set_interface_size(m))
        view.add_command(label='Expand all controls', command=lambda: self.current_app()._set_all_sections(True))
        bar.add_cascade(label='Interface size', menu=view); root.config(menu=bar)
        for prefix in ('Control', 'Command'):
            for key, fn in [('n', self.new), ('o', self.open_dialog), ('s', self.save), ('Shift-S', lambda: self.save(True)), ('z', undo)]:
                def shortcut(event, command=fn, key=key):
                    # Descendant dialogs and editable-field undo own their keys.
                    if event.widget.winfo_toplevel() is not root: return
                    if key == 'z' and event.widget.winfo_class() in ('Entry', 'TEntry', 'Text', 'Spinbox', 'TSpinbox', 'TCombobox'):
                        return
                    command(); return 'break'
                try: root.bind('<' + prefix + '-' + key + '>', shortcut)
                except tk.TclError: pass
        def close():
            if self.confirm_close():
                self.discard_recovery(); self.dispose(); root.quit(); root.destroy()
        root.protocol('WM_DELETE_WINDOW', close)
        self._recovery_offer = root.after(150, self.offer_unsaved_recovery)
        self.title()

    def current_app(self):
        manager = self.main.manager
        if manager and manager._apps:
            return manager._apps[manager.notebook.index(manager.notebook.select())]
        return self.main

    def set_interface_size(self, mode):
        for app in self.apps.values(): app.interface_size_var.set(mode); app._apply_interface_size()
        self.mark_dirty()
