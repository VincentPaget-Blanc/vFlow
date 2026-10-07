"""Real entry point, visibility, responsiveness and benchmark-load smoke check.

Use a display; MODE is source/module/console/spyder. Spyder modes
exercise spyder-kernels' real runner, without claiming its desktop front end.
"""
from pathlib import Path
import json,os,runpy,sys,tempfile,time,traceback,faulthandler
import tkinter as tk
from tkinter import messagebox
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
mode=os.environ.get('VFLOW_STARTUP_MODE','spyder-isolated')
faulthandler.enable()
errors=[]; observations=[]
for name in ('showinfo','showwarning'):
    setattr(messagebox,name,lambda *a,**k:None)
messagebox.showerror=lambda *a,**k:errors.append(str(a))
messagebox.askyesno=lambda *a,**k:True
messagebox.askyesnocancel=lambda *a,**k:False
from vflow.ui.tab_manager import FlowTabManagerBase
original_init=FlowTabManagerBase.__init__
state=tempfile.TemporaryDirectory(prefix='vflow-startup-')
def initialize(manager,root):
    original_init(manager,root)
    app=manager._apps[0]
    app._workspace.state_dir=Path(state.name)
    app._workspace.recent_path=Path(state.name)/'recent.json'
    deadline=time.monotonic()+8
    def verify_window():
        try:
            if not (root.winfo_ismapped() and app._workspace_tree.winfo_ismapped() and app._task_notebook.winfo_ismapped()) and time.monotonic()<deadline:
                root.after(100,verify_window)
                return
            assert root.state()=='normal' and root.winfo_ismapped()
            assert app._workspace_tree.winfo_ismapped()
            assert app._task_notebook.winfo_ismapped()
            app.plot_type_var.set('Dot Plot');app.show_marginals_var.set(False)
            paths=[str(ROOT/'benchmark_extensions/frozen_v1/cytometry'/name) for name in
                   ('Control_01.csv','Control_02.csv','Treatment_01.csv','Treatment_02.csv')]
            app._load_paths(paths)
            # Exercise sizing/font changes during the first event-loop turns.
            for width,height,size in [(1024,640,'Large'),(1440,900,'Compact'),(1280,800,'Automatic')]:
                root.geometry(f'{width}x{height}')
                app.interface_size_var.set(size);app._apply_interface_size()
            root.after(200,verify_loaded)
        except Exception:
            errors.append(traceback.format_exc());close()
    def verify_loaded():
        try:
            if app._sample_layout_pending is not None and time.monotonic()<deadline:
                root.after(100,verify_loaded)
                return
            assert len(app.loaded_files)==4
            assert sum(len(frame) for frame in app.loaded_files.values())==48000
            assert app._sample_layout_pending is None
            assert not app._sample_layout_busy
            assert app._sample_show_button.winfo_ismapped()
            app._select_sidebar_task('Gates')
            observations.append({'mode':mode,'version':__import__('vflow').__version__,
                'tk':root.tk.call('info','patchlevel'),'mapped':True,'samples':4,'events':48000})
        except Exception:
            errors.append(traceback.format_exc())
        finally:close()
    def close():
        if observations and not errors:print('PASS',json.dumps(observations),flush=True)
        if errors:print('ERROR',json.dumps(errors),flush=True)
        app._workspace.dispose();root.quit();root.destroy()
    root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
    root.after(200,verify_window)
FlowTabManagerBase.__init__=initialize
