from pathlib import Path

import pytest

from vflow.ui.gate_interaction import invoke_hover_cursor_policy


def test_helper_forwards_captured_inputs_with_historical_keyword_mapping():
    seen = []
    sentinel = object()

    def planner(**kwargs):
        seen.append(kwargs)
        return sentinel

    result = invoke_hover_cursor_policy(
        planner=planner,
        new_hover=7,
        pinned_gate_id=3,
        new_interior=9,
    )

    assert result is sentinel
    assert seen == [{
        'new_hover': 7,
        'pinned_gate_id': 3,
        'new_interior': 9,
    }]


def test_planner_failure_propagates_unchanged():
    def planner(**kwargs):
        raise RuntimeError('planner-fail')

    with pytest.raises(RuntimeError, match='planner-fail'):
        invoke_hover_cursor_policy(
            planner=planner,
            new_hover=None,
            pinned_gate_id=None,
            new_interior=None,
        )


def test_helper_does_not_normalize_falsey_or_custom_values():
    seen = {}

    def planner(**kwargs):
        seen.update(kwargs)
        return kwargs

    result = invoke_hover_cursor_policy(
        planner=planner,
        new_hover=0,
        pinned_gate_id=False,
        new_interior='',
    )

    assert result == seen
    assert seen == {
        'new_hover': 0,
        'pinned_gate_id': False,
        'new_interior': '',
    }


def test_controller_keeps_planner_and_all_concrete_input_acquisition_inside_try():
    source = Path('vflow/controllers/gate_interaction_controller.py').read_text()
    start = source.index('                # Update Tk cursor')
    end = source.index('\n                # Redraw whenever any hover state changed', start)
    block = source[start:end]

    assert 'try:' in block
    assert 'cursor_policy = invoke_hover_cursor_policy(' in block
    assert 'planner=plan_hover_cursor_policy' in block
    assert 'new_hover=new_hover' in block
    assert 'pinned_gate_id=host._pinned_gate_id' in block
    assert 'new_interior=new_interior' in block
    assert 'run_hover_cursor_application_sequence(' in block
    assert 'except Exception:' in block
    assert 'pass' in block


def test_controller_source_pins_planner_capture_and_argument_evaluation_order():
    source = Path('vflow/controllers/gate_interaction_controller.py').read_text()
    start = source.index('cursor_policy = invoke_hover_cursor_policy(')
    end = source.index('\n                    run_hover_cursor_application_sequence(', start)
    block = source[start:end]

    positions = [
        block.index('planner=plan_hover_cursor_policy'),
        block.index('new_hover=new_hover'),
        block.index('pinned_gate_id=host._pinned_gate_id'),
        block.index('new_interior=new_interior'),
    ]
    assert positions == sorted(positions)


def test_planner_is_captured_before_pinned_gate_access():
    source = Path('vflow/controllers/gate_interaction_controller.py').read_text()
    start = source.index('cursor_policy = invoke_hover_cursor_policy(')
    end = source.index('\n                    run_hover_cursor_application_sequence(', start)
    block = source[start:end]
    assert block.index('planner=plan_hover_cursor_policy') < block.index('host._pinned_gate_id')


def test_policy_invocation_remains_before_cursor_application_and_hover_presentation():
    source = Path('vflow/controllers/gate_interaction_controller.py').read_text()
    invoke = source.index('cursor_policy = invoke_hover_cursor_policy(')
    apply = source.index('run_hover_cursor_application_sequence(', invoke)
    presentation = source.index('hover_plan = plan_hover_presentation(', apply)
    assert invoke < apply < presentation


def test_helper_has_no_controller_event_tk_or_exception_policy_authority():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    start = source.index('def invoke_hover_cursor_policy(')
    end = source.index('\n\ndef run_hover_cursor_application_sequence', start)
    helper = source[start:end]

    forbidden = [
        'self.',
        'event.',
        '_pinned_gate_id',
        '_cursor_for_hover',
        'get_tk_widget',
        'canvas.',
        'except Exception',
        'plan_hover_presentation',
    ]
    for token in forbidden:
        assert token not in helper


def test_helper_does_not_own_cursor_policy_implementation():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    start = source.index('def invoke_hover_cursor_policy(')
    end = source.index('\n\ndef run_hover_cursor_application_sequence', start)
    helper = source[start:end]
    assert 'if new_hover or pinned_gate_id' not in helper
    assert 'new_interior is not None' not in helper
    assert 'planner(' in helper


def test_cursor_policy_implementation_itself_remains_in_headless_service():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    assert 'def plan_hover_cursor_policy(' in source
    assert 'if new_hover is not None or pinned_gate_id is not None:' in source
    assert 'if new_interior is not None:' in source
