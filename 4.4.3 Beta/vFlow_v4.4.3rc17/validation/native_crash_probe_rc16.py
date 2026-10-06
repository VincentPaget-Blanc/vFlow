"""One isolated probe; intentionally unsafe controls must never run in the main app."""
import argparse, faulthandler, gc, json, os, sys, threading, weakref
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--package-root', type=Path, default=ROOT)
parser.add_argument('--scenario', choices=['worker_gc','main_gc','kde','audit','scan'], required=True)
args = parser.parse_args(); sys.path.insert(0,str(args.package_root))
faulthandler.enable(); gc.disable()
import tkinter as tk
events=[]
retired=tk.Tk();retired.cycle=retired;version=str(retired.tk.call('info','patchlevel'))
retired.destroy();ref=weakref.ref(retired,lambda _:events.append(threading.get_ident()));del retired
print(json.dumps({'stage':'retired','scenario':args.scenario,'tk':version,'main_thread':threading.get_ident(),'pending':ref() is not None}),flush=True)
if args.scenario in ('worker_gc','main_gc'):
    if args.scenario == 'main_gc': gc.collect()
    worker=threading.Thread(target=gc.collect,name='probe-gc');worker.start();worker.join()
elif args.scenario == 'kde':
    import numpy as np
    from vflow.plotting.kde_payloads import compute_kde_jobs_parallel, compute_density_render_payload
    rng=np.random.default_rng(1701);x=rng.normal(size=100);y=rng.normal(size=100);valid=np.ones(100,dtype=bool)
    def payload():
        gc.collect()
        return compute_density_render_payload(x,y,x,y,valid)
    result=compute_kde_jobs_parallel([(n,payload,(),{}) for n in range(2)],max_workers=2)
    assert all(value.action=='payload' for value in result.values())
else:
    import tempfile,time
    from tkinter import messagebox,font,filedialog
    from vflow.legacy.vflow_app import FlowTabManager
    messagebox.showinfo=messagebox.showwarning=lambda *a,**k:None
    messagebox.askyesnocancel=lambda *a,**k:False
    # Imports/GUI setup can collect old roots. Seed another retired interpreter
    # only after the live app is ready, immediately before the worker boundary.
    gc.collect();root=tk.Tk();font.nametofont('TkDefaultFont').configure(family='DejaVu Sans')
    manager=FlowTabManager(root);app=manager._apps[0];owner=app._workspace
    app.plot_type_var.set('Dot Plot');app.show_marginals_var.set(False)
    import pandas as pd
    with tempfile.TemporaryDirectory() as folder:
        owner.state_dir=Path(folder);owner.recent_path=Path(folder)/'recent.json'
        paths=[]
        for n in range(2):
            p=Path(folder)/f'{n}.csv';pd.DataFrame({'X':[1.,2.,3.,4.,5.],'Y':[2.,4.,1.,3.,6.]}).to_csv(p,index=False);paths.append(str(p))
        app._load_paths(paths);root.update()
        orphan=tk.Tk();orphan.cycle=orphan;orphan.destroy()
        orphan_ref=weakref.ref(orphan,lambda _:events.append(threading.get_ident()));del orphan
        if args.scenario=='audit':
            import vflow.ui.statistical_audit_dialog as module
            original=module.materialize_population_inputs
            def materialize(*a,**k):gc.collect();return original(*a,**k)
            module.materialize_population_inputs=materialize
            dialog=module.StatisticalAuditDialog(owner,app);dialog.prepare()
            deadline=time.monotonic()+10
            while dialog.worker.is_alive() and time.monotonic()<deadline:root.update();time.sleep(.005)
            assert not dialog.worker.is_alive();dialog.poll();assert dialog.prepared;dialog.close()
        else:
            import vflow.workspace.controller as module
            from vflow.workspace.model import FileReference
            owner.missing={'probe':FileReference(str(Path(folder)/'absent.csv'),filename='absent.csv')}
            def scan(*a,**k):gc.collect();return {'probe':[]}
            module.scan_candidates=scan;filedialog.askdirectory=lambda **k:folder
            owner.find_missing();deadline=time.monotonic()+10
            while owner._scan_running and time.monotonic()<deadline:root.update();time.sleep(.005)
            assert not owner._scan_running
        assert orphan_ref() is None
    owner.dispose();root.destroy()
assert ref() is None
print(json.dumps({'stage':'passed','scenario':args.scenario,'finalizer_threads':events,'main_thread':threading.get_ident()}),flush=True)
