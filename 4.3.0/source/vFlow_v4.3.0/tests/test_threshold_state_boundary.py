import inspect

from vflow.core.threshold_state import ThresholdState
from vflow.legacy.vflow_app import FlowApp


class Flag:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value


def test_threshold_state_module_is_tk_free():
    import vflow.core.threshold_state as module

    source = inspect.getsource(module)
    assert "import tkinter" not in source
    assert "from tkinter" not in source
    assert "BooleanVar" not in source


def test_threshold_snapshot_does_not_mutate_live_gate_or_replace_variables():
    x_flag = Flag(True)
    y_flag = Flag(False)
    gate = {
        "type": "crosshair",
        "x_thresh_vars": [x_flag],
        "y_thresh_var": y_flag,
        "y_thresh_vars": [],
    }

    state = ThresholdState.from_gate(gate)

    assert state.x_flags == (True,)
    assert state.y_flag is False
    assert gate["x_thresh_vars"][0] is x_flag
    assert gate["y_thresh_var"] is y_flag


def test_flowapp_keeps_threshold_toggle_side_effects_in_legacy_controller():
    source = inspect.getsource(FlowApp._on_thresh_toggle)

    assert "self._sel_gate()" in source
    assert "self._compute_gate_stats_for(sel)" in source
    assert "self.refresh_plot()" in source
    assert "self._update_stats_display()" in source
    assert "ThresholdState" not in source
