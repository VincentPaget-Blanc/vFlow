"""Abrupt exit and fresh-process checkpoint restoration; app-only dependencies."""
import argparse,hashlib,json,os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
p=argparse.ArgumentParser();p.add_argument('phase',choices=['saved_crash','unsaved_crash','saved_verify','unsaved_verify']);p.add_argument('--folder',type=Path,required=True);a=p.parse_args()
import tkinter as tk
from tkinter import messagebox,font
from vflow.legacy.vflow_app import FlowTabManager
from vflow.statistics import run_audit
from vflow.statistics.workspace_audit import prepare_samples,commit,decide
from vflow.statistics.audit_serialization import read_bundle
folder=a.folder.resolve();folder.mkdir(parents=True,exist_ok=True);saved=a.phase.startswith('saved');crash=a.phase.endswith('crash')
errors=[];messagebox.showinfo=messagebox.showwarning=lambda *x,**k:None;messagebox.showerror=lambda *x,**k:errors.append(str(x))
messagebox.askyesno=lambda *x,**k:True;messagebox.askyesnocancel=lambda *x,**k:False
root=tk.Tk();root.report_callback_exception=lambda *x:errors.append(str(x))
if os.environ.get('VFLOW_TEST_FONT'):font.nametofont('TkDefaultFont').configure(family=os.environ['VFLOW_TEST_FONT'])
manager=FlowTabManager(root);app=manager._apps[0];owner=app._workspace;owner.state_dir=folder/'state';owner.recent_path=owner.state_dir/'recent.json'
if owner._recovery_offer:root.after_cancel(owner._recovery_offer);owner._recovery_offer=None
app.plot_type_var.set('Dot Plot');app.show_marginals_var.set(False)
workspace=folder/'study.vflow';expected=folder/'expected.json'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def gate(app,x0,x1,y0,y1):
    app._add_gate(auto_type='rectangle');g=app._sel_gate();g.update(x0=x0,x1=x1,y0=y0,y1=y1,applied=True);app._bind_gate_context(g);app.refresh_plot();return g
if crash:
    names=['Control_01.csv','Control_02.csv','Treatment_01.csv','Treatment_02.csv']
    for name in names:shutil.copy2(ROOT/'benchmark_extensions/frozen_v1/cytometry'/name,folder/name)
    paths=[str(folder/name) for name in names];app._load_paths(paths)
    app.x_var.set('FSC-A');app.y_var.set('SSC-A');app.apply_axes();app.x_scale_var.set('linear');app.y_scale_var.set('linear')
    first=gate(app,45000.,105000.,5000.,55000.);gid=first['id'];ids=[owner.sample_id(path) for path in paths]
    app._open_subgate(75000.,30000.);child=manager._apps[1];child.plot_type_var.set('Dot Plot');cg=gate(child,55000.,95000.,10000.,45000.);child._open_subgate(75000.,30000.)
    bundle=run_audit(prepare_samples(owner,app,ids[:2]),variables=['FSC-A','SSC-A']);ref=commit(owner,bundle)
    if saved:assert owner.save(path=workspace)
    original_sha=sha(workspace) if saved else None;original_gate=owner.document.default_gate_session
    original_gate_sha=sha(original_gate.absolute_path) if original_gate else None
    app._sel_gate_id=gid;app._sel_gate()['x1']=100000.;app.refresh_plot();owner.capture(app)
    owner.show_sample(app,ids[1]);app.gate_scope_var.set('Current sample');owner.scope_changed(app);app._sel_gate_id=gid;app._sel_gate()['x1']=80000.;app.refresh_plot();owner.capture(app)
    app._exclude_file(paths[3]);app.file_vars[paths[1]].set(False);app._on_active_files_changed()
    decide(owner,ref,ids[0],'note',note='Unsaved recovery review');owner.rename('Recovered benchmark edits');owner.autosave()
    assert owner.recovery_path.is_file() and owner._recovery_gate_path.is_file() and not errors
    meta={'ids':ids,'gid':gid,'child_gid':cg['id'],'raw_hashes':{name:sha(folder/name) for name in names},'audit_id':ref.audit_id,
        'audit_sha':sha(ref.result.absolute_path),'original_sha':original_sha,'original_gate':original_gate.absolute_path if original_gate else None,'original_gate_sha':original_gate_sha}
    expected.write_text(json.dumps(meta,indent=2));os._exit(85)
else:
    meta=json.loads(expected.read_text())
    if saved:assert owner.open(workspace)
    else:owner.offer_unsaved_recovery()
    root.update();ids=meta['ids'];gid=meta['gid']
    assert owner.dirty and owner.gates_dirty and owner.workspace_name()=='Recovered benchmark edits'
    assert set(owner.document.samples)==set(ids) and owner.document.samples[ids[3]].excluded and not owner.document.samples[ids[1]].active
    assert len(app.loaded_files)==3 and sum(map(len,app.loaded_files.values()))==36000 and len(manager._apps)==3
    assert owner.stores['main'].resolve_gate(ids[0],gid)['x1']==100000. and owner.stores['main'].resolve_gate(ids[1],gid)['x1']==80000.
    ref=owner.document.audits[meta['audit_id']];bundle=read_bundle(ref,owner.path)
    assert sha(ref.result.resolve(owner.path))==meta['audit_sha'] and len(ref.decision_history)==1 and ref.decision_history[0]['note']=='Unsaved recovery review'
    assert sum(s['event_count'] for s in bundle['sample_qc'])==24000
    if saved:assert sha(workspace)==meta['original_sha'] and sha(meta['original_gate'])==meta['original_gate_sha']
    checkpoint=owner.recovery_path;assert owner.save(save_as=True,path=folder/'recovered.vflow');assert not checkpoint.exists()
    assert owner.open(folder/'recovered.vflow') and not owner.dirty and not owner.gates_dirty and owner.workspace_name()=='Recovered benchmark edits'
    assert owner.stores['main'].resolve_gate(ids[1],gid)['x1']==80000. and len(owner.document.audits[meta['audit_id']].decision_history)==1
    assert all(sha(folder/name)==h for name,h in meta['raw_hashes'].items()) and not errors
    result={'phase':a.phase,'passed':True,'loaded_events':36000,'saved_audit_events':24000,'nested_populations':2,'raw_hashes_unchanged':True,'errors':errors}
    (folder/(a.phase+'.json')).write_text(json.dumps(result,indent=2));owner.dispose();root.destroy();print(json.dumps(result))
