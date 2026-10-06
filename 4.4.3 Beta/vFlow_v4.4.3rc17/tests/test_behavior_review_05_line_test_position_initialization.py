from vflow.legacy.vflow_app import FlowApp
from vflow.ui.gate_interaction import GateHoverCache


def test_explicit_none_survives_cache_clear():
    cache = GateHoverCache()
    assert cache.get_last_line_test_pos() is None
    cache.set_last_line_test_pos((1.0, 2.0))
    cache.clear()
    assert cache.get_last_line_test_pos() is None


def test_flowapp_first_planner_input_remains_none():
    app = FlowApp.__new__(FlowApp)
    assert app._last_line_test_pos is None
    assert getattr(app, '_last_line_test_pos', None) is None


def test_first_committed_position_replaces_explicit_none():
    app = FlowApp.__new__(FlowApp)
    assert app._last_line_test_pos is None
    app._last_line_test_pos = (11.0, 13.0)
    assert app._last_line_test_pos == (11.0, 13.0)
