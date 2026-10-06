"""Real Tk integration tests; use DISPLAY or xvfb-run on Linux."""
import copy
import json
import os
from pathlib import Path
import tkinter as tk
import numpy as np
import pandas as pd
import pytest
from vflow.legacy.vflow_app import FlowTabManager
from vflow.workspace.controller import session_payload
from vflow.workspace.gates import filter_lineage
from vflow.workspace.model import atomic_json

pytestmark=pytest.mark.skipif(not os.environ.get('DISPLAY') and os.name!='nt' and os.sys.platform!='darwin',reason='Tk display required')

@pytest.fixture
def experiment(tmp_path,monkeypatch):
    from tkinter import messagebox
    errors=[]
    for method in ('showinfo','showwarning'):monkeypatch.setattr(messagebox,method,lambda *a,**k:None)
    monkeypatch.setattr(messagebox,'showerror',lambda *a,**k:errors.append(a))
    monkeypatch.setattr(messagebox,'askyesno',lambda *a,**k:True)
    monkeypatch.setattr(messagebox,'askyesnocancel',lambda *a,**k:False)
    root=tk.Tk();root.report_callback_exception=lambda *a:errors.append(a)
    if os.environ.get('VFLOW_TEST_FONT'):
        from tkinter import font
        font.nametofont('TkDefaultFont').configure(family=os.environ['VFLOW_TEST_FONT'])
    manager=FlowTabManager(root);app=manager._apps[0]
    app._workspace.state_dir = tmp_path/"state"
    app._workspace.recent_path = tmp_path/"state/recent.json"
    app.plot_type_var.set('Dot Plot');app.show_marginals_var.set(False)
    paths=[]
    for name in ['A','B','C']:
        p=tmp_path/(name+'.csv');pd.DataFrame({'X':[30.,50.,90.,120.,220.],'Y':[30.,50.,90.,120.,70.],
            'U':[1.,2.,3.,4.,5.],'V':[6.,7.,8.,9.,10.]}).to_csv(p,index=False);paths.append(str(p))
    app._load_paths(paths);root.update()
    app.x_var.set('X');app.y_var.set('Y');app.apply_axes()
    app.x_scale_var.set('linear');app.y_scale_var.set('linear');root.update()
    yield root,manager,app,paths,errors
    app._workspace.dispose()
    root.destroy()
    assert errors==[]


def new_gate(app):
    g=app._add_gate(auto_type='rectangle')
    # Legacy add returns the new dict through selection.
    g=app._sel_gate();g.update(x0=20.,x1=100.,y0=20.,y1=100.,applied=True)
    app._bind_gate_context(g);app._recompute_all_gate_stats();app.refresh_plot();return g


def test_real_gui_sample_views_overlay_and_scope(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    owner.show_sample(app,owner.sample_id(paths[0]));app.x_var.set('U');app.y_var.set('V');app.apply_axes()
    app._cycle_next();assert (app.x_channel,app.y_channel)==('U','V') # compatible initial view
    app.x_var.set('X');app.y_var.set('Y');app.apply_axes();app._cycle_prev()
    assert (app.x_channel,app.y_channel)==('U','V')
    app.view_mode_var.set('overlay');app._on_view_mode_change();assert (app.x_channel,app.y_channel)==('X','Y')
    app.view_mode_var.set('cycle');app._on_view_mode_change();assert (app.x_channel,app.y_channel)==('U','V')
    app.gate_scope_var.set('Current sample');owner.scope_changed(app)
    assert app.view_mode_var.get()=='cycle'
    app.view_mode_var.set('overlay');app._on_view_mode_change();assert app.gate_scope_var.get()=='All samples (default)'
    root.update()


def test_real_gui_override_counts_cache_copy_reset_undo(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace;g=new_gate(app);gid=g['id']
    original={p:app.gate_stats[gid][p]['stats']['IN']['count'] for p in paths}
    assert set(original.values())=={3}
    sid=owner.sample_id(paths[1]);owner.show_sample(app,sid);app.gate_scope_var.set('Current sample');owner.scope_changed(app)
    app._sel_gate()['x1']=70.;app._recompute_all_gate_stats();app.refresh_plot()
    assert app.gate_stats[gid][paths[1]]['stats']['IN']['count']==2
    assert app.gate_stats[gid][paths[0]]['stats']['IN']['count']==3
    owner.gate_action(app,'copy',gid,[owner.sample_id(paths[2])]);assert app.gate_stats[gid][paths[2]]['stats']['IN']['count']==2
    owner.gate_action(app,'undo',gid);assert app.gate_stats[gid][paths[2]]['stats']['IN']['count']==3
    owner.gate_action(app,'reset',gid);assert app.gate_stats[gid][paths[1]]['stats']['IN']['count']==3


def test_real_gui_save_reopen_external_sessions_and_recovery(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace;g=new_gate(app);gid=g['id']
    sid=owner.sample_id(paths[1]);owner.gate_action(app,'copy',gid,[sid]);dest=tmp_path/'Experiment.vflow'
    assert owner.save(path=str(dest));raw=dest.read_text();assert 'vertices' not in raw
    bundle=owner.document.default_gate_session.resolve(dest);assert bundle and Path(bundle).is_file()
    app.x_var.set('U');app.y_var.set('V');app.apply_axes();owner.autosave();assert owner.recovery_path.exists()
    explicit=dest.read_bytes();assert b'"x_channel": "X"' in explicit
    owner.discard_recovery();assert owner.open(str(dest));root.update()
    assert app.gates and app.gates[0]['id']==gid
    assert owner.stores['main'].resolve_gate(sid,gid)
    assert app.gate_stats[gid][paths[1]]['stats']['IN']['count']==3


def test_real_gui_offscale_arrays_and_all_plot_modes(experiment):
    root,manager,app,paths,errors=experiment;g=new_gate(app);before=app.loaded_files[paths[0]].copy();gid=g['id']
    counts=copy.deepcopy(app.gate_stats)
    app.lock_scale_var.set(True);app._locked_xlim=[0.,100.];app._locked_ylim=[0.,100.]
    app.show_marginals_var.set(True)
    for mode in ['Dot Plot','Density','Contour Plot']:
        app.plot_type_var.set(mode);root.update()
        assert app._offscale_counts['x_high']==6
        pd.testing.assert_frame_equal(app.loaded_files[paths[0]],before)
        assert app.gate_stats==counts
        for collection in app.ax.collections:
            if len(collection.get_offsets())>1:
                assert np.max(collection.get_offsets())<=100.000001


def test_real_gui_nested_population_refresh_and_reopen(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace;g=new_gate(app);gid=g['id']
    app._open_subgate(50.,50.)
    assert len(manager._apps)==2
    child=manager._apps[1];child.plot_type_var.set('Dot Plot');child.refresh_plot()
    assert len(child.loaded_files[paths[1]])==3
    sid=owner.sample_id(paths[1]);owner.show_sample(app,sid);app.gate_scope_var.set('Current sample');owner.scope_changed(app)
    app._sel_gate()['x1']=70.;app.refresh_plot();child.refresh_plot()
    assert len(child.loaded_files[paths[1]])==2 and len(child.loaded_files[paths[0]])==3
    dest=tmp_path/'Nested.vflow';assert owner.save(path=str(dest))
    assert 'vertices' not in dest.read_text() and '"x0"' not in dest.read_text()
    assert owner.open(str(dest));root.update()
    assert len(manager._apps)==2
    restored=manager._apps[1];restored.refresh_plot()
    assert len(restored.loaded_files[paths[1]])==2


def test_real_gui_sizes_collapsed_controls_and_missing_channels(experiment):
    root,manager,app,paths,errors=experiment
    for size in ['Automatic','Compact','Comfortable','Large']:
        app.interface_size_var.set(size);app._apply_interface_size();root.geometry('1024x768');root.update()
        assert app._workspace_tree.winfo_ismapped()
        assert app._status_lbl.winfo_ismapped() and app._toolbar_frame.winfo_ismapped()
        from tkinter import font
        assert font.nametofont('VFlowBody').actual('size') >= 10
        app._set_all_sections(True);root.update();app._set_all_sections(False);root.update()
    app._set_all_sections(True)
    sid=app._workspace.sample_id(paths[0]);app._workspace.show_sample(app,sid)
    app.x_var.set('X');app.y_var.set('Y');app.apply_axes()
    app.loaded_files[paths[1]]=app.loaded_files[paths[1]].drop(columns=['Y'])
    app._cycle_next();root.update()
    assert 'Required channel' in app._workspace_view_warning


def test_real_gui_sample_only_gate_is_not_global(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    sid=owner.sample_id(paths[1]);owner.show_sample(app,sid);app.gate_scope_var.set('Current sample');owner.scope_changed(app)
    g=new_gate(app);gid=g['id'];assert not owner.stores['main'].global_gates
    app.view_mode_var.set('overlay');app._on_view_mode_change()
    assert not app.gates and any(g['id']==gid for g in app._analysis_gates())
    assert owner.stores['main'].resolve_gate(owner.sample_id(paths[0]),gid) is None
    assert app.gate_stats[gid][paths[1]]['stats']['IN']['count']==3
    dest=tmp_path/'Sparse.vflow';assert owner.save(path=str(dest));assert owner.open(str(dest));root.update()
    assert not app.gates and any(g['id']==gid for g in app._analysis_gates())


def test_real_gui_partial_reopen_scan_relink_and_exclusion(experiment,tmp_path,monkeypatch):
    root,manager,app,paths,errors=experiment;owner=app._workspace;g=new_gate(app);gid=g['id']
    app._exclude_file(paths[2]);app.file_vars[paths[1]].set(False);app._on_active_files_changed()
    dest=tmp_path/'References.vflow';assert owner.save(path=str(dest))
    moved=tmp_path/'Moved';moved.mkdir();Path(paths[0]).rename(moved/'A.csv')
    gatepath=Path(owner.document.default_gate_session.absolute_path);gatepath.rename(moved/gatepath.name)
    assert owner.open(str(dest));root.update();assert len(owner.missing)==2
    assert len(owner.document.samples)==3 and paths[2] in app.excluded_files
    from tkinter import filedialog
    monkeypatch.setattr(filedialog,'askdirectory',lambda **k:str(moved))
    owner.find_missing()
    import time
    for _ in range(150):
        root.update()
        if not owner._scan_running:break
        time.sleep(.01)
    assert not owner.missing
    assert str(moved/'A.csv') in app.loaded_files and app.gates
    assert app.file_vars[paths[1]].get() is False
    assert owner.dirty


def test_real_gui_multigate_partition_and_secondary_analysis_use_overrides(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace;first=new_gate(app);gid=first['id']
    sid=owner.sample_id(paths[1]);owner.show_sample(app,sid);app.gate_scope_var.set('Current sample');owner.scope_changed(app)
    app._sel_gate()['x1']=70.;app.refresh_plot()
    app.view_mode_var.set('overlay');app._on_view_mode_change();second=new_gate(app)
    second.update(x0=80.,x1=200.,y0=20.,y1=200.);app._recompute_all_gate_stats();app.refresh_plot()
    from vflow.services.batch_plot_samples import build_batch_plot_samples
    from vflow.services.batch_plot_results import compute_batch_plot_results
    samples=build_batch_plot_samples(loaded_files=app.loaded_files,active_paths=paths,file_colors=app.file_colors,sample_colors=['red'])
    results=compute_batch_plot_results(samples,dist_col='X',gate=first,region_name='IN',x_channel='X',y_channel='Y',use_gate=True,
        transform_xy=app._transform_xy,gate_mask_for=app._gate_mask_for,
        sample_gate_resolver=lambda label,df,g:owner.resolved_gate(app,df.attrs['vflow_source_path'],g))
    assert not results.failed
    assert sorted(len(vals) for vals,color in results.dist_cache.values())==[2,3,3]
    app.stats_mode_var.set('merged');app._update_stats_display();root.update()
    items=app.stats_tree.get_children();assert items
    parent=items[0];children=app.stats_tree.get_children(parent)
    total=sum(int(str(app.stats_tree.item(i,'values')[0]).replace(',','')) for i in children)
    assert total==15


def test_real_gui_multilevel_lineage_keeps_all_parent_namespaces(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace;first=new_gate(app)
    app._open_subgate(50.,50.);child=manager._apps[1];child.plot_type_var.set('Dot Plot')
    child.x_var.set('X');child.y_var.set('Y');child.apply_axes();child.x_scale_var.set('linear');child.y_scale_var.set('linear')
    second=new_gate(child);child._open_subgate(50.,50.);grandchild=manager._apps[2]
    assert [stage.get('workspace_tab_id') for stage in grandchild.population_lineage]==[app._workspace_tab_id,child._workspace_tab_id]
    sid=owner.sample_id(paths[1]);owner.show_sample(app,sid);app.gate_scope_var.set('Current sample');owner.scope_changed(app)
    app._sel_gate()['x1']=70.;app.refresh_plot();grandchild.refresh_plot()
    assert len(grandchild.loaded_files[paths[1]])==2 and len(grandchild.loaded_files[paths[0]])==3


def test_real_gui_missing_gate_resource_never_opens_child_as_full_population(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace;new_gate(app);app._open_subgate(50.,50.)
    child=manager._apps[1];child.refresh_plot();dest=tmp_path/'MissingParent.vflow';assert owner.save(path=str(dest))
    Path(owner.document.default_gate_session.absolute_path).unlink()
    assert owner.open(str(dest));root.update()
    assert len(manager._apps)==2 and not manager._apps[1].loaded_files
    assert len(app.loaded_files)==3 and 'gate:default' in owner.missing


def test_real_gui_drag_handle_copies_gate_to_sample(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace;g=new_gate(app);gid=g['id']
    app._set_all_sections(False);app._sections['GATE MANAGER'][0].set(True);app._toggle_section('GATE MANAGER');root.update()
    handles=[]
    def walk(w):
        for child in w.winfo_children():
            if getattr(child,'_vflow_drag_gate_id',None)==gid:handles.append(child)
            walk(child)
    walk(app.gate_manager_frame);assert handles
    handle=handles[0];tree=app._workspace_tree;target=owner.sample_id(paths[1]);root.update()
    bounds=tree.bbox(target);assert bounds
    tx=tree.winfo_rootx()+bounds[0]+40;ty=tree.winfo_rooty()+bounds[1]+bounds[3]//2
    hx,hy=handle.winfo_rootx(),handle.winfo_rooty()
    handle.event_generate('<ButtonPress-1>',x=1,y=1,rootx=hx+1,rooty=hy+1)
    handle.event_generate('<B1-Motion>',x=tx-hx,y=ty-hy,rootx=tx,rooty=ty)
    handle.event_generate('<ButtonRelease-1>',x=tx-hx,y=ty-hy,rootx=tx,rooty=ty)
    root.update();assert gid in owner.stores['main'].sample_overrides[target]


def test_real_gui_child_sample_membership_and_source_exclusion(experiment):
    root,manager,app,paths,errors=experiment;new_gate(app)
    app.file_vars[paths[2]].set(False);app._on_active_files_changed();app._open_subgate(50.,50.)
    child=manager._apps[1];child.refresh_plot();assert paths[2] not in child.loaded_files
    app._exclude_file(paths[1]);child.refresh_plot();assert paths[1] not in child.loaded_files
    assert paths[0] in child.loaded_files


def test_real_gui_region_labels_agree_with_sample_override_counts(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace;g=new_gate(app)
    sid=owner.sample_id(paths[1]);owner.show_sample(app,sid);app.gate_scope_var.set('Current sample');owner.scope_changed(app)
    app._sel_gate()['x1']=70.;app._recompute_all_gate_stats();app.refresh_plot()
    app.view_mode_var.set('overlay');app._on_view_mode_change();root.update()
    assert any('(8)' in text.get_text() and '53.3%' in text.get_text() for text in app.ax.texts)


def test_real_gui_gate_copy_rejects_unavailable_target_lineage(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace;parent=new_gate(app);app._open_subgate(50.,50.)
    child=manager._apps[1];child.plot_type_var.set('Dot Plot');child.x_var.set('X');child.y_var.set('Y');child.apply_axes()
    child.x_scale_var.set('linear');child.y_scale_var.set('linear');gate=new_gate(child)
    sid=owner.sample_id(paths[1]);owner.stores['main'].sample_overrides[sid]={parent['id']:None};owner.stores['main'].revision+=1
    child.refresh_plot();store=owner.stores[child._workspace_tab_id];before=store.snapshot()
    owner.gate_action(child,'copy',gate['id'],[sid]);assert store.snapshot()==before


def test_auto_fit_default_pools_all_active_even_in_cycle(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    owner.show_sample(app,owner.sample_id(paths[1]))
    app.file_vars[paths[2]].set(False);app._on_active_files_changed()
    app._workspace_tree.selection_set(owner.sample_id(paths[2]))
    np.testing.assert_array_equal(app._collect_x_transform(),np.tile([30.,50.,90.,120.,220.],2))
    assert len(app._collect_y_transform())==10
    app.lock_scale_var.set(True);app._locked_xlim=[0.,60.];app._locked_ylim=[0.,60.];app.refresh_plot()
    assert len(app._collect_x_transform())==10


def test_auto_fit_selected_subset_is_independent_of_gate_targets_and_reopens(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    sid=owner.sample_id(paths[1]);app._workspace_tree.selection_set(sid)
    app.auto_gate_input_var.set('Selected samples (workspace list)')
    app.auto_gate_otsu();gid=app._sel_gate_id;store=owner.stores['main']
    assert len(app._collect_x_transform())==5
    assert store.global_gates and not any(store.sample_overrides.values())
    assert all(store.resolve_gate(owner.sample_id(p),gid) for p in paths)
    assert app._sel_gate()['_auto_fit']['sample_ids']==[sid]
    assert app._sel_gate()['_auto_fit']['source_rows']=={sid:5}
    counts=copy.deepcopy(app.gate_stats)
    dest=tmp_path/'Fitted.vflow';assert owner.save(path=str(dest));assert owner.open(str(dest));root.update()
    assert app.auto_gate_input_var.get()=='Selected samples (workspace list)'
    assert list(app._workspace_tree.selection())==[sid]
    assert app._sel_gate()['_auto_fit']['sample_ids']==[sid]
    assert app.gate_stats==counts


def test_auto_fit_current_source_can_apply_globally_or_to_one_sample(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    sid=owner.sample_id(paths[1]);owner.show_sample(app,sid)
    app.auto_gate_input_var.set('Current sample');app.auto_gate_otsu();gid=app._sel_gate_id
    assert app._sel_gate()['_auto_fit']['sample_ids']==[sid]
    assert all(owner.stores['main'].resolve_gate(owner.sample_id(p),gid) for p in paths)
    app.gate_scope_var.set('Current sample');owner.scope_changed(app)
    app.auto_gate_otsu()
    assert gid in owner.stores['main'].sample_overrides[sid]
    assert app._sel_gate()['_auto_fit']['application_scope']=='Current sample'


@pytest.mark.parametrize('method',['auto_gate_otsu','auto_gate_derivative','auto_gate_gmm_multi','auto_gate_cluster_polygons'])
def test_every_auto_method_receives_the_same_explicit_full_subset(experiment,monkeypatch,method):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    legacy=getattr(app,method).__func__.__wrapped__.__globals__
    wanted=[owner.sample_id(p) for p in paths[:2]]
    app._workspace_tree.selection_set(wanted);app.auto_gate_input_var.set('Selected samples (workspace list)')
    owner.show_sample(app,wanted[0]);app.lock_scale_var.set(True);app._locked_xlim=[40.,60.];app._locked_ylim=[40.,60.]
    seen=[]
    def threshold(values,**kw):seen.append(np.array(values));return float(np.median(values))
    if method=='auto_gate_otsu':monkeypatch.setitem(legacy,'otsu_threshold',threshold)
    elif method=='auto_gate_derivative':
        monkeypatch.setitem(legacy,'derivative_threshold',threshold)
        monkeypatch.setattr(app,'_kde_valley_supported',lambda *a:True)
    elif method=='auto_gate_gmm_multi':
        original=legacy['fit_gmm_crossings']
        def crossing(values,*a,**kw):seen.append(np.array(values));return original(values,*a,**kw)
        monkeypatch.setitem(legacy,'fit_gmm_crossings',crossing)
    else:
        original=legacy['prepare_cluster_polygon_data']
        def prepare(x,y,xr,yr,**kw):seen.extend([np.array(x),np.array(y)]);assert len(xr)==len(yr)==10;return original(x,y,xr,yr,**kw)
        monkeypatch.setitem(legacy,'prepare_cluster_polygon_data',prepare)
    getattr(app,method)()
    assert len(seen)==2
    np.testing.assert_array_equal(seen[0],np.tile([30.,50.,90.,120.,220.],2))
    np.testing.assert_array_equal(seen[1],np.tile([30.,50.,90.,120.,70.],2))


def test_entire_workspace_replaces_only_the_selected_gate_overrides_and_undo(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace;g=new_gate(app);gid=g['id']
    second=new_gate(app);other_id=second['id'];store=owner.stores['main']
    sids=[owner.sample_id(p) for p in paths]
    owner.show_sample(app,sids[1]);app.gate_scope_var.set('Current sample');owner.scope_changed(app)
    app._select_gate(gid);app._sel_gate()['x1']=70.;app.refresh_plot()
    owner.gate_action(app,'copy',gid,[sids[2]])
    store.sample_overrides[sids[2]][gid]['x1']=50.
    store.copy_to_sample(store.resolve_gate(sids[0],other_id),sids[2],['X','Y'])
    app.file_vars[paths[2]].set(False);app._on_active_files_changed()
    before=store.snapshot();owner.gate_action(app,'workspace',gid)
    assert all(store.resolve_gate(sid,gid)['x1']==70. for sid in sids)
    assert other_id in store.sample_overrides[sids[2]]
    owner.gate_action(app,'undo',gid);assert store.snapshot()==before
    owner.gate_action(app,'workspace',gid)
    dest=tmp_path/'WorkspaceApply.vflow';assert owner.save(path=str(dest));assert owner.open(str(dest));root.update()
    assert all(owner.stores['main'].resolve_gate(sid,gid)['x1']==70. for sid in sids)
    assert not app.file_vars[paths[2]].get()


def test_selected_sample_edit_is_sparse_preserves_unedited_gates_and_undo(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace;g=new_gate(app);gid=g['id']
    second=new_gate(app);other=second['id'];store=owner.stores['main'];sids=[owner.sample_id(p) for p in paths]
    store.copy_to_sample(store.resolve_gate(sids[0],other),sids[2],['X','Y']);store.sample_overrides[sids[2]][other]['x1']=55.
    app._workspace_tree.selection_set(sids[1:]);app.gate_scope_var.set('Selected samples');owner.scope_changed(app)
    app._select_gate(gid);before=store.snapshot();app._sel_gate()['x1']=70.;app.refresh_plot()
    assert store.resolve_gate(sids[0],gid)['x1']==100.
    assert all(store.resolve_gate(sid,gid)['x1']==70. for sid in sids[1:])
    assert store.resolve_gate(sids[2],other)['x1']==55.
    assert app.gate_stats[gid][paths[0]]['stats']['IN']['count']==3
    assert app.gate_stats[gid][paths[1]]['stats']['IN']['count']==2
    owner.gate_action(app,'undo',gid);assert store.snapshot()==before
    app.view_mode_var.set('overlay');app._on_view_mode_change();assert app.gate_scope_var.get()=='All samples (default)'


def test_selected_sample_edit_rejects_incompatible_target_atomically(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace;g=new_gate(app);gid=g['id'];store=owner.stores['main']
    sids=[owner.sample_id(p) for p in paths];app._workspace_tree.selection_set(sids[1:])
    app.gate_scope_var.set('Selected samples');owner.scope_changed(app)
    app.loaded_files[paths[2]]=app.loaded_files[paths[2]].drop(columns=['Y'])
    before=store.snapshot();app._sel_gate()['x1']=70.;owner.commit_gates(app)
    assert store.snapshot()==before
    assert app._sel_gate()['x1']==100.
    assert 'Required channel: Y' in app.status_var.get()


def test_auto_gate_reuse_is_one_undo_step_and_scope_change_cancels_live_rerun(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    app.auto_gate_otsu();store=owner.stores['main'];gid=app._sel_gate_id;before=store.snapshot()
    # Different training population yields a changed result without changing display limits.
    app.loaded_files[paths[1]]['X']+=1000.;app.auto_gate_otsu()
    assert store.snapshot()!=before
    owner.gate_action(app,'undo',gid);assert store.snapshot()==before
    app.file_vars[paths[2]].set(False);app._on_active_files_changed();snapshot=store.snapshot()
    app._rerun_last_auto_gate();assert store.snapshot()==snapshot
    assert 'Click the method' in app.status_var.get()


def test_drag_feedback_does_not_mutate_fitting_row_selection(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace;g=new_gate(app);gid=g['id'];sids=[owner.sample_id(p) for p in paths]
    app._workspace_tree.selection_set(sids[:2]);root.update()
    handle=next(w for row in app.gate_manager_frame.winfo_children() for w in row.winfo_children() if getattr(w,'_vflow_drag_gate_id',None)==gid)
    tree=app._workspace_tree;box=tree.bbox(sids[2]);x=tree.winfo_rootx()+20;y=tree.winfo_rooty()+box[1]+box[3]//2
    handle.event_generate('<ButtonPress-1>',x=2,y=2)
    handle.event_generate('<B1-Motion>',x=x-handle.winfo_rootx(),y=y-handle.winfo_rooty(),rootx=x,rooty=y)
    assert tree.item(sids[2],'tags')==('drop_target',)
    assert list(tree.selection())==sids[:2]
    handle.event_generate('<ButtonRelease-1>',x=x-handle.winfo_rootx(),y=y-handle.winfo_rooty(),rootx=x,rooty=y)
    assert not tree.item(sids[2],'tags')
    assert list(tree.selection())==sids[:2]


def test_plot_header_names_sample_scope_and_overlay_overrides(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace;g=new_gate(app);gid=g['id']
    sid=owner.sample_id(paths[1]);owner.show_sample(app,sid);app.gate_scope_var.set('Current sample');owner.scope_changed(app)
    app._sel_gate()['x1']=70.;app.refresh_plot();assert 'B.csv' in app.fig._suptitle.get_text()
    assert 'Current sample' in app.fig._suptitle.get_text()
    app.view_mode_var.set('overlay');app._on_view_mode_change()
    assert 'Custom samples:' in app.fig._suptitle.get_text()


def test_cluster_input_keeps_nan_and_log_invalid_rows_aligned(experiment,monkeypatch):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    app.x_scale_var.set('log');root.update()
    app.loaded_files[paths[0]].loc[0,'X']=0.
    app.loaded_files[paths[0]].loc[1,'Y']=np.nan
    legacy=app.auto_gate_cluster_polygons.__func__.__wrapped__.__globals__
    original=legacy['prepare_cluster_polygon_data'];seen=[]
    def prepare(x,y,xr,yr,**kw):
        assert len(x)==len(y)==len(xr)==len(yr)==15
        valid=np.isfinite(x)&np.isfinite(y);seen.append((xr[valid],yr[valid]))
        return original(x,y,xr,yr,**kw)
    monkeypatch.setitem(legacy,'prepare_cluster_polygon_data',prepare)
    app.auto_gate_cluster_polygons();assert len(seen)==1
    assert len(seen[0][0])==13
    np.testing.assert_array_equal(seen[0][0][:3],[90.,120.,220.])
    np.testing.assert_array_equal(seen[0][1][:3],[90.,120.,70.])


def test_cluster_creating_multiple_gates_is_one_undo_step(experiment,monkeypatch):
    root,manager,app,paths,errors=experiment;owner=app._workspace;new_gate(app);before=owner.stores['main'].snapshot()
    for p in paths:app.loaded_files[p]=pd.concat([app.loaded_files[p]]*4,ignore_index=True)
    app._invalidate_analysis_caches(data_changed=True)
    legacy=app.auto_gate_cluster_polygons.__func__.__wrapped__.__globals__
    from vflow.core.auto_gate import ClusterPolygonComputation
    result=ClusterPolygonComputation(algorithm_tag='hdbscan',algorithm_label='HDBSCAN',polygons=[[(25.,25.),(60.,25.),(60.,60.)],[(80.,80.),(130.,80.),(130.,130.)]],noise_count=0,labels_count=60,n_total=60,cluster_count=2)
    monkeypatch.setitem(legacy,'fit_cluster_polygons',lambda *a,**k:result)
    app.auto_gate_cluster_polygons();assert len(app.gates)==3
    owner.gate_action(app,'undo',app._sel_gate_id);assert owner.stores['main'].snapshot()==before


def test_empty_fitting_selection_creates_no_gate(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    app.auto_gate_input_var.set('Selected samples (workspace list)');app._workspace_tree.selection_set(())
    before=owner.stores['main'].snapshot();app.auto_gate_otsu();assert owner.stores['main'].snapshot()==before
    assert not app.gates


def test_auto_fitting_in_child_uses_each_samples_resolved_parent(experiment,monkeypatch):
    root,manager,app,paths,errors=experiment;owner=app._workspace;g=new_gate(app);gid=g['id']
    sid=owner.sample_id(paths[1]);owner.show_sample(app,sid);app.gate_scope_var.set('Current sample');owner.scope_changed(app)
    app._sel_gate()['x1']=70.;app.refresh_plot();app._open_subgate(50.,50.)
    child=manager._apps[1];child.auto_gate_input_var.set('Active samples (pooled)')
    frames=child._auto_gate_data();assert [len(frames[p]) for p in paths]==[3,2,3]
    np.testing.assert_array_equal(child._collect_x_transform(),[30.,50.,90.,30.,50.,30.,50.,90.])


def test_tab_selection_refreshes_parent_changes_and_child_active_state_reopens(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace;g=new_gate(app);gid=g['id'];app._open_subgate(50.,50.)
    child=manager._apps[1];child.file_vars[paths[2]].set(False);child._on_active_files_changed()
    manager.notebook.select(0);root.update();sid=owner.sample_id(paths[1]);owner.show_sample(app,sid)
    app.gate_scope_var.set('Current sample');owner.scope_changed(app);app._sel_gate()['x1']=70.;app.refresh_plot()
    manager.notebook.select(1);root.update();assert len(child.loaded_files[paths[1]])==2
    child_id=child._workspace_tab_id;dest=tmp_path/'ActiveChild.vflow';assert owner.save(path=str(dest))
    assert owner.open(str(dest));root.update();restored=owner.apps[child_id]
    assert manager.notebook.index(manager.notebook.select())==1
    assert not restored.file_vars[paths[2]].get() and app.file_vars[paths[2]].get()


def test_current_sample_copy_uses_resolved_gate_even_when_editing_all_samples(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace;g=new_gate(app);gid=g['id'];sids=[owner.sample_id(p) for p in paths]
    owner.show_sample(app,sids[1]);app.gate_scope_var.set('Current sample');owner.scope_changed(app)
    app._sel_gate()['x1']=70.;app.refresh_plot();app.gate_scope_var.set('All samples (default)');owner.scope_changed(app)
    assert app._sel_gate()['x1']==100.
    owner.gate_action(app,'copy',gid,[sids[2]])
    assert owner.stores['main'].resolve_gate(sids[2],gid)['x1']==70.


def test_pinned_active_checkbox_controls_pooled_fitting(experiment):
    root,manager,app,paths,errors=experiment;owner=app._workspace;sid=owner.sample_id(paths[1]);root.update()
    tree=app._workspace_tree;box=tree.bbox(sid,'active');assert box
    tree.event_generate('<Button-1>',x=box[0]+box[2]//2,y=box[1]+box[3]//2)
    root.update();assert not app.file_vars[paths[1]].get()
    assert len(app._collect_x_transform())==10


def test_missing_parent_lineage_survives_redraw_and_state_save(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace;new_gate(app);app._open_subgate(50.,50.)
    dest=tmp_path/'Missing.vflow';assert owner.save(path=str(dest));gate_path=Path(owner.document.default_gate_session.absolute_path)
    moved=gate_path.with_suffix('.moved');gate_path.rename(moved)
    assert owner.open(str(dest));root.update();child=manager._apps[1];tab_id=child._workspace_tab_id
    for _ in range(5):child.refresh_plot();root.update();assert not child.loaded_files
    assert owner.document.tabs[tab_id]['lineage']
    assert owner.save();assert owner.document.default_gate_session.absolute_path==str(gate_path)
    assert owner.open(str(dest));root.update();assert not manager._apps[1].loaded_files
    assert app._add_gate(auto_type='rectangle') is None
    owner.document.default_gate_session.accept(moved,owner.path)
    owner.restoring=True
    try:owner.reload_resources()
    finally:owner.restoring=False
    restored=manager._apps[1];restored.population_lineage=copy.deepcopy(owner._loaded_lineages[tab_id]);restored._workspace_display_signature=None
    restored.refresh_plot();assert len(restored.loaded_files[paths[0]])==3


def test_native_gate_save_in_selected_scope_keeps_correct_external_references(experiment,tmp_path,monkeypatch):
    root,manager,app,paths,errors=experiment;owner=app._workspace;new_gate(app);sids=[owner.sample_id(p) for p in paths]
    app._workspace_tree.selection_set(sids[1:]);app.gate_scope_var.set('Selected samples');owner.scope_changed(app)
    from tkinter import filedialog
    gate_file=tmp_path/'SelectedGates.json';monkeypatch.setattr(filedialog,'asksaveasfilename',lambda **k:str(gate_file))
    app.save_gates();assert gate_file.exists()
    assert all(owner.document.samples[sid].gate_session.absolute_path==str(gate_file) for sid in sids[1:])
    assert owner.document.samples[sids[0]].gate_session is None
    dest=tmp_path/'SelectedNative.vflow';assert owner.save(path=str(dest));assert owner.open(str(dest));root.update()
    assert app.gates
