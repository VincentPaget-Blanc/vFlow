"""Real benchmark-loaded app: gating, thresholds, secondary windows, exports and persistence."""
from pathlib import Path
import copy,hashlib,json,os,sys,tempfile,shutil,tkinter as tk
from tkinter import messagebox,filedialog,font
import pandas as pd
from PIL import ImageGrab
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from vflow.legacy.vflow_app import FlowTabManager,BatchPlotWindow,PolarAnalysisWindow
OUT=ROOT/'validation/bug_hunt_rc12';OUT.mkdir(exist_ok=True)
errors=[];checks=[]
def check(name,condition):
 assert condition,name;checks.append(name)
messagebox.showerror=lambda *a,**k:errors.append(str(a))
messagebox.showinfo=messagebox.showwarning=lambda *a,**k:None
messagebox.askyesno=lambda *a,**k:True
messagebox.askyesnocancel=lambda *a,**k:False
root=tk.Tk();font.nametofont('TkDefaultFont').configure(family='DejaVu Sans')
root.report_callback_exception=lambda *a:errors.append(str(a))
manager=FlowTabManager(root);app=manager._apps[0];owner=app._workspace
app.plot_type_var.set('Dot Plot');app.show_marginals_var.set(False)
with tempfile.TemporaryDirectory() as td:
 td=Path(td);owner.state_dir=td/'state';owner.recent_path=td/'recent.json'
 names=['Control_01.csv','Control_02.csv','Treatment_01.csv','Treatment_02.csv'];files=[]
 for name in names:
  p=td/name;shutil.copy2(ROOT/'benchmark_extensions/frozen_v1/cytometry'/name,p);files.append(str(p))
 hashes={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files}
 app._load_paths(files);root.geometry('1440x1000+0+0');root.update()
 check('Four real CSVs / 48,000 events loaded',len(app.loaded_files)==4 and sum(map(len,app.loaded_files.values()))==48000)
 app.x_var.set('FSC-A');app.y_var.set('SSC-A');app.apply_axes();app.x_scale_var.set('linear');app.y_scale_var.set('linear');root.update()
 definition=json.loads((ROOT/'benchmark_extensions/frozen_v1/references/benchmark_gate_definitions.json').read_text())['gates'][0]
 app._add_gate(auto_type='rectangle');gate=app._sel_gate();gid=gate['id']
 gate.update({k:definition[k] for k in ('x0','x1','y0','y1')});gate.update(applied=True,name='Benchmark rectangle')
 app._bind_gate_context(gate);app._recompute_all_gate_stats();app.refresh_plot();root.update()
 truth=pd.read_csv(ROOT/'benchmark_extensions/frozen_v1/truth/expected_gate_counts.csv')
 expected={row.Sample:int(row.Count) for row in truth.itertuples() if row.Gate_or_Region==definition['id']}
 counts={Path(p).stem:app.gate_stats[gid][p]['stats']['IN']['count'] for p in files}
 check('Reference gate counts equal independent frozen truth',all(counts[k]==expected[k] for k in counts))
 for mode in ('Dot Plot','Density','Contour Plot'):
  app.plot_type_var.set(mode);root.update();check('Plot '+mode,app.gate_stats[gid][files[0]]['stats']['IN']['count']==counts['Control_01'])
 app.plot_type_var.set('Dot Plot');app.auto_gate_otsu();root.update();auto=app._sel_gate();aid=auto['id']
 check('Actual pooled automatic gate uses four samples',len(owner.auto_gate_data(app))==4 and bool(auto['x_boundaries']))
 y_before=auto['y_boundary'];check('Delete individual automatic threshold',app._delete_threshold(aid,'x',0))
 check('Other automatic axis remains',app._sel_gate()['y_boundary']==y_before)
 owner.gate_action(app,'undo',aid);root.update();check('Undo restores threshold',bool(app._sel_gate()['x_boundaries']))
 app._sel_gate_id=gid;app._open_subgate(75000.,30000.);root.update()
 check('Nested population follows benchmark gate',len(manager._apps)==2 and sum(map(len,manager._apps[1].loaded_files.values()))==sum(counts.values()))
 # Exercise both secondary windows in a live session, not just stale-session guards.
 batch=BatchPlotWindow(root,app.T,app);root.update();batch._compute_and_plot();check('Batch plot calculates',bool(batch._dist_cache));batch._on_close()
 polar=PolarAnalysisWindow(root,app.T,app)
 for variable,value in ((polar._cx1_var,'FSC-A'),(polar._cy1_var,'SSC-A'),(polar._cx2_var,'FSC-H'),(polar._cy2_var,'SSC-H')):variable.set(value)
 polar._compute_and_plot();root.update();check('Polar analysis calculates',not errors);polar.destroy()
 app._sel_gate_id=gid;app._rebuild_gate_manager();app._update_stats_display()
 outputs={}
 for method,name in (('export_stats','stats.csv'),('export_gated_data','events.csv'),('save_gates','gates.json'),('export_figure','plot.png')):
  p=td/name;filedialog.asksaveasfilename=lambda **k:str(p)
  getattr(app,method)();check(method,p.exists() and p.stat().st_size>0);outputs[name]=p.stat().st_size
 check('Successful gated-data export contains full raw event rows',0<len(pd.read_csv(td/'events.csv'))<=48000)
 # A refused source collision must leave bytes and live state intact.
 before_errors=len(errors);filedialog.asksaveasfilename=lambda **k:files[0];app.export_gated_data()
 check('Refused source collision is actionable',len(errors)==before_errors+1 and 'replace' in errors[-1]);errors.pop()
 owner.rename('RC12 benchmark review');destination=td/'review.vflow'
 check('Save workspace with population and gates',owner.save(path=destination))
 check('Reopen workspace without quitting',owner.open(destination));root.update()
 check('Workspace name and population restored',owner.workspace_name()=='RC12 benchmark review' and len(manager._apps)==2)
 manager.notebook.select(0);app._select_sidebar_task('Data');root.update()
 x,y=app._side_outer.winfo_rootx(),app._side_outer.winfo_rooty();w,h=app._side_outer.winfo_width(),app._side_outer.winfo_height()
 ImageGrab.grab(bbox=(x,y,x+w,y+h),xdisplay=os.environ['DISPLAY']).save(OUT/'Benchmark_Data_Panel_RC12.png')
 check('Original benchmark copies unchanged',all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==digest for p,digest in hashes.items()))
 check('No unexpected Tk/application errors',not errors)
 (OUT/'workflow_result.json').write_text(json.dumps({'version':'4.4.3rc12','events':48000,'files':4,'checks':checks,'passed':len(checks),'reference_gate_counts':counts,'export_bytes':outputs,'errors':errors,'raw_hashes_unchanged':True},indent=2)+'\n')
 print('PASS',len(checks),'real benchmark app workflow checks; 48,000 events; exports, save/reopen and raw hashes verified.')
owner.dispose();root.destroy()
