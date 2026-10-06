"""Real Tk integration: populations, immutable history, loading and worker commits."""
import copy
import json
import os
import time
from pathlib import Path
import tkinter as tk
import numpy as np
import pandas as pd
import pytest
from tests.test_workspace_gui import experiment,new_gate
from tests.format_fixtures import write_fixture
from vflow.statistics import run_audit
from vflow.statistics.workspace_audit import prepare_samples,commit,decide,decide_many
from vflow.statistics.audit_serialization import read_bundle,source_identity_warnings
from vflow.ui.statistical_audit_dialog import StatisticalAuditDialog,AuditResultsDialog,AuditListDialog
from vflow.ui.audit_interpretation import show_interpretation

pytestmark=pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='Tk display required')

def test_real_audit_resolved_child_population_and_historical_override(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace;gate=new_gate(app);sid=owner.sample_id(paths[1]);gid=gate['id']
    owner.show_sample(app,sid);app.gate_scope_var.set('Current sample');owner.scope_changed(app);app._sel_gate()['x1']=70.;app.refresh_plot()
    app._open_subgate(50.,50.);child=manager._apps[1];child.refresh_plot()
    ids=[owner.sample_id(p) for p in paths]
    samples=prepare_samples(owner,child,ids)
    assert [len(s.dataframe) for s in samples]==[3,2,3]
    # Two events are intentionally insufficient for numeric eligibility; the
    # transaction rejects rather than silently dropping this selected peer.
    with pytest.raises(ValueError,match='eligible'):run_audit(samples)
    full=prepare_samples(owner,app,ids);bundle=run_audit(full,variables=['X','Y']);ref=commit(owner,bundle)
    snap=copy.deepcopy(bundle['samples'][1]['population_snapshot'])
    app._sel_gate()['x1']=60.;app.refresh_plot();assert bundle['samples'][1]['population_snapshot']==snap
    target=tmp_path/'audit.vflow';assert owner.save(path=str(target))
    assert ref.result.absolute_path.startswith(str(tmp_path/'audit_audits'))
    assert owner.open(str(target));assert read_bundle(owner.document.audits[ref.audit_id],target)==bundle

def test_real_review_actions_reuse_exclusion_and_preserve_history(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    sid=owner.sample_id(paths[0]);s=prepare_samples(owner,app,[owner.sample_id(p) for p in paths]);bundle=run_audit(s)
    ref=commit(owner,bundle);before=Path(ref.result.absolute_path).read_bytes()
    results=AuditResultsDialog(owner,ref,bundle);root.update();assert len(results.tree.get_children())==3
    decide(owner,ref,sid,'keep');assert paths[0] in app.loaded_files
    decide(owner,ref,sid,'exclude',note='manual quality review');assert paths[0] in app.excluded_files and owner.document.samples[sid].excluded
    decide(owner,ref,sid,'restore');assert paths[0] in app.loaded_files and not owner.document.samples[sid].excluded
    assert Path(ref.result.absolute_path).read_bytes()==before
    assert [x['action'] for x in ref.decision_history]==['keep','exclude','restore']
    target=tmp_path/'history.vflow';assert owner.save(path=str(target));assert owner.open(str(target));root.update()
    assert len(owner.document.audits[ref.audit_id].decision_history)==3
    listing=AuditListDialog(owner);root.update();listing.destroy();results.destroy()

def test_real_audit_worker_run_and_cancel_transaction(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace;dialog=StatisticalAuditDialog(owner,app);root.update()
    dialog.prepare()
    deadline=time.monotonic()+15
    while dialog.worker.is_alive() and time.monotonic()<deadline:root.update();time.sleep(.01)
    dialog.poll();root.update();assert dialog.variables.size()>=4
    dialog.run()
    deadline=time.monotonic()+15
    while dialog.worker.is_alive() and time.monotonic()<deadline:root.update();time.sleep(.01)
    dialog.poll();root.update();assert len(owner.document.audits)==1
    assert dialog.status.get().startswith('Audit saved:')
    before=set(owner.document.audits);dialog.run();dialog.cancel_event.set()
    while dialog.worker.is_alive() and time.monotonic()<deadline:root.update();time.sleep(.01)
    dialog.poll();root.update();assert set(owner.document.audits)==before;dialog.close()

def test_real_multi_member_lmd_load_reopen_regenerates_from_original(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    a,_=write_fixture(tmp_path/'a.fcs',types=('I','I'),bits=(16,16),names=('X','Y'),rows=[(1,2),(3,4),(5,6)])
    b,_=write_fixture(tmp_path/'b.fcs',types=('I','I'),bits=(16,16),names=('X','Y'),rows=[(9,8),(7,6),(5,4)])
    source=tmp_path/'plate.lmd';source.write_bytes(a.read_bytes()+b.read_bytes());app._load_paths([str(source)]);root.update()
    proprietary=[s for s in owner.document.samples.values() if s.source.absolute_path==str(source)]
    assert len(proprietary)==2 and len({s.source_member_id for s in proprietary})==2
    target=tmp_path/'multi.vflow';assert owner.save(path=str(target))
    for p in tmp_path.glob('plate*.csv'):p.unlink()
    assert owner.open(str(target));root.update();assert len(app.loaded_files)==5
    for sample in proprietary:
        key=owner.path_for(sample.sample_id);assert key in app.loaded_files
        assert app.loaded_files[key].attrs['vflow_source_path']==str(source)
    owner.remove_sample(proprietary[0].sample_id);assert len(app.loaded_files)==4

def test_unavailable_audit_bundle_reported_and_relinked(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    bundle=run_audit(prepare_samples(owner,app,[owner.sample_id(p) for p in paths]));ref=commit(owner,bundle)
    target=tmp_path/'refs.vflow';assert owner.save(path=str(target));old=Path(ref.result.absolute_path);moved=tmp_path/'move';moved.mkdir();old.rename(moved/old.name)
    assert owner.open(str(target));assert 'audit:'+ref.audit_id in owner.missing
    stored=owner.document.audits[ref.audit_id];stored.result.accept(moved/old.name,target)
    assert read_bundle(stored,target)==bundle
    Path(paths[0]).write_text('X,Y\n1,2\n')
    assert source_identity_warnings(bundle,owner.document,target)

def test_old_result_dialog_cannot_review_a_reopened_workspace(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    bundle=run_audit(prepare_samples(owner,app,[owner.sample_id(p) for p in paths]));ref=commit(owner,bundle)
    results=AuditResultsDialog(owner,ref,bundle);sid=ref.selected_sample_ids[0]
    target=tmp_path/'reopened.vflow';assert owner.save(path=str(target));assert owner.open(str(target))
    with pytest.raises(ValueError,match='previously opened workspace'):decide(owner,ref,sid,'exclude')
    assert not owner.document.samples[sid].excluded
    assert ref.decision_history==[] and owner.document.audits[ref.audit_id].decision_history==[]
    results.refresh();assert 'workspace changed' in results.tree.item(sid)['values'][-1]
    results.destroy()

def test_bulk_review_preflights_all_sources_before_changing_any(experiment,monkeypatch):
    from tkinter import simpledialog
    root,manager,app,paths,errors=experiment;owner=app._workspace
    b=run_audit(prepare_samples(owner,app,[owner.sample_id(p) for p in paths]));ref=commit(owner,b)
    ids=ref.selected_sample_ids[:2]
    for sid in ids:decide(owner,ref,sid,'exclude')
    app.excluded_files[paths[1]]=None
    results=AuditResultsDialog(owner,ref,b);results.tree.selection_set(ids)
    monkeypatch.setattr(simpledialog,'askstring',lambda *a,**k:'reviewed')
    before=copy.deepcopy(ref.decision_history);results.action('restore')
    assert errors and 'unavailable' in str(errors.pop())
    assert ref.decision_history==before and paths[0] in app.excluded_files
    results.destroy()

def test_acquisition_member_change_prevents_audit_commit(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    b=run_audit(prepare_samples(owner,app,[owner.sample_id(p) for p in paths]));sid=b['samples'][0]['sample_id']
    owner.document.samples[sid].source_member_id='different member'
    with pytest.raises(ValueError,match='identity changed'):commit(owner,b)
    assert owner.document.audits=={}
    assert source_identity_warnings(b,owner.document)

def test_interpretation_and_model_details_visible_at_minimum_size(experiment):
    from PIL import ImageGrab
    root,manager,app,paths,errors=experiment;owner=app._workspace
    ids=[owner.sample_id(p) for p in paths]
    b=run_audit(prepare_samples(owner,app,ids),audit_type='hierarchy',hierarchy_mapping=dict(zip(ids,['Bio_A','Bio_B','Bio_C'])))
    ref=commit(owner,b);results=AuditResultsDialog(owner,ref,b);results.geometry('720x450+0+0');root.update()
    def descendants(widget):
        for child in widget.winfo_children():yield child;yield from descendants(child)
    buttons=[w for w in descendants(results) if isinstance(w,tk.ttk.Button)]
    assert len(buttons)==8 and all(w.winfo_ismapped() for w in buttons)
    assert all(w.winfo_rootx()+w.winfo_width()<=results.winfo_rootx()+results.winfo_width() for w in buttons)
    destination=Path(__file__).resolve().parents[1]/'validation'
    ImageGrab.grab(xdisplay=os.environ['DISPLAY']).save(destination/'audit_results_rc3.png')
    results.tree.selection_set(ids[0]);results.details();root.update()
    details=[w for w in results.winfo_children() if isinstance(w,tk.Toplevel)][0]
    notebook=next(w for w in descendants(details) if isinstance(w,tk.ttk.Notebook))
    assert 'Leave-one-out models' in [notebook.tab(tab,'text') for tab in notebook.tabs()]
    notebook.select(1);root.update()
    ImageGrab.grab(xdisplay=os.environ['DISPLAY']).save(destination/'audit_hierarchy_details_rc3.png')
    help_window=show_interpretation(results,b);help_window.geometry('+400+0');root.update()
    text=next(w for w in descendants(help_window) if isinstance(w,tk.Text)).get('1.0','end')
    for phrase in ('not p-values','squared measurement units','1,000,000','equal weight','confidence estimate','Relative change'):
        assert phrase in text
    ImageGrab.grab(xdisplay=os.environ['DISPLAY']).save(destination/'audit_interpretation_rc3.png')
    help_window.destroy()
    old_bundle={**b,'analysis_version':'audit-2'};historical_help=show_interpretation(results,old_bundle)
    legacy=next(w for w in descendants(historical_help) if isinstance(w,tk.Text)).get('1.0','end')
    assert '1e-20' in legacy and '1e-12' in legacy and 'Run a new audit' in legacy
    historical_help.destroy();details.destroy();results.destroy()

def test_closed_worker_dialog_cannot_schedule_callbacks(experiment):
    root,manager,app,paths,errors=experiment
    dialog=StatisticalAuditDialog(app._workspace,app);dialog.geometry('680x580');root.update()
    assert dialog.run_button.winfo_ismapped() and dialog.prepare_button.winfo_ismapped()
    dialog.prepare();dialog.close()
    dialog.poll();root.update()
    assert dialog.cancel_event.is_set() and dialog._closed

@pytest.mark.parametrize('action',['exclude','restore'])
def test_review_failure_after_mutation_rolls_back_entire_selection(experiment,monkeypatch,action):
    root,manager,app,paths,errors=experiment;owner=app._workspace;new_gate(app)
    b=run_audit(prepare_samples(owner,app,[owner.sample_id(p) for p in paths]));ref=commit(owner,b)
    ids=ref.selected_sample_ids[:2]
    if action=='restore':
        for sid in ids:decide(owner,ref,sid,'exclude')
    else:
        app.file_vars[paths[2]].set(False);app._on_active_files_changed()
    original_frames={p:df for p,df in {**app.loaded_files,**app.excluded_files}.items()}
    loaded_before=set(app.loaded_files);excluded_before=set(app.excluded_files)
    active_before={p:v.get() for p,v in app.file_vars.items()};history=copy.deepcopy(ref.decision_history)
    metadata={sid:(s.active,s.excluded) for sid,s in owner.document.samples.items()}
    original=getattr(app,'_'+action+'_file')
    def fail_later(path):
        original(path)
        if path==paths[1]:raise RuntimeError('injected UI failure after inclusion changed')
    monkeypatch.setattr(app,'_'+action+'_file',fail_later)
    with pytest.raises(ValueError,match='restored'):decide_many(owner,ref,ids,action,note='must be atomic')
    assert set(app.loaded_files)==loaded_before and set(app.excluded_files)==excluded_before
    assert {p:v.get() for p,v in app.file_vars.items()}==active_before
    assert ref.decision_history==history
    assert {sid:(s.active,s.excluded) for sid,s in owner.document.samples.items()}==metadata
    for p,df in original_frames.items():assert {**app.loaded_files,**app.excluded_files}[p] is df
    root.update();assert not errors

def test_failed_save_as_preserves_live_audit_and_gate_references(experiment,tmp_path,monkeypatch):
    from dataclasses import asdict
    from vflow.workspace.model import Workspace
    root,manager,app,paths,errors=experiment;owner=app._workspace;gate=new_gate(app)
    b=run_audit(prepare_samples(owner,app,[owner.sample_id(p) for p in paths]));ref=commit(owner,b)
    old=tmp_path/'old/project.vflow';assert owner.save(path=str(old));old_bytes=old.read_bytes()
    gate['x1']=95.;app.refresh_plot();owner.capture(app)
    refs={key:asdict(value) for key,value in owner.document.references()}
    result=AuditResultsDialog(owner,ref,b)
    with monkeypatch.context() as patch:
        patch.setattr(Workspace,'save',lambda *a,**k:(_ for _ in ()).throw(OSError('disk full')))
        assert not owner.save(save_as=True,path=str(tmp_path/'new/project.vflow'))
    assert errors and 'disk full' in str(errors.pop())
    assert owner.path==str(old) and old.read_bytes()==old_bytes
    assert {key:asdict(value) for key,value in owner.document.references()}==refs
    assert result.is_current() and read_bundle(ref,owner.path)==b
    assert owner.save(save_as=True,path=str(tmp_path/'new/project.vflow'))
    assert result.is_current();result.destroy()

def test_save_as_preserves_imported_audit_compression_bytes(experiment,tmp_path):
    import gzip
    from vflow.workspace.model import FileReference
    root,manager,app,paths,errors=experiment;owner=app._workspace
    b=run_audit(prepare_samples(owner,app,[owner.sample_id(p) for p in paths]));ref=commit(owner,b)
    original=gzip.compress(json.dumps(b,sort_keys=True).encode(),compresslevel=0,mtime=37)
    external=tmp_path/'imported.gz';external.write_bytes(original);ref.result=FileReference.create(external,owner.path,kind='audit')
    assert owner.save(save_as=True,path=str(tmp_path/'relocated/project.vflow'))
    assert Path(ref.result.absolute_path).read_bytes()==original and external.read_bytes()==original
    assert read_bundle(ref,owner.path)==b

def test_old_audit_list_handles_new_workspace_without_callback_error(experiment,monkeypatch):
    from tkinter import messagebox
    root,manager,app,paths,errors=experiment;owner=app._workspace
    b=run_audit(prepare_samples(owner,app,[owner.sample_id(p) for p in paths]));ref=commit(owner,b)
    listing=AuditListDialog(owner);listing.tree.selection_set(ref.audit_id)
    owner.clear();messages=[];monkeypatch.setattr(messagebox,'showinfo',lambda *a,**k:messages.append(a))
    listing.open_selected();root.update()
    assert messages and 'Workspace changed' in str(messages)
    assert not owner.document.audits and not errors;listing.destroy()
