import ast
import inspect
from pathlib import Path

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.legacy.vflow_app import FlowApp


def test_gate_threshold_planning_service_is_tk_free():
    path = Path('vflow/services/gate_threshold_planning.py')
    source = path.read_text()
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any(name == 'tkinter' or name.startswith('tkinter.') for name in imports)
    assert 'BooleanVar(' not in source


def test_manual_release_delegates_plan_but_keeps_tk_materialization_in_flowapp():
    source = inspect.getsource(GateInteractionController.on_release)
    assert 'manual_crosshair_threshold_plan()' in source
    assert "gate['x_thresh_vars'] = [tk.BooleanVar" in source
    assert "gate['y_thresh_var']  = tk.BooleanVar" in source
    assert "gate['applied']       = True" in source


def test_single_y_auto_gate_delegates_plan_but_keeps_mutation_in_flowapp():
    source = inspect.getsource(FlowApp._apply_gate_and_refresh)
    assert 'single_y_auto_threshold_plan(xbs_raw)' in source
    assert "target['x_thresh_vars'] = [tk.BooleanVar" in source
    assert "target['y_thresh_var']  = tk.BooleanVar" in source
    assert "target['y_thresh_vars'] = [tk.BooleanVar" in source
    assert 'self._bind_gate_context(target)' in source
    assert 'self._analysis_cache_obj().clear_gate_dependent()' in source


def test_gmm_multi_delegates_plan_without_moving_scientific_fit_or_side_effects():
    source = inspect.getsource(FlowApp.auto_gate_gmm_multi)
    assert 'fit_gmm_crossings(' in source
    assert 'multi_y_auto_threshold_plan(xbs_raw, ybs_raw)' in source
    assert "target['x_thresh_vars'] = [tk.BooleanVar" in source
    assert "target['y_thresh_vars'] = [tk.BooleanVar" in source
    assert 'self._bind_gate_context(target)' in source
    assert 'self._compute_gate_stats_for(target)' in source


def test_threshold_toggle_callback_remains_unchanged_controller_side_effects():
    source = inspect.getsource(FlowApp._on_thresh_toggle)
    assert 'gate_threshold_planning' not in source
    assert 'self._sel_gate()' in source
    assert 'self._compute_gate_stats_for(sel)' in source
    assert 'self.refresh_plot()' in source
    assert 'self._update_stats_display()' in source
