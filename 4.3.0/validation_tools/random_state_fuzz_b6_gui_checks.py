#!/usr/bin/env python3
"""Deterministic real-GUI state-transition fuzz added by B6."""
from __future__ import annotations
import sys,tempfile,traceback,json,random
from pathlib import Path
import tkinter as tk
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/'source'/'vFlow_v4.3.0'; sys.path.insert(0,str(SRC))
from vflow.legacy.vflow_app import FlowApp
from vflow.legacy import vflow_app as legacy
class MB:
 errors=[];warnings=[]
 @classmethod
 def showerror(cls,t,m,*a,**k): cls.errors.append(f'{t}: {m}')
 @classmethod
 def showwarning(cls,t,m,*a,**k): cls.warnings.append(f'{t}: {m}')
 @staticmethod
 def showinfo(*a,**k): pass
 @staticmethod
 def askyesno(*a,**k): return False
legacy.messagebox=MB
rng=np.random.default_rng(12345); rnd=random.Random(12345)
fail=[]; ops=[]; async_errors=[]
with tempfile.TemporaryDirectory() as td:
 td=Path(td); paths=[]
 for i in range(3):
  n=100; p=td/f'f{i}.csv'; pd.DataFrame({'X':rng.normal(500+i*100,400,n),'Y':rng.normal(700+i*100,500,n),'Z':rng.lognormal(6,1,n)}).to_csv(p,index=False);paths.append(str(p))
 root=tk.Tk();root.withdraw();root.report_callback_exception=lambda et,e,tb: async_errors.append(''.join(traceback.format_exception(et,e,tb)))
 app=FlowApp(root);app._load_paths(paths);app.show_labels_var.set(False);app.show_legend_var.set(False);app.x_var.set('X');app.y_var.set('Y');app.apply_axes();app.canvas.draw()
 scales=['linear','asinh','log','legacy_biexp','legacy_logicle','logicle_gml2']; chans=['X','Y','Z']; plots=['Dot Plot','Density','Contour Plot']
 def invariant(step):
  try:
   xl=app.ax.get_xlim();yl=app.ax.get_ylim()
   if not (np.all(np.isfinite(xl)) and xl[0]<xl[1]): raise AssertionError(f'bad xlim {xl}')
   if not (np.all(np.isfinite(yl)) and yl[0]<yl[1]): raise AssertionError(f'bad ylim {yl}')
   if app.show_marginals_var.get() != (app.ax_top is not None and app.ax_right is not None): raise AssertionError('marginal axes mismatch')
   ids=[g['id'] for g in app.gates]
   if len(ids)!=len(set(ids)): raise AssertionError('duplicate gate ids')
   for attr in ('_sel_gate_id','_draw_gate_id','_hover_gate_id','_pinned_gate_id','_interior_hover_gate_id'):
    v=getattr(app,attr)
    if v is not None and v not in ids: raise AssertionError(f'stale {attr}={v}, ids={ids}')
   if set(app.loaded_files)&set(app.excluded_files): raise AssertionError('loaded/excluded overlap')
   if set(app.file_vars)!=set(app.loaded_files): raise AssertionError(f'file_vars mismatch {set(app.file_vars)^set(app.loaded_files)}')
   if app.view_mode_var.get()=='cycle' and app._active():
    if not 0 <= app.cycle_idx < len(app._active()): raise AssertionError(f'cycle idx {app.cycle_idx}')
   if app.lock_scale_var.get():
    if app._locked_xlim is None or app._locked_ylim is None: raise AssertionError('lock state missing limits')
    if not(app._locked_xlim[0]<app._locked_xlim[1] and app._locked_ylim[0]<app._locked_ylim[1]): raise AssertionError('lock limits inverted')
  except Exception as e:
   fail.append({'step':step,'op':ops[-1] if ops else None,'error':repr(e),'trace':traceback.format_exc()}); raise
 for step in range(80):
  op=rnd.choice(['scale','axes','marg','plot','grid','fit','lock','nudge','view','file','theme','add','delete','select','stats','cofactor'])
  ops.append(op)
  try:
   if op=='scale':
    app.x_scale_var.set(rnd.choice(scales));app.y_scale_var.set(rnd.choice(scales))
   elif op=='axes':
    x,y=rnd.sample(chans,2);app.x_var.set(x);app.y_var.set(y);app.apply_axes()
   elif op=='marg': app.show_marginals_var.set(not app.show_marginals_var.get());app.refresh_plot()
   elif op=='plot': app.plot_type_var.set(rnd.choice(plots));app.refresh_plot()
   elif op=='grid': app.show_grid_var.set(not app.show_grid_var.get());app.refresh_plot()
   elif op=='fit': app.fit_axes_var.set(not app.fit_axes_var.get());app.refresh_plot()
   elif op=='lock': app.lock_scale_var.set(not app.lock_scale_var.get());app._on_lock_scale_toggle()
   elif op=='nudge' and app.lock_scale_var.get(): app._nudge_axis(rnd.choice('xy'),rnd.choice(['lo','hi']),rnd.choice([-1,1]))
   elif op=='view': app.view_mode_var.set(rnd.choice(['overlay','cycle']));app._on_view_mode_change()
   elif op=='file':
    p=rnd.choice(list(app.file_vars));app.file_vars[p].set(not app.file_vars[p].get());app._on_active_files_changed()
   elif op=='theme': app.toggle_theme()
   elif op=='add':
    # create rectangle in current channels; geometry can include signed values
    g=app._add_gate(auto_type='rectangle',auto_apply={'x0':-100,'x1':700,'y0':-200,'y1':900});app._finish_gate(g)
   elif op=='delete' and app.gates:
    app._select_gate(rnd.choice(app.gates)['id']);app.clear_gate()
   elif op=='select' and app.gates: app._select_gate(rnd.choice(app.gates)['id'])
   elif op=='stats': app.stats_mode_var.set(rnd.choice(['perfile','merged']));app._update_stats_display()
   elif op=='cofactor': app.cofactor_str.set(str(rnd.choice([10,50,150,500,1000])))
   root.update_idletasks(); root.update(); app.canvas.draw(); invariant(step)
  except Exception as e:
   if not fail: fail.append({'step':step,'op':op,'error':repr(e),'trace':traceback.format_exc()})
   break
 result={'status':'PASS' if not fail and not async_errors and not MB.errors else 'FAIL','steps_completed':step+1,'failure':fail[:1],'async_errors':async_errors[:3],'messagebox_errors':MB.errors[:10],'last_ops':ops[-20:]}; print(json.dumps(result,indent=2)); raise SystemExit(0 if result['status']=='PASS' else 1)
