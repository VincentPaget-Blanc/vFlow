"""Exercise restored controls, constrained layouts and persistence with real Tk."""
import copy
import os
import tkinter as tk
from tkinter import ttk
import pytest
from tests.test_workspace_gui import experiment, new_gate
from tests.test_task_sidebar_gui import widgets
from vflow.ui.batch_stats_dialog import BatchStatsDialog
from vflow.ui.axis_name_resolver import AxisNameResolverDialog, ExactAxisNameResolverDialog, UnresolvedFilesDialog
from vflow.ui.statistical_audit_dialog import AuditListDialog
from vflow.legacy.vflow_app import PolarAnalysisWindow, BatchPlotWindow

pytestmark=pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='Native Tk display required')

def button(parent,text):
    return next(w for w in widgets(parent) if isinstance(w,ttk.Button) and w.cget('text')==text)

def inside(w,parent):
    assert w.winfo_ismapped()
    assert w.winfo_width()>20 and w.winfo_height()>12
    assert w.winfo_rooty()>=parent.winfo_rooty()
    assert w.winfo_rooty()+w.winfo_height()<=parent.winfo_rooty()+parent.winfo_height()
    assert w.winfo_rootx()+w.winfo_width()<=parent.winfo_rootx()+parent.winfo_width()

@pytest.mark.parametrize('size',['Automatic','Compact','Comfortable','Large'])
def test_sample_area_is_larger_and_adjustable_without_losing_tasks(experiment,size):
    root,manager,app,paths,errors=experiment
    root.geometry('1280x900');app.interface_size_var.set(size);app._apply_interface_size();root.update()
    tree=app._workspace_tree
    row_height=int(ttk.Style(root).lookup('Treeview','rowheight'))
    assert tree.winfo_height()>=len(tree.get_children())*row_height
    default=app._sample_task_pane.sash_coord(0)[1]
    app._sample_task_pane.sash_place(0,0,default+80);app._sample_pane_released();root.update()
    assert app._sidebar_state()['sample_panel_fraction']==pytest.approx(app._sample_task_pane.sash_coord(0)[1]/app._sidebar_outer_canvas.winfo_height(),abs=.01)
    for task in ('Data','Plot','Gates','Analysis'):
        app._select_sidebar_task(task);root.update();inside(app._task_notebook,root)
    dest=app._workspace.state_dir.parent/'pane.vflow';assert app._workspace.save(path=str(dest))
    fraction=app._sample_panel_fraction;app._sample_panel_fraction=None
    assert app._workspace.open(str(dest));root.update()
    assert app._sample_panel_fraction==pytest.approx(fraction)

@pytest.mark.parametrize('invalid',[None,True,'large',float('inf'),float('nan')])
def test_malformed_sample_pane_preferences_fall_back_safely(experiment,invalid):
    root,manager,app,paths,errors=experiment
    app._restore_sidebar_state({'sample_panel_fraction':invalid});root.update()
    assert app._sample_panel_fraction is None


def test_exclude_restore_direct_buttons_preserve_gate_truth_and_activation(experiment):
    root,manager,app,paths,errors=experiment;gate=new_gate(app)
    before=copy.deepcopy(app.gate_stats);original=app.loaded_files[paths[0]]
    app.file_vars[paths[1]].set(False)
    tree=app._workspace_tree;sid=app._workspace.sample_id(paths[0]);tree.selection_set(sid);root.update()
    app._sample_exclude_button.invoke();root.update()
    assert paths[0] in app.excluded_files and paths[0] not in app.loaded_files
    tree.selection_set(sid);root.update();app._sample_restore_button.invoke();root.update()
    assert app.loaded_files[paths[0]] is original
    assert not app.file_vars[paths[1]].get()
    assert app.gate_stats[gate['id']][paths[0]]==before[gate['id']][paths[0]]
    tree.selection_set([app._workspace.sample_id(p) for p in paths[:2]]);root.update()
    assert app._sample_exclude_button.instate(['disabled']) and app._sample_restore_button.instate(['disabled'])


def test_gate_threshold_shortcut_and_direct_delete_use_existing_population(experiment):
    root,manager,app,paths,errors=experiment;gate=new_gate(app)
    app._select_sidebar_task('Gates');root.update()
    app._show_gate_info(gate['id']);root.update()
    assert app._sel_gate_id==gate['id'] and app._sections['GATE INFO'][0].get()
    assert app._task_pages['Gates']['canvas'].yview()[0]>0
    button(app.thresh_panel,'Delete gate').invoke();root.update();assert not app.gates


def test_rename_rejects_blank_and_keeps_cancel_reachable(experiment):
    root,manager,app,paths,errors=experiment;gate=new_gate(app);old=gate['name'];checks=[]
    def interact():
        d=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
        try:
            d.update_idletasks()
            if not d.winfo_ismapped(): d.wait_visibility()
            inside(button(d,'Rename'),d);inside(button(d,'Cancel'),d)
            entry=next(w for w in widgets(d) if isinstance(w,ttk.Entry))
            entry.delete(0,'end');button(d,'Rename').invoke();assert d.winfo_exists() and gate['name']==old
            entry.insert(0,'New gate label');button(d,'Rename').invoke();checks.append(True)
        finally:
            if d.winfo_exists():d.destroy()
    root.after(80,interact);app._rename_gate(gate['id']);assert checks and gate['name']=='New gate label'

@pytest.mark.parametrize('dialog',[AxisNameResolverDialog,ExactAxisNameResolverDialog,UnresolvedFilesDialog,BatchStatsDialog,AuditListDialog])
@pytest.mark.parametrize('size',['Comfortable','Large'])
def test_dialog_actions_remain_visible_at_minimum_height(experiment,dialog,size):
    root,manager,app,paths,errors=experiment;app.interface_size_var.set(size);app._apply_interface_size();root.update()
    if dialog is BatchStatsDialog:
        d=dialog(root,app.T,[str(app._workspace.state_dir.parent)],'X','Y');d.geometry('620x420');names=['Cancel','Run Batch Export']
    elif dialog is AuditListDialog:
        d=dialog(app._workspace);d.geometry('700x360');names=['Close','Open audit']
    else:
        d=dialog(root,app);width,height=d.minsize();d.geometry(f'{width}x{height}');names=['Close']
    root.update()
    try:
        for name in names:inside(button(d,name),d)
        if dialog in (AxisNameResolverDialog,ExactAxisNameResolverDialog,UnresolvedFilesDialog):
            for control in widgets(d):
                if isinstance(control,ttk.Button):inside(control,d)
        if dialog is BatchStatsDialog:
            d._suffix_var.set('');d._refresh_preview();root.update()
            before=d._body_canvas.yview()[0]
            next(w for w in widgets(d) if 'text' in w.keys() and w.cget('text')=='Root folder to scan:').event_generate('<Button-5>')
            root.update();assert d._body_canvas.yview()[0]>before
    finally:d.destroy()

@pytest.mark.parametrize('dialog',[PolarAnalysisWindow,BatchPlotWindow])
def test_auxiliary_sidebar_width_and_statistics_scroll_access(experiment,dialog):
    root,manager,app,paths,errors=experiment;d=dialog(root,app.T,app);root.update()
    try:
        d._layout_pane.sash_place(0,420,0);root.update()
        assert d._sb_canvas.winfo_width()>390
        assert abs(d._sb.winfo_width()-d._sb_canvas.winfo_width())<=2
        assert d._stats_tree.cget('xscrollcommand') and d._stats_tree.cget('yscrollcommand')
        label=next(w for w in widgets(d._sb) if isinstance(w,ttk.Label))
        before=d._sb_canvas.yview()[0];label.event_generate('<Button-5>');root.update()
        assert d._sb_canvas.yview()[0]>before
        d._sb_canvas.yview_moveto(1);root.update()
        assert d._stats_tree.winfo_ismapped()
    finally:d._on_close()


def test_task_panel_linux_wheel_over_labels_and_macos_small_delta(experiment):
    root,manager,app,paths,errors=experiment
    app._select_sidebar_task('Plot');app._set_all_sections(True);root.geometry('1024x768');root.update()
    canvas=app._task_pages['Plot']['canvas'];canvas.yview_moveto(0)
    label=next(w for w in widgets(app._task_pages['Plot']['content']) if isinstance(w,ttk.Label) and w.winfo_ismapped())
    label.event_generate('<Button-5>');root.update();assert canvas.yview()[0]>0
    label.event_generate('<Button-4>');root.update();assert canvas.yview()[0]==0
    label.event_generate('<MouseWheel>',delta=-1);root.update();assert canvas.yview()[0]>0
