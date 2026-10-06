from vflow.controllers.gate_interaction_controller import GateInteractionController
import ast
from pathlib import Path

import pytest

from vflow.ui.gate_interaction import GateHoverCache


def test_gate_hover_cache_defaults_expose_explicit_none_line_position():
    cache = GateHoverCache()
    assert cache.handle_pixel_cache == {}
    assert cache.get_last_line_test_pos() is None

    cache.set_last_line_test_pos((12.0, 18.0))
    assert cache.get_last_line_test_pos() == (12.0, 18.0)

    cache.clear()
    assert cache.handle_pixel_cache == {}
    assert cache.get_last_line_test_pos() is None


def test_flowapp_last_line_position_is_explicit_none_before_first_write():
    from vflow.legacy.vflow_app import FlowApp

    app = FlowApp.__new__(FlowApp)
    assert hasattr(app, '_last_line_test_pos') is True
    assert app._last_line_test_pos is None
    assert getattr(app, '_last_line_test_pos', None) is None

    app._last_line_test_pos = (3.0, 4.0)
    assert app._last_line_test_pos == (3.0, 4.0)
    assert app._gate_hover_cache_obj().get_last_line_test_pos() == (3.0, 4.0)


def test_flowapp_handle_pixel_cache_and_owner_are_bidirectional():
    from vflow.legacy.vflow_app import FlowApp

    app = FlowApp.__new__(FlowApp)
    first = {7: [(10.0, 20.0, 'corner', 0)]}
    app._handle_px_cache = first
    cache = app._gate_hover_cache_obj()
    assert cache.handle_pixel_cache is first
    assert app._handle_px_cache is first

    second = {9: [(30.0, 40.0, 'center', None)]}
    cache.handle_pixel_cache = second
    assert app._handle_px_cache is second


def test_legacy_cache_mutations_operate_on_central_owner():
    from vflow.legacy.vflow_app import FlowApp

    app = FlowApp.__new__(FlowApp)
    app._handle_px_cache = {1: ['a'], 2: ['b']}
    owner = app._gate_hover_cache_obj()

    app._handle_px_cache.pop(1, None)
    assert owner.handle_pixel_cache == {2: ['b']}

    app._handle_px_cache = {}
    assert owner.handle_pixel_cache == {}


def test_rebuild_handle_cache_still_owns_transform_and_replacement_timing():
    import inspect
    method = inspect.getsource(GateInteractionController.rebuild_handle_px_cache)

    # The draw/UI method still clears/rebuilds the cache and performs the
    # authoritative post-render transform.  Only ownership moved.
    assert 'host._handle_px_cache = {}' in method
    assert 'host.ax.transData.transform' in method
    assert "host._handle_px_cache[gate['id']] = entries" in method

    shell = Path('vflow/ui/flow_app_shell.py').read_text()
    assert "self.canvas.mpl_connect('draw_event', self._rebuild_handle_px_cache)" in shell


def test_line_test_position_write_timing_remains_in_on_motion():
    source = Path('vflow/controllers/gate_interaction_controller.py').read_text()
    start = source.index('    def on_motion(')
    end = source.index('\n    def on_release(', start)
    method = source[start:end]
    plan_pos = method.index('invoke_hover_hit_test_plan(')
    planner_pos = method.index('planner=plan_hover_hit_testing', plan_pos)
    write_pos = method.index("setattr(host, '_last_line_test_pos', value)")
    line_test_pos = method.index('host._hit_test_gate_line(event, threshold_px=8)')
    assert plan_pos < planner_pos < write_pos < line_test_pos


def test_hover_cache_owner_module_stays_tk_and_matplotlib_free():
    source = Path('vflow/ui/gate_interaction.py').read_text()
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any(name == 'tkinter' or name.startswith('tkinter.') for name in imports)
    assert not any(name == 'matplotlib' or name.startswith('matplotlib.') for name in imports)
