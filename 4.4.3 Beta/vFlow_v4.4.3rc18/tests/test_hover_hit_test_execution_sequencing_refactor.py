from pathlib import Path

import pytest

from vflow.ui.gate_interaction import run_hover_hit_test_execution_sequence


class Plan:
    def __init__(self, log, run_values=(True, True), pos_values=((3, 4), (3, 4))):
        self.log = log
        self._run_values = iter(run_values)
        self._pos_values = iter(pos_values)

    @property
    def run_line_test(self):
        self.log.append('get_run_line_test')
        return next(self._run_values)

    @property
    def next_line_test_pos(self):
        self.log.append('get_next_line_test_pos')
        return next(self._pos_values)


class Continuation:
    def __init__(self, log, hover_gate_id, run_interior_test):
        self.log = log
        self._hover_gate_id = hover_gate_id
        self._run_interior_test = run_interior_test

    @property
    def hover_gate_id(self):
        self.log.append('get_continuation_hover')
        return self._hover_gate_id

    @property
    def run_interior_test(self):
        self.log.append('get_run_interior_test')
        return self._run_interior_test


class Hit(dict):
    def __init__(self, log, *args, truth=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = log
        self.truth = truth

    def __bool__(self):
        self.log.append('hit_truth')
        return self.truth

    def __getitem__(self, key):
        self.log.append(('hit_getitem', key))
        return super().__getitem__(key)


def run_sequence(*, plan, continuation, hit=None, line_result=8):
    log = plan.log

    def commit(value):
        log.append(('commit_pos', value))

    def line_test():
        log.append('line_test')
        return line_result

    def continue_test(**kwargs):
        log.append(('continue', kwargs['line_gate_id'], kwargs['line_test_ran'], kwargs['mode']))
        return continuation

    def interior_test():
        log.append('interior_test')
        return hit

    result = run_hover_hit_test_execution_sequence(
        plan=plan,
        mode='draw',
        commit_line_test_pos=commit,
        run_line_test=line_test,
        continue_hit_testing=continue_test,
        run_interior_test=interior_test,
    )
    return result, log


def test_line_position_is_committed_before_line_test_and_second_plan_read():
    log = []
    plan = Plan(log)
    continuation = Continuation(log, hover_gate_id=8, run_interior_test=False)
    result, log = run_sequence(plan=plan, continuation=continuation)
    assert result == (8, None)
    assert log == [
        'get_run_line_test',
        'get_next_line_test_pos',
        'get_next_line_test_pos',
        ('commit_pos', (3, 4)),
        'line_test',
        'get_run_line_test',
        ('continue', 8, True, 'draw'),
        'get_continuation_hover',
        'get_run_interior_test',
    ]


def test_false_first_run_flag_skips_position_and_line_but_second_flag_is_still_read():
    log = []
    plan = Plan(log, run_values=(False, True), pos_values=())
    continuation = Continuation(log, hover_gate_id=5, run_interior_test=False)
    result, log = run_sequence(plan=plan, continuation=continuation)
    assert result == (5, None)
    assert 'line_test' not in log
    assert not any(isinstance(item, tuple) and item and item[0] == 'commit_pos' for item in log)
    assert ('continue', None, True, 'draw') in log


def test_none_next_position_skips_commit_but_line_test_still_runs():
    log = []
    plan = Plan(log, pos_values=(None,))
    continuation = Continuation(log, hover_gate_id=2, run_interior_test=False)
    result, log = run_sequence(plan=plan, continuation=continuation)
    assert result == (2, None)
    assert 'line_test' in log
    assert not any(isinstance(item, tuple) and item and item[0] == 'commit_pos' for item in log)
    assert log.count('get_next_line_test_pos') == 1


def test_interior_hit_is_optional_and_truthy_hit_reads_id_lazily():
    log = []
    plan = Plan(log, run_values=(False, False), pos_values=())
    continuation = Continuation(log, hover_gate_id=None, run_interior_test=True)
    hit = Hit(log, {'id': 17}, truth=True)
    result, log = run_sequence(plan=plan, continuation=continuation, hit=hit)
    assert result == (None, 17)
    assert log[-3:] == ['interior_test', 'hit_truth', ('hit_getitem', 'id')]


def test_falsey_interior_hit_does_not_read_id():
    log = []
    plan = Plan(log, run_values=(False, False), pos_values=())
    continuation = Continuation(log, hover_gate_id=None, run_interior_test=True)
    hit = Hit(log, {'id': 17}, truth=False)
    result, log = run_sequence(plan=plan, continuation=continuation, hit=hit)
    assert result == (None, None)
    assert ('hit_getitem', 'id') not in log


def test_no_interior_request_never_calls_interior_callback():
    log = []
    plan = Plan(log, run_values=(False, False), pos_values=())
    continuation = Continuation(log, hover_gate_id=4, run_interior_test=False)
    result, log = run_sequence(plan=plan, continuation=continuation)
    assert result == (4, None)
    assert 'interior_test' not in log


def test_line_test_failure_stops_before_second_run_flag_and_continuation():
    log = []
    plan = Plan(log)

    def fail_line():
        log.append('line_test')
        raise RuntimeError('line-fail')

    with pytest.raises(RuntimeError, match='line-fail'):
        run_hover_hit_test_execution_sequence(
            plan=plan,
            mode='draw',
            commit_line_test_pos=lambda value: log.append(('commit_pos', value)),
            run_line_test=fail_line,
            continue_hit_testing=lambda **kwargs: log.append('continue'),
            run_interior_test=lambda: log.append('interior'),
        )
    assert log[-1] == 'line_test'
    assert log.count('get_run_line_test') == 1


def test_flowapp_retains_concrete_threshold_storage_mode_and_hit_tests():
    source = Path('vflow/controllers/gate_interaction_controller.py').read_text()
    assert "invoke_hover_hit_test_plan(" in source
    assert "planner=plan_hover_hit_testing" in source
    assert "mode=mode" in source
    assert "setattr(host, '_last_line_test_pos', value)" in source
    assert "host._hit_test_gate_line(event, threshold_px=8)" in source
    assert "continue_hover_hit_testing(**kwargs)" in source
    assert "host._hit_test_gate_interior(event)" in source
    assert "run_hover_hit_test_execution_sequence(" in source


def test_helper_has_no_concrete_controller_event_threshold_or_tk_authority():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    start = source.index('def run_hover_hit_test_execution_sequence(')
    end = source.index('\n\n@dataclass', start)
    helper = source[start:end]
    assert 'self.' not in helper
    assert 'event.' not in helper
    assert 'threshold_px=8' not in helper
    assert '_last_line_test_pos' not in helper
    assert 'canvas' not in helper
    assert 'tk.' not in helper


def test_hit_id_access_occurs_only_after_hit_truth_test_in_helper_source():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    start = source.index('def run_hover_hit_test_execution_sequence(')
    end = source.index('\n\n@dataclass', start)
    helper = source[start:end]
    assert "hit['id'] if hit else None" in helper
