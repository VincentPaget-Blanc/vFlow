import pytest

from vflow.legacy.vflow_app import FlowApp


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _Axes:
    def __init__(self, fail=None):
        self.fail = fail
        self.calls = []

    def get_xlim(self):
        self.calls.append("xlim")
        if self.fail == "xlim":
            raise RuntimeError("xlim")
        return (0.0, 1.0)

    def get_ylim(self):
        self.calls.append("ylim")
        if self.fail == "ylim":
            raise RuntimeError("ylim")
        return (2.0, 3.0)


class _Event:
    dblclick = False
    x = 10.0
    y = 20.0
    xdata = 1.0
    ydata = 2.0


def _base_app(*, button, fail=None, handle=False):
    app = FlowApp.__new__(FlowApp)
    axes = _Axes(fail=fail)
    app.ax = axes
    _Event.inaxes = axes
    _Event.button = button

    app.gate_mode_var = _Var("draw")
    app.gate_type_var = _Var("rectangle")
    app._poly_active = False
    app._sel_gate_id = 1
    app._pinned_gate_id = None
    app._interior_hover_gate_id = None
    app._drag_last_draw = 9.0
    app._handle_drag = None
    app._gate_move = None
    app._draw_gate_id = 4
    app._draw_frozen_xlim = "OLDX"
    app._draw_frozen_ylim = "OLDY"
    app.moving_gate = False

    gate = {
        "id": 4,
        "type": "rectangle",
        "applied": False,
        "x0": None,
        "x1": None,
        "y0": None,
        "y1": None,
    }
    app.gates = [gate]
    app._draw_gate_obj = lambda: gate
    app._start_blit_drag = lambda: None
    app._preview_gate = lambda *args, **kwargs: None
    app._blit_render = lambda: None
    app._rebuild_gate_manager = lambda: None
    app._rebuild_thresh_panel = lambda: None
    app._hit_test_gate_line = lambda *args, **kwargs: None
    app._hit_test_gate_interior = lambda event: None

    hit = {
        "gate_id": 4,
        "gate": gate,
        "handle": "corner",
        "idx": 0,
        "orig": {},
    }
    app._hit_test_handles = (lambda event: hit) if handle else (lambda event: None)
    return app, axes, gate, hit


@pytest.mark.parametrize("failure", ["xlim", "ylim"])
def test_draw_axis_snapshot_failure_rolls_back_transient_start_state(failure):
    app, axes, gate, _ = _base_app(button=1, fail=failure)

    with pytest.raises(RuntimeError, match=failure):
        app._on_click(_Event())

    # BR-GEO-004: failed snapshot no longer leaves a half-started draw interaction.
    assert app.moving_gate is False
    assert app._drag_last_draw == 9.0
    assert app._draw_frozen_xlim == "OLDX"
    assert app._draw_frozen_ylim == "OLDY"
    # Gate initialization is deliberately *not* rolled back here (BR-GEO-001 remains separate).
    assert gate["type"] == "rectangle"
    assert axes.calls == (["xlim"] if failure == "xlim" else ["xlim", "ylim"])


@pytest.mark.parametrize("failure", ["xlim", "ylim"])
def test_handle_axis_snapshot_failure_leaves_no_partial_frozen_limits(failure):
    app, axes, _, hit = _base_app(button=3, fail=failure, handle=True)

    with pytest.raises(RuntimeError, match=failure):
        app._on_click(_Event())

    assert "frozen_xlim" not in hit
    assert "frozen_ylim" not in hit
    assert app._handle_drag is None
    assert app._drag_last_draw == 9.0
    assert axes.calls == (["xlim"] if failure == "xlim" else ["xlim", "ylim"])


def test_handle_axis_snapshot_failure_restores_preexisting_frozen_values():
    app, _, _, hit = _base_app(button=3, fail="ylim", handle=True)
    previous_x = [91.0, 92.0]
    previous_y = [93.0, 94.0]
    hit["frozen_xlim"] = previous_x
    hit["frozen_ylim"] = previous_y

    with pytest.raises(RuntimeError, match="ylim"):
        app._on_click(_Event())

    assert hit["frozen_xlim"] is previous_x
    assert hit["frozen_ylim"] is previous_y
    assert app._handle_drag is None


def test_successful_draw_start_preserves_historical_state_and_axis_order():
    app, axes, _, _ = _base_app(button=1)

    app._on_click(_Event())

    assert axes.calls == ["xlim", "ylim"]
    assert app.moving_gate is True
    assert app._drag_last_draw == 0.0
    assert app._draw_frozen_xlim == [0.0, 1.0]
    assert app._draw_frozen_ylim == [2.0, 3.0]


def test_successful_handle_start_preserves_historical_payload_and_axis_order():
    app, axes, _, hit = _base_app(button=3, handle=True)

    app._on_click(_Event())

    assert axes.calls == ["xlim", "ylim"]
    assert app._handle_drag is hit
    assert hit["frozen_xlim"] == [0.0, 1.0]
    assert hit["frozen_ylim"] == [2.0, 3.0]
    assert app._drag_last_draw == 0.0
