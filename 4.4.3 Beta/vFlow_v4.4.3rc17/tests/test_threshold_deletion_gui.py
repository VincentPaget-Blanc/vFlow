"""Exercise physical boundary deletion through real Tk/workspace/export paths."""
import copy,os
import tkinter as tk
from tkinter import ttk
import pandas as pd
import pytest
from tests.test_workspace_gui import experiment
from tests.test_task_sidebar_gui import widgets
from vflow.ui.folder_scan_dialog import FolderScanDialog
from vflow.ui.tooltips import tooltip

pytestmark=pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='Native Tk display required')

def crosshair(app):
    app._add_gate(auto_type='crosshair');g=app._sel_gate()
    g.update(x_boundaries=[40.,100.,200.],x_thresh_vars=[tk.BooleanVar(app.root,value=v) for v in [True,False,True]],
        y_boundaries=[40.,100.],y_thresh_vars=[tk.BooleanVar(app.root,value=v) for v in [False,True]],y_boundary=999.,applied=True)
    app._bind_gate_context(g);app._recompute_all_gate_stats();app.refresh_plot();app._show_gate_info(g['id']);return app._sel_gate()

def delete(app,axis,index):
    buttons=[w for w in widgets(app.thresh_panel) if isinstance(w,ttk.Button) and w.cget('text')=='Delete']
    # Threshold panel presents multi-Y first, then X.
    g=app._sel_gate();n_y=len(g.get('y_boundaries') or []) or int(g.get('y_boundary') is not None)
    buttons[index+(n_y if axis=='x' else 0)].invoke()

@pytest.mark.parametrize('axis,index',[('x',0),('x',1),('x',2),('y',0),('y',1)])
def test_delete_buttons_reindex_preserve_values_save_reopen_and_undo(experiment,tmp_path,axis,index):
    root,manager,app,paths,errors=experiment;g=crosshair(app);gid=g['id'];owner=app._workspace
    original=copy.deepcopy(owner.stores['main'].resolve_gate(None,gid));source=app.loaded_files[paths[0]].copy()
    delete(app,axis,index);root.update();edited=owner.stores['main'].resolve_gate(None,gid)
    assert len(edited[axis+'_boundaries'])==len(original[axis+'_boundaries'])-1
    pd.testing.assert_frame_equal(app.loaded_files[paths[0]],source)
    assert sum(v['count'] for v in app.gate_stats[gid][paths[0]]['stats'].values())==5
    owner.gate_action(app,'undo',gid);root.update();assert owner.stores['main'].resolve_gate(None,gid)==original
    delete(app,axis,index);root.update();dest=tmp_path/'Edited.vflow';assert owner.save(path=str(dest))
    assert owner.open(str(dest));root.update();assert owner.stores['main'].resolve_gate(None,gid)==edited

@pytest.mark.parametrize('scope',['Current sample','Selected samples'])
def test_delete_respects_sample_scope_and_keeps_shared_gate(experiment,scope):
    root,manager,app,paths,errors=experiment;g=crosshair(app);gid=g['id'];owner=app._workspace
    original=copy.deepcopy(owner.stores['main'].resolve_gate(None,gid))
    sid=owner.sample_id(paths[0]);owner.show_sample(app,sid)
    selected=[owner.sample_id(p) for p in paths[:2]]
    app._workspace_tree.selection_set(selected);app.gate_scope_var.set(scope);owner.scope_changed(app);root.update()
    assert app._delete_threshold(gid,'x',0);root.update()
    assert owner.stores['main'].resolve_gate(None,gid)==original
    expected=selected if scope=='Selected samples' else [sid]
    for p in paths:
        target=owner.sample_id(p);count=len(owner.stores['main'].resolve_gate(target,gid)['x_boundaries'])
        assert count==(2 if target in expected else 3)


def test_remove_every_boundary_undo_and_untick_summary(experiment):
    root,manager,app,paths,errors=experiment;g=crosshair(app);gid=g['id']
    for v in app._sel_gate()['x_thresh_vars']+app._sel_gate()['y_thresh_vars']:v.set(False)
    app._on_thresh_toggle();assert 'All thresholds are unticked' in app._threshold_summary_var.get()
    while app._sel_gate()['x_boundaries']:assert app._delete_threshold(gid,'x',0)
    while app._sel_gate().get('y_boundaries'):assert app._delete_threshold(gid,'y',0)
    root.update();assert 'No thresholds remain' in app._threshold_summary_var.get()
    summary=next(w for w in widgets(app.thresh_panel) if 'textvariable' in w.keys() and str(w.cget('textvariable'))==str(app._threshold_summary_var))
    viewport=app._task_pages['Gates']['canvas']
    assert summary.winfo_rooty()>=viewport.winfo_rooty()
    assert summary.winfo_rooty()+summary.winfo_height()<=viewport.winfo_rooty()+viewport.winfo_height()
    assert app.gate_stats[gid]=={}
    app._workspace.gate_action(app,'undo',gid);root.update();assert app._sel_gate()['y_boundaries']==[100.]
    before=app._workspace.stores['main'].snapshot()
    assert not app._delete_threshold(999,'x',0) and not app._delete_threshold(gid,'y',99)
    assert app._workspace.stores['main'].snapshot()==before


def test_actual_otsu_fit_surfaces_thresholds_and_deletion_keeps_other_axis(experiment):
    root,manager,app,paths,errors=experiment
    app._select_sidebar_task('Gates');app._gate_tools_notebook.select(app._gate_tool_pages['AUTO-GATE'])
    app.auto_gate_otsu();root.update();g=app._sel_gate();gid=g['id'];old_y=g['y_boundary']
    assert app._sidebar_task()=='Gates' and app._task_pages['Gates']['canvas'].yview()[0]>0
    assert app._delete_threshold(gid,'x',0);root.update()
    assert not app._sel_gate()['x_boundaries'] and app._sel_gate()['y_boundary']==old_y
    assert sum(v['count'] for v in app.gate_stats[gid][paths[0]]['stats'].values())==5


def test_tiny_threshold_values_are_displayed_without_rounding_to_zero(experiment):
    root,manager,app,paths,errors=experiment;g=crosshair(app)
    app._sel_gate()['x_boundaries']=[1.23456789e-8];app._sel_gate()['x_thresh_vars']=[tk.BooleanVar(root,value=True)]
    app._rebuild_thresh_panel();root.update()
    labels=[str(w.cget('text')) for w in widgets(app.thresh_panel) if 'text' in w.keys()]
    assert any('1.23456789e-08' in text for text in labels)


def test_show_sample_is_disabled_when_selection_cannot_display_data(experiment):
    root,manager,app,paths,errors=experiment;tree=app._workspace_tree
    tree.selection_remove(tree.selection());root.update();assert app._sample_show_button.instate(['disabled'])
    sid=app._workspace.sample_id(paths[0]);tree.selection_set(sid);root.update();assert app._sample_show_button.instate(['!disabled'])
    app._exclude_file(paths[0]);root.update();assert app._sample_show_button.instate(['disabled'])


def test_folder_list_scrolls_over_checkboxes_and_reveals_long_names(experiment,tmp_path):
    root,manager,app,paths,errors=experiment
    folder=tmp_path/'files';folder.mkdir()
    for i in range(70):(folder/(str(i)+'_Long_measurement_filename_'*5+'.csv')).write_text('X,Y\n1,2\n')
    d=FolderScanDialog(root,app.T);d._folder.set(str(folder));d._scan();root.update()
    try:
        check=next(w for w in widgets(d._inner) if isinstance(w,ttk.Checkbutton))
        check.event_generate('<Button-5>');root.update();assert d._cv.yview()[0]>0
        assert d._cv.xview()[1]<1 and d._cv.cget('xscrollcommand')
        d._cv.xview_moveto(1);root.update();assert d._cv.xview()[0]>0
        d._desel_all();assert not d._selected_paths();d._sel_all();assert len(d._selected_paths())==70
    finally:d.destroy()


def test_empty_tooltip_is_suppressed_and_keyboard_help_can_be_dismissed(experiment):
    root,manager,app,paths,errors=experiment
    top=tk.Toplevel(root);top.geometry('240x120+30+30')
    widget=ttk.Button(top,text='Help');widget.pack();tooltip(widget,lambda:'');root.update()
    widget.event_generate('<FocusIn>');root.after(480,root.quit);root.mainloop();assert widget._vflow_tooltip['window'] is None
    widget.destroy();widget=ttk.Button(top,text='Help');widget.pack();tooltip(widget,'Meaningful keyboard help')
    root.update();widget.focus_force();root.update();root.after(480,root.quit);root.mainloop()
    assert widget._vflow_tooltip['window'] is not None
    widget.event_generate('<Escape>');root.update();assert widget._vflow_tooltip['window'] is None;top.destroy()


def test_empty_threshold_gate_roundtrips_and_shared_empty_does_not_hide_override(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;g=crosshair(app);gid=g['id'];owner=app._workspace
    sid=owner.sample_id(paths[1]);owner.gate_action(app,'copy',gid,[sid]);root.update()
    while app._sel_gate()['x_boundaries']:assert app._delete_threshold(gid,'x',0)
    while app._sel_gate().get('y_boundaries'):assert app._delete_threshold(gid,'y',0)
    root.update();assert set(app.gate_stats[gid])=={paths[1]}
    dest=tmp_path/'Empty.vflow';assert owner.save(path=str(dest));assert owner.open(str(dest));root.update()
    assert app._sel_gate()['x_boundaries']==[] and app._sel_gate()['y_boundary'] is None
    assert set(app.gate_stats[gid])=={paths[1]}


def test_linked_population_becomes_unavailable_when_its_region_disappears_and_undo_restores(experiment):
    root,manager,app,paths,errors=experiment;g=crosshair(app);gid=g['id']
    app._open_subgate(50.,50.);root.update();child=manager._apps[-1]
    assert child is not app and sum(len(df) for df in child.loaded_files.values())==6
    assert app._delete_threshold(gid,'x',0);child.refresh_plot();root.update()
    assert not child.loaded_files
    app._workspace.gate_action(app,'undo',gid);child.refresh_plot();root.update()
    assert sum(len(df) for df in child.loaded_files.values())==6


def test_deleted_boundary_is_reflected_in_statistics_csv(experiment,tmp_path,monkeypatch):
    from tkinter import filedialog
    root,manager,app,paths,errors=experiment;g=crosshair(app);gid=g['id']
    assert app._delete_threshold(gid,'x',0)
    output=tmp_path/'counts.csv';monkeypatch.setattr(filedialog,'asksaveasfilename',lambda **kw:str(output))
    app.export_stats();table=pd.read_csv(output)
    assert 'Count' in table and sorted(table[table['File']=='A.csv']['Count'].tolist())==[0,1,1,3]


def test_rerunning_auto_gate_after_all_deletions_restores_a_serializable_partition(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;app.auto_gate_otsu();gid=app._sel_gate_id
    assert app._delete_threshold(gid,'x',0) and app._delete_threshold(gid,'y',0)
    assert app._sel_gate()['thresholds_empty'] is True
    app.auto_gate_otsu();root.update()
    assert 'thresholds_empty' not in app._sel_gate() and app.gate_stats[gid]
    assert app._workspace.save(path=str(tmp_path/'Refit.vflow'))


def test_extra_checkbox_flags_are_trimmed_and_remaining_unticked_flags_are_effective(experiment):
    root,manager,app,paths,errors=experiment;g=crosshair(app)
    g['x_thresh_vars']=[tk.BooleanVar(root,value=v) for v in [False,True,False,True]]
    app._rebuild_thresh_panel();app._on_thresh_toggle();root.update()
    assert len(app._sel_gate()['x_thresh_vars'])==3
    assert not app._sel_gate()['x_thresh_vars'][0].get()
    assert sorted(v['count'] for v in app.gate_stats[g['id']][paths[0]]['stats'].values())==[0,1,1,3]


def test_threshold_edit_reuses_existing_density_computation(experiment):
    import time
    from pathlib import Path
    import numpy as np
    root,manager,app,paths,errors=experiment
    rng=np.random.default_rng(447);dense=[]
    for source in paths:
        path=Path(source).with_name('Dense_'+Path(source).name)
        pd.DataFrame({'X':rng.normal(100,35,200),'Y':rng.normal(90,25,200)}).to_csv(path,index=False);dense.append(str(path))
    app.clear_all_files();app._load_paths(dense);app.x_var.set('X');app.y_var.set('Y');app.apply_axes()
    g=crosshair(app);gid=g['id'];app.plot_type_var.set('Density');app.refresh_plot()
    for _ in range(80):
        root.update()
        if len(app._density_cache)>=3:break
        time.sleep(.01)
    assert len(app._density_cache)>=3
    before={key:id(value) for key,value in app._density_cache.items()}
    assert app._delete_threshold(gid,'x',0);root.update()
    assert all(key in app._density_cache and id(app._density_cache[key])==value for key,value in before.items())
