import ast
import inspect
import textwrap

import vflow.services.axis_input_planning as svc
from vflow.legacy.vflow_app import FlowApp


def _method_calls(fn):
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    return {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Attribute, ast.Name))
    }


def test_axis_input_service_is_tk_free_and_does_not_own_analysis_state():
    tree = ast.parse(inspect.getsource(svc))
    imported_modules = {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imported_names = {
        alias.name for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    assert not any(name.startswith('tkinter') for name in imported_modules)
    assert 'tkinter' not in imported_names
    assert 'AnalysisState' not in imported_names
    assert '_analysis_context_changed' not in called
    assert 'refresh_plot' not in called


def test_flowapp_callbacks_delegate_planning_but_keep_context_side_effects():
    apply_axes = _method_calls(FlowApp.apply_axes)
    apply_scales = _method_calls(FlowApp._apply_scales)
    trace = _method_calls(FlowApp._on_cofactor_change)
    validate = _method_calls(FlowApp._validate_cofactor_entry)

    assert 'plan_axis_apply' in apply_axes
    assert '_analysis_context_changed' in apply_axes
    assert 'refresh_plot' in apply_axes

    assert 'plan_scale_apply' in apply_scales
    assert '_analysis_context_changed' in apply_scales

    assert 'plan_cofactor_trace' in trace
    assert '_analysis_context_changed' in trace

    assert 'plan_cofactor_entry' in validate
    assert '_analysis_context_changed' in validate
