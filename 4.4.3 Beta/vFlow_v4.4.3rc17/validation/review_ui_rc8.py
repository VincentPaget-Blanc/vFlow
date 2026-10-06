"""Native visual inventory of app-owned tasks, menus and dialogs."""
import json,os,sys,tempfile,time
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk,messagebox
from PIL import ImageGrab,Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from vflow.legacy.vflow_app import FlowTabManager,PolarAnalysisWindow,BatchPlotWindow
from vflow.ui.folder_scan_dialog import FolderScanDialog
from vflow.ui.batch_stats_dialog import BatchStatsDialog
from vflow.ui.axis_name_resolver import AxisNameResolverDialog,ExactAxisNameResolverDialog,UnresolvedFilesDialog
from vflow.ui.statistical_audit_dialog import StatisticalAuditDialog,AuditResultsDialog,AuditListDialog
from vflow.ui.audit_interpretation import show_interpretation
from vflow.statistics import run_audit
from vflow.statistics.workspace_audit import prepare_samples,commit
PHASE=sys.argv[1] if len(sys.argv)>1 else 'after'
OUT=ROOT/'validation'/('ui_review_rc8_'+PHASE);OUT.mkdir(exist_ok=True)
errors=[];notes=[];records=[]
messagebox.showerror=lambda *a,**k:errors.append(str(a));messagebox.showinfo=messagebox.showwarning=lambda *a,**k:notes.append(str(a))
messagebox.askyesno=lambda *a,**k:True;messagebox.askyesnocancel=lambda *a,**k:False
root=tk.Tk();tkfont.nametofont('TkDefaultFont').configure(family='DejaVu Sans');root.report_callback_exception=lambda *a:errors.append(str(a))
manager=FlowTabManager(root);root.geometry('1440x1080+0+0');app=manager._apps[0];owner=app._workspace

def descendants(w):
 for c in w.winfo_children():yield c;yield from descendants(c)
def snapshot(w,name):
 root.update();w.lift() if isinstance(w,tk.Toplevel) else None;root.update()
 x,y=w.winfo_rootx(),w.winfo_rooty();width,height=w.winfo_width(),w.winfo_height()
 p=OUT/(name+'.png');ImageGrab.grab(bbox=(x,y,x+width,y+height),xdisplay=os.environ['DISPLAY']).save(p)
 controls=[]
 for child in descendants(w):
  if 'text' in child.keys():
   text=str(child.cget('text'))
   if text:controls.append({'kind':child.winfo_class(),'text':text,'mapped':bool(child.winfo_ismapped()),'rect':[child.winfo_rootx()-x,child.winfo_rooty()-y,child.winfo_width(),child.winfo_height()]})
 records.append({'file':p.name,'size':[width,height],'controls':controls})
 return p

def menu_snapshot(menu,name,x=590,y=120):
 menu.post(x,y);root.update();snapshot(menu,name);labels=[]
 for i in range((menu.index('end') or 0)+1):
  if menu.type(i) not in ('separator','tearoff'):labels.append({'label':menu.entrycget(i,'label'),'state':menu.entrycget(i,'state')})
 records[-1]['menu_entries']=labels;menu.unpost();root.update()

with tempfile.TemporaryDirectory() as td:
 owner.state_dir=Path(td)/'state';owner.recent_path=Path(td)/'recent.json'
 files=[ROOT/'benchmark_extensions/frozen_v1/cytometry'/f for f in ['Control_01.csv','Control_02.csv','Treatment_01.csv','Treatment_02.csv']]
 app._load_paths([str(p) for p in files]);app.interface_size_var.set('Comfortable');app._apply_interface_size()
 if app._theme_name!='light':app.toggle_theme()
 app._main_pane.sash_place(0,500,0);root.update()
 app.x_var.set('FSC-A');app.y_var.set('SSC-A');app.apply_axes();app.x_scale_var.set('linear');app.y_scale_var.set('linear');app.plot_type_var.set('Dot Plot')
 app._add_gate(auto_type='rectangle');g=app._sel_gate();g.update(x0=45000.,x1=105000.,y0=5000.,y1=55000.,name='Benchmark lymphocytes',applied=True)
 app._bind_gate_context(g);app._rebuild_gate_manager();app._rebuild_thresh_panel();app.refresh_plot();root.update()
 owner.save(path=str(Path(td)/'Benchmark.vflow'))
 for i,task in enumerate(['Data','Plot','Gates','Analysis'],1):
  app._select_sidebar_task(task);root.update();snapshot(app._side_outer,f'{i:02d}_{task}')
 app._gate_tools_notebook.select(app._gate_tool_pages['AUTO-GATE']);app._select_sidebar_task('Gates');root.update();snapshot(app._side_outer,'05_Automatic')
 app._set_all_sections(True);app._select_sidebar_task('Plot');root.update();snapshot(app._side_outer,'06_Plot_Advanced')
 app._select_sidebar_task('Gates');app._gate_tools_notebook.select(app._gate_tool_pages['GATING']);root.update();snapshot(app._side_outer,'07_Gates_Advanced')
 app._select_sidebar_task('Analysis');root.update();snapshot(app._side_outer,'08_Analysis_Advanced')
 for task in ('Plot','Gates','Analysis'):
  app._select_sidebar_task(task);app._task_pages[task]['canvas'].yview_moveto(1);root.update();snapshot(app._side_outer,'08_'+task+'_Bottom');app._task_pages[task]['canvas'].yview_moveto(0)
 app._select_sidebar_task('Plot');root.update();snapshot(root,'09_Full_App')
 bar=root.nametowidget(root.cget('menu'))
 for i in range(bar.index('end')+1):
  if bar.type(i)=='cascade':menu_snapshot(root.nametowidget(bar.entrycget(i,'menu')),f'10_Menu_{i}')
 menu_snapshot(owner._recent_menu,'11_Recent');menu_snapshot(app._sidebar_settings_menu,'12_Settings')
 posted=[];orig=tk.Menu.tk_popup;tk.Menu.tk_popup=lambda m,x,y:posted.append(m)
 sid=owner.sample_id(str(files[0]));app._workspace_tree.selection_set(sid);owner.sample_menu(app,sid=sid);menu_snapshot(posted[-1],'13_Sample_Context')
 # The gate menu is bound to its visible name (it need not be a native button).
 app._select_sidebar_task('Gates');root.update()
 name=next(w for w in descendants(app.gate_manager_frame) if 'text' in w.keys() and 'Benchmark lymphocytes' in str(w.cget('text')))
 name.event_generate('<Button-3>',x=5,y=5);root.update()
 if posted:menu_snapshot(posted[-1],'14_Gate_Context')
 tk.Menu.tk_popup=orig
 d=FolderScanDialog(root,app.T);snapshot(d,'15_Folder_Load_Concatenate');d.destroy()
 d=BatchStatsDialog(root,app.T,[str(files[0].parent)],app.x_channel,app.y_channel);snapshot(d,'16_Batch_Stats');d.destroy()
 d=AxisNameResolverDialog(root,app);snapshot(d,'17_Axis_Name_Resolver');d.destroy()
 for cls,tag in [(ExactAxisNameResolverDialog,'17_Exact_Columns'),(UnresolvedFilesDialog,'17_Unresolved_Files')]:
  d=cls(root,app);snapshot(d,tag);d.destroy()
 app._edit_logicle_params();d=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel));snapshot(d,'18_Logicle');d.destroy()
 def capture_rename():
  d=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel));snapshot(d,'19_Rename_Gate');d.destroy()
 root.after(100,capture_rename);app._rename_gate(g['id'])
 d=StatisticalAuditDialog(owner,app);snapshot(d,'20_Audit_Preparation');d.close()
 ids=[owner.sample_id(str(p)) for p in files[:2]];bundle=run_audit(prepare_samples(owner,app,ids));ref=commit(owner,bundle)
 d=AuditResultsDialog(owner,ref,bundle);snapshot(d,'21_Audit_Results');d.tree.selection_set(ids[0]);d.details();detail=next(w for w in descendants(d) if isinstance(w,tk.Toplevel));snapshot(detail,'22_Audit_Details');detail.destroy()
 d.export();export=next(w for w in descendants(d) if isinstance(w,tk.Toplevel));snapshot(export,'23_Audit_Export');export.destroy();d.destroy()
 d=AuditListDialog(owner);snapshot(d,'24_Saved_Audits');d.destroy()
 show_interpretation(root,bundle);d=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel));snapshot(d,'25_Audit_Interpretation');d.destroy()
 # Exercise genuine automatic fits and the new per-threshold actions.
 app.auto_gate_otsu();root.update();gid=app._sel_gate_id
 snapshot(app._side_outer,'31_Otsu_Thresholds')
 app._delete_threshold(gid,'x',0);root.update();snapshot(app._side_outer,'32_Delete_X')
 app._delete_threshold(gid,'y',0);root.update();snapshot(app._side_outer,'33_Empty_Threshold_Gate')
 owner.save(path=str(Path(td)/'Empty_Threshold_Benchmark.vflow'))
 owner.gate_action(app,'undo',gid);app._show_gate_info(gid);root.update();snapshot(app._side_outer,'34_Undo_Threshold')
 app.auto_gate_gmm_multi();root.update();gid=app._sel_gate_id;snapshot(app._side_outer,'35_GMM_Thresholds')
 ybs=app._sel_gate().get('y_boundaries') or []
 if ybs:app._delete_threshold(gid,'y',len(ybs)//2)
 app._show_gate_info(gid);root.update();snapshot(app._side_outer,'36_GMM_Delete_Y')
 owner.gate_action(app,'undo',gid);app._show_gate_info(gid);root.update();snapshot(app._side_outer,'37_GMM_Undo')
 scan_folder=Path(td)/'long_file_names';scan_folder.mkdir()
 for i in range(70):(scan_folder/(str(i)+'_Long_measurement_filename_'*5+'.csv')).write_text('X,Y\n1,2\n')
 d=FolderScanDialog(root,app.T);d._folder.set(str(scan_folder));d._scan();root.update();snapshot(d,'38_Folder_Scroll');d._cv.yview_moveto(1);d._cv.xview_moveto(1);root.update();snapshot(d,'39_Folder_Scroll_End');d.destroy()
 # A separate benchmark microscopy population exercises the actual vector controls.
 owner.clear();micro=sorted((ROOT/'benchmark_extensions/frozen_v1/microscopy').glob('Microscopy_0[123].csv'))
 app._load_paths([str(p) for p in micro]);root.update()
 for cls,tag in [(PolarAnalysisWindow,'26_Polar'),(BatchPlotWindow,'28_Batch_Plots')]:
  d=cls(root,app.T,app);root.update()
  if cls is PolarAnalysisWindow:
   for var,column in [(d._cx1_var,'Ch1-X'),(d._cy1_var,'Ch1-Y'),(d._cx2_var,'Ch2-X'),(d._cy2_var,'Ch2-Y')]:var.set(column)
   d._compute_and_plot()
  time.sleep(.2);root.update();snapshot(d,tag)
  d._sb_canvas.yview_moveto(1);root.update();snapshot(d,tag+'_Bottom');d._on_close()
 # Task tabs remain reachable with a larger font and small window.
 root.geometry('1024x768+0+0');app.interface_size_var.set('Large');app._apply_interface_size();root.update();app._select_sidebar_task('Plot');snapshot(root,'30_Small_Large_Font')
 owner.dispose();root.destroy()
metadata={'phase':PHASE,'errors':errors,'notes':notes,'views':records}
(OUT/'inventory.json').write_text(json.dumps(metadata,indent=2)+'\n')
# Contact sheets are annotated copies for inspection; individual PNGs are native captures.
paths=sorted(OUT.glob('*.png'))
for start in range(0,len(paths),8):
 sheet=Image.new('RGB',(1600,2080),'white');draw=ImageDraw.Draw(sheet)
 for k,p in enumerate(paths[start:start+8]):
  im=Image.open(p);im.thumbnail((780,460));x=(k%2)*800;y=(k//2)*520
  draw.text((x+10,y+4),p.stem,fill='black');sheet.paste(im,(x+10,y+30))
 sheet.save(OUT/f'contact_{start//8+1}.jpg')
print(json.dumps({'phase':PHASE,'views':len(records),'errors':errors,'notes':notes},indent=2))
assert not errors,errors
