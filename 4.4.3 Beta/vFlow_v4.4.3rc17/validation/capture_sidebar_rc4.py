"""Capture native sidebar viewports with untouched frozen benchmark acquisitions."""
import json,os,sys,tempfile
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox
from PIL import ImageGrab
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from vflow.legacy.vflow_app import FlowTabManager
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT.parent/'vFlow_Benchmark_Left_Panel_Screenshots'
OUTPUT.mkdir(exist_ok=True)
errors=[]
messagebox.showerror=lambda *a,**k:errors.append(str(a))
messagebox.showinfo=messagebox.showwarning=lambda *a,**k:None
root=tk.Tk();tkfont.nametofont('TkDefaultFont').configure(family='DejaVu Sans');root.report_callback_exception=lambda *a:errors.append(str(a))
manager=FlowTabManager(root);root.geometry('1440x1100+0+0');app=manager._apps[0];owner=app._workspace
with tempfile.TemporaryDirectory() as td:
    owner.state_dir=Path(td)/'state';owner.recent_path=Path(td)/'recent.json'
    files=[ROOT/'benchmark_extensions/frozen_v1/cytometry'/name for name in ['Control_01.csv','Control_02.csv','Treatment_01.csv','Treatment_02.csv']]
    app._load_paths([str(p) for p in files]);root.update()
    app.interface_size_var.set('Comfortable');app._apply_interface_size()
    if app._theme_name!='light':app.toggle_theme()
    app._main_pane.sash_place(0,570,0)
    app.x_var.set('FSC-A');app.y_var.set('SSC-A');app.apply_axes()
    app.x_scale_var.set('linear');app.y_scale_var.set('linear');app.plot_type_var.set('Dot Plot');app.refresh_plot();root.update()
    app._set_all_sections(True);root.update()
    app._add_gate(auto_type='rectangle');gate=app._sel_gate()
    definition=json.loads((ROOT/'benchmark_extensions/frozen_v1/references/benchmark_gate_definitions.json').read_text())['gates'][0]
    gate.update({k:definition[k] for k in ('x0','x1','y0','y1')});gate['name']=definition['id'];gate['applied']=True
    app._bind_gate_context(gate);app._rebuild_gate_manager();app._rebuild_thresh_panel();app._recompute_all_gate_stats();app.refresh_plot();root.update()
    assert len(app.loaded_files)==4 and len(owner.document.samples)==4
    assert owner.save(path=str(Path(td)/'Benchmark.vflow'))
    records=[]
    for name,section in [('01_Samples_and_Files','FILES'),('02_Axes_and_Scales','AXES'),('03_Manual_Gating','GATING'),('04_Automatic_Gating','AUTO-GATE'),('05_Gate_Manager_and_Statistics','GATE MANAGER'),('06_Exports_and_Analysis','EXPORT')]:
        fraction=0. if section=='FILES' else app._sections[section][1]._section_header.winfo_y()/app.sidebar.winfo_height()
        app._side_canvas.yview_moveto(fraction);root.update()
        x=app._side_outer.winfo_rootx();y=app._side_outer.winfo_rooty();w=app._side_outer.winfo_width();h=app._side_outer.winfo_height()
        path=OUTPUT/(name+'.png')
        ImageGrab.grab(bbox=(x,y,x+w,y+h),xdisplay=os.environ['DISPLAY']).save(path)
        records.append({'file':path.name,'viewport_fraction':fraction,'pixels':[w,h]})
    (OUTPUT/'README.md').write_text('# Benchmark dataset — native left panel screenshots\n\nFour frozen cytometry CSVs are loaded: Control_01, Control_02, Treatment_01 and Treatment_02. All are active. The all-samples rectangle is G_LYMPH_RECT from the benchmark gate definitions. The screenshot session uses Light mode, Comfortable text and a widened sidebar; sections are expanded. The pinned workspace/sample panel remains visible as the lower controls scroll. These are unaltered native screenshots captured from the actual Linux/Tk application, not mockups.\n\n01: samples and sources.\n02: axes and scales.\n03: manual gating.\n04: automatic gating.\n05: gate manager and statistics.\n06: exports and analysis.\n\nThe capture requests DejaVu Sans; the native Tk font fallback is recorded in the validation metadata. Screenshots use the Linux/Tk runtime; macOS and Windows styling may differ.\n')
    (ROOT/'validation/sidebar_capture_rc4.json').write_text(json.dumps({'sources':[p.name for p in files],'events':{Path(p).name:len(df) for p,df in app.loaded_files.items()},'screenshots':records,'capture_font':tkfont.nametofont('TkDefaultFont').actual(),'errors':errors},indent=2)+'\n')
    assert not errors,errors
owner.dispose();root.destroy()
print(OUTPUT)
