"""Portable native release exercise; each phase is invoked in a fresh process."""
import argparse, faulthandler, gc, hashlib, json, os, shutil, sys, threading, time, weakref
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));faulthandler.enable()
p=argparse.ArgumentParser();p.add_argument('phase',choices=['create','verify','interrupt_before','interrupt_after','verify_before','verify_after','long_session']);p.add_argument('--folder',type=Path,required=True);p.add_argument('--cycles',type=int,default=20);p.add_argument('--seconds',type=float,default=0);args=p.parse_args()
import tkinter as tk
from tkinter import messagebox,font
import pandas as pd
from vflow.legacy.vflow_app import FlowTabManager,BatchPlotWindow,PolarAnalysisWindow
from vflow.ui.statistical_audit_dialog import StatisticalAuditDialog
from vflow.statistics.workspace_audit import prepare_samples,commit,decide
from vflow.statistics.audit_serialization import read_bundle
from vflow.statistics import run_audit
def wait_dialog(root,dialog):
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        root.update()
        if not dialog._busy and not (dialog.worker and dialog.worker.is_alive()) and dialog.messages.empty():return
        time.sleep(.005)
    raise AssertionError('Audit worker did not settle')
folder=args.folder.resolve();folder.mkdir(parents=True,exist_ok=True);meta_path=folder/'expected.json'
errors=[];messagebox.showinfo=messagebox.showwarning=lambda *a,**k:None
messagebox.showerror=lambda *a,**k:errors.append(str(a));messagebox.askyesno=lambda *a,**k:True;messagebox.askyesnocancel=lambda *a,**k:False
root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(str(a));root.tk.createcommand('bgerror',lambda msg:errors.append('Tcl: '+str(msg)))
if os.environ.get('VFLOW_TEST_FONT'):font.nametofont('TkDefaultFont').configure(family=os.environ['VFLOW_TEST_FONT'])
manager=FlowTabManager(root);app=manager._apps[0];owner=app._workspace;owner.state_dir=folder/'state';owner.recent_path=owner.state_dir/'recent.json'
app.plot_type_var.set('Dot Plot');app.show_marginals_var.set(False)
original=folder/'Original/session.vflow';copy=folder/'Copies/session-copy.vflow'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def counts(gid):
 app._recompute_all_gate_stats();return {Path(path).stem:app.gate_stats[gid][path]['stats']['IN']['count'] for path in app.loaded_files}
def verify(meta,edited=False):
 assert len(owner.document.samples)==4 and len(app.loaded_files)==4 and sum(map(len,app.loaded_files.values()))==48000
 assert set(owner.document.samples)==set(meta['ids']) and not owner.missing
 assert owner.workspace_name()==('Interrupted edit committed' if edited else 'Copied benchmark')
 sid=next(iter(owner.document.samples));gate=owner.stores['main'].resolve_gate(sid,meta['gid'])
 assert gate['x1']==meta['x1']+(123. if edited else 0.)
 if not edited:assert counts(meta['gid'])==meta['counts']
 assert all(sha(folder/'Original'/name)==digest for name,digest in meta['raw_hashes'].items())
 assert set(owner.document.audits)=={meta['audit_id']}
 ref=owner.document.audits[meta['audit_id']]
 assert sha(ref.result.resolve(owner.path))==meta['audit_sha'] and len(ref.decision_history)==1
 assert ref.decision_history[0]['note']=='Benchmark retention note'
 bundle=read_bundle(ref,owner.path)
 assert sum(s['event_count'] for s in bundle['sample_qc'])==24000 and bundle['variables']==['FSC-A','SSC-A']
 assert not errors,errors
start=time.monotonic();record={'phase':args.phase,'python':sys.version.split()[0],'tk':str(root.tk.call('info','patchlevel')),'passed':False}
if args.phase=='create':
 original.parent.mkdir();copy.parent.mkdir();names=['Control_01.csv','Control_02.csv','Treatment_01.csv','Treatment_02.csv']
 for name in names:shutil.copy2(ROOT/'benchmark_extensions/frozen_v1/cytometry'/name,original.parent/name)
 app._load_paths([str(original.parent/name) for name in names]);root.update()
 app.x_var.set('FSC-A');app.y_var.set('SSC-A');app.apply_axes();app.x_scale_var.set('linear');app.y_scale_var.set('linear')
 definition=json.loads((ROOT/'benchmark_extensions/frozen_v1/references/benchmark_gate_definitions.json').read_text())['gates'][0]
 app._add_gate(auto_type='rectangle');gate=app._sel_gate();gate.update({k:definition[k] for k in ('x0','x1','y0','y1')});gate.update(applied=True,name='Benchmark rectangle');app._bind_gate_context(gate);app._recompute_all_gate_stats();app.refresh_plot()
 bundle=run_audit(prepare_samples(owner,app,[owner.sample_id(str(original.parent/name)) for name in names[:2]]),variables=['FSC-A','SSC-A'])
 ref=commit(owner,bundle);decide(owner,ref,ref.selected_sample_ids[0],'note',note='Benchmark retention note')
 owner.rename('Original benchmark');assert owner.save(path=original);old_workspace=sha(original);old_gate=Path(owner.document.default_gate_session.absolute_path);old_gate_sha=sha(old_gate)
 old_audit=Path(ref.result.resolve(owner.path));old_audit_sha=sha(old_audit)
 owner.rename('Copied benchmark');assert owner.save(save_as=True,path=copy)
 assert sha(old_audit)==old_audit_sha and Path(ref.result.resolve(owner.path))!=old_audit and read_bundle(ref,owner.path)==bundle
 assert sha(original)==old_workspace and sha(old_gate)==old_gate_sha and Path(owner.document.default_gate_session.absolute_path)!=old_gate
 meta={'ids':list(owner.document.samples),'gid':gate['id'],'x1':gate['x1'],'counts':counts(gate['id']),'raw_hashes':{n:sha(original.parent/n) for n in names},'audit_id':ref.audit_id,'audit_sha':sha(ref.result.resolve(owner.path)),'copy_sha':sha(copy),'copy_gate':Path(owner.document.default_gate_session.absolute_path).name,'copy_gate_sha':sha(owner.document.default_gate_session.absolute_path)}
 assert meta['counts']=={'Control_01':7273,'Control_02':7020,'Treatment_01':7081,'Treatment_02':7058}
 meta_path.write_text(json.dumps(meta,indent=2)+'\n');assert owner.open(copy);verify(meta)
 record.update(save_as_preserves_old_revision=True,events=48000,counts=meta['counts'])
else:
 meta=json.loads(meta_path.read_text());assert owner.open(copy);root.update();verify(meta,edited=args.phase=='verify_after')
 if args.phase.startswith('interrupt_'):
  owner.rename('Interrupted edit committed');app._sel_gate_id=meta['gid'];app._sel_gate()['x1']+=123.;app.refresh_plot();owner.capture(app)
  import vflow.workspace.model as model
  replace=model.os.replace
  def interrupt(source,target):
   if Path(target)==copy:
    if args.phase=='interrupt_before':os._exit(83)
    replace(source,target);os._exit(84)
   return replace(source,target)
  model.os.replace=interrupt
  owner.save();raise AssertionError('Did not interrupt final workspace replacement')
 elif args.phase=='verify_before':
  assert sha(copy)==meta['copy_sha'] and sha(copy.parent/meta['copy_gate'])==meta['copy_gate_sha'];record['previous_revision_intact']=True
 elif args.phase=='verify_after':record['committed_revision_complete']=True
 elif args.phase=='long_session':
  snapshots=[];weak=[];switches=0;active_start=time.monotonic();audit_runs=0;cycles=0
  for cycle in range(args.cycles):
   if args.seconds and cycle and time.monotonic()-active_start>=args.seconds:break
   cycles=cycle+1
   for path in (original,copy):
    assert owner.open(path);root.update();switches+=1
    assert sum(map(len,app.loaded_files.values()))==48000 and counts(meta['gid'])==meta['counts']
   dialog=StatisticalAuditDialog(owner,app);dialog.prepare();wait_dialog(root,dialog);assert sum(len(x.dataframe) for x in dialog.prepared)==48000
   weak.append(weakref.ref(dialog));dialog.close();del dialog
   release=threading.Event();dialog=StatisticalAuditDialog(owner,app);dialog.start(lambda:release.wait(5));worker=dialog.worker
   dialog.close();release.set();worker.join(timeout=3);assert not worker.is_alive();del dialog,worker;root.update();gc.collect()
   assert all(ref() is None for ref in weak), 'Closed audit dialog retained'
   assert set(owner.document.audits)=={meta['audit_id']}
   if cycle%5==0:
    current=run_audit(prepare_samples(owner,app,list(owner.document.samples)),variables=['FSC-A','SSC-A'])
    assert sum(s['event_count'] for s in current['sample_qc'])==48000;audit_runs+=1
    batch=BatchPlotWindow(root,app.T,app);root.update();batch._compute_and_plot();assert batch._dist_cache;batch._on_close();del batch
    polar=PolarAnalysisWindow(root,app.T,app)
    for variable,value in ((polar._cx1_var,'FSC-A'),(polar._cy1_var,'SSC-A'),(polar._cx2_var,'FSC-H'),(polar._cy2_var,'SSC-H')):variable.set(value)
    polar._compute_and_plot();root.update();polar.destroy();del polar;gc.collect()
   try:
    import resource
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
   except ImportError:rss=None
   snapshots.append({'cycle':cycle+1,'root_children':len(root.children),'peak_rss_platform_units':rss})
   assert not errors,errors
   if cycle%10==0:print(json.dumps({'stage':'endurance','cycle':cycles,'workspace_switches':switches,'active_seconds':round(time.monotonic()-active_start,3)}),flush=True)
  verify(meta);record.update(cycles=cycles,workspace_switches=switches,real_audit_preparations=cycles,cancelled_closed_workers=cycles,real_audit_runs=audit_runs,active_seconds=round(time.monotonic()-active_start,3),closed_dialogs_collected=True,snapshots=snapshots)
record.update(saved_audit_events=24000,review_note_preserved=True,bundle_bytes_preserved=True,passed=True,seconds=round(time.monotonic()-start,3),errors=errors)
owner.dispose();root.destroy();assert not errors,errors
(folder/(args.phase+'.json')).write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
