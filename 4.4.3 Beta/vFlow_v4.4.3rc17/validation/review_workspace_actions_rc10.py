"""Real benchmark data through Data workspace actions and native screenshots."""
from pathlib import Path
import json,os,tempfile,hashlib,sys
import tkinter as tk
from tkinter import messagebox,filedialog,font
from PIL import ImageGrab
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vflow.legacy.vflow_app import FlowTabManager
OUT=ROOT/'validation/workspace_actions_rc10';OUT.mkdir(exist_ok=True)
errors=[];records=[]
messagebox.showerror=lambda *a,**kw:errors.append(str(a))
messagebox.showinfo=messagebox.showwarning=lambda *a,**kw:None
messagebox.askyesnocancel=lambda *a,**kw:False
messagebox.askyesno=lambda *a,**kw:True
root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(str(a))
font.nametofont('TkDefaultFont').configure(family='DejaVu Sans')
manager=FlowTabManager(root);app=manager._apps[0];owner=app._workspace
root.geometry('1440x1080+0+0')
app.plot_type_var.set('Dot Plot');app.show_marginals_var.set(False)
files=[ROOT/'benchmark_extensions/frozen_v1/cytometry'/n for n in ('Control_01.csv','Control_02.csv','Treatment_01.csv','Treatment_02.csv')]
original={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
def snap(name):
 root.update(); w=app._side_outer; x,y=w.winfo_rootx(),w.winfo_rooty()
 ImageGrab.grab(bbox=(x,y,x+w.winfo_width(),y+w.winfo_height()),xdisplay=os.environ['DISPLAY']).save(OUT/(name+'.png'))
 records.append({'file':name+'.png','size':[w.winfo_width(),w.winfo_height()],'name':owner.workspace_name(),'state':app._workspace_save_state_var.get(),'events':sum(len(df) for df in app.loaded_files.values()),'samples':len(owner.document.samples),'tk_scaling':float(root.tk.call('tk','scaling'))})
with tempfile.TemporaryDirectory() as td:
 td=Path(td);owner.state_dir=td/'state';owner.recent_path=td/'recent.json'
 app._load_paths([str(p) for p in files]);app.x_var.set('FSC-A');app.y_var.set('SSC-A');app.apply_axes()
 if app._theme_name!='light':app.toggle_theme()
 app.interface_size_var.set('Comfortable');app._apply_interface_size();app._main_pane.sash_place(0,520,0)
 app._select_sidebar_task('Data');root.update();snap('01_Data_Workspace_Controls')
 app._workspace_name_entry.focus_force();root.update();app._workspace_name_var.set('Benchmark workspace α');app._workspace_name_entry.event_generate('<Return>');root.update()
 dest=td/'Benchmark.vflow';filedialog.asksaveasfilename=lambda **kw:str(dest)
 app._workspace_action_buttons['Save'].invoke();root.update();assert dest.exists()
 app._workspace_action_buttons['Close'].invoke();root.update();assert not owner.document.samples
 filedialog.askopenfilename=lambda **kw:str(dest)
 app._workspace_action_buttons['Open…'].invoke();root.update();app._select_sidebar_task('Data');root.update()
 assert owner.workspace_name()=='Benchmark workspace α'
 assert not owner.dirty and not owner.gates_dirty
 assert len(app.loaded_files)==4 and sum(len(df) for df in app.loaded_files.values())==48000
 snap('02_Saved_And_Reopened')
 for width,height,scale,mode,name in [(1024,768,1.,'Compact','03_Compact_1024'),(1920,1080,2.,'Large','04_Large_200_Percent')]:
  root.tk.call('tk','scaling',(96/72)*scale);root.geometry(f'{width}x{height}+0+0');app.interface_size_var.set(mode);app._apply_interface_size();root.update();app._select_sidebar_task('Data');root.update();app._task_pages['Data']['canvas'].yview_moveto(0);snap(name)
 assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha for p,sha in original.items())
 assert not errors
 (OUT/'inventory.json').write_text(json.dumps({'views':records,'errors':errors,'platform':'Linux/Python3.12/Tk9/Xvfb','real_benchmark_files':4,'events':48000,'save_close_open_controls_passed':True,'source_hashes_unchanged':True},indent=2)+'\n')
 print('PASS UI benchmark controls: 4 files, 48000 events; save-close-open and name persistence; 4 native views; no callback errors.',flush=True)
owner.dispose();root.destroy()
