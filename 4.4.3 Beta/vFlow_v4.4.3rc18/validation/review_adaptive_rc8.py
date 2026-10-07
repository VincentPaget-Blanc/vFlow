"""Native adaptive sample views with supplied benchmark inputs and labeled subsets."""
from pathlib import Path
import os,sys,json,tempfile
import tkinter as tk
import tkinter.font as font
from tkinter import messagebox,ttk
from PIL import ImageGrab,Image,ImageDraw
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from vflow.legacy.vflow_app import FlowTabManager
OUT=ROOT/'validation/adaptive_review_rc8';OUT.mkdir(exist_ok=True)
errors=[];records=[]
messagebox.showerror=lambda *a,**k:errors.append(str(a));messagebox.showwarning=messagebox.showinfo=lambda *a,**k:None
messagebox.askyesno=lambda *a,**k:True;messagebox.askyesnocancel=lambda *a,**k:False
root=tk.Tk();font.nametofont('TkDefaultFont').configure(family='DejaVu Sans');root.report_callback_exception=lambda *a:errors.append(str(a))
manager=FlowTabManager(root);app=manager._apps[0];owner=app._workspace

def snap(name):
 root.update();w=app._side_outer;x,y=w.winfo_rootx(),w.winfo_rooty();width,height=w.winfo_width(),w.winfo_height()
 ImageGrab.grab(bbox=(x,y,x+width,y+height),xdisplay=os.environ['DISPLAY']).save(OUT/(name+'.png'))
 records.append({'file':name+'.png','size':[width,height],'sample_count':len(app._workspace_tree.get_children()),'sample_tree_height':app._workspace_tree.winfo_height(),'outer_scroll':list(app._sidebar_outer_canvas.yview()),'row_height':int(ttk.Style(root).lookup('Treeview','rowheight')),'scaling':float(root.tk.call('tk','scaling')),'mode':app.interface_size_var.get()})

with tempfile.TemporaryDirectory() as td:
 td=Path(td);owner.state_dir=td/'state';owner.recent_path=td/'recent.json'
 files=[ROOT/'benchmark_extensions/frozen_v1/cytometry'/name for name in ('Control_01.csv','Control_02.csv','Treatment_01.csv','Treatment_02.csv')]
 app.plot_type_var.set('Dot Plot');app.show_marginals_var.set(False);app._load_paths([str(p) for p in files]);app.x_var.set('FSC-A');app.y_var.set('SSC-A');app.apply_axes()
 if app._theme_name!='light':app.toggle_theme()
 root.geometry('1440x1080+0+0');app.interface_size_var.set('Comfortable');app._apply_interface_size();app._main_pane.sash_place(0,520,0);root.update();app._sidebar_outer_canvas.yview_moveto(0)
 snap('01_Short_List')
 frames=[pd.read_csv(p).head(250) for p in files];extra=[]
 for i in range(60-len(files)):
  p=td/f'UI_Subset_{i+1:02d}.csv';frames[i%len(frames)].to_csv(p,index=False);extra.append(str(p))
 app._load_paths(extra);root.update();app._sidebar_outer_canvas.yview_moveto(0);snap('02_Long_List_1080')
 app._select_sidebar_task('Plot');root.update();snap('03_Click_Plot_Settings')
 app._task_pages['Plot']['canvas'].yview_moveto(1);root.update();snap('04_Plot_Export_End')
 app._select_sidebar_task('Gates');root.update();snap('05_Click_Gates')
 for w,h,scale,mode,name in [(1024,640,1,'Compact','06_Compact_640'),(1440,900,1.5,'Comfortable','07_Scaling_150'),(1920,1080,2,'Large','08_Scaling_200')]:
  root.tk.call('tk','scaling',96/72*scale);root.geometry(f'{w}x{h}+0+0');app.interface_size_var.set(mode);app._apply_interface_size();root.update();app._sidebar_outer_canvas.yview_moveto(0);snap(name)
 root.tk.call('tk','scaling',96/72);root.geometry('1440x1080+0+0');app.interface_size_var.set('Comfortable');app._apply_interface_size();root.update()
 app._sample_task_pane.sash_place(0,0,round(app._sidebar_outer_canvas.winfo_height()*.55));app._sample_pane_released();root.update();app._sidebar_outer_canvas.yview_moveto(0);snap('09_Manual_Divider')
 app.sample_panel_mode_var.set('Automatic');app._set_sample_panel_mode();root.update();app._sidebar_outer_canvas.yview_moveto(0);owner.save(path=str(td/'Adaptive.vflow'));owner.open(str(td/'Adaptive.vflow'));root.update();snap('10_Automatic_Reopened')
metadata={'views':records,'errors':errors,'data':'4 frozen cytometry CSVs (48,000 events) plus 56 labeled 250-row benchmark subsets for UI stress only (62,000 total events). Subsets are not independent biological acquisitions.','platform':'Linux/Tk 9/Xvfb'}
(OUT/'inventory.json').write_text(json.dumps(metadata,indent=2)+'\n')
thumbs=[]
for r in records:
 im=Image.open(OUT/r['file']).convert('RGB');im.thumbnail((330,640));tile=Image.new('RGB',(350,685),'#eee');tile.paste(im,((350-im.width)//2,30));ImageDraw.Draw(tile).text((8,8),r['file'],fill='#111');thumbs.append(tile)
for i in range(0,len(thumbs),5):
 sheet=Image.new('RGB',(350*len(thumbs[i:i+5]),685),'#eee')
 for j,t in enumerate(thumbs[i:i+5]):sheet.paste(t,(350*j,0))
 sheet.save(OUT/f'contact_{i//5+1}.jpg')
print(json.dumps({'native_views':len(records),'errors':errors,'events':sum(len(df) for df in app.loaded_files.values())}))
owner.dispose();root.destroy();assert not errors
