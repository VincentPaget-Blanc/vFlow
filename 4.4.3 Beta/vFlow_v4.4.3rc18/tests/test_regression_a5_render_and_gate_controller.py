from types import SimpleNamespace

from matplotlib.figure import Figure

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.plotting.render_lifecycle import can_preserve_axis_state, reset_refresh_axes


def _rectangle_gate():
    return {
        "id": 1, "name": "Gate 1", "type": "rectangle", "applied": True,
        "color": "#ff0000", "linestyle": "-", "linewidth": 1.0,
        "x0": 1.0, "x1": 4.0, "y0": 2.0, "y1": 6.0,
    }


def test_preview_gate_real_controller_path_builds_handle_cache_without_nameerror():
    fig = Figure()
    ax = fig.add_subplot(111)
    gate = _rectangle_gate()
    host = SimpleNamespace(
        ax=ax, gates=[gate], _preview_artists=[], _handle_artists=[],
        _handle_px_cache={}, _sel_gate_id=1, _handle_drag=None,
        _hover_gate_id=None, _pinned_gate_id=None, _interior_hover_gate_id=None,
        _hover_handle_key=None, _poly_active=False, _poly_cursor=None,
        _draw_gate_id=None, x_scale="linear", y_scale="linear",
        _gate_context_matches=lambda g: True,
    )
    controller = GateInteractionController(host)
    controller.preview_gate()
    assert len(host._preview_artists) == 1
    assert 1 in host._handle_px_cache
    assert len(host._handle_px_cache[1]) == 5


def test_full_axis_reset_linearizes_previous_log_state_and_restores_ordered_fresh_limits():
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.set_yscale("log")
    ax.set_ylim(1.0, 100000.0)
    reset_refresh_axes([ax], preserve_axis_state=False)
    assert ax.get_yscale() == "linear"
    lo, hi = ax.get_ylim()
    assert lo < hi
    assert (lo, hi) == (0.0, 1.0)


def test_axis_state_reuse_is_forbidden_across_scale_transition():
    fig = Figure()
    ax = fig.add_subplot(111)
    ax.set_yscale("log")
    assert not can_preserve_axis_state(
        ax, plot_type="Dot Plot", target_x_scale="linear", target_y_scale="asinh")
    ax.set_yscale("linear")
    assert can_preserve_axis_state(
        ax, plot_type="Dot Plot", target_x_scale="linear", target_y_scale="linear")
    assert not can_preserve_axis_state(
        ax, plot_type="Contour Plot", target_x_scale="linear", target_y_scale="linear")

class _Var:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


def test_flowapp_scale_callback_keeps_x_and_y_assignments_on_their_own_axes():
    from vflow.app.state import AnalysisState
    from vflow.legacy.vflow_app import FlowApp

    app = FlowApp.__new__(FlowApp)
    app.__dict__["_analysis_state"] = AnalysisState(
        x_channel="X", y_channel="Y", x_scale="asinh", y_scale="asinh", cofactor=150.0
    )
    gate = {"id": 1, "type": "rectangle", "applied": True}
    app.gates = [gate]
    app._bind_gate_context(gate)
    app.x_scale_var = _Var("linear")
    app.y_scale_var = _Var("legacy_logicle")
    app.cofactor_str = _Var("150")
    app._analysis_context_changed = lambda: None

    app._apply_scales()

    assert app.x_scale == "linear"
    assert app.y_scale == "legacy_logicle"
    assert gate["_analysis_context"]["x_scale"] == "linear"
    assert gate["_analysis_context"]["y_scale"] == "legacy_logicle"


def test_derivative_and_otsu_autogates_use_the_current_axis_transform_parameter_helper():
    import inspect
    from vflow.legacy.vflow_app import FlowApp

    for method in (FlowApp.auto_gate_derivative, FlowApp.auto_gate_otsu):
        source = inspect.getsource(method)
        assert "_transform_params_for_axis" in source
        assert "_axis_transform_params" not in source
