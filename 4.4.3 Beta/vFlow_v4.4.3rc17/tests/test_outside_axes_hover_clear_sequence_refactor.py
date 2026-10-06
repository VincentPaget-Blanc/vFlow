import inspect

import pytest

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.legacy.vflow_app import FlowApp
from vflow.ui.gate_interaction import run_outside_axes_hover_clear_sequence


def _callbacks(*, fail=None, swallowed_cursor_failure=False):
    log = []

    def step(name):
        def call():
            log.append(name)
            if fail == name:
                raise RuntimeError(f"{name}-fail")
        return call

    def reset_cursor():
        log.append("cursor")
        if fail == "cursor" and not swallowed_cursor_failure:
            raise RuntimeError("cursor-fail")
        # The real controller callback owns the legacy broad try/except and
        # therefore swallows widget/configuration failures before returning.

    callbacks = {
        "clear_hover_gate_id": step("hover"),
        "clear_hover_handle_key": step("handle"),
        "clear_interior_hover_gate_id": step("interior"),
        "reset_cursor": reset_cursor,
        "preview_gate": step("preview"),
        "schedule_draw": step("draw"),
    }
    return log, callbacks


def test_outside_axes_hover_clear_sequence_preserves_full_callback_order():
    log, callbacks = _callbacks()
    assert run_outside_axes_hover_clear_sequence(**callbacks) is None
    assert log == ["hover", "handle", "interior", "cursor", "preview", "draw"]


@pytest.mark.parametrize(
    "fail,expected",
    [
        ("hover", ["hover"]),
        ("handle", ["hover", "handle"]),
        ("interior", ["hover", "handle", "interior"]),
        ("preview", ["hover", "handle", "interior", "cursor", "preview"]),
        ("draw", ["hover", "handle", "interior", "cursor", "preview", "draw"]),
    ],
)
def test_outside_axes_hover_clear_sequence_preserves_unswallowed_failure_cutoffs(fail, expected):
    log, callbacks = _callbacks(fail=fail)
    with pytest.raises(RuntimeError, match=rf"^{fail}-fail$"):
        run_outside_axes_hover_clear_sequence(**callbacks)
    assert log == expected


def test_flowapp_retains_outside_axes_condition_cursor_policy_state_preview_canvas_and_return():
    source = inspect.getsource(GateInteractionController.on_motion)
    start = source.index("elif should_clear_hover_outside_axes(")
    end = source.index("\n        if event.inaxes != host.ax:", start)
    branch = source[start:end]

    assert "hover_gate_id=host._hover_gate_id" in branch
    assert "interior_hover_gate_id=host._interior_hover_gate_id" in branch
    assert "resolve_hover_handle_key=lambda: host._hover_handle_key" in branch
    assert "def _reset_outside_axes_hover_cursor():" in branch
    assert "host.canvas.get_tk_widget().config(cursor='')" in branch
    assert "except Exception:" in branch
    assert "pass" in branch
    assert "run_outside_axes_hover_clear_sequence(" in branch
    assert "clear_hover_gate_id=lambda: setattr(host, '_hover_gate_id', None)" in branch
    assert "clear_hover_handle_key=lambda: setattr(host, '_hover_handle_key', None)" in branch
    assert "clear_interior_hover_gate_id=lambda: setattr(host, '_interior_hover_gate_id', None)" in branch
    assert "reset_cursor=_reset_outside_axes_hover_cursor" in branch
    assert "preview_gate=lambda: host._preview_gate()" in branch
    assert "schedule_draw=lambda: host.canvas.draw_idle()" in branch
    assert branch.rstrip().endswith("return")


def test_headless_outside_axes_hover_clear_sequence_does_not_absorb_controller_or_ui_authority():
    source = inspect.getsource(run_outside_axes_hover_clear_sequence)
    forbidden = [
        "self.", "event.", "should_clear_hover_outside_axes", "get_tk_widget",
        "self._hover_gate_id", "self._hover_handle_key", "self._interior_hover_gate_id",
        "_preview_gate", "canvas.draw_idle", "matplotlib", "tkinter",
    ]
    for token in forbidden:
        assert token not in source
