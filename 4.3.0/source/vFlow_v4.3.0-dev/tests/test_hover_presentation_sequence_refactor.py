import inspect

import pytest

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.legacy.vflow_app import FlowApp
from vflow.ui.gate_interaction import (
    HoverPresentationPlan,
    run_hover_presentation_sequence,
)


def _callbacks(*, changed=True, fail=None):
    log = []
    plan = HoverPresentationPlan(
        hover_gate_id=7,
        hover_handle_key=(7, "corner", 2),
        interior_hover_gate_id=9,
        changed=changed,
    )

    def step(name):
        def call(*args):
            log.append((name, *args))
            if fail == name:
                raise RuntimeError(f"{name}-fail")
        return call

    callbacks = {
        "plan": plan,
        "commit_hover_gate_id": step("hover"),
        "commit_hover_handle_key": step("handle"),
        "commit_interior_hover_gate_id": step("interior"),
        "preview_gate": step("preview"),
        "schedule_draw": step("draw"),
    }
    return log, callbacks


def test_hover_presentation_sequence_preserves_commit_then_redraw_order():
    log, callbacks = _callbacks(changed=True)
    assert run_hover_presentation_sequence(**callbacks) is True
    assert log == [
        ("hover", 7),
        ("handle", (7, "corner", 2)),
        ("interior", 9),
        ("preview",),
        ("draw",),
    ]


def test_hover_presentation_sequence_unchanged_commits_state_without_redraw():
    log, callbacks = _callbacks(changed=False)
    assert run_hover_presentation_sequence(**callbacks) is False
    assert log == [
        ("hover", 7),
        ("handle", (7, "corner", 2)),
        ("interior", 9),
    ]


@pytest.mark.parametrize(
    "fail,expected",
    [
        ("hover", ["hover"]),
        ("handle", ["hover", "handle"]),
        ("interior", ["hover", "handle", "interior"]),
        ("preview", ["hover", "handle", "interior", "preview"]),
        ("draw", ["hover", "handle", "interior", "preview", "draw"]),
    ],
)
def test_hover_presentation_sequence_callback_failures_preserve_cutoff(fail, expected):
    log, callbacks = _callbacks(changed=True, fail=fail)
    with pytest.raises(RuntimeError, match=rf"^{fail}-fail$"):
        run_hover_presentation_sequence(**callbacks)
    assert [entry[0] for entry in log] == expected


def test_flowapp_retains_hover_hit_cursor_state_preview_and_canvas_authority():
    source = inspect.getsource(GateInteractionController.on_motion)
    hover_start = source.index("hover_plan = plan_hover_presentation(")
    outside_start = source.index("elif should_clear_hover_outside_axes(")
    branch = source[hover_start:outside_start]

    assert "run_hover_presentation_sequence" in branch
    assert "commit_hover_gate_id=lambda value: setattr(host, '_hover_gate_id', value)" in branch
    assert "commit_hover_handle_key=lambda value: setattr(host, '_hover_handle_key', value)" in branch
    assert "commit_interior_hover_gate_id=lambda value: setattr(host, '_interior_hover_gate_id', value)" in branch
    assert "preview_gate=lambda: host._preview_gate()" in branch
    assert "schedule_draw=lambda: host.canvas.draw_idle()" in branch
    assert "if hover_redraw:" in branch
    assert "return" in branch

    # Cursor application remains before hover-state planning/commit.
    cursor_index = source.index("host.canvas.get_tk_widget().config(cursor=cursor)")
    assert cursor_index < hover_start


def test_headless_hover_sequence_does_not_absorb_hit_testing_cursor_or_controller_state():
    source = inspect.getsource(run_hover_presentation_sequence)
    forbidden = [
        "self.", "event.", "_hit_test", "_cursor_for_hover", "get_tk_widget",
        "self._hover_gate_id", "self._hover_handle_key", "self._interior_hover_gate_id",
        "_preview_gate", "canvas.draw_idle", "matplotlib", "tkinter",
    ]
    for token in forbidden:
        assert token not in source
