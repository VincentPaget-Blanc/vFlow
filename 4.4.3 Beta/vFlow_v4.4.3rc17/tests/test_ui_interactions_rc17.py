"""Real mouse/keyboard regressions for workspace and analysis interactions."""
import copy
import os
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
import pytest
from matplotlib.backend_bases import MouseEvent
from tests.test_workspace_gui import experiment, new_gate
from tests.test_audit_selection_gui import click
from vflow.legacy.vflow_app import BatchPlotWindow, PolarAnalysisWindow

pytestmark = pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='Native display required')


def row_click(app, sid, column='#0', gap=1000, state=0):
    tree = app._workspace_tree
    tree.see(sid); app.root.update()
    x, y, w, h = tree.bbox(sid, column)
    click(tree, x+max(5,w//2), y+h//2, gap=gap, state=state)


def widgets(widget):
    for child in widget.winfo_children():
        yield child
        yield from widgets(child)


@pytest.mark.parametrize('column', ['#0', '#1'])
def test_rapid_clicks_never_switch_to_cycle(experiment, column):
    root, manager, app, paths, errors = experiment
    owner = app._workspace; sid = owner.sample_id(paths[0])
    initial = app.file_vars[paths[0]].get()
    row_click(app, sid, column)
    row_click(app, sid, column, gap=100)
    assert app.view_mode_var.get() == 'overlay'
    assert app.file_vars[paths[0]].get() == initial
    row_click(app, sid, column, gap=100)
    assert app.view_mode_var.get() == 'overlay'
    if column == '#1': assert app.file_vars[paths[0]].get() != initial


def test_row_selection_is_persistent_and_independent_of_activity(experiment):
    root, manager, app, paths, errors = experiment
    owner = app._workspace; ids = [owner.sample_id(p) for p in paths]
    for sid in ids: row_click(app, sid)
    assert set(app._workspace_tree.selection()) == set(ids)
    row_click(app, ids[1]); assert set(app._workspace_tree.selection()) == {ids[0],ids[2]}
    row_click(app, ids[1], state=0x4)
    row_click(app, ids[0], '#1')
    assert set(app._workspace_tree.selection()) == set(ids)
    assert all(app.file_vars[p].get() for p in paths[1:])
    assert not app.file_vars[paths[0]].get()
    assert app.view_mode_var.get() == 'overlay'


def test_keyboard_and_blank_clicks_do_not_replace_selection(experiment):
    root, manager, app, paths, errors = experiment
    ids = [app._workspace.sample_id(p) for p in paths]; tree = app._workspace_tree
    row_click(app, ids[0]); tree.focus_force(); root.update()
    tree.event_generate('<Down>'); root.update()
    assert tree.focus() == ids[1] and tree.selection() == (ids[0],)
    tree.event_generate('<space>'); root.update()
    assert set(tree.selection()) == set(ids[:2])
    tree.event_generate('<Return>'); root.update()
    assert tree.selection() == (ids[0],)
    click(tree, 15, 4)
    last = tree.bbox(ids[-1]); blank_y = max(tree.winfo_height()-3, last[1]+last[3]+4)
    assert not tree.identify_row(blank_y)
    click(tree, 10, blank_y)
    assert tree.selection() == (ids[0],)
    assert app.view_mode_var.get() == 'overlay'


@pytest.mark.parametrize('operation', ['toggle', 'exclude', 'restore', 'all'])
def test_cycle_keeps_current_sample_when_other_members_change(experiment, operation):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    sid = owner.sample_id(paths[1]); owner.show_sample(app, sid)
    app.x_var.set('U'); app.y_var.set('V'); app.apply_axes()
    if operation == 'toggle': owner.toggle_sample(owner.sample_id(paths[0]), app)
    elif operation == 'exclude': app._exclude_file(paths[0])
    elif operation == 'restore':
        app._exclude_file(paths[0]); app._restore_file(paths[0])
    else:
        owner.toggle_sample(owner.sample_id(paths[0]), app); app._select_all()
    assert owner.current_sid(app) == sid
    assert (app.x_channel, app.y_channel) == ('U','V')
    assert app.view_mode_var.get() == 'cycle'


def test_all_none_preserve_highlights_and_saved_views(experiment, tmp_path):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    ids = [owner.sample_id(p) for p in paths]
    row_click(app, ids[0]); row_click(app, ids[2])
    app._unselect_all(); assert not app._active()
    assert set(app._workspace_tree.selection()) == {ids[0],ids[2]}
    assert app.view_mode_var.get() == 'overlay'
    app._select_all(); assert len(app._active()) == 3
    assert owner.save(path=str(tmp_path/'Selections.vflow'))
    assert owner.open(str(tmp_path/'Selections.vflow')); root.update()
    assert set(app._workspace_tree.selection()) == {ids[0],ids[2]}
    assert app.view_mode_var.get() == 'overlay'


def test_show_sample_remains_an_explicit_action(experiment):
    root, manager, app, paths, errors = experiment; sid = app._workspace.sample_id(paths[1])
    row_click(app, sid); app._sample_show_button.invoke(); root.update()
    assert app.view_mode_var.get() == 'cycle' and app._workspace.current_sid(app) == sid


@pytest.mark.parametrize('mode', ['pan', 'zoom'])
def test_navigation_toolbar_cannot_draw_or_move_gates(experiment, mode):
    root, manager, app, paths, errors = experiment
    gate = new_gate(app); before = app._plain_gate_snapshot(gate)
    app.gate_mode_var.set('draw'); app.gate_type_var.set('rectangle')
    toolbar = app.canvas.toolbar; getattr(toolbar,mode)()
    px, py = app.ax.transData.transform((50,50))
    for button in (1,2,3):
        event = MouseEvent('button_press_event', app.canvas, px, py, button=button)
        app._on_click(event)
        app._on_motion(MouseEvent('motion_notify_event', app.canvas, px+20, py+10, button=button))
    assert len(app.gates) == 1 and app._plain_gate_snapshot(app.gates[0]) == before
    assert not app.moving_gate and app._handle_drag is None and app._gate_move is None
    getattr(toolbar,mode)()


def test_middle_click_does_not_draw_and_right_double_does_not_open_tab(experiment):
    root, manager, app, paths, errors = experiment; new_gate(app)
    px, py = app.ax.transData.transform((50,50)); before = len(app.gates)
    app.gate_mode_var.set('draw'); app.gate_type_var.set('rectangle')
    app._on_click(MouseEvent('button_press_event',app.canvas,px,py,button=2))
    assert len(app.gates) == before and not app.moving_gate
    app.gate_mode_var.set('none')
    app._on_click(MouseEvent('button_press_event',app.canvas,px,py,button=3,dblclick=True))
    app._on_release(MouseEvent('button_release_event',app.canvas,px,py,button=3))
    assert len(manager._apps) == 1


def test_workspace_shortcuts_do_not_run_from_dialogs_or_text_undo(experiment, monkeypatch):
    root, manager, app, paths, errors = experiment; owner = app._workspace; new_gate(app)
    calls=[]
    monkeypatch.setattr(owner,'gate_action',lambda *a,**k:calls.append(a))
    dialog=tk.Toplevel(root); entry=ttk.Entry(dialog);entry.pack();root.update()
    entry.focus_force();root.update();entry.event_generate('<Control-z>');root.update()
    assert calls == []
    dialog.destroy();app._workspace_name_entry.focus_force();root.update()
    app._workspace_name_entry.event_generate('<Control-z>');root.update(); assert calls == []
    app._workspace_tree.focus_force();root.update()
    app._workspace_tree.event_generate('<Control-z>');root.update();assert len(calls) == 1


@pytest.mark.parametrize('invalid', ['nan', 'inf', '-1', '0', '99', ''])
def test_invalid_gate_width_cannot_poison_plot(experiment, invalid):
    root, manager, app, paths, errors = experiment; gate = new_gate(app)
    app._select_sidebar_task('Gates'); root.update()
    spin=next(w for w in widgets(app.gate_manager_frame) if isinstance(w,ttk.Spinbox))
    before=gate['linewidth'];spin.set(invalid);root.update()
    assert app._sel_gate()['linewidth'] == before
    spin.focus_force();root.update();spin.event_generate('<Return>');root.update()
    assert float(spin.get()) == before
    app.refresh_plot();root.update()


@pytest.mark.parametrize('window_type', [BatchPlotWindow, PolarAnalysisWindow])
def test_secondary_windows_honor_active_samples_and_keep_local_choices(experiment, window_type):
    root, manager, app, paths, errors = experiment
    app._workspace.toggle_sample(app._workspace.sample_id(paths[0]),app)
    window=window_type(root,app.T,app);root.update()
    try:
        assert paths[0] not in window._file_vars or not window._file_vars[paths[0]].get()
        window._file_vars[paths[1]].set(False);window._build_file_list();root.update()
        assert not window._file_vars[paths[1]].get()
        assert app.file_vars[paths[1]].get()
    finally:window._on_close()


def test_context_menu_blank_area_preserves_selection(experiment):
    root, manager, app, paths, errors = experiment; tree=app._workspace_tree
    sid=app._workspace.sample_id(paths[0]);row_click(app,sid)
    event=SimpleNamespace(x=15,y=4,x_root=15,y_root=4)
    assert app._workspace.sample_menu(app,event) == 'break'
    assert tree.selection() == (sid,)


def test_empty_cycle_does_not_overwrite_overlay_axes(experiment):
    root, manager, app, paths, errors = experiment; owner=app._workspace
    owner.show_sample(app,owner.sample_id(paths[1]))
    app.x_var.set('U');app.y_var.set('V');app.apply_axes()
    app._unselect_all();app._select_all()
    app.view_mode_var.set('overlay');app._on_view_mode_change();root.update()
    assert (app.x_channel,app.y_channel)==('X','Y')


@pytest.mark.parametrize('gesture', ['click', 'escape'])
def test_tooltip_dismissal_precedes_handlers_that_stop_events(experiment, gesture):
    from vflow.ui.tooltips import tooltip
    root,manager,app,paths,errors=experiment
    top=tk.Toplevel(root);widget=ttk.Treeview(top);widget.pack();tooltip(widget,'Keyboard help')
    widget.bind('<Button-1>',lambda e:(widget.focus_set(),'break')[1])
    widget.bind('<Escape>',lambda e:'break');root.update()
    widget.focus_force();root.update()
    widget.event_generate('<FocusIn>');root.after(480,root.quit);root.mainloop()
    assert widget._vflow_tooltip['window'] is not None
    if gesture=='click':click(widget,10,25)
    else:widget.event_generate('<Escape>');root.update()
    assert widget._vflow_tooltip['window'] is None and widget._vflow_tooltip['timer'] is None
    root.after(480,root.quit);root.mainloop()
    assert widget._vflow_tooltip['window'] is None
    top.destroy()


def test_mouse_focus_does_not_schedule_obstructing_tooltip_and_destroy_cleans_tag(experiment):
    from vflow.ui.tooltips import tooltip
    root,manager,app,paths,errors=experiment
    top=tk.Toplevel(root);widget=ttk.Treeview(top);widget.pack();tooltip(widget,'Help')
    widget.bind('<Button-1>',lambda e:(widget.focus_set(),'break')[1]);root.update()
    tag=widget.bindtags()[0];assert tag.startswith('VFlowTooltipInput')
    click(widget,10,25);widget.event_generate('<FocusIn>');root.update()
    assert widget._vflow_tooltip['timer'] is None
    root.after(480,root.quit);root.mainloop()
    assert widget._vflow_tooltip['window'] is None
    top.destroy();root.update();assert not root.bind_class(tag,'<ButtonPress>')
