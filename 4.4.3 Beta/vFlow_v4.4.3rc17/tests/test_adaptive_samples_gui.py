"""Native, externally visible fit/scroll/state checks for adaptive samples."""
import copy,json,os
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import pytest
from tests.test_workspace_gui import experiment,new_gate
from tests.test_task_sidebar_gui import widgets

pytestmark=pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='Native Tk display required')

def many_samples(app,tmp_path,total=60):
    first=next(iter(app.loaded_files.values()))
    paths=[]
    for i in range(total-len(app.loaded_files)):
        path=tmp_path/f'Extra_{i:03d}.csv';first.to_csv(path,index=False);paths.append(str(path))
    app._load_paths(paths);app.root.update();return paths

def visible(widget,viewport):
    assert widget.winfo_ismapped()
    top=viewport.winfo_rooty();bottom=top+viewport.winfo_height()
    assert top-2<=widget.winfo_rooty()
    assert widget.winfo_rooty()+widget.winfo_height()<=bottom+2
    assert widget.winfo_rootx()+widget.winfo_width()<=viewport.winfo_rootx()+viewport.winfo_width()+2

LAYOUTS=[(w,h,scale,mode) for w,h,scale in [(1024,640,1),(1440,900,1.5),(1920,1080,2)] for mode in ('Automatic','Compact','Comfortable','Large')]
@pytest.mark.parametrize('width,height,scale,mode',LAYOUTS)
def test_long_list_uses_window_height_and_keeps_footer_and_tabs_visible(experiment,tmp_path,width,height,scale,mode):
    root,manager,app,paths,errors=experiment
    root.tk.call('tk','scaling',(96/72)*scale)
    root.geometry(f'{width}x{height}');app.interface_size_var.set(mode);app._apply_interface_size()
    many_samples(app,tmp_path);app._sidebar_outer_canvas.yview_moveto(0);root.update()
    viewport=app._sidebar_outer_canvas;tree=app._workspace_tree
    for text in ('All active','None active','Actions…','Exclude','Restore','Show sample','Prev','Next'):
        visible(next(w for w in widgets(app._workspace_panel) if isinstance(w,ttk.Button) and w.cget('text')==text),viewport)
    # All tabs fit above the fold; the task body is intentionally below it.
    tab_bottom=app._task_pages[app._sidebar_task()]['page'].winfo_rooty()
    assert tab_bottom<=viewport.winfo_rooty()+viewport.winfo_height()+2
    assert tab_bottom>=viewport.winfo_rooty()+viewport.winfo_height()-int(ttk.Style(root).lookup('Treeview','rowheight'))-10
    assert tree.winfo_height()>int(ttk.Style(root).lookup('Treeview','rowheight'))*2
    assert tree.yview()[1]<1
    assert app._sample_panel_fraction is None
    for task in ('Data','Plot','Gates','Analysis'):
        app._select_sidebar_task(task);root.update();visible(app._task_notebook,viewport)
    root.tk.call('tk','scaling',96/72)


def test_short_list_fits_rows_and_long_list_reacts_to_add_remove_and_resize(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;root.geometry('1280x800');root.update()
    row=int(ttk.Style(root).lookup('Treeview','rowheight'))
    assert 3*row<=app._workspace_tree.winfo_height()<=4*row+14
    short=app._workspace_tree.winfo_height();extra=many_samples(app,tmp_path)
    assert app._workspace_tree.winfo_height()>short+5*row
    before=app._workspace_tree.winfo_height();root.geometry('1280x1000');root.update()
    assert app._workspace_tree.winfo_height()>before+150
    for p in extra:app._workspace.remove_sample(app._workspace.sample_id(p))
    root.update();assert app._workspace_tree.winfo_height()<=4*row+14
    assert app.sample_panel_mode_var.get()=='Automatic'


def test_scrolling_is_scoped_and_clicking_same_task_reveals_its_settings(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;many_samples(app,tmp_path);root.update()
    outer=app._sidebar_outer_canvas;tree=app._workspace_tree;outer.yview_moveto(0)
    tree.event_generate('<MouseWheel>',delta=-120);root.update();assert tree.yview()[0]>0 and outer.yview()[0]==0
    button=next(w for w in widgets(app._workspace_panel) if isinstance(w,ttk.Button) and w.cget('text')=='All active')
    button.event_generate('<Button-5>');root.update();assert outer.yview()[0]>0
    app._select_sidebar_task('Plot');root.update();visible(app._task_notebook,outer)
    position=outer.yview()[0];page=app._task_pages['Plot'];page['canvas'].yview_moveto(0)
    page['canvas'].event_generate('<Button-5>');root.update();assert page['canvas'].yview()[0]>0 and outer.yview()[0]==position
    outer.yview_moveto(0);root.update()
    notebook=app._task_notebook
    for x in range(notebook.winfo_width()):
        try:
            if notebook.index('@'+str(x)+',10')==1:break
        except tk.TclError:pass
    else:raise AssertionError('Plot tab is not clickable')
    notebook.event_generate('<ButtonPress-1>',x=x,y=10);notebook.event_generate('<ButtonRelease-1>',x=x,y=10)
    root.update();assert outer.yview()[0]>0
    old=outer.yview();app.canvas.get_tk_widget().event_generate('<Button-5>');root.update();assert outer.yview()==old


def test_manual_divider_and_automatic_mode_save_reopen_on_different_window_size(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;many_samples(app,tmp_path);root.geometry('1280x900');root.update()
    pane=app._sample_task_pane;viewport=app._sidebar_outer_canvas
    pane.sash_place(0,0,round(viewport.winfo_height()*.55));app._sample_pane_released();root.update()
    fraction=app._sample_panel_fraction;assert .52<fraction<.58
    g=new_gate(app);counts=copy.deepcopy(app.gate_stats)
    app._select_sidebar_task('Gates');root.update();saved_scroll=viewport.yview()[0]
    dest=tmp_path/'Adaptive.vflow';assert app._workspace.save(path=str(dest))
    app.sample_panel_mode_var.set('Automatic');app._set_sample_panel_mode();root.geometry('1440x1000');root.update()
    assert app._workspace.open(str(dest));root.update()
    assert app._sample_panel_fraction==pytest.approx(fraction) and app.sample_panel_mode_var.get()=='Manual'
    assert app._sidebar_task()=='Gates' and app.gate_stats==counts
    assert viewport.yview()[0]==pytest.approx(saved_scroll,abs=.04)
    visible(app._task_notebook,viewport)
    app.sample_panel_mode_var.set('Automatic');app._set_sample_panel_mode();viewport.yview_moveto(0);root.update()
    assert app._sample_panel_fraction is None
    assert app._workspace.save();assert app._workspace.open(str(dest));root.update()
    assert app._sample_panel_fraction is None and app.sample_panel_mode_var.get()=='Automatic'
    assert len(app._workspace_tree.get_children())==60


@pytest.mark.parametrize('bad',[True,'bottom',None,float('nan'),float('inf')])
def test_invalid_outer_scroll_preference_does_not_break_workspace(experiment,bad):
    root,manager,app,paths,errors=experiment
    app._restore_sidebar_state({'sidebar_outer_scroll':bad});root.update()
    assert app._sidebar_outer_canvas.yview()[0]==0


def test_pending_resize_and_outer_wheel_bindings_are_disposed(experiment):
    root,manager,app,paths,errors=experiment
    app._sample_pane_configured();assert app._sample_layout_pending
    tag=app._sidebar_outer_wheel_tag;app._dispose_adaptive_sidebar();root.update()
    assert app._sample_layout_pending is None and not root.bind_class(tag,'<MouseWheel>')
    app._sample_pane_configured();assert app._sample_layout_pending is None


def test_rapid_resize_settles_and_each_task_keeps_its_scroll_position(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;many_samples(app,tmp_path)
    for width,height in [(1440,900),(1024,640),(1920,1080),(1280,800)]:root.geometry(f'{width}x{height}')
    root.update();assert app._sample_layout_pending is None
    app._sidebar_outer_canvas.yview_moveto(0)
    visible(app._sample_show_button,app._sidebar_outer_canvas)
    app._select_sidebar_task('Plot');root.update();page=app._task_pages['Plot']['canvas'];page.yview_moveto(.3);root.update()
    before=page.yview()
    for name in ('Data','Gates','Analysis','Plot'):app._select_sidebar_task(name);root.update()
    assert page.yview()==before


@pytest.mark.parametrize('scale,mode',[(1,'Automatic'),(1.5,'Comfortable'),(2,'Large')])
def test_gate_action_labels_fit_with_outer_scrollbar_and_scaled_fonts(experiment,scale,mode):
    root,manager,app,paths,errors=experiment
    root.tk.call('tk','scaling',96/72*scale);root.geometry('1920x1080')
    app.interface_size_var.set(mode);app._apply_interface_size();new_gate(app);app._rebuild_gate_manager();app._select_sidebar_task('Gates');root.update()
    controls=[w for w in widgets(app.gate_manager_frame) if isinstance(w,ttk.Button) and w.cget('text') in ('Rename','Delete','Info / thresholds')]
    assert len(controls)==3
    for control in controls:
        assert control.winfo_width()>=control.winfo_reqwidth()
        assert control.winfo_rootx()+control.winfo_width()<=app._sidebar_outer_canvas.winfo_rootx()+app._sidebar_outer_canvas.winfo_width()
    root.tk.call('tk','scaling',96/72)
