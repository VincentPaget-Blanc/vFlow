import ast
import inspect

import vflow.services.active_file_changes as svc
from vflow.legacy.vflow_app import FlowApp


def _method_calls(fn):
    tree = ast.parse(inspect.getsource(fn).lstrip())
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                names.append(f.id)
            elif isinstance(f, ast.Attribute):
                names.append(f.attr)
    return names


def test_active_file_change_service_is_tk_free_and_side_effect_free_by_import_boundary():
    source = inspect.getsource(svc)
    assert 'tkinter' not in source
    assert 'messagebox' not in source
    assert 'refresh_plot' not in source
    assert '_invalidate_analysis_caches' not in source
    assert '_recompute_all_gate_stats' not in source


def test_flowapp_active_file_callback_delegates_decision_but_keeps_side_effects():
    calls = _method_calls(FlowApp._on_active_files_changed)
    assert 'plan_active_file_change' in calls
    assert '_update_channel_menus' in calls
    assert '_analysis_context_changed' in calls
    assert '_recompute_all_gate_stats' in calls
    assert 'refresh_plot' in calls


def test_flowapp_context_change_keeps_scientific_side_effect_order_and_only_formats_status_outside():
    calls = _method_calls(FlowApp._analysis_context_changed)
    assert calls.index('_invalidate_analysis_caches') < calls.index('_recompute_all_gate_stats')
    assert calls.index('_recompute_all_gate_stats') < calls.index('refresh_plot')
    assert '_gate_context_matches' in calls
    assert 'build_incompatible_gate_status' in calls
    assert 'set' in calls
