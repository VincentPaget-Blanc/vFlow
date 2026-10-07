"""Regression coverage for consolidated controls and selected-gate ownership."""
import copy
import os
import tkinter as tk
from tkinter import ttk
import pytest
from tests.test_workspace_gui import experiment, new_gate
from tests.test_ui_interactions_rc17 import widgets, row_click

pytestmark = pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='Native display required')

def test_editor_styles_only_selected_gate_and_survives_delete_undo(experiment):
    root, manager, app, paths, errors = experiment
    first = new_gate(app); second = new_gate(app)
    app._select_sidebar_task('Gates'); root.update()
    assert not any(isinstance(w, ttk.Spinbox) for w in widgets(app.gate_manager_frame))
    app._select_gate(first['id']); root.update()
    width = next(w for w in widgets(app.thresh_panel) if isinstance(w, ttk.Spinbox))
    width.set('2.5'); root.update()
    assert app._sel_gate()['linewidth'] == 2.5
    assert next(g for g in app.gates if g['id'] == second['id'])['linewidth'] == .5
    app._select_gate(second['id']); root.update()
    assert not width.winfo_exists()
    style = next(w for w in widgets(app.thresh_panel) if isinstance(w, ttk.Combobox))
    style.set('- - Dashed'); root.update()
    assert app._sel_gate()['linestyle'] == '--'
    assert next(g for g in app.gates if g['id'] == first['id'])['linestyle'] == '-'
    before = copy.deepcopy(app.gate_stats)
    delete = next(w for w in widgets(app.thresh_panel) if isinstance(w, ttk.Button) and w.cget('text') == 'Delete gate')
    delete.invoke(); root.update()
    assert app._sel_gate_id == first['id'] and len(app.gates) == 1
    app._workspace.gate_action(app, 'undo', first['id']); root.update()
    assert len(app.gates) == 2 and app.gate_stats == before

def test_conditional_sample_and_cycle_controls_restore(experiment, tmp_path):
    root, manager, app, paths, errors = experiment
    owner = app._workspace; sid = owner.sample_id(paths[0])
    row_click(app, sid); root.update()
    assert app._sample_exclude_button.winfo_ismapped()
    assert not app._sample_restore_button.winfo_ismapped()
    app._sample_exclude_button.invoke(); root.update()
    row_click(app, sid) if sid not in app._workspace_tree.selection() else None
    assert app._sample_restore_button.winfo_ismapped()
    assert not app._sample_exclude_button.winfo_ismapped()
    app._sample_restore_button.invoke(); root.update()
    assert app._sample_exclude_button.winfo_ismapped()
    assert not app._btn_prev.winfo_ismapped()
    app._sample_show_button.invoke(); root.update()
    assert app._btn_prev.winfo_ismapped() and owner.current_sid(app) == sid
    dest = tmp_path/'clean.vflow'; assert owner.save(path=str(dest))
    app.view_mode_var.set('overlay'); app._on_view_mode_change(); root.update()
    assert not app._btn_next.winfo_ismapped()
    assert owner.open(str(dest)); root.update()
    assert app._btn_next.winfo_ismapped() and owner.current_sid(app) == sid
    assert not app._btn_next.instate(['disabled'])

def test_consolidated_controls_keep_commands_and_keyboard_gate_selection(experiment):
    root, manager, app, paths, errors = experiment
    app._select_sidebar_task('Data'); root.update()
    assert set(app._workspace_action_buttons) == {'Open…', 'Save'}
    menu = app._workspace_actions_menu
    labels = [menu.entrycget(i, 'label') for i in range(menu.index('end')+1)]
    assert labels == ['New', 'Save As…', 'Close', 'Open Recent…']
    assert not any(isinstance(w, ttk.Button) and w.cget('text') == 'Selected sample actions…' for w in widgets(app._side_outer))
    assert not app.excluded_list_frame.winfo_ismapped()
    first = new_gate(app); second = new_gate(app)
    app._select_sidebar_task('Gates'); root.update()
    label = next(w for w in widgets(app.gate_manager_frame) if isinstance(w, ttk.Label) and first['name'] in str(w.cget('text')))
    label.focus_force(); root.update(); label.event_generate('<Return>'); root.update()
    assert app._sel_gate_id == first['id']
    assert root.focus_get() is app._gate_name_widgets[first['id']]
    assert not app._sections['GATING'][1]._section_header.winfo_ismapped()
    assert app._sections['GATING'][1].winfo_ismapped()
