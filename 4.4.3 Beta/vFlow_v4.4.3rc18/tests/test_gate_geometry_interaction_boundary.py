import ast
import inspect
from pathlib import Path

from vflow.controllers.gate_interaction_controller import GateInteractionController
import vflow.services.gate_geometry_interaction as geometry_service
from vflow.legacy.vflow_app import FlowApp


def test_geometry_planner_is_tk_and_matplotlib_free():
    src = inspect.getsource(geometry_service)
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any(name.startswith("tkinter") for name in imported)
    assert not any(name.startswith("matplotlib") for name in imported)


def test_flowapp_keeps_event_geometry_and_render_side_effects():
    click = inspect.getsource(GateInteractionController.on_click)
    motion = inspect.getsource(GateInteractionController.on_motion)
    release = inspect.getsource(GateInteractionController.on_release)
    assert "plan_handle_drag_start" in click
    assert "plan_gate_move_start" in click
    assert "plan_draw_start" in click
    assert "gate_snapshot(" in click
    assert "np.array([event.x, event.y]" in click
    assert "iter_gate_draw_assignments(" in motion
    assert "gate[key] = value" in motion
    assert "update_gate_from_control_points(" in motion
    assert "_drag_handle_update(" in motion
    assert "_finish_gate(" in release
    assert "tk.BooleanVar" in release


def test_live_geometry_math_stays_out_of_planner():
    src = inspect.getsource(geometry_service)
    forbidden = [
        "iter_gate_draw_assignments", "update_gate_draw", "update_gate_from_handle_drag",
        "update_gate_from_control_points", "gate_mask", "compute_gate_regions",
        "BooleanVar", "transData", "draw_idle", "blit",
    ]
    for token in forbidden:
        assert token not in src


def test_packaged_flowapp_is_the_release_authority():
    from vflow import main
    module = main._load_legacy_module()
    assert FlowApp is module.FlowApp
    assert module.__name__ == "vflow.legacy.vflow_app"


def test_body_move_wiring_calls_planner_with_live_legacy_payload():
    import numpy as np

    class Var:
        def __init__(self, value): self.value = value
        def get(self): return self.value

    class Ax:
        def get_xlim(self): return (-2.5, 8.0)
        def get_ylim(self): return (-4.0, 12.25)

    class Event:
        dblclick = False
        button = 3
        x = 123.0
        y = 456.0
        xdata = 1.0
        ydata = 2.0

    app = FlowApp.__new__(FlowApp)
    app.ax = Ax(); Event.inaxes = app.ax
    app.gate_mode_var = Var('draw')
    app._poly_active = False
    app._sel_gate_id = 1
    app._pinned_gate_id = None
    app._interior_hover_gate_id = 99
    app._handle_drag = None
    app._gate_move = None
    app._drag_last_draw = 5.0
    gate = {'id': 3, 'type': 'rectangle', 'applied': True,
            'x0': 0.0, 'x1': 1.0, 'y0': 0.0, 'y1': 1.0}
    app.gates = [gate]
    app._hit_test_handles = lambda event: None
    app._hit_test_gate_interior = lambda event: gate
    app._gate_pts_to_pixels = lambda value: np.array([[10., 20.], [30., 40.]])
    app._start_blit_drag = lambda: None
    app._rebuild_gate_manager = lambda: None
    app._rebuild_thresh_panel = lambda: None

    app._on_click(Event())

    assert app._gate_move['gate_id'] == 3
    assert app._gate_move['gate'] is gate
    assert app._gate_move['press_px'].tolist() == [123.0, 456.0]
    assert app._gate_move['orig_px'].tolist() == [[10.0, 20.0], [30.0, 40.0]]
    assert app._gate_move['frozen_xlim'] == [-2.5, 8.0]
    assert app._gate_move['frozen_ylim'] == [-4.0, 12.25]
    assert app._drag_last_draw == 0.0


def test_gate_body_motion_delegates_only_pixel_translation_not_transform_or_mutation():
    import inspect
    from vflow.legacy.vflow_app import FlowApp

    source = inspect.getsource(GateInteractionController.on_motion)
    assert "translate_gate_pixel_points" in source
    assert "host.ax.transData.inverted().transform(shifted_px)" in source
    assert "update_gate_from_control_points(gate, new_data)" in source
    inverse_call = "host.ax.transData.inverted().transform(shifted_px)"
    assert source.index("translate_gate_pixel_points") < source.index(inverse_call)


def test_geometry_interaction_service_remains_headless_and_does_not_mutate_gates():
    import inspect
    import vflow.services.gate_geometry_interaction as service

    source = inspect.getsource(service)
    assert "tkinter" not in source
    assert "matplotlib" in source  # documentation may mention matplotlib
    assert "from matplotlib" not in source
    assert "import matplotlib" not in source
    assert "update_gate_from_control_points" not in source


def test_handle_drag_controller_applies_pure_assignments_after_cache_eviction():
    source = inspect.getsource(GateInteractionController.drag_handle_update)
    assert "iter_handle_drag_assignments" in source
    assert "gate[key] = value" in source
    assert "update_gate_from_handle_drag(" not in source
    assert source.index("evict_cache_keys(host._scatter_cache, stale_sc)") < \
           source.index("iter_handle_drag_assignments")


def test_handle_drag_pure_planner_lives_in_headless_core_and_does_not_mutate_gate():
    import inspect
    import vflow.core.gates as gates

    source = inspect.getsource(gates.iter_handle_drag_assignments)
    assert "tkinter" not in source
    assert "matplotlib" not in source
    assert "gate[" not in source
    assert "yield" in source
