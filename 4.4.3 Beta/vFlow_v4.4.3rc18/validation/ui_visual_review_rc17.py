"""Benchmark-backed mouse interactions and rendered UI snapshots."""
import hashlib,json,os,sys,tempfile,tkinter as tk
from pathlib import Path
from tkinter import messagebox,font
from PIL import ImageGrab
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from vflow.legacy.vflow_app import FlowTabManager
from vflow.ui.statistical_audit_dialog import StatisticalAuditDialog
from tests.test_ui_interactions_rc17 import row_click
from tests.test_audit_selection_gui import click_sample,click_variable,wait_dialog
OUT=ROOT/'validation/ui_visual_rc17';OUT.mkdir(exist_ok=True)
errors=[];checks=[];views=[]
for name in ('showinfo','showwarning'):setattr(messagebox,name,lambda *a,**k:None)
messagebox.showerror=lambda *a,**k:errors.append(str(a))
messagebox.askyesnocancel=lambda *a,**k:False
root=tk.Tk();font.nametofont('TkDefaultFont').configure(family='DejaVu Sans')
root.report_callback_exception=lambda *a:errors.append(str(a))
manager=FlowTabManager(root);app=manager._apps[0];owner=app._workspace

def check(name,condition):
 assert condition,name
 checks.append(name)
def snap(widget,name):
 root.update();x,y=widget.winfo_rootx(),widget.winfo_rooty();w,h=widget.winfo_width(),widget.winfo_height()
 ImageGrab.grab(bbox=(x,y,x+w,y+h),xdisplay=os.environ['DISPLAY']).save(OUT/(name+'.png'))
 views.append({'name':name,'size':[w,h]})
with tempfile.TemporaryDirectory() as folder:
 owner.state_dir=Path(folder);owner.recent_path=Path(folder)/'recent.json'
 files=[str(ROOT/'benchmark_extensions/frozen_v1/cytometry'/n) for n in ('Control_01.csv','Control_02.csv','Treatment_01.csv','Treatment_02.csv')]
 hashes={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files}
 app.plot_type_var.set('Dot Plot');app.show_marginals_var.set(False)
 app._load_paths(files);app.x_var.set('FSC-A');app.y_var.set('SSC-A');app.apply_axes();root.update()
 ids=[owner.sample_id(p) for p in files]
 root.geometry('1440x1000+0+0');app.interface_size_var.set('Comfortable');app._apply_interface_size();root.update()
 row_click(app,ids[0]);row_click(app,ids[1]);row_click(app,ids[2],'#1')
 check('Two persistent row targets and independently inactive third sample',set(app._workspace_tree.selection())==set(ids[:2]) and not app.file_vars[files[2]].get())
 check('Selecting/toggling keeps Overlay',app.view_mode_var.get()=='overlay')
 check('Multi-target selection disables single-sample Show/Exclude',app._sample_show_button.instate(['disabled']) and app._sample_exclude_button.instate(['disabled']))
 app._select_sidebar_task('Data');root.update();snap(app._side_outer,'01_Data_selection')
 for task in ('Plot','Gates','Analysis'):
  app._select_sidebar_task(task);root.update();snap(app._side_outer,'02_'+task)
 owner.show_sample(app,ids[1]);row_click(app,ids[0],'#1')
 check('Other-sample deactivation keeps Cycle identity',owner.current_sid(app)==ids[1])
 app._select_all();app.view_mode_var.set('overlay');app._on_view_mode_change()
 dialog=StatisticalAuditDialog(owner,app);root.update();dialog.no_samples_button.invoke()
 for sid in ids[:2]:click_sample(dialog,sid)
 dialog.prepare();wait_dialog(root,dialog)
 check('Prepared benchmark audit with eligible variables',dialog.prepared is not None and dialog.variables.size()>0)
 names=list(dialog.variables.get(0,'end'));dialog.no_variables_button.invoke()
 for name in ('FSC-A','SSC-A'):click_variable(dialog,names.index(name))
 check('Audit mouse variable choices remain additive',len(dialog.variables.curselection())==2)
 snap(dialog,'03_Audit_selection');dialog.close()
 app.toggle_theme();app._select_sidebar_task('Plot');root.geometry('1024x768+0+0');root.update();snap(app._side_outer,'04_Light_compact_window')
 check('Raw benchmark bytes unchanged',all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha for p,sha in hashes.items()))
 check('No callback errors',not errors)
 (OUT/'result.json').write_text(json.dumps({'passed':len(checks),'checks':checks,'errors':errors,'views':views,'tk':root.tk.call('info','patchlevel'),'events':48000},indent=2)+'\n')
 print('PASS',len(checks),'benchmark interaction checks;',len(views),'native screenshots; Tk',root.tk.call('info','patchlevel'))
owner.dispose();root.destroy()
