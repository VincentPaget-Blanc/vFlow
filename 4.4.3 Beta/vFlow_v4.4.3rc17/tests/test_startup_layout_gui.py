"""Startup layout must settle without recursively pumping the Tk event loop."""
import os
import tkinter as tk
import pytest
from tests.test_workspace_gui import experiment

pytestmark = pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='Native Tk display required')


def test_layout_does_not_pump_nested_idle_events(experiment, monkeypatch):
    root, manager, app, paths, errors = experiment
    def nested_pump():
        raise AssertionError('Layout recursively pumped idle events')
    monkeypatch.setattr(app._task_notebook, 'update_idletasks', nested_pump)
    monkeypatch.setattr(app._sample_task_pane, 'update_idletasks', nested_pump)
    root.geometry('1280x800')
    app._sample_pane_configured()
    root.update()
    assert app._sample_layout_pending is None
    assert not app._sample_layout_busy
    assert app._sample_show_button.winfo_ismapped()


def test_reentrant_request_is_deferred_without_changing_current_pass(experiment):
    root, manager, app, paths, errors = experiment
    app._sample_layout_busy = True
    try:
        app._layout_adaptive_samples()
        assert app._sample_layout_busy
        assert app._sample_layout_again
    finally:
        app._sample_layout_busy = False
    app._sample_pane_configured()
    root.update()
    assert app._sample_layout_pending is None


def test_unchanged_geometry_does_not_sustain_configure_feedback(experiment, monkeypatch):
    root, manager, app, paths, errors = experiment
    root.update()
    writes = []
    canvas = app._sidebar_outer_canvas
    original = canvas.itemconfigure
    def configure(*args, **kwargs):
        writes.append(kwargs)
        # A window system can notify again when virtual geometry is requested.
        app._sample_pane_configured()
        return original(*args, **kwargs)
    monkeypatch.setattr(canvas, 'itemconfigure', configure)
    for _ in range(8):
        app._layout_adaptive_samples()
    root.update()
    assert writes == []
    assert app._sample_layout_pending is None


def test_font_and_window_changes_keep_timer_and_layout_responsive(experiment):
    root, manager, app, paths, errors = experiment
    ticks = []
    root.after(0, lambda: ticks.append('alive'))
    for width, height, mode in [(1024, 640, 'Large'), (1440, 900, 'Compact'), (1280, 800, 'Automatic')]:
        root.geometry(f'{width}x{height}')
        app.interface_size_var.set(mode)
        app._apply_interface_size()
    root.update()
    assert ticks == ['alive']
    assert app._sample_layout_pending is None
    app._select_sidebar_task('Gates')
    root.update()
    assert app._task_notebook.winfo_ismapped()
    assert not app._sample_layout_busy
