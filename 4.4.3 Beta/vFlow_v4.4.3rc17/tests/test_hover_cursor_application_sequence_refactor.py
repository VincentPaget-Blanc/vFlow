import inspect

import pytest

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.legacy.vflow_app import FlowApp
from vflow.ui.gate_interaction import run_hover_cursor_application_sequence


def test_hover_cursor_application_sequence_resolves_hover_lazily_then_applies():
    log = []

    def resolve():
        log.append("resolve")
        return "sb_h_double_arrow"

    def apply(cursor):
        log.append(("apply", cursor))

    assert run_hover_cursor_application_sequence(
        cursor_policy="hover",
        resolve_hover_cursor=resolve,
        apply_cursor=apply,
    ) is None
    assert log == ["resolve", ("apply", "sb_h_double_arrow")]


@pytest.mark.parametrize("policy", ["", "fleur", "crosshair", None, 0, False])
def test_hover_cursor_application_sequence_non_hover_policy_skips_resolver(policy):
    log = []

    def resolve():
        raise AssertionError("resolver must stay lazy for non-hover policy")

    def apply(cursor):
        log.append(cursor)

    run_hover_cursor_application_sequence(
        cursor_policy=policy,
        resolve_hover_cursor=resolve,
        apply_cursor=apply,
    )
    assert log == [policy]


def test_hover_cursor_application_sequence_resolver_failure_preserves_cutoff():
    log = []

    def resolve():
        log.append("resolve")
        raise RuntimeError("resolve-fail")

    def apply(cursor):
        log.append(("apply", cursor))

    with pytest.raises(RuntimeError, match="^resolve-fail$"):
        run_hover_cursor_application_sequence(
            cursor_policy="hover",
            resolve_hover_cursor=resolve,
            apply_cursor=apply,
        )
    assert log == ["resolve"]


def test_hover_cursor_application_sequence_apply_failure_occurs_after_resolution():
    log = []

    def resolve():
        log.append("resolve")
        return "cursor-x"

    def apply(cursor):
        log.append(("apply", cursor))
        raise RuntimeError("apply-fail")

    with pytest.raises(RuntimeError, match="^apply-fail$"):
        run_hover_cursor_application_sequence(
            cursor_policy="hover",
            resolve_hover_cursor=resolve,
            apply_cursor=apply,
        )
    assert log == ["resolve", ("apply", "cursor-x")]


def test_hover_cursor_application_sequence_preserves_policy_equality_truth_semantics():
    log = []

    class Truth:
        def __bool__(self):
            log.append("truth")
            return True

    class Policy:
        def __eq__(self, other):
            log.append(("eq", other))
            return Truth()

    def resolve():
        log.append("resolve")
        return "resolved"

    def apply(cursor):
        log.append(("apply", cursor))

    run_hover_cursor_application_sequence(
        cursor_policy=Policy(),
        resolve_hover_cursor=resolve,
        apply_cursor=apply,
    )
    assert log == [
        ("eq", "hover"),
        "truth",
        "resolve",
        ("apply", "resolved"),
    ]


def test_flowapp_retains_cursor_policy_resolution_tk_exception_and_ordering_authority():
    source = inspect.getsource(GateInteractionController.on_motion)
    cursor_start = source.index("# Update Tk cursor")
    hover_start = source.index("hover_plan = plan_hover_presentation(")
    branch = source[cursor_start:hover_start]

    assert "try:" in branch
    assert "cursor_policy = invoke_hover_cursor_policy(" in branch
    assert "planner=plan_hover_cursor_policy" in branch
    assert "new_hover=new_hover" in branch
    assert "pinned_gate_id=host._pinned_gate_id" in branch
    assert "new_interior=new_interior" in branch
    assert "run_hover_cursor_application_sequence(" in branch
    assert "cursor_policy=cursor_policy" in branch
    assert "resolve_hover_cursor=lambda: host._cursor_for_hover(event)" in branch
    assert "apply_cursor=lambda cursor: host.canvas.get_tk_widget().config(cursor=cursor)" in branch
    assert "except Exception:" in branch
    assert "pass" in branch
    assert source.index("run_hover_cursor_application_sequence(", cursor_start) < hover_start


def test_headless_hover_cursor_application_sequence_does_not_absorb_controller_or_ui_authority():
    source = inspect.getsource(run_hover_cursor_application_sequence)
    forbidden = [
        "self.",
        "event.",
        "_cursor_for_hover",
        "get_tk_widget",
        "canvas.",
        "tkinter",
        "matplotlib",
        "plan_hover_presentation",
        "_hover_gate_id",
        "_hover_handle_key",
        "_interior_hover_gate_id",
    ]
    for token in forbidden:
        assert token not in source
