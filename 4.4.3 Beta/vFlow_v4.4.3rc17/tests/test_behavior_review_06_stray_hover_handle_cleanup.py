import inspect

from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.legacy.vflow_app import FlowApp
from vflow.ui.gate_interaction import should_clear_hover_outside_axes


def test_outside_axes_clear_checks_handle_only_when_both_gate_ids_are_absent():
    calls = []

    def resolve(value):
        def inner():
            calls.append(value)
            return value
        return inner

    assert should_clear_hover_outside_axes(
        hover_gate_id=7,
        interior_hover_gate_id=None,
        resolve_hover_handle_key=resolve((7, "edge", 0)),
    ) is True
    assert should_clear_hover_outside_axes(
        hover_gate_id=None,
        interior_hover_gate_id=9,
        resolve_hover_handle_key=resolve((9, "edge", 0)),
    ) is True
    assert calls == []

    assert should_clear_hover_outside_axes(
        hover_gate_id=None,
        interior_hover_gate_id=None,
        resolve_hover_handle_key=resolve(None),
    ) is False
    assert calls == [None]

    stray = (3, "edge", 0)
    assert should_clear_hover_outside_axes(
        hover_gate_id=None,
        interior_hover_gate_id=None,
        resolve_hover_handle_key=resolve(stray),
    ) is True
    assert calls == [None, stray]


def test_outside_axes_clear_treats_gate_id_zero_as_present_without_handle_read():
    def forbidden():
        raise AssertionError("hover handle must remain lazy when a gate ID is present")

    assert should_clear_hover_outside_axes(
        hover_gate_id=0,
        interior_hover_gate_id=None,
        resolve_hover_handle_key=forbidden,
    ) is True
    assert should_clear_hover_outside_axes(
        hover_gate_id=None,
        interior_hover_gate_id=0,
        resolve_hover_handle_key=forbidden,
    ) is True


def test_flowapp_outside_axes_condition_passes_handle_as_lazy_resolver_after_gate_ids():
    source = inspect.getsource(GateInteractionController.on_motion)
    start = source.index("elif should_clear_hover_outside_axes(")
    end = source.index("\n        if event.inaxes != host.ax:", start)
    branch = source[start:end]

    hover = branch.index("hover_gate_id=host._hover_gate_id")
    interior = branch.index("interior_hover_gate_id=host._interior_hover_gate_id")
    handle = branch.index("resolve_hover_handle_key=lambda: host._hover_handle_key")
    assert hover < interior < handle


def test_flowapp_clears_a_lone_stray_handle_outside_axes():
    class Var:
        def get(self):
            return "draw"

    class Widget:
        def __init__(self, log):
            self.log = log
        def config(self, **kwargs):
            self.log.append(("cursor", kwargs.get("cursor")))

    class Canvas:
        def __init__(self, log):
            self.log = log
        def get_tk_widget(self):
            self.log.append(("widget",))
            return Widget(self.log)
        def draw_idle(self):
            self.log.append(("draw",))

    class Event:
        xdata = None
        ydata = None

    app = FlowApp.__new__(FlowApp)
    log = []
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
    app.canvas = Canvas(log)
    app.ax = object()
    app._preview_gate = lambda *args, **kwargs: log.append(("preview",))

    event = Event()
    event.inaxes = object()
    app._on_motion(event)

    assert app._hover_gate_id is None
    assert app._hover_handle_key is None
    assert app._interior_hover_gate_id is None
    assert log == [("widget",), ("cursor", ""), ("preview",), ("draw",)]
