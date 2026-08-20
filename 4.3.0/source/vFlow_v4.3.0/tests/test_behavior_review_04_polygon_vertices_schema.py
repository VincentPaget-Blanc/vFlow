from types import SimpleNamespace

import pytest

from vflow.core.gates import (
    PolygonGeometrySchemaError,
    append_polygon_vertex,
    plan_polygon_finish,
    require_polygon_vertices,
)
from vflow.legacy import vflow_app as legacy_mod
from vflow.legacy.vflow_app import FlowApp


def test_require_polygon_vertices_rejects_only_explicit_none():
    marker = object()
    assert require_polygon_vertices(marker, operation="test") is marker
    assert require_polygon_vertices([], operation="test") == []
    with pytest.raises(PolygonGeometrySchemaError) as excinfo:
        require_polygon_vertices(None, operation="test")
    text = str(excinfo.value)
    assert "'vertices' is None" in text
    assert "test" in text
    assert "recreate the polygon gate" in text


def test_valid_polygon_append_and_finish_semantics_are_unchanged():
    gate = {"type": "polygon"}
    append_polygon_vertex(gate, 1.0, 2.0)
    append_polygon_vertex(gate, 3.0, 4.0)
    assert gate["vertices"] == [(1.0, 2.0), (3.0, 4.0)]
    assert not plan_polygon_finish(gate).can_finish
    append_polygon_vertex(gate, 5.0, 6.0)
    assert plan_polygon_finish(gate).can_finish


def test_none_vertices_is_not_mutated_by_core_schema_failures():
    gate = {"type": "polygon", "vertices": None}
    with pytest.raises(PolygonGeometrySchemaError):
        append_polygon_vertex(gate, 1.0, 2.0)
    assert gate["vertices"] is None
    with pytest.raises(PolygonGeometrySchemaError):
        plan_polygon_finish(gate)
    assert gate["vertices"] is None


class _Var:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value


class _Ax:
    pass


def _build_append_app(gate):
    app = FlowApp.__new__(FlowApp)
    app.ax = _Ax()
    app.gate_mode_var = _Var("draw")
    app.gate_type_var = _Var("polygon")
    app._poly_active = True
    app._draw_gate_obj = lambda: gate
    app.gates = [gate]
    app.manager = False
    app._sel_gate = lambda: None
    app._open_subgate = lambda *_: (_ for _ in ()).throw(AssertionError("subgate"))
    app._update_poly_close_btn = lambda: (_ for _ in ()).throw(AssertionError("close button"))
    app._preview_gate = lambda **_: (_ for _ in ()).throw(AssertionError("preview"))
    app._blit_render = lambda: (_ for _ in ()).throw(AssertionError("render"))
    app._drag_last_draw = 0.0
    return app


def test_controller_append_none_shows_actionable_error_and_stops(monkeypatch):
    gate = {"id": 7, "type": "polygon", "applied": False, "vertices": None}
    app = _build_append_app(gate)
    dialogs = []
    monkeypatch.setattr(legacy_mod.messagebox, "showerror", lambda title, message, **kw: dialogs.append((title, message, kw)))
    event = SimpleNamespace(
        inaxes=app.ax, dblclick=False, button=1,
        xdata=3.0, ydata=4.0, x=30, y=40,
    )

    app._on_click(event)

    assert gate["vertices"] is None
    assert len(dialogs) == 1
    assert dialogs[0][0] == "Polygon Gate"
    assert "Cannot add a polygon vertex" in dialogs[0][1]
    assert "'vertices' is None" in dialogs[0][1]


def test_controller_finish_none_shows_actionable_error_without_partial_close(monkeypatch):
    gate = {"id": 8, "type": "polygon", "applied": False, "vertices": None}
    app = FlowApp.__new__(FlowApp)
    app._poly_active = True
    app._poly_cursor = (1.0, 2.0)
    app._draw_gate_id = 8
    app._draw_gate_obj = lambda: gate
    app._update_poly_close_btn = lambda: (_ for _ in ()).throw(AssertionError("close button"))
    app._end_blit_drag = lambda: (_ for _ in ()).throw(AssertionError("end blit"))
    app._finish_gate = lambda *_: (_ for _ in ()).throw(AssertionError("finish"))
    dialogs = []
    monkeypatch.setattr(legacy_mod.messagebox, "showerror", lambda title, message, **kw: dialogs.append((title, message, kw)))

    app._poly_finish()

    assert gate == {"id": 8, "type": "polygon", "applied": False, "vertices": None}
    assert app._poly_active is True
    assert app._poly_cursor == (1.0, 2.0)
    assert app._draw_gate_id == 8
    assert len(dialogs) == 1
    assert dialogs[0][0] == "Polygon Gate"
    assert "Cannot close the polygon" in dialogs[0][1]
    assert "'vertices' is None" in dialogs[0][1]
