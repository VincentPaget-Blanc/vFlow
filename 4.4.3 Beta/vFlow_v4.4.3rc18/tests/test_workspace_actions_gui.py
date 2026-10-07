"""Exercise the visible Data workspace controls, including durable naming."""
import json
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
import pytest
from tests.test_workspace_gui import experiment, new_gate

pytestmark = pytest.mark.skipif(not os.environ.get('DISPLAY') and os.name != 'nt' and os.sys.platform != 'darwin', reason='Tk display required')


def edit_name(root, app, text, key='<Return>'):
    app._workspace_name_entry.focus_force(); root.update()
    app._workspace_name_var.set(text)
    app._workspace_name_entry.event_generate(key); root.update()


def test_data_buttons_save_open_rename_and_repeat_edit(experiment, tmp_path, monkeypatch):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    app._select_sidebar_task('Data'); root.update()
    assert app._sections['WORKSPACE'][1].winfo_ismapped()
    assert all(b.winfo_ismapped() for b in app._workspace_action_buttons.values())
    gate = new_gate(app); gid = gate['id']; sid = owner.sample_id(paths[1])
    edit_name(root, app, 'Synaptosome study α')
    dest = tmp_path/'Study.vflow'
    options = []
    def save_dialog(**kw): options.append(kw); return str(dest)
    monkeypatch.setattr(filedialog, 'asksaveasfilename', save_dialog)
    app._workspace_action_buttons['Save'].invoke(); root.update()
    assert owner.path == str(dest)
    assert options[0]['initialfile'] == 'Synaptosome study α.vflow'
    assert app._workspace_save_state_var.get() == 'Saved'
    app._workspace_actions_menu.invoke('Close'); root.update()
    assert not owner.document.samples and owner.path is None
    assert app._workspace_name_var.get() == 'Untitled Workspace'
    monkeypatch.setattr(filedialog, 'askopenfilename', lambda **kw: str(dest))
    app._workspace_action_buttons['Open…'].invoke(); root.update()
    assert owner.workspace_name() == 'Synaptosome study α'
    assert len(owner.document.samples) == 3 and app.gate_stats[gid][paths[0]]['stats']['IN']['count'] == 3
    edit_name(root, app, 'Reviewed study β')
    app._exclude_file(paths[2]); owner.show_sample(app, sid)
    app.gate_scope_var.set('Current sample'); owner.scope_changed(app)
    app._sel_gate()['x1'] = 70.; app.refresh_plot()
    app._workspace_action_buttons['Save'].invoke(); root.update()
    assert owner.open(str(dest)); root.update()
    assert app._workspace_name_var.get() == 'Reviewed study β'
    assert paths[2] in app.excluded_files
    assert owner.stores['main'].resolve_gate(sid, gid)['x1'] == 70.
    assert app.gate_stats[gid][paths[1]]['stats']['IN']['count'] == 2
    assert json.loads(dest.read_text())['ui_state']['workspace_name'] == 'Reviewed study β'


def test_pending_name_saved_without_enter_and_escape_cancel(experiment, tmp_path, monkeypatch):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    edit_name(root, app, 'Committed')
    edit_name(root, app, 'Cancel me', '<Escape>')
    assert owner.workspace_name() == app._workspace_name_var.get() == 'Committed'
    app._workspace_name_var.set('Typed then Save')
    dest = tmp_path/'Pending.vflow'
    monkeypatch.setattr(filedialog, 'asksaveasfilename', lambda **kw: str(dest))
    app._workspace_action_buttons['Save'].invoke(); root.update()
    assert owner.workspace_name() == 'Typed then Save'
    assert json.loads(dest.read_text())['ui_state']['workspace_name'] == 'Typed then Save'
    assert owner.open(str(dest)); root.update()
    assert app._workspace_name_var.get() == 'Typed then Save'


def test_name_focus_out_blank_and_capture_preservation(experiment, tmp_path):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    app._workspace_name_entry.focus_force(); root.update()
    app._workspace_name_var.set('  Long / study: name α  ')
    app._workspace_tree.focus_force(); root.update()
    assert owner.workspace_name() == 'Long / study: name α'
    assert owner.suggested_filename() == 'Long _ study_ name α.vflow'
    owner.capture(app); owner.autosave()
    assert json.loads(owner.recovery_path.read_text())['ui_state']['workspace_name'] == owner.workspace_name()
    edit_name(root, app, '   ')
    assert owner.workspace_name() == app._workspace_name_var.get() == 'Long / study: name α'
    assert owner.save(path=str(tmp_path/'Named.vflow'))
    app._workspace_name_entry.focus_force(); root.update()
    app._workspace_name_var.set('Still typing')
    owner.mark_dirty(); root.update()
    assert app._workspace_name_var.get() == 'Still typing'
    app._workspace_name_entry.event_generate('<Escape>'); root.update()
    assert app._workspace_name_var.get() == 'Long / study: name α'


def test_save_as_keeps_display_name_and_original_file(experiment, tmp_path, monkeypatch):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    edit_name(root, app, 'Stable name')
    old = tmp_path/'Original.vflow'; new = tmp_path/'Copy.vflow'
    assert owner.save(path=str(old)); before = old.read_bytes()
    monkeypatch.setattr(filedialog, 'asksaveasfilename', lambda **kw: str(new))
    app._workspace_actions_menu.invoke('Save As…'); root.update()
    assert owner.path == str(new) and old.read_bytes() == before
    assert owner.workspace_name() == 'Stable name'
    assert owner.open(str(new)); root.update()
    assert app._workspace_name_var.get() == 'Stable name'
    assert str(new) in owner.recents()
    labels = [app._workspace_recent_menu.entrycget(i, 'label') for i in range(app._workspace_recent_menu.index('end')+1)]
    assert labels[:2] == [str(new), str(old)]
    app._workspace_recent_menu.invoke(1); root.update()
    assert owner.path == str(old) and owner.workspace_name() == 'Stable name'


def test_cancelled_new_open_save_and_failed_open_preserve_workspace(experiment, tmp_path, monkeypatch):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    edit_name(root, app, 'Keep me'); before = set(owner.document.samples)
    monkeypatch.setattr(messagebox, 'askyesnocancel', lambda *a, **kw: None)
    app._workspace_actions_menu.invoke('New'); root.update()
    assert owner.workspace_name() == 'Keep me' and set(owner.document.samples) == before
    monkeypatch.setattr(filedialog, 'asksaveasfilename', lambda **kw: '')
    app._workspace_action_buttons['Save'].invoke()
    assert owner.path is None and owner.dirty
    monkeypatch.setattr(filedialog, 'askopenfilename', lambda **kw: '')
    app._workspace_action_buttons['Open…'].invoke()
    assert set(owner.document.samples) == before
    failures=[]; monkeypatch.setattr(messagebox, 'showerror', lambda *a, **kw: failures.append(a))
    bad=tmp_path/'Bad.vflow'; bad.write_text('{broken')
    monkeypatch.setattr(filedialog, 'askopenfilename', lambda **kw: str(bad))
    app._workspace_action_buttons['Open…'].invoke(); root.update()
    assert failures and set(owner.document.samples) == before and owner.workspace_name() == 'Keep me'


def test_old_workspace_falls_back_to_filename_and_name_syncs_population(experiment, tmp_path):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    dest=tmp_path/'Old study.vflow'; assert owner.save(path=str(dest))
    data=json.loads(dest.read_text()); data['ui_state'].pop('workspace_name', None)
    dest.write_text(json.dumps(data)); assert owner.open(str(dest)); root.update()
    assert app._workspace_name_var.get() == 'Old study'
    new_gate(app); app._open_subgate(50.,50.); root.update()
    child=manager._apps[1]
    edit_name(root, child, 'Shared experiment')
    assert app._workspace_name_var.get() == child._workspace_name_var.get() == 'Shared experiment'
    assert owner.path == str(dest)
    child._workspace_action_buttons['Save'].invoke(); root.update()
    assert owner.open(str(dest)); root.update()
    assert all(a._workspace_name_var.get() == 'Shared experiment' for a in manager._apps)
    assert owner.path == str(dest)


@pytest.mark.parametrize('mode,scale,width,height', [('Compact',1.,1024,768),('Automatic',1.5,1500,960),('Large',2.,2200,1400)])
def test_workspace_controls_reachable_on_scaled_screens(experiment, mode, scale, width, height):
    root, manager, app, paths, errors = experiment
    previous_scale=root.tk.call('tk','scaling')
    try:
        root.tk.call('tk','scaling',(96/72)*scale);root.geometry(f'{width}x{height}')
        app.interface_size_var.set(mode);app._apply_interface_size();app._select_sidebar_task('Data');root.update()
        page=app._task_pages['Data']; page['canvas'].yview_moveto(0);root.update()
        for button in app._workspace_action_buttons.values():
            assert button.winfo_ismapped()
            assert button.winfo_width() >= app._workspace._fonts['VFlowControl'].measure(button.cget('text'))
        assert app._workspace_name_entry.winfo_width() > 50
        assert ttk.Style(root).lookup('TMenubutton','font') == 'VFlowControl'
    finally:
        root.tk.call('tk','scaling',previous_scale)


def test_open_switches_loaded_workspaces_without_quitting_and_save_prompt(experiment, tmp_path, monkeypatch):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    first=tmp_path/'First.vflow';second=tmp_path/'Second.vflow'
    edit_name(root, app, 'First study');assert owner.save(path=str(first))
    edit_name(root, app, 'Second study');app._exclude_file(paths[2]);assert owner.save(True, path=str(second))
    monkeypatch.setattr(filedialog, 'askopenfilename', lambda **kw: str(first))
    app._workspace_action_buttons['Open…'].invoke();root.update()
    assert root.winfo_exists() and root.winfo_ismapped()
    assert owner.path==str(first) and owner.workspace_name()=='First study' and paths[2] in app.loaded_files
    edit_name(root, app, 'First study revised')
    monkeypatch.setattr(filedialog, 'askopenfilename', lambda **kw: str(second))
    monkeypatch.setattr(messagebox, 'askyesnocancel', lambda *a, **kw: None)
    app._workspace_action_buttons['Open…'].invoke();root.update()
    assert owner.path==str(first) and owner.workspace_name()=='First study revised' and owner.dirty
    monkeypatch.setattr(messagebox, 'askyesnocancel', lambda *a, **kw: True)
    app._workspace_action_buttons['Open…'].invoke();root.update()
    assert owner.path==str(second) and owner.workspace_name()=='Second study' and paths[2] in app.excluded_files
    assert json.loads(first.read_text())['ui_state']['workspace_name']=='First study revised'


def test_open_restores_sections_without_false_unsaved_changes(experiment, tmp_path, monkeypatch):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    app._select_sidebar_task('Data');root.update();edit_name(root, app, 'Saved study')
    dest=tmp_path/'Saved.vflow';assert owner.save(path=str(dest))
    assert owner.open(str(dest));root.update()
    assert not owner.dirty and not owner.gates_dirty
    assert app._workspace_save_state_var.get()=='Saved'
    assert not root.title().endswith('*')
    prompts=[]
    monkeypatch.setattr(messagebox, 'askyesnocancel', lambda *a, **kw: prompts.append(a))
    assert owner.confirm_close() and not prompts
    # A real section edit still becomes dirty and is saved normally.
    app._disclose_section('WORKSPACE');root.update()
    assert owner.dirty and app._workspace_save_state_var.get()=='Unsaved changes'
    assert owner.save();assert owner.open(str(dest));root.update()
    assert not owner.dirty and not app._sections['WORKSPACE'][0].get()
