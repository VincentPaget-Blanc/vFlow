"""Native regression checks for the approved task layout and control preservation."""
import copy
import os
import tkinter as tk
from tkinter import ttk
import pytest
from tests.test_workspace_gui import experiment,new_gate
from vflow.ui.task_sidebar import AUTO_METHODS
from vflow.config.constants import ALL_SCALES

pytestmark=pytest.mark.skipif(not os.environ.get('DISPLAY') and os.name!='nt' and os.sys.platform!='darwin',reason='Tk display required')

def widgets(parent):
    for child in parent.winfo_children():
        yield child
        yield from widgets(child)

def control_variables(app):
    result=set()
    for w in widgets(app._side_outer):
        for name in ('variable','textvariable'):
            if name in w.keys():result.add(str(w.cget(name)))
    return result

def test_single_sample_list_and_view_selector_and_all_original_settings(experiment):
    root,manager,app,paths,errors=experiment
    assert [app._task_notebook.tab(t,'text') for t in app._task_notebook.tabs()]==['Data','Plot','Gates','Analysis']
    selectors=[w for w in widgets(app._side_outer) if isinstance(w,ttk.Radiobutton) and str(w.cget('variable'))==str(app.view_mode_var)]
    assert sorted(w.cget('value') for w in selectors)==['cycle','overlay']
    assert not app.file_list_frame.winfo_ismapped() and not app.file_list_frame.winfo_children()
    assert len(app._workspace_tree.get_children())==3
    expected=['view_mode_var','gate_scope_var','x_var','y_var','x_scale_var','y_scale_var','cofactor_str',
              'plot_type_var','dot_size_var','alpha_var','prob_var','show_marginals_var','show_labels_var',
              'show_legend_var','show_grid_var','fit_axes_var','lock_scale_var','gate_mode_var','gate_type_var',
              'auto_gate_input_var','auto_sensitivity_var','gmm_max_x_var','gmm_max_y_var','stats_mode_var']
    assert {str(getattr(app,n)) for n in expected}<=control_variables(app)
    dot=next(w for w in app._scale_widgets if str(w.cget('variable'))==str(app.dot_size_var))
    assert float(dot.cget('from'))==1 and float(dot.cget('to'))==12 and float(dot.cget('resolution'))==1
    alpha=next(w for w in app._scale_widgets if str(w.cget('variable'))==str(app.alpha_var))
    assert float(alpha.cget('from'))==.05 and float(alpha.cget('to'))==1 and float(alpha.cget('resolution'))==.05
    for var in (app.x_scale_var,app.y_scale_var):
        menu=next(w for w in widgets(app._side_outer) if isinstance(w,ttk.Combobox) and str(w.cget('textvariable'))==str(var))
        assert tuple(menu.cget('values'))==tuple(ALL_SCALES)
    for task in ('Data','Plot','Gates','Analysis'):
        app._select_sidebar_task(task);root.update()
        assert app._workspace_tree.winfo_ismapped() and app._btn_prev.winfo_ismapped() and app._btn_next.winfo_ismapped()


def test_original_action_callbacks_and_exports_remain_registered(experiment):
    root,manager,app,paths,errors=experiment
    registered=[]
    for w in widgets(app._side_outer):
        if 'command' in w.keys():registered.append(str(w.cget('command')))
    required=['load_files','load_from_folder','clear_all_files','_select_all','_unselect_all',
              'save_excluded_list','load_excluded_list','apply_axes','open_axis_name_resolver',
              '_on_lock_scale_toggle','_edit_logicle_params','_on_gate_mode_change','_on_gate_type_change',
              '_poly_finish','clear_gate','clear_all_gates','_add_gate','_update_stats_display','save_gates',
              'load_gates','export_stats','export_gated_data','batch_export_stats','export_figure',
              'open_polar_analysis','open_batch_plots','_on_view_mode_change','_cycle_prev','_cycle_next']
    assert not [name for name in required if not any(command.endswith(name) for command in registered)]
    menu=app._sidebar_settings_menu
    assert str(menu.entrycget(0,'command')).endswith('toggle_theme')
    app._sections['STATISTICAL AUDITS'][0].set(True);app._toggle_section('STATISTICAL AUDITS');root.update()
    text=[w.cget('text') for w in widgets(app._sections['STATISTICAL AUDITS'][1]) if 'text' in w.keys()]
    assert 'Statistical Audit…' in text and 'Saved audits…' in text


@pytest.mark.parametrize('method',list(AUTO_METHODS))
def test_all_four_auto_methods_dispatch_through_calculate(experiment,monkeypatch,method):
    root,manager,app,paths,errors=experiment
    called=[];monkeypatch.setattr(app,AUTO_METHODS[method],lambda:called.append(method))
    app._select_sidebar_task('Gates');app._gate_tools_notebook.select(app._gate_tool_pages['AUTO-GATE'])
    app.auto_gate_method_var.set(method);app._auto_method_menu.event_generate('<<ComboboxSelected>>');root.update()
    assert bool(app._gmm_controls.winfo_ismapped())==(method=='GMM Multi')
    app._auto_calculate_button.invoke();assert called==[method]
    assert app.auto_gate_input_var.get()=='Active samples (pooled)' and app.gate_scope_var.get()=='All samples (default)'


def test_method_change_cancels_old_sensitivity_rerun_and_reenables_on_calculate(experiment):
    root,manager,app,paths,errors=experiment
    app._last_auto_gate_fn=lambda:None;token=app._sens_rerun_pending=root.after(5000,lambda:None)
    app.auto_gate_method_var.set('Otsu');app._auto_method_menu.event_generate('<<ComboboxSelected>>')
    assert app._last_auto_gate_fn is None and app._sens_rerun_pending is None
    with pytest.raises(tk.TclError):root.tk.call('after','info',token)
    app._auto_calculate_button.invoke()
    assert app._last_auto_gate_fn==app.auto_gate_otsu and app._sel_gate()['auto_method']=='otsu'
    app.auto_sensitivity_var.set(6)
    assert app._sens_rerun_pending is not None


def test_pinned_cycle_buttons_enable_and_wrap_without_touching_selection(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    selected=[owner.sample_id(paths[0]),owner.sample_id(paths[2])];app._workspace_tree.selection_set(selected)
    app.view_mode_var.set('cycle');app._on_view_mode_change();root.update()
    assert not app._btn_next.instate(['disabled']) and not app._btn_prev.instate(['disabled'])
    start=owner.current_sid(app);app._btn_next.invoke();assert owner.current_sid(app)!=start
    assert app._workspace_scope_label.get().startswith('2/3 ')
    app._btn_prev.invoke();assert owner.current_sid(app)==start
    assert app._workspace_scope_label.get().startswith('1/3 ')
    assert set(app._workspace_tree.selection())==set(selected)
    app.view_mode_var.set('overlay');app._on_view_mode_change()
    assert app._btn_next.instate(['disabled']) and app._btn_prev.instate(['disabled'])
    assert 'Gates apply to:' in app._workspace_scope_label.get()


def test_sample_actions_exclude_restore_and_reveal_keep_other_activation(experiment,monkeypatch):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    monkeypatch.setattr(tk.Menu,'tk_popup',lambda *a,**k:None)
    monkeypatch.setattr(tk.Menu,'grab_release',lambda *a,**k:None)
    app.file_vars[paths[1]].set(False);app._on_active_files_changed()
    sid=owner.sample_id(paths[0]);app._workspace_tree.selection_set(sid)
    app._selected_sample_actions();menu=app._workspace_sample_menu
    entries={menu.entrycget(i,'label'):i for i in range(menu.index('end')+1) if menu.type(i)=='command'}
    assert {'Show only this sample','Assign gate session…','Sample details…','Reset saved view','Locate source file…',
            'Find Missing Files…','Clear sample-specific gate session','Remove from workspace',
            'Exclude from analysis','Restore to analysis',app._file_manager_menu_label()}<=entries.keys()
    menu.invoke(entries['Exclude from analysis']);assert paths[0] in app.excluded_files and not app.file_vars[paths[1]].get()
    app._selected_sample_actions();menu=app._workspace_sample_menu
    restore=next(i for i in range(menu.index('end')+1) if menu.type(i)=='command' and menu.entrycget(i,'label')=='Restore to analysis')
    menu.invoke(restore);assert paths[0] in app.loaded_files and not app.file_vars[paths[1]].get()
    assert len(app._workspace_tree.get_children())==3


def test_task_and_gate_tool_state_reopen_and_old_workspace_defaults(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    app._select_sidebar_task('Gates');app._gate_tools_notebook.select(app._gate_tool_pages['AUTO-GATE'])
    app.auto_gate_method_var.set('Otsu');app._auto_method_changed();root.update()
    dest=tmp_path/'Task-tabs.vflow';assert owner.save(path=str(dest))
    assert owner.document.ui_state['sidebar_task']=='Gates' and owner.document.ui_state['auto_gate_method']=='Otsu'
    app._select_sidebar_task('Data');assert owner.open(str(dest));root.update()
    assert app._sidebar_task()=='Gates' and app.auto_gate_method_var.get()=='Otsu'
    assert app._gate_tools_notebook.select()==str(app._gate_tool_pages['AUTO-GATE'])
    import json
    old=json.loads(dest.read_text())
    for state in [old['ui_state'],*[t['ui_state'] for t in old['tabs'].values()]]:
        for key in ['sidebar_task','sidebar_gate_tool','auto_gate_method','sidebar_scroll']:state.pop(key,None)
    dest.write_text(json.dumps(old));assert owner.open(str(dest));root.update()
    assert app._sidebar_task()=='Plot' and app.auto_gate_method_var.get()=='GMM Multi'


@pytest.mark.parametrize('size',['Automatic','Compact','Comfortable','Large'])
def test_every_task_tab_and_pinned_list_accessible_at_1024_768(experiment,size):
    root,manager,app,paths,errors=experiment
    root.geometry('1024x768');app.interface_size_var.set(size);app._apply_interface_size();root.update()
    notebook=app._task_notebook;selected=notebook.nametowidget(notebook.select());y=max(1,selected.winfo_y()//2)
    visible=set()
    for x in range(notebook.winfo_width()):
        try:visible.add(notebook.index('@'+str(x)+','+str(y)))
        except tk.TclError:pass
    assert visible=={0,1,2,3}
    for name in ['Data','Plot','Gates','Analysis']:
        app._select_sidebar_task(name);root.update()
        assert app._task_pages[name]['canvas'].winfo_height()>100
        assert app._workspace_tree.winfo_ismapped() and app._status_lbl.winfo_ismapped()
    app._select_sidebar_task('Gates');app._gate_tools_notebook.select(app._gate_tool_pages['AUTO-GATE']);root.update()
    canvas=app._task_pages['Gates']['canvas']
    for control in app._gmm_controls.winfo_children():
        assert control.winfo_ismapped()
        assert control.winfo_rootx()+control.winfo_width()<=canvas.winfo_rootx()+canvas.winfo_width()


def test_scroll_is_local_to_task_and_dynamic_gate_controls_remain(experiment):
    root,manager,app,paths,errors=experiment
    root.geometry('1024x600');app._set_all_sections(True);app._select_sidebar_task('Plot');root.update()
    plot=app._task_pages['Plot']['canvas'];plot.yview_moveto(.5);root.update();before=plot.yview()
    app._select_sidebar_task('Data');root.update();assert plot.yview()==before
    app._select_sidebar_task('Plot');root.update();assert plot.yview()==before
    plot.event_generate('<MouseWheel>',delta=120);root.update();assert plot.yview()[0]<before[0]
    app._select_sidebar_task('Gates');app._gate_tools_notebook.select(app._gate_tool_pages['GATING']);root.update()
    app._poly_active=True;app._update_poly_close_btn();root.update();assert app._poly_close_btn.winfo_ismapped()
    gate=new_gate(app);before_gate=copy.deepcopy(gate)
    app._sections['GATE INFO'][0].set(True);app._toggle_section('GATE INFO');root.update()
    assert app.thresh_panel.winfo_ismapped()
    for task in ['Data','Plot','Analysis','Gates']:app._select_sidebar_task(task);root.update()
    assert app._sel_gate()==before_gate


@pytest.mark.parametrize('state',[{'sidebar_task':['Gates']},{'sidebar_gate_tool':{}},
    {'auto_gate_method':['Otsu']},{'sidebar_scroll':{'Plot':float('nan'),'Data':'bad'}}])
def test_invalid_optional_ui_state_does_not_break_workspace(experiment,state):
    root,manager,app,paths,errors=experiment
    app._restore_sidebar_state(state);root.update()
    assert len(app.loaded_files)==3 and app.auto_gate_method_var.get() in AUTO_METHODS


def test_child_sidebar_bindings_disposed_when_population_tab_closes(experiment):
    root,manager,app,paths,errors=experiment;new_gate(app);app._open_subgate(50.,50.);root.update()
    child=manager._apps[1];tag=child._sidebar_wheel_tag
    assert root.bind_class(tag,'<MouseWheel>')
    commands=list(child._sidebar_wheel_callbacks.values())
    manager._close_tab(1);root.update()
    assert not root.bind_class(tag,'<MouseWheel>') and len(manager._apps)==1
    assert not any(command in root._tclCommands for command in commands)


def test_long_workspace_name_cannot_hide_settings(experiment):
    root,manager,app,paths,errors=experiment
    app._workspace_name_var.set('Long workspace name '*20);root.geometry('1024x768');root.update()
    assert app._sidebar_settings_button.winfo_ismapped()
    assert app._sidebar_settings_button.winfo_rootx()+app._sidebar_settings_button.winfo_width()<=app._side_outer.winfo_rootx()+app._side_outer.winfo_width()


def test_theme_menu_updates_every_task_without_losing_settings_or_data(experiment):
    root,manager,app,paths,errors=experiment
    frames=dict(app.loaded_files);values={n:str(getattr(app,n).get()) for n in ['x_var','y_var','x_scale_var','y_scale_var','cofactor_str','gate_scope_var','auto_gate_input_var']}
    app._select_sidebar_task('Analysis');before=app._theme_name;app._sidebar_settings_menu.invoke(0);root.update()
    assert app._theme_name!=before and app._sidebar_task()=='Analysis'
    assert all(page['canvas'].cget('background')==app.T['sidebar_bg'] for page in app._task_pages.values())
    assert all(app.loaded_files[p] is frame for p,frame in frames.items())
    assert {n:str(getattr(app,n).get()) for n in values}==values
