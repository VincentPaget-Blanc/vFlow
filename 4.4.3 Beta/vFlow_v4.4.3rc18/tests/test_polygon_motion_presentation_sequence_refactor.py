import inspect

import pytest

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.legacy.vflow_app import FlowApp
from vflow.services.gate_geometry_interaction import (
    run_polygon_motion_presentation_sequence,
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
        "render_frame": step("render"),
    }
    return log, callbacks


def test_polygon_motion_presentation_preserves_success_order_and_time_identity():
    token = object()
    log, callbacks = _callbacks(redraw_time=token)
    assert run_polygon_motion_presentation_sequence(**callbacks) is True
    assert log == [
        ("resolve",),
        ("commit", token),
        ("preview",),
        ("render",),
    ]


def test_polygon_motion_presentation_throttle_stops_before_all_side_effects():
    log, callbacks = _callbacks(redraw_time=None)
    assert run_polygon_motion_presentation_sequence(**callbacks) is False
    assert log == [("resolve",)]


@pytest.mark.parametrize(
    "fail,expected",
    [
        ("resolve", ["resolve"]),
        ("commit", ["resolve", "commit"]),
        ("preview", ["resolve", "commit", "preview"]),
        ("render", ["resolve", "commit", "preview", "render"]),
    ],
)
def test_polygon_motion_presentation_callback_failures_preserve_cutoff(fail, expected):
    log, callbacks = _callbacks(fail=fail)
    with pytest.raises(RuntimeError, match=rf"^{fail}-fail$"):
        run_polygon_motion_presentation_sequence(**callbacks)
    assert [entry[0] for entry in log] == expected


def test_flowapp_retains_polygon_cursor_clock_throttle_preview_and_render_authority():
    source = inspect.getsource(GateInteractionController.on_motion)
    start = source.index("if gt == 'polygon' and host._poly_active and mode == 'draw':")
    end = source.index("# ── Hover detection", start)
    branch = source[start:end]
    assert "run_polygon_motion_presentation_sequence" in branch
    assert "event.xdata is not None and event.ydata is not None" in branch
    assert "host._poly_cursor = (event.xdata, event.ydata)" in branch
    assert "time.monotonic()" in branch
    assert "now - host._drag_last_draw < 0.016" in branch
    assert "host._drag_last_draw = now" in branch
    assert "host._preview_gate(skip_cache=True)" in branch
    assert "host._blit_render()" in branch
    assert branch.index("host._poly_cursor = (event.xdata, event.ydata)") < branch.index(
        "run_polygon_motion_presentation_sequence"
    )


def test_headless_polygon_helper_does_not_absorb_concrete_motion_authority():
    source = inspect.getsource(run_polygon_motion_presentation_sequence)
    forbidden = [
        "self.", "time.monotonic", "_drag_last_draw", "_poly_cursor",
        "event.", "xdata", "ydata", "_preview_gate", "_blit_render",
    ]
    for token in forbidden:
        assert token not in source
