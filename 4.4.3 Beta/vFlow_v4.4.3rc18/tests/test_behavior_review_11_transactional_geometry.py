from types import SimpleNamespace

import pytest

from vflow.app.cache import AnalysisCache
from vflow.core.cache_keys import gate_signature
from vflow.legacy.vflow_app import FlowApp


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _RaiseSet(dict):
    def __init__(self, *args, fail_key=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fail_key = fail_key
        self.sets = []

    def __setitem__(self, key, value):
        self.sets.append((key, value))
        if key == self.fail_key:
            raise RuntimeError(f"fail:{key}")
        return super().__setitem__(key, value)


class _LateOrig(dict):
    def __init__(self):
        super().__init__(x0=0.0, x1=4.0, y0=1.0, y1=5.0)
        self.calls = []

    def __getitem__(self, key):
        self.calls.append(key)
        if self.calls == ["x0", "x1", "y0", "y1", "x0", "x1"]:
            raise RuntimeError("late x1 failure")
        return super().__getitem__(key)


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


class _ClickEvent:
    dblclick = False
    button = 1
    xdata = 3.5
    ydata = 4.5


def _gate_geometry(gate):
    keys = (
        "type", "x0", "x1", "y0", "y1", "x_boundaries",
        "y_boundary", "vertices", "applied",
    )
    return {key: gate[key] for key in keys if key in gate}


def test_handle_late_calculation_failure_rolls_back_geometry_but_keeps_conservative_eviction():
    gate = {
        "id": 1, "type": "rectangle", "applied": True,
        "x0": 0.0, "x1": 4.0, "y0": 1.0, "y1": 5.0,
    }
    before = _gate_geometry(gate)
    sig = gate_signature(gate)
    cache = AnalysisCache()
    cache.gate_masks[(1, "p", "X", "Y", "linear", "linear", 150.0, 1, sig)] = "mask"
    cache.scatter[(1, "p", "X", "Y", "linear", "linear", 150.0, (sig,), 4, 0.5, "c", False)] = "scatter"

    app = FlowApp.__new__(FlowApp)
    app.__dict__["_analysis_cache"] = cache
    orig = _LateOrig()
    payload = {"gate": gate, "handle": "center", "idx": 4, "orig": orig}
    app._handle_drag = payload

    with pytest.raises(RuntimeError, match="^late x1 failure$"):
        app._drag_handle_update(3.0, 5.0)

    assert _gate_geometry(gate) == before
    assert orig.calls == ["x0", "x1", "y0", "y1", "x0", "x1"]
    assert cache.gate_masks == {}
    assert cache.scatter == {}
    assert app._handle_drag is payload


def test_fresh_motion_assignment_failure_restores_prior_geometry_and_preserves_interaction_state():
    gate = _RaiseSet(
        {"id": 2, "type": "rectangle", "applied": False,
         "x0": 1.0, "x1": 1.0, "y0": 2.0, "y1": 2.0},
        fail_key="y1",
    )
    before = _gate_geometry(gate)
    app = FlowApp.__new__(FlowApp)
    app.ax = object()
    app._handle_drag = None
    app._gate_move = None
    app.moving_gate = True
    app.gate_mode_var = _Var("draw")
    app.gate_type_var = _Var("rectangle")
    app._poly_active = False
    app._draw_gate_obj = lambda: gate
    app._drag_last_draw = 9.0
    app._draw_frozen_xlim = [0.0, 1.0]
    app._draw_frozen_ylim = [2.0, 3.0]
    event = SimpleNamespace(inaxes=app.ax, xdata=9.0, ydata=10.0, x=90.0, y=100.0)

    with pytest.raises(RuntimeError, match="^fail:y1$"):
        app._on_motion(event)

    assert _gate_geometry(gate) == before
    assert gate.sets == [("x1", 9.0), ("y1", 10.0)]
    assert app.moving_gate is True
    assert app._drag_last_draw == 9.0
    assert app._draw_frozen_xlim == [0.0, 1.0]
    assert app._draw_frozen_ylim == [2.0, 3.0]


@pytest.mark.parametrize(
    "gate,event,fail_key,expected_sets",
    [
        (
            {"id": 3, "type": "crosshair", "applied": False,
             "x_boundaries": [1.0], "y_boundary": 2.0},
            SimpleNamespace(xdata=5.0, ydata=6.0),
            "y_boundary",
            [("x_boundaries", [5.0]), ("y_boundary", 6.0)],
        ),
        (
            {"id": 4, "type": "rectangle", "applied": False,
             "x0": 1.0, "x1": 1.0, "y0": 2.0, "y1": 2.0},
            SimpleNamespace(xdata=5.0, ydata=6.0),
            "y1",
            [("x1", 5.0), ("y1", 6.0)],
        ),
    ],
)
def test_fresh_release_assignment_failure_restores_geometry_but_preserves_historical_release_transient_state(
    gate, event, fail_key, expected_sets
):
    gate = _RaiseSet(gate, fail_key=fail_key)
    before = _gate_geometry(gate)
    app = FlowApp.__new__(FlowApp)
    app._handle_drag = None
    app._gate_move = None
    app.moving_gate = True
    app._draw_frozen_xlim = [0.0, 1.0]
    app._draw_frozen_ylim = [2.0, 3.0]
    app._draw_gate_id = gate["id"]
    app._draw_gate_obj = lambda: gate

    with pytest.raises(RuntimeError, match=rf"^fail:{fail_key}$"):
        app._on_release(event)

    assert _gate_geometry(gate) == before
    assert gate.sets == expected_sets
    # BR-GEO-001 does not rewrite the pre-existing release-state order.
    assert app.moving_gate is False
    assert app._draw_frozen_xlim is None
    assert app._draw_frozen_ylim is None
    assert app._draw_gate_id == gate["id"]


def _initialization_app(gate, *, axis_fail=None):
    app = FlowApp.__new__(FlowApp)
    app.ax = _Axes(fail=axis_fail)
    _ClickEvent.inaxes = app.ax
    app.gate_mode_var = _Var("draw")
    app.gate_type_var = _Var("rectangle")
    app._poly_active = False
    app.gates = [gate]
    app._draw_gate_id = gate["id"]
    app._sel_gate_id = gate["id"]
    app._pinned_gate_id = None
    app._interior_hover_gate_id = None
    app._handle_drag = None
    app._gate_move = None
    app._drag_last_draw = 9.0
    app._draw_frozen_xlim = "OLDX"
    app._draw_frozen_ylim = "OLDY"
    app.moving_gate = False
    app._draw_gate_obj = lambda: gate
    app._start_blit_drag = lambda: None
    app._preview_gate = lambda *args, **kwargs: None
    app._blit_render = lambda: None
    return app


def test_initialization_assignment_failure_restores_type_and_all_prior_geometry():
    gate = _RaiseSet(
        {"id": 7, "type": "ellipse", "applied": False,
         "x0": 10.0, "x1": 11.0, "y0": 12.0, "y1": 13.0},
        fail_key="y0",
    )
    before = _gate_geometry(gate)
    app = _initialization_app(gate)

    with pytest.raises(RuntimeError, match="^fail:y0$"):
        app._on_click(_ClickEvent())

    assert _gate_geometry(gate) == before
    assert gate.sets == [("type", "rectangle"), ("x0", 3.5), ("y0", 4.5)]
    assert app.moving_gate is False
    assert app._drag_last_draw == 9.0
    assert app._draw_frozen_xlim == "OLDX"
    assert app._draw_frozen_ylim == "OLDY"
    assert app._draw_gate_id == 7


@pytest.mark.parametrize("axis_fail,axis_calls", [("xlim", ["xlim"]), ("ylim", ["xlim", "ylim"])])
def test_axis_snapshot_failure_after_complete_initialization_keeps_br08_coherent_gate_semantics(axis_fail, axis_calls):
    gate = {
        "id": 8, "type": "ellipse", "applied": False,
        "x0": 10.0, "x1": 11.0, "y0": 12.0, "y1": 13.0,
    }
    app = _initialization_app(gate, axis_fail=axis_fail)

    with pytest.raises(RuntimeError, match=axis_fail):
        app._on_click(_ClickEvent())

    assert _gate_geometry(gate) == {
        "type": "rectangle", "x0": 3.5, "x1": 3.5,
        "y0": 4.5, "y1": 4.5, "applied": False,
    }
    assert app.ax.calls == axis_calls
    assert app.moving_gate is False
    assert app._drag_last_draw == 9.0
    assert app._draw_frozen_xlim == "OLDX"
    assert app._draw_frozen_ylim == "OLDY"
    assert app._draw_gate_id == 8
