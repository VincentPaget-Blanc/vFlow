"""Native workspace write/read/edit/re-read in separate interpreter processes."""
from pathlib import Path
import os,sys,json,hashlib
import tkinter as tk
from tkinter import messagebox
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vflow.legacy.vflow_app import FlowTabManager
from tests.test_workspace_gui import new_gate
from tests.test_threshold_deletion_gui import crosshair
BASE=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else Path(__file__).resolve().parent/'workspace_persistence_rc15_run'
BASE.mkdir(parents=True,exist_ok=True)
phase=sys.argv[1]
errors=[]
for method in ('showinfo','showwarning'):setattr(messagebox,method,lambda *a,**k:None)
messagebox.showerror=lambda *a,**k:errors.append(str(a))
messagebox.askyesno=lambda *a,**k:True
messagebox.askyesnocancel=lambda *a,**k:False
root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(str(a))
manager=FlowTabManager(root);app=manager._apps[0];owner=app._workspace
owner.state_dir=BASE/('state_'+phase);owner.recent_path=owner.state_dir/'recent.json'
app.plot_type_var.set('Dot Plot');app.show_marginals_var.set(False)
workspace=BASE/'Edited.vflow';meta_path=BASE/'expected.json'
paths=[str(BASE/(name+'.csv')) for name in ('A','B','C','D')]
def geometry(gid,sid=None):
 return owner.stores['main'].resolve_gate(sid,gid)
def rename_from_header(name):
 app._workspace_name_entry.focus_force();root.update();app._workspace_name_var.set(name);app._workspace_name_entry.event_generate('<Return>');root.update()
def verify(meta,final=False):
 assert owner.workspace_name()==('Edited benchmark final' if final else 'Edited benchmark')
 assert app._workspace_name_var.get()==owner.workspace_name()
 sid_a=owner.sample_id(paths[0]);sid_b=owner.sample_id(paths[1]);sid_d=owner.sample_id(paths[3])
 assert len(owner.document.samples)==3
 assert owner.sample_id(paths[2]) is None
 assert paths[3] in app.loaded_files and paths[0] in app.excluded_files
 assert not app.file_vars[paths[1]].get() and app.file_vars[paths[3]].get()
 assert (owner.document.overlay_view.x_channel,owner.document.overlay_view.y_channel)==('X','Y')
 assert app.interface_size_var.get()=='Comfortable'
 assert app._sidebar_task()=='Analysis'
 assert app._sample_panel_fraction==.63
 rect=meta['rectangle'];thr=meta['threshold']
 assert geometry(rect,sid_b)['x1']==(90. if final else 70.)
 assert geometry(rect,sid_d)['x1']==100.
 assert geometry(rect,sid_d)['name']==('Renamed again' if final else 'Reviewed gate')
 gate=geometry(thr,sid_d)
 assert gate['x_boundaries']==([200.] if final else [100.,200.])
 assert gate['x_thresh_vars']==([True] if final else [False,True])
 assert gate['y_boundaries']==[40.,100.] and gate['y_thresh_vars']==[False,True]
 # Inactive samples intentionally have no live statistics. Activate for the numerical check, then restore.
 owner.toggle_sample(sid_b,app);app._recompute_all_gate_stats();root.update()
 assert app.gate_stats[rect][paths[1]]['stats']['IN']['count']==(3 if final else 2)
 assert app.gate_stats[rect][paths[3]]['stats']['IN']['count']==3
 owner.toggle_sample(sid_b,app);root.update();assert not app.file_vars[paths[1]].get()
 assert geometry(thr,sid_b)['x_boundaries']==([200.] if final else [100.,200.])
 assert app.gate_scope_var.get()=='All samples (default)'
 assert not owner.missing
 if final:
  assert owner.document.samples[sid_d].view.x_channel=='U'
  assert owner.document.samples[sid_d].view.y_channel=='V'
 for p,sha in meta['source_hashes'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha
if phase=='create':
 for p in paths:
  pd.DataFrame({'X':[30.,50.,90.,120.,220.],'Y':[30.,50.,90.,120.,70.],'U':[1.,2.,3.,4.,5.],'V':[6.,7.,8.,9.,10.]}).to_csv(p,index=False)
 app._load_paths(paths[:3]);root.update();app.x_var.set('X');app.y_var.set('Y');app.apply_axes();app.x_scale_var.set('linear');app.y_scale_var.set('linear')
 rect=new_gate(app)['id'];thr=crosshair(app)['id'];root.update()
 assert owner.save(path=str(BASE/'Baseline.vflow'))
 baseline_bytes=(BASE/'Baseline.vflow').read_bytes()
 app._select_gate(rect);app._sel_gate()['name']='Reviewed gate';app._recompute_all_gate_stats();app.refresh_plot()
 owner.show_sample(app,owner.sample_id(paths[1]));app.gate_scope_var.set('Current sample');owner.scope_changed(app)
 app._select_gate(rect);app._sel_gate()['x1']=70.;app._recompute_all_gate_stats();app.refresh_plot()
 app.view_mode_var.set('overlay');app._on_view_mode_change();app._select_gate(thr);assert app._delete_threshold(thr,'x',0)
 app._exclude_file(paths[0]);owner.toggle_sample(owner.sample_id(paths[1]),app)
 owner.remove_sample(owner.sample_id(paths[2]));app._load_paths([paths[3]])
 app.interface_size_var.set('Comfortable');app._apply_interface_size();app._select_sidebar_task('Analysis');app._sample_panel_fraction=.63
 rename_from_header('Edited benchmark');root.update();assert owner.save(path=str(workspace));assert workspace.read_bytes()!=baseline_bytes
 assert (BASE/'Baseline.vflow').read_bytes()==baseline_bytes
 meta={'rectangle':rect,'threshold':thr,'source_hashes':{p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},'baseline_gate_path':owner.document.default_gate_session.absolute_path}
 meta_path.write_text(json.dumps(meta,indent=2)+'\n')
elif phase=='edit_again':
 meta=json.loads(meta_path.read_text());assert owner.open(str(workspace));root.update();verify(meta)
 original=workspace.read_bytes();previous_gate=Path(owner.document.default_gate_session.absolute_path);previous_bytes=previous_gate.read_bytes()
 app._select_gate(meta['rectangle']);app._sel_gate()['name']='Renamed again';app._recompute_all_gate_stats();app.refresh_plot()
 owner.show_sample(app,owner.sample_id(paths[1]));app.gate_scope_var.set('Current sample');owner.scope_changed(app)
 app._select_gate(meta['rectangle']);app._sel_gate()['x1']=90.;app._recompute_all_gate_stats();app.refresh_plot()
 app.view_mode_var.set('overlay');app._on_view_mode_change();app._select_gate(meta['threshold']);assert app._delete_threshold(meta['threshold'],'x',0)
 owner.show_sample(app,owner.sample_id(paths[3]));app.x_var.set('U');app.y_var.set('V');app.apply_axes()
 app.view_mode_var.set('overlay');app._on_view_mode_change();app.file_vars[paths[1]].set(False);app._on_active_files_changed();app._select_sidebar_task('Analysis');root.update()
 rename_from_header('Edited benchmark final');assert owner.save();assert workspace.read_bytes()!=original
 assert Path(owner.document.default_gate_session.absolute_path)!=previous_gate
 assert previous_gate.read_bytes()==previous_bytes
else:
 meta=json.loads(meta_path.read_text());assert owner.open(str(workspace));root.update();verify(meta,final=phase=='verify_final')
 record={'phase':phase,'separate_process':True,'passed':True,'samples':len(owner.document.samples),'gate_count':len(owner.stores['main'].global_gates),'workspace_bytes':workspace.stat().st_size}
 (BASE/(phase+'.json')).write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps(record))
owner.dispose();root.destroy();assert errors==[],errors
print('PASS '+phase)
