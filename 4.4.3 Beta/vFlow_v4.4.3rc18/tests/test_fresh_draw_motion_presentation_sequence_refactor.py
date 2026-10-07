import inspect

import pytest

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.legacy.vflow_app import FlowApp
from vflow.services.gate_geometry_interaction import (
    run_fresh_draw_motion_presentation_sequence,
)


def _callbacks(*, redraw_time=12.5, fail=None):
    log = []

    def step(name, result=None):
        def call(*args):
            log.append((name, *args))
            if fail == name:
                raise RuntimeError(f"{name}-fail")
            return result
        return call

    callbacks = {
        "resolve_redraw_time": step("resolve", redraw_time),
        "commit_redraw_time": step("commit"),
        "preview_gate": step("preview"),
        "restore_frozen_axes": step("restore"),
        "render_frame": step("render"),
    }
    return log, callbacks


def test_fresh_draw_motion_presentation_preserves_success_order_and_time_identity():
    token = object()
    log, callbacks = _callbacks(redraw_time=token)
    assert run_fresh_draw_motion_presentation_sequence(**callbacks) is True
    assert log == [
        ("resolve",),
        ("commit", token),
        ("preview",),
        ("restore",),
        ("render",),
    ]


def test_fresh_draw_motion_presentation_throttle_stops_before_all_side_effects():
    log, callbacks = _callbacks(redraw_time=None)
    assert run_fresh_draw_motion_presentation_sequence(**callbacks) is False
    assert log == [("resolve",)]


@pytest.mark.parametrize(
    "fail,expected",
    [
        ("resolve", ["resolve"]),
        ("commit", ["resolve", "commit"]),
        ("preview", ["resolve", "commit", "preview"]),
        ("restore", ["resolve", "commit", "preview", "restore"]),
        ("render", ["resolve", "commit", "preview", "restore", "render"]),
    ],
)
def test_fresh_draw_motion_presentation_callback_failures_preserve_cutoff(fail, expected):
    log, callbacks = _callbacks(fail=fail)
    with pytest.raises(RuntimeError, match=rf"^{fail}-fail$"):
        run_fresh_draw_motion_presentation_sequence(**callbacks)
    assert [entry[0] for entry in log] == expected


def test_flowapp_retains_fresh_draw_guard_geometry_clock_axis_and_render_authority():
    source = inspect.getsource(GateInteractionController.on_motion)
    start = source.index("if event.inaxes != host.ax:")
    branch = source[start:]
    assert "run_fresh_draw_motion_presentation_sequence" in branch
    assert "x, y = event.xdata, event.ydata" in branch
    assert "if not host.moving_gate:" in branch
    assert "gate = host._draw_gate_obj()" in branch
    assert "if not gate:" in branch
    assert "for key, value in iter_gate_draw_assignments(gate, x, y):" in branch
    assert "gate[key] = value" in branch
    assert "time.monotonic()" in branch
    assert "now - host._drag_last_draw < 0.016" in branch
    assert "host._drag_last_draw = now" in branch
    assert "host._preview_gate(skip_cache=True)" in branch
    assert "if host._draw_frozen_xlim is not None:" in branch
    assert "host.ax.set_xlim(host._draw_frozen_xlim)" in branch
    assert "host.ax.set_ylim(host._draw_frozen_ylim)" in branch
    assert "host._blit_render()" in branch
    assert branch.index("gate[key] = value") < branch.index(
        "run_fresh_draw_motion_presentation_sequence"
    )


def test_headless_fresh_draw_helper_does_not_absorb_concrete_motion_authority():
    source = inspect.getsource(run_fresh_draw_motion_presentation_sequence)
    forbidden = [
        "self.", "event.", "xdata", "ydata", "moving_gate", "_draw_gate_obj",
        "iter_gate_draw_assignments", "gate[", "time.monotonic", "_drag_last_draw",
        "_preview_gate", "_draw_frozen_xlim", "_draw_frozen_ylim", "set_xlim",
        "set_ylim", "_blit_render",
    ]
    for token in forbidden:
        assert token not in source
