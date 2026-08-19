import inspect
from types import SimpleNamespace

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.legacy.vflow_app import FlowApp


def test_flowapp_event_surface_is_thin_composed_delegate():
    click = inspect.getsource(FlowApp._on_click)
    motion = inspect.getsource(FlowApp._on_motion)
    release = inspect.getsource(FlowApp._on_release)
    assert "_interaction_controller().on_click(event)" in click
    assert "_interaction_controller().on_motion(event)" in motion
    assert "_interaction_controller().on_release(event)" in release
    assert "plan_gate_move_start" not in click
    assert "plan_hover_presentation" not in motion
    assert "resolve_release_interaction_path" not in release


def test_lazy_interaction_controller_is_composed_once_per_flowapp():
    app = FlowApp.__new__(FlowApp)
    first = app._interaction_controller()
    second = app._interaction_controller()
    assert isinstance(first, GateInteractionController)
    assert first is second
    assert first._host is app


def test_event_lifecycle_authority_moved_to_controller_module():
    click = inspect.getsource(GateInteractionController.on_click)
    motion = inspect.getsource(GateInteractionController.on_motion)
    release = inspect.getsource(GateInteractionController.on_release)
    assert "plan_handle_drag_start" in click
    assert "plan_gate_move_start" in click
    assert "invoke_hover_hit_test_plan" in motion
    assert "run_hover_presentation_sequence" in motion
    assert "resolve_release_interaction_path" in release
    assert "run_crosshair_release_side_effect_sequence" in release
    # Host state must be mutated through the composed host, never accidentally
    # installed on the controller object itself.
    assert "setattr(self," not in motion
    assert "getattr(self," not in motion


def test_outside_axes_stray_handle_mutation_targets_host_not_controller():
    class Var:
        def get(self):
            return "draw"

    class Widget:
        def config(self, **_kwargs):
            pass

    class Canvas:
        def get_tk_widget(self):
            return Widget()
        def draw_idle(self):
            pass

    app = FlowApp.__new__(FlowApp)
    app._handle_drag = None
    app._gate_move = None
    app.gate_mode_var = Var()
    app.gate_type_var = Var()
    app._poly_active = False
    app.moving_gate = False
    app._pinned_gate_id = None
    app._hover_gate_id = None
    app._hover_handle_key = (3, "edge", 0)
    app._interior_hover_gate_id = None
    app.canvas = Canvas()
    app.ax = object()
    app._preview_gate = lambda *args, **kwargs: None

    event = SimpleNamespace(inaxes=object(), xdata=None, ydata=None)
    controller = app._interaction_controller()
    controller.on_motion(event)

    assert app._hover_handle_key is None
    assert not hasattr(controller, "_hover_handle_key")


def test_interaction_helper_implementations_are_owned_by_composed_controller():
    line_wrapper = inspect.getsource(FlowApp._hit_test_gate_line)
    preview_wrapper = inspect.getsource(FlowApp._preview_gate)
    drag_wrapper = inspect.getsource(FlowApp._drag_handle_update)
    assert "_gate_interaction_owner(self).hit_test_gate_line" in line_wrapper
    assert "_gate_interaction_owner(self).preview_gate" in preview_wrapper
    assert "_gate_interaction_owner(self).drag_handle_update" in drag_wrapper

    line_owner = inspect.getsource(GateInteractionController.hit_test_gate_line)
    preview_owner = inspect.getsource(GateInteractionController.preview_gate)
    drag_owner = inspect.getsource(GateInteractionController.drag_handle_update)
    assert "bounded_vertical_line_distance" in line_owner
    assert "gate_preview_style" in preview_owner
    assert "iter_handle_drag_assignments" in drag_owner


def test_nonlinear_ellipse_preview_uses_membership_equivalent_sampled_outline():
    source = inspect.getsource(GateInteractionController.preview_gate)
    assert "host.x_scale == 'linear' and host.y_scale == 'linear'" in source
    assert "ellipse_perimeter_points(gate, n_points=256)" in source
    # The nonlinear branch must not use a Matplotlib Ellipse patch: its Bezier
    # control points are distorted by non-affine axis transforms differently
    # from the raw-data ellipse equation used for gate membership.
    nonlinear = source.split("else:\n                        points = ellipse_perimeter_points", 1)[1]
    assert "host.ax.plot" in nonlinear
    assert "host._preview_artists.append(line)" in nonlinear


def test_event_lifecycle_preserves_legacy_helper_override_surface():
    click = inspect.getsource(GateInteractionController.on_click)
    motion = inspect.getsource(GateInteractionController.on_motion)
    # The controller intentionally calls through the host compatibility facade
    # so existing monkeypatch/failure-oracle boundaries remain observable.
    assert "host._hit_test_handles(event)" in click
    assert "host._hit_test_gate_interior(event)" in click
    assert "host._preview_gate(skip_cache=True)" in motion
    assert "host._blit_render()" in motion
