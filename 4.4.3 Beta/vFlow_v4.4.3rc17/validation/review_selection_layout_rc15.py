"""Native benchmark-loaded audit and empty workspace layout review."""
from pathlib import Path
import sys,os,json,tempfile,tkinter as tk
from tkinter import messagebox,font
from PIL import ImageGrab
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from vflow.legacy.vflow_app import FlowTabManager
from vflow.ui.statistical_audit_dialog import StatisticalAuditDialog
from tests.test_audit_selection_gui import click_sample,click_variable,wait_dialog
OUT=ROOT/'validation/audit_selection_rc15';OUT.mkdir(exist_ok=True)
errors=[];views=[]
messagebox.showerror=lambda *a,**k:errors.append(str(a))
messagebox.showinfo=messagebox.showwarning=lambda *a,**k:None
messagebox.askyesnocancel=lambda *a,**k:False
root=tk.Tk();font.nametofont('TkDefaultFont').configure(family='DejaVu Sans');root.report_callback_exception=lambda *a:errors.append(str(a))
manager=FlowTabManager(root);app=manager._apps[0];owner=app._workspace

def snap(widget,name):
 root.update();x,y=widget.winfo_rootx(),widget.winfo_rooty();w,h=widget.winfo_width(),widget.winfo_height()
 ImageGrab.grab(bbox=(x,y,x+w,y+h),xdisplay=os.environ['DISPLAY']).save(OUT/(name+'.png'))
 views.append({'file':name+'.png','size':[w,h],'mode':app.interface_size_var.get(),'scaling':float(root.tk.call('tk','scaling'))})
with tempfile.TemporaryDirectory() as td:
 owner.state_dir=Path(td);owner.recent_path=Path(td)/'recent.json'
 app.plot_type_var.set('Dot Plot');app.show_marginals_var.set(False)
 files=[str(ROOT/'benchmark_extensions/frozen_v1/cytometry'/n) for n in ('Control_01.csv','Control_02.csv','Treatment_01.csv','Treatment_02.csv')]
 app._load_paths(files);root.update()
 root.tk.call('tk','scaling',96/72*2);app.interface_size_var.set('Large');app._apply_interface_size();root.update()
 dialog=StatisticalAuditDialog(owner,app);root.update();dialog.geometry('+0+0');root.update()
 dialog.no_samples_button.invoke()
 for p in files[:2]:click_sample(dialog,owner.sample_id(p))
 dialog.prepare();wait_dialog(root,dialog);dialog.no_variables_button.invoke();names=list(dialog.variables.get(0,'end'))
 for name in ('FSC-A','SSC-A'):click_variable(dialog,names.index(name))
 assert dialog.samples.winfo_ismapped() and dialog.prepare_button.winfo_ismapped()
 dialog.samples.yview_moveto(0);root.update()
 assert dialog.samples.bbox(owner.sample_id(files[0])) and dialog.run_button.winfo_ismapped()
 snap(dialog,'02_Large_200_Percent_Audit');dialog.close()
 root.tk.call('tk','scaling',96/72);app.interface_size_var.set('Comfortable');app._apply_interface_size()
 root.geometry('1440x1000+0+0');owner.clear();app._select_sidebar_task('Data');root.update()
 assert not hasattr(app,'_workspace_empty_open') and app._workspace_action_buttons['Open…'].winfo_ismapped()
 snap(app._side_outer,'03_Empty_Data_Workspace')
 assert not errors
 (OUT/'layout_inventory.json').write_text(json.dumps({'views':views,'errors':errors,'real_benchmark_files':4,'events':48000,'platform':'Linux/Tk9/Xvfb; 1920x1080 screen'},indent=2)+'\n')
 print('PASS 2 layout reviews: Large/200% audit with sample/prepare controls visible; empty Data workspace without duplicate Open. No callback errors.')
owner.dispose();root.destroy()
