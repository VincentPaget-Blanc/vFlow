from pathlib import Path

import pytest

from vflow.ui.gate_interaction import invoke_hover_hit_test_plan


def test_helper_forwards_captured_inputs_with_historical_keyword_mapping():
    seen = []
    sentinel = object()

    def planner(**kwargs):
        seen.append(kwargs)
        return sentinel

    result = invoke_hover_hit_test_plan(
        planner=planner,
        handle_gate_id=7,
        hover_handle_key=('edge', 'left'),
        current_hover_gate_id=3,
        current_pos=(10, 20),
        last_line_test_pos=(1, 2),
        min_delta=10,
    )

    assert result is sentinel
    assert seen == [{
        'handle_gate_id': 7,
        'hover_handle_key': ('edge', 'left'),
        'current_hover_gate_id': 3,
        'current_pos': (10, 20),
        'last_line_test_pos': (1, 2),
        'min_delta': 10,
    }]


def test_planner_failure_propagates_unchanged():
    def planner(**kwargs):
        raise RuntimeError('planner-fail')

    with pytest.raises(RuntimeError, match='planner-fail'):
        invoke_hover_hit_test_plan(
            planner=planner,
            handle_gate_id=None,
            hover_handle_key=None,
            current_hover_gate_id=None,
            current_pos=(0, 0),
            last_line_test_pos=None,
            min_delta=10,
        )


def test_helper_does_not_normalize_falsey_or_custom_values():
    seen = {}

    def planner(**kwargs):
        seen.update(kwargs)
        return kwargs

    result = invoke_hover_hit_test_plan(
        planner=planner,
        handle_gate_id=0,
        hover_handle_key=False,
        current_hover_gate_id='',
        current_pos=(False, 0),
        last_line_test_pos=0,
        min_delta=False,
    )

    assert result == seen
    assert seen == {
        'handle_gate_id': 0,
        'hover_handle_key': False,
        'current_hover_gate_id': '',
        'current_pos': (False, 0),
        'last_line_test_pos': 0,
        'min_delta': False,
    }


def test_controller_keeps_planner_and_all_concrete_input_acquisition():
    source = Path('vflow/controllers/gate_interaction_controller.py').read_text()
    start = source.index('hit_test_plan = invoke_hover_hit_test_plan(')
    end = source.index('\n                # Optional line/interior hit-test execution', start)
    block = source[start:end]

    required = [
        'planner=plan_hover_hit_testing',
        'handle_gate_id=new_hover',
        'hover_handle_key=new_hover_handle_key',
        'current_hover_gate_id=host._hover_gate_id',
        'current_pos=(event.x, event.y)',
        "last_line_test_pos=getattr(host, '_last_line_test_pos', None)",
        'min_delta=10',
    ]
    for text in required:
        assert text in block


def test_controller_source_pins_argument_evaluation_order():
    source = Path('vflow/controllers/gate_interaction_controller.py').read_text()
    start = source.index('hit_test_plan = invoke_hover_hit_test_plan(')
    end = source.index('\n                # Optional line/interior hit-test execution', start)
    block = source[start:end]

    positions = [
        block.index('planner=plan_hover_hit_testing'),
        block.index('handle_gate_id=new_hover'),
        block.index('hover_handle_key=new_hover_handle_key'),
        block.index('current_hover_gate_id=host._hover_gate_id'),
        block.index('current_pos=(event.x, event.y)'),
        block.index("last_line_test_pos=getattr(host, '_last_line_test_pos', None)"),
        block.index('min_delta=10'),
    ]
    assert positions == sorted(positions)


def test_controller_keeps_event_x_before_event_y_in_single_tuple_expression():
    source = Path('vflow/controllers/gate_interaction_controller.py').read_text()
    start = source.index('hit_test_plan = invoke_hover_hit_test_plan(')
    end = source.index('\n                # Optional line/interior hit-test execution', start)
    block = source[start:end]
    pos_expr = 'current_pos=(event.x, event.y)'
    assert pos_expr in block
    expr = block[block.index(pos_expr):block.index(pos_expr) + len(pos_expr)]
    assert expr.index('event.x') < expr.index('event.y')


def test_planner_is_captured_before_controller_state_and_event_inputs():
    source = Path('vflow/controllers/gate_interaction_controller.py').read_text()
    start = source.index('hit_test_plan = invoke_hover_hit_test_plan(')
    end = source.index('\n                # Optional line/interior hit-test execution', start)
    block = source[start:end]
    planner = block.index('planner=plan_hover_hit_testing')
    assert planner < block.index('host._hover_gate_id')
    assert planner < block.index('event.x')
    assert planner < block.index("getattr(host, '_last_line_test_pos', None)")


def test_helper_has_no_controller_event_or_hover_cache_authority():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    start = source.index('def invoke_hover_hit_test_plan(')
    end = source.index('\n\ndef run_hover_hit_test_execution_sequence', start)
    helper = source[start:end]

    assert 'self.' not in helper
    assert 'event.' not in helper
    assert 'self._hover_gate_id' not in helper
    assert "getattr(self, '_last_line_test_pos'" not in helper
    assert 'getattr(' not in helper
    assert 'HANDLE_PX' not in helper
    assert 'canvas' not in helper


def test_helper_does_not_own_min_delta_policy_literal():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    start = source.index('def invoke_hover_hit_test_plan(')
    end = source.index('\n\ndef run_hover_hit_test_execution_sequence', start)
    helper = source[start:end]
    assert 'min_delta=10' not in helper
    assert 'min_delta=min_delta' in helper


def test_plan_implementation_itself_remains_in_headless_service():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    assert 'def plan_hover_hit_testing(' in source
    assert 'line_hover_test_plan(' in source
