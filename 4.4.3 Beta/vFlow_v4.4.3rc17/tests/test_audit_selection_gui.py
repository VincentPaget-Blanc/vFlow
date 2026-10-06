"""Native click semantics, async edges and actual benchmark audit transactions."""
import hashlib,json,os,queue,threading,time
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox,simpledialog
import pandas as pd
import pytest
from tests.test_workspace_gui import experiment
from vflow.ui.statistical_audit_dialog import StatisticalAuditDialog,AuditResultsDialog
from vflow.statistics import run_audit
from vflow.statistics.workspace_audit import prepare_samples
from vflow.statistics.audit_serialization import read_bundle
from vflow.statistics.audit_export import export_xlsx,export_csv_package

pytestmark=pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='Native display required')
ROOT=Path(__file__).resolve().parents[1]
_clock=1000

def click(widget,x,y,*,gap=1000,state=0):
    global _clock
    _clock+=gap
    widget.event_generate('<ButtonPress-1>',x=int(x),y=int(y),time=_clock,state=state)
    widget.event_generate('<ButtonRelease-1>',x=int(x),y=int(y),time=_clock+10,state=state)
    widget.update()

def click_sample(dialog,sid,column='#0',gap=1000,state=0):
    dialog.samples.see(sid);dialog.update();box=dialog.samples.bbox(sid,column)
    assert box
    if box[1]+box[3]>dialog.samples.winfo_height()-4:
        dialog.samples.yview_scroll(1,'units');dialog.update();box=dialog.samples.bbox(sid,column)
        assert box
    y=min(box[1]+box[3]//2,dialog.samples.winfo_height()-4)
    assert box[1]<=y<box[1]+box[3]
    assert dialog.samples.identify_row(y)==sid
    click(dialog.samples,box[0]+max(3,box[2]//2),y,gap=gap,state=state)

def click_variable(dialog,index,gap=1000,state=0):
    dialog.variables.see(index);dialog.update();box=dialog.variables.bbox(index)
    assert box
    click(dialog.variables,8,box[1]+box[3]//2,gap=gap,state=state)

def wait_dialog(root,dialog):
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        root.update()
        if not dialog._busy and not (dialog.worker and dialog.worker.is_alive()) and dialog.messages.empty():return
        time.sleep(.005)
    raise AssertionError('Audit worker did not settle')

@pytest.fixture
def audit_dialog(experiment):
    root,manager,app,paths,errors=experiment
    dialog=StatisticalAuditDialog(app._workspace,app);root.update()
    yield root,manager,app,paths,errors,dialog
    if dialog.winfo_exists():dialog.close()


def test_sample_plain_clicks_toggle_without_clearing_others(audit_dialog):
    root,manager,app,paths,errors,dialog=audit_dialog
    ids=dialog.samples.get_children();dialog.no_samples_button.invoke()
    click_sample(dialog,ids[0]);click_sample(dialog,ids[1])
    assert set(dialog.samples.selection())==set(ids[:2])
    click_sample(dialog,ids[0]);assert dialog.samples.selection()==(ids[1],)
    click_sample(dialog,ids[2],state=0x4);assert set(dialog.samples.selection())==set(ids[1:])
    click_sample(dialog,ids[0],state=0x1);assert set(dialog.samples.selection())==set(ids)
    # Headings, separators and unused table space do not alter selection.
    before=dialog.samples.selection();click(dialog.samples,15,4)
    click(dialog.samples,10,dialog.samples.winfo_height()-3)
    assert dialog.samples.selection()==before


def test_sample_keyboard_navigation_preserves_selection_and_space_toggles(audit_dialog):
    root,manager,app,paths,errors,dialog=audit_dialog
    ids=dialog.samples.get_children();dialog.no_samples_button.invoke()
    dialog.samples.focus_force();dialog.samples.focus(ids[0]);root.update()
    dialog.samples.event_generate('<space>');root.update()
    assert dialog.samples.selection()==(ids[0],)
    dialog.samples.event_generate('<Down>');root.update()
    assert dialog.samples.focus()==ids[1] and dialog.samples.selection()==(ids[0],)
    dialog.samples.event_generate('<Return>');root.update()
    assert set(dialog.samples.selection())==set(ids[:2])
    dialog.samples.event_generate('<space>');root.update()
    assert dialog.samples.selection()==(ids[0],)
    dialog.all_samples_button.invoke();assert set(dialog.samples.selection())==set(ids)
    dialog.no_samples_button.invoke();assert not dialog.samples.selection()


def test_variable_clicks_keyboard_focus_and_blank_space_preserve_selection(audit_dialog):
    root,manager,app,paths,errors,dialog=audit_dialog
    for name in ('X','Y','U'):dialog.variables.insert('end',name)
    click_variable(dialog,0);click_variable(dialog,1)
    assert dialog.variables.curselection()==(0,1)
    click_variable(dialog,0);assert dialog.variables.curselection()==(1,)
    dialog.samples.focus_force();root.update();assert dialog.variables.curselection()==(1,)
    dialog.variables.focus_force();dialog.variables.activate(2);root.update()
    dialog.variables.event_generate('<space>');root.update()
    assert dialog.variables.curselection()==(1,2)
    dialog.variables.event_generate('<Up>');root.update()
    assert dialog.variables.curselection()==(1,2)
    before=dialog.variables.curselection();click(dialog.variables,10,dialog.variables.winfo_height()-3)
    assert dialog.variables.curselection()==before
    dialog.prepared=[object()]
    dialog.all_variables_button.invoke();assert dialog.variables.curselection()==(0,1,2)
    assert '3 selected' in dialog.status.get()
    dialog.no_variables_button.invoke();assert not dialog.variables.curselection()
    assert '0 selected' in dialog.status.get()
    dialog.variables.delete(0,'end');click(dialog.variables,8,8);assert not dialog.variables.curselection()


def test_double_click_biological_id_edits_without_changing_membership(audit_dialog,monkeypatch):
    root,manager,app,paths,errors,dialog=audit_dialog
    dialog.kind.set('hierarchy');dialog.update_hierarchy();root.update()
    ids=dialog.samples.get_children();before=set(dialog.samples.selection());calls=[]
    monkeypatch.setattr(simpledialog,'askstring',lambda *a,**k:calls.append(a) or ' bio α ')
    click_sample(dialog,ids[0],column='bio');click_sample(dialog,ids[0],column='bio',gap=50)
    assert calls and dialog.mapping[ids[0]]=='bio α'
    assert set(dialog.samples.selection())==before
    dialog.samples.selection_remove(ids[1]);before=set(dialog.samples.selection());calls.clear()
    click_sample(dialog,ids[1],column='bio');click_sample(dialog,ids[1],column='bio',gap=50)
    assert calls and set(dialog.samples.selection())==before
    calls.clear();click_sample(dialog,ids[2]);click_sample(dialog,ids[2],gap=50)
    assert not calls and set(dialog.samples.selection())==before


def test_changed_sample_selection_requires_prepare_and_empty_inputs_are_rejected(audit_dialog,monkeypatch):
    root,manager,app,paths,errors,dialog=audit_dialog;alerts=[]
    monkeypatch.setattr(messagebox,'showerror',lambda *a,**k:alerts.append(a))
    dialog.prepare();wait_dialog(root,dialog)
    assert dialog.prepared and dialog.variables.size()
    sid=dialog.samples.get_children()[0];click_sample(dialog,sid)
    dialog.run();assert alerts and 'Prepare' in str(alerts[-1]) and not app._workspace.document.audits
    dialog.prepare();wait_dialog(root,dialog)
    assert {s.sample_id for s in dialog.prepared}==set(dialog.samples.selection())
    dialog.no_variables_button.invoke();dialog.run();assert 'variable' in str(alerts[-1])
    dialog.no_samples_button.invoke();dialog.prepare();assert 'sample' in str(alerts[-1])


def test_busy_inputs_freeze_and_close_does_not_commit(audit_dialog):
    root,manager,app,paths,errors,dialog=audit_dialog
    for name in ('X','Y'):dialog.variables.insert('end',name)
    dialog.all_variables_button.invoke();ids=dialog.samples.selection();release=threading.Event()
    dialog.start(lambda:release.wait(5));root.update()
    try:
        click_sample(dialog,ids[0]);click_variable(dialog,0)
        dialog.no_samples_button.invoke();dialog.no_variables_button.invoke()
        assert dialog.samples.selection()==ids and dialog.variables.curselection()==(0,1)
        assert dialog.run_button.instate(['disabled']) and dialog.prepare_button.instate(['disabled'])
        assert dialog.kind.get()=='qc'
        dialog.close();release.set();dialog.worker.join(timeout=2);root.update()
        assert not app._workspace.document.audits and dialog.cancel_event.is_set()
    finally:release.set()


def test_queue_result_arriving_at_worker_exit_is_not_lost(audit_dialog):
    root,manager,app,paths,errors,dialog=audit_dialog;owner=app._workspace
    bundle=run_audit(prepare_samples(owner,app,[owner.sample_id(p) for p in paths]),variables=['X','Y'])
    class ExitQueue(queue.Queue):
        delivered=False
        def get_nowait(self):
            if not self.delivered and self.empty():
                self.delivered=True;self.put(('result',bundle));raise queue.Empty
            return super().get_nowait()
    dialog.messages=ExitQueue();dialog.set_busy(True)
    dialog.worker=threading.Thread(target=lambda:None);dialog.worker.start();dialog.worker.join()
    dialog.poll();assert dialog._poll_id is not None and not owner.document.audits
    dialog.poll();root.update()
    assert len(owner.document.audits)==1 and not dialog._busy
    assert dialog.status.get().startswith('Audit saved:')

@pytest.mark.parametrize('action',['same_file','new_workspace','closed_population'])
def test_old_dialog_cannot_run_against_replaced_workspace_or_closed_tab(experiment,tmp_path,monkeypatch,action):
    root,manager,app,paths,errors=experiment;owner=app._workspace;alerts=[]
    monkeypatch.setattr(messagebox,'showerror',lambda *a,**k:alerts.append(a))
    if action=='closed_population':
        from tests.test_workspace_gui import new_gate
        new_gate(app);app._open_subgate(50.,50.);app=manager._apps[1];root.update()
    dialog=StatisticalAuditDialog(owner,app);root.update();dialog.prepare();wait_dialog(root,dialog)
    old_id=owner.document.workspace_id
    if action=='same_file':
        dest=tmp_path/'Same.vflow';assert owner.save(path=str(dest));assert owner.open(str(dest));root.update()
        assert owner.document.workspace_id==old_id
    elif action=='new_workspace':owner.clear();root.update()
    else:manager._close_tab(1);root.update()
    try:
        dialog.run();dialog.prepare()
        assert len(alerts)==2 and all('changed' in str(a) for a in alerts)
        assert not owner.document.audits and not dialog._busy
    finally:dialog.close()


def test_scroll_long_variable_names_and_many_samples_keeps_toggled_items(audit_dialog):
    root,manager,app,paths,errors,dialog=audit_dialog
    for i in range(60):dialog.samples.insert('','end',iid=f'ui_{i}',text=f'UI row {i}')
    dialog.no_samples_button.invoke();click_sample(dialog,'ui_0');click_sample(dialog,'ui_59')
    assert set(dialog.samples.selection())=={'ui_0','ui_59'}
    for i in range(60):dialog.variables.insert('end',f'Numeric variable {i} '+('long name '*20))
    click_variable(dialog,0);click_variable(dialog,59)
    assert dialog.variables.curselection()==(0,59)
    dialog.variables.xview_moveto(1);dialog.samples.yview_moveto(0);root.update()
    assert dialog.variables.xview()[0]>0 and dialog.variables.curselection()==(0,59)
    assert set(dialog.samples.selection())=={'ui_0','ui_59'}


def test_empty_sidebar_has_only_data_workspace_open(experiment):
    root,manager,app,paths,errors=experiment;app._workspace.clear();root.update()
    assert not hasattr(app,'_workspace_empty_open')
    assert app._workspace_action_buttons['Open…'].winfo_exists()
    app._select_sidebar_task('Data');root.update()
    assert app._workspace_action_buttons['Open…'].winfo_ismapped()
    def descendants(widget):
        for child in widget.winfo_children():yield child;yield from descendants(child)
    assert not [w for w in descendants(app._workspace_panel) if isinstance(w,ttk.Button) and str(w.cget('text')).startswith('Open Workspace')]


def test_real_benchmark_selected_audit_export_save_and_reopen(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    owner.clear();app.plot_type_var.set('Dot Plot');app.show_marginals_var.set(False)
    sources=[ROOT/'benchmark_extensions/frozen_v1/cytometry'/n for n in ('Control_01.csv','Control_02.csv','Treatment_01.csv','Treatment_02.csv')]
    original={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    app._load_paths([str(p) for p in sources]);root.update()
    dialog=StatisticalAuditDialog(owner,app);dialog.geometry('920x850+650+70');root.update()
    try:
        dialog.no_samples_button.invoke();ids=[owner.sample_id(str(p)) for p in sources[:2]]
        click_sample(dialog,ids[0]);click_sample(dialog,ids[1])
        assert set(dialog.samples.selection())==set(ids)
        dialog.prepare();wait_dialog(root,dialog);dialog.no_variables_button.invoke()
        variables=list(dialog.variables.get(0,'end'));wanted=['FSC-A','SSC-A']
        for name in wanted:click_variable(dialog,variables.index(name))
        assert [dialog.variables.get(i) for i in dialog.variables.curselection()]==wanted
        from PIL import ImageGrab
        OUT=ROOT/'validation/audit_selection_rc15';OUT.mkdir(exist_ok=True)
        x,y=dialog.winfo_rootx(),dialog.winfo_rooty()
        ImageGrab.grab(bbox=(x,y,x+dialog.winfo_width(),y+dialog.winfo_height()),xdisplay=os.environ['DISPLAY']).save(OUT/'01_Selected_Benchmark_Audit.png')
        dialog.run();wait_dialog(root,dialog)
        assert len(owner.document.audits)==1
        ref=next(iter(owner.document.audits.values()));bundle=read_bundle(ref,owner.path)
        assert set(ref.selected_sample_ids)==set(ids) and bundle['variables']==wanted
        assert all(row['event_count']==12000 for row in bundle['sample_qc'])
        assert all(row['status']=='pairwise_only' for row in bundle['sample_qc'])
        assert len(app.loaded_files)==4 and not app.excluded_files
        results=next(w for w in root.winfo_children() if isinstance(w,AuditResultsDialog))
        results.tree.selection_set(ids[0]);results.details();root.update()
        export_xlsx(bundle,tmp_path/'audit.xlsx',ref,owner.document);export_csv_package(bundle,tmp_path/'audit.zip',ref,owner.document)
        assert (tmp_path/'audit.xlsx').stat().st_size>0 and (tmp_path/'audit.zip').stat().st_size>0
        dest=tmp_path/'Audit.vflow';assert owner.save(path=str(dest));dialog.close()
        assert owner.open(str(dest));root.update()
        assert len(owner.document.audits)==1 and read_bundle(owner.document.audits[ref.audit_id],owner.path)['variables']==wanted
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha for p,sha in original.items())
        (OUT/'benchmark_result.json').write_text(json.dumps({'files_loaded':4,'events_loaded':48000,'audited_sample_count':2,'audited_events':24000,'selected_variables':wanted,'status':'pairwise_only','no_automatic_exclusion':True,'exports_and_workspace_reopen_passed':True,'raw_hashes_unchanged':True,'errors':errors},indent=2)+'\n')
    finally:
        if dialog.winfo_exists():dialog.close()


def test_result_from_reopened_same_workspace_is_rejected_even_with_same_id(audit_dialog,tmp_path,monkeypatch):
    root,manager,app,paths,errors,dialog=audit_dialog;owner=app._workspace
    bundle=run_audit(prepare_samples(owner,app,[owner.sample_id(p) for p in paths]),variables=['X','Y'])
    dest=tmp_path/'Same.vflow';assert owner.save(path=str(dest));old_id=owner.document.workspace_id
    assert owner.open(str(dest));root.update();assert owner.document.workspace_id==old_id
    alerts=[];monkeypatch.setattr(messagebox,'showerror',lambda *a,**k:alerts.append(a))
    dialog.messages.put(('result',bundle));dialog.poll();root.update()
    assert alerts and not owner.document.audits and 'not committed' in dialog.status.get()
    dialog.prepared=prepare_samples(owner,app,[owner.sample_id(p) for p in paths])
    dialog.messages.put(('variables',(['X','Y'],[])));dialog.poll();root.update()
    assert dialog.prepared is None and not dialog.variables.size() and 'changed' in dialog.status.get()


def test_finished_worker_with_pending_result_cannot_start_second_run(audit_dialog):
    root,manager,app,paths,errors,dialog=audit_dialog;owner=app._workspace
    bundle=run_audit(prepare_samples(owner,app,[owner.sample_id(p) for p in paths]),variables=['X','Y'])
    dialog.set_busy(True);dialog.worker=threading.Thread(target=lambda:None)
    dialog.worker.start();dialog.worker.join();dialog.messages.put(('result',bundle))
    calls=[];dialog.start(lambda:calls.append(True));dialog.run()
    assert not calls and not owner.document.audits
    dialog.poll();root.update();assert len(owner.document.audits)==1 and not dialog._busy
    assert dialog.variables.cget('state')=='normal' and not dialog.run_button.instate(['disabled'])


def test_mouse_drag_does_not_replace_persistent_selections(audit_dialog):
    root,manager,app,paths,errors,dialog=audit_dialog
    ids=dialog.samples.get_children();dialog.no_samples_button.invoke();click_sample(dialog,ids[0]);click_sample(dialog,ids[1])
    box=dialog.samples.bbox(ids[2]);dialog.samples.event_generate('<B1-Motion>',x=10,y=box[1]+box[3]//2);root.update()
    assert set(dialog.samples.selection())==set(ids[:2])
    for name in ('X','Y','U'):dialog.variables.insert('end',name)
    click_variable(dialog,0);click_variable(dialog,1)
    box=dialog.variables.bbox(2);dialog.variables.event_generate('<B1-Motion>',x=8,y=box[1]+box[3]//2);root.update()
    assert dialog.variables.curselection()==(0,1)


@pytest.mark.parametrize('none_selected',[False,True])
def test_reprepare_changed_samples_preserves_variable_choices(audit_dialog,none_selected):
    root,manager,app,paths,errors,dialog=audit_dialog
    dialog.prepare();wait_dialog(root,dialog);dialog.no_variables_button.invoke()
    values=list(dialog.variables.get(0,'end'))
    if not none_selected:
        click_variable(dialog,values.index('X'));click_variable(dialog,values.index('Y'))
    click_sample(dialog,dialog.samples.get_children()[0]);dialog.prepare();wait_dialog(root,dialog)
    assert [dialog.variables.get(i) for i in dialog.variables.curselection()]==([] if none_selected else ['X','Y'])
    assert ('0 selected' if none_selected else '2 selected') in dialog.status.get()


@pytest.mark.parametrize('theme',['dark','light'])
def test_variable_highlight_is_readable_and_persists_after_focus_moves(experiment,theme):
    root,manager,app,paths,errors=experiment
    if app._theme_name!=theme:app.toggle_theme()
    dialog=StatisticalAuditDialog(app._workspace,app);root.update()
    try:
        dialog.variables.insert('end','X');click_variable(dialog,0)
        dialog.samples.focus_force();root.update()
        assert dialog.variables.curselection()==(0,)
        assert dialog.variables.cget('selectbackground')==app.T['sel_bg']
        assert dialog.variables.cget('selectforeground')=='white'
        assert dialog.variables.cget('background')==app.T['field_bg']
        # Live theme changes refresh when the audit gains focus again.
        app.toggle_theme();dialog.variables.focus_force();root.update()
        assert dialog.variables.cget('background')==app.T['field_bg']
        assert dialog.variables.curselection()==(0,)
    finally:dialog.close()


@pytest.mark.parametrize('mode,scale',[('Compact',1.),('Automatic',1.),('Comfortable',1.5),('Large',2.)])
def test_audit_scaled_geometry_preserves_tables_and_actions(experiment,mode,scale):
    root,manager,app,paths,errors=experiment;previous=root.tk.call('tk','scaling')
    dialog=None
    try:
        root.tk.call('tk','scaling',96/72*scale);app.interface_size_var.set(mode);app._apply_interface_size();root.update()
        dialog=StatisticalAuditDialog(app._workspace,app);root.update()
        assert dialog.winfo_width()<=root.winfo_screenwidth()-40
        assert dialog.winfo_height()<=root.winfo_screenheight()-80
        assert dialog.samples.winfo_ismapped() and dialog.prepare_button.winfo_ismapped()
        assert dialog.samples.bbox(dialog.samples.get_children()[0])
        dialog.prepare();wait_dialog(root,dialog)
        assert dialog.variables.winfo_ismapped() and dialog.variables.bbox(0)
        dialog.samples.yview_moveto(0);root.update()
        second=dialog.samples.bbox(dialog.samples.get_children()[1])
        assert second and second[1]+second[3]<=dialog.samples.winfo_height()-2
        assert dialog.run_button.winfo_rooty()+dialog.run_button.winfo_height()<=dialog.winfo_rooty()+dialog.winfo_height()
        ids=dialog.samples.get_children();dialog.no_samples_button.invoke();click_sample(dialog,ids[0]);click_sample(dialog,ids[1])
        assert set(dialog.samples.selection())==set(ids[:2])
        dialog.no_variables_button.invoke();click_variable(dialog,0);click_variable(dialog,1)
        assert dialog.variables.curselection()==(0,1)
        assert 1<=int(dialog.variables.cget('height'))<=7
    finally:
        if dialog is not None and dialog.winfo_exists():dialog.close()
        root.tk.call('tk','scaling',previous)
