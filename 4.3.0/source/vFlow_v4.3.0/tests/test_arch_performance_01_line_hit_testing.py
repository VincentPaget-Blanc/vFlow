import math

import numpy as np
from matplotlib.figure import Figure

from vflow.core.gates import (
    closed_polygon_points,
    ellipse_perimeter_points,
    point_to_polyline_min_distance,
    point_to_segment_distance,
    rectangle_line_segments,
)
from vflow.legacy.vflow_app import FlowApp


class _Event:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class _App:
    pass


def _legacy_shape_line_hit(app, event, threshold_px=8):
    ex, ey = event.x, event.y

    def data_to_px(dx, dy):
        try:
            return app.ax.transData.transform((dx, dy))
        except Exception:
            return None

    try:
        app.ax.get_window_extent()
    except Exception:
        return None

    best_gid, best_dist = None, float("inf")
    for gate in app.gates:
        if not gate.get("applied"):
            continue
        gid = gate["id"]
        gt = gate.get("type", "crosshair")
        if gt == "rectangle":
            for a_pt, b_pt in rectangle_line_segments(gate):
                pa = data_to_px(*a_pt)
                pb = data_to_px(*b_pt)
                if pa is None or pb is None:
                    continue
                d = point_to_segment_distance(ex, ey, pa[0], pa[1], pb[0], pb[1])
                if d < threshold_px and d < best_dist:
                    best_dist, best_gid = d, gid
        elif gt == "ellipse":
            pts = [data_to_px(*pt) for pt in ellipse_perimeter_points(gate, n_points=64)]
            pts = [p for p in pts if p is not None]
            for i in range(len(pts)):
                pa, pb = pts[i], pts[(i + 1) % len(pts)]
                d = point_to_segment_distance(ex, ey, pa[0], pa[1], pb[0], pb[1])
                if d < threshold_px and d < best_dist:
                    best_dist, best_gid = d, gid
        elif gt == "polygon":
            closed = closed_polygon_points(gate)
            if not closed:
                continue
            for i in range(len(closed) - 1):
                pa = data_to_px(*closed[i])
                pb = data_to_px(*closed[i + 1])
                if pa is None or pb is None:
                    continue
                d = point_to_segment_distance(ex, ey, pa[0], pa[1], pb[0], pb[1])
                if d < threshold_px and d < best_dist:
                    best_dist, best_gid = d, gid
    return best_gid


def test_vectorized_polyline_distance_matches_scalar_segments():
    rng = np.random.default_rng(42001)
    for closed in (False, True):
        for _ in range(400):
            n = int(rng.integers(2, 30))
            pts = rng.normal(size=(n, 2)) * 100.0
            if rng.random() < 0.2:
                pts[int(rng.integers(0, n))] = pts[0]
            px, py = rng.normal(size=2) * 100.0
            if closed:
                pairs = [(pts[i], pts[(i + 1) % n]) for i in range(n)]
            else:
                pairs = list(zip(pts[:-1], pts[1:]))
            expected = min(
                point_to_segment_distance(px, py, a[0], a[1], b[0], b[1])
                for a, b in pairs
            )
            actual = point_to_polyline_min_distance(px, py, pts, closed=closed)
            assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)


def test_vectorized_polyline_ignores_nonfinite_segments_like_threshold_comparisons():
    pts = np.array([[0.0, 0.0], [10.0, 0.0], [np.nan, 2.0], [20.0, 0.0]])
    assert point_to_polyline_min_distance(5.0, 3.0, pts) == 3.0


def test_shape_line_hit_matches_legacy_reference_randomized():
    fig = Figure(figsize=(8, 6), dpi=100)
    ax = fig.add_subplot(111)
    ax.set_xlim(-20, 80)
    ax.set_ylim(-20, 80)
    app = _App()
    app.ax = ax
    rng = np.random.default_rng(42002)
    gates = []
    for gid in range(18):
        kind = ("rectangle", "ellipse", "polygon")[gid % 3]
        cx, cy = rng.uniform(-5, 65, size=2)
        if kind in ("rectangle", "ellipse"):
            dx, dy = rng.uniform(1, 12, size=2)
            gate = {
                "id": gid,
                "applied": True,
                "type": kind,
                "x0": cx - dx,
                "y0": cy - dy,
                "x1": cx + dx,
                "y1": cy + dy,
            }
        else:
            count = int(rng.integers(3, 16))
            angles = np.sort(rng.uniform(0, 2 * np.pi, size=count))
            radii = rng.uniform(2, 12, size=count)
            gate = {
                "id": gid,
                "applied": True,
                "type": "polygon",
                "vertices": [
                    (cx + r * np.cos(a), cy + r * np.sin(a))
                    for a, r in zip(angles, radii)
                ],
            }
        gates.append(gate)
    app.gates = gates

    for _ in range(500):
        event = _Event(*rng.uniform(0, 800, size=2))
        assert FlowApp._hit_test_gate_line(app, event, threshold_px=8) == _legacy_shape_line_hit(
            app, event, threshold_px=8
        )


class _BBox:
    x0 = 0.0
    x1 = 1000.0
    y0 = 0.0
    y1 = 1000.0


class _CountingTransform:
    def __init__(self, *, reject_batches=False):
        self.calls = 0
        self.reject_batches = reject_batches

    def transform(self, values):
        self.calls += 1
        arr = np.asarray(values, dtype=float)
        if self.reject_batches and arr.ndim == 2:
            raise RuntimeError("batch unsupported")
        return arr * 10.0 + np.array([100.0, 100.0])


class _Axes:
    def __init__(self, transform):
        self.transData = transform

    def get_window_extent(self):
        return _BBox()


def test_ellipse_line_hit_uses_one_batch_transform_on_normal_path():
    transform = _CountingTransform()
    app = _App()
    app.ax = _Axes(transform)
    app.gates = [{
        "id": 1,
        "applied": True,
        "type": "ellipse",
        "x0": 0.0,
        "y0": 0.0,
        "x1": 10.0,
        "y1": 8.0,
    }]
    FlowApp._hit_test_gate_line(app, _Event(150.0, 100.0), threshold_px=8)
    assert transform.calls == 1


def test_batch_transform_failure_falls_back_to_scalar_shape_hit_testing():
    transform = _CountingTransform(reject_batches=True)
    app = _App()
    app.ax = _Axes(transform)
    app.gates = [{
        "id": 7,
        "applied": True,
        "type": "ellipse",
        "x0": 0.0,
        "y0": 0.0,
        "x1": 10.0,
        "y1": 8.0,
    }]
    event = _Event(150.0, 100.0)
    assert FlowApp._hit_test_gate_line(app, event, threshold_px=8) == _legacy_shape_line_hit(
        app, event, threshold_px=8
    )
    assert transform.calls > 64

from matplotlib.path import Path as MplPath
from vflow.core.gates import (
    ellipse_area,
    ellipse_center_radii,
    finite_point_pairs,
    is_finite_point,
    point_in_ellipse,
    point_in_rectangle,
    polygon_area,
    rectangle_area,
    rectangle_bounds,
    smaller_area_hit,
)
from vflow.core.transforms import forward_transform


class _DataEvent:
    def __init__(self, x, y):
        self.xdata = x
        self.ydata = y


def _legacy_interior_hit(app, event):
    x, y = event.xdata, event.ydata
    if x is None or y is None:
        return None
    best, best_area = None, float("inf")
    for gate in app.gates:
        if not gate.get("applied"):
            continue
        gt = gate.get("type", "crosshair")
        inside = False
        area = float("inf")
        if gt == "rectangle":
            bounds = rectangle_bounds(gate)
            xlo, xhi, ylo, yhi = bounds
            inside = point_in_rectangle(x, y, bounds)
            try:
                xs_t = app._fwd(np.array([xlo, xhi], float), app.x_scale)
                ys_t = app._fwd(np.array([ylo, yhi], float), app.y_scale)
                if np.all(np.isfinite(xs_t)) and np.all(np.isfinite(ys_t)):
                    area = float((xs_t[1] - xs_t[0]) * (ys_t[1] - ys_t[0]))
                else:
                    area = rectangle_area(bounds)
            except Exception:
                area = rectangle_area(bounds)
        elif gt == "ellipse":
            cx, cy, rx, ry = ellipse_center_radii(gate)
            if rx > 0 and ry > 0:
                inside = point_in_ellipse(x, y, (cx, cy, rx, ry))
                try:
                    xs_t = app._fwd(np.array([cx-rx, cx+rx], float), app.x_scale)
                    ys_t = app._fwd(np.array([cy-ry, cy+ry], float), app.y_scale)
                    if np.all(np.isfinite(xs_t)) and np.all(np.isfinite(ys_t)):
                        area = float(np.pi * (xs_t[1] - xs_t[0]) / 2
                                     * (ys_t[1] - ys_t[0]) / 2)
                    else:
                        area = ellipse_area(rx, ry)
                except Exception:
                    area = ellipse_area(rx, ry)
        elif gt == "polygon":
            verts = gate.get("vertices", [])
            if len(verts) >= 3:
                try:
                    vx_t = app._fwd(
                        np.asarray([v[0] for v in verts], dtype=float), app.x_scale)
                    vy_t = app._fwd(
                        np.asarray([v[1] for v in verts], dtype=float), app.y_scale)
                    x_t = float(app._fwd(np.asarray([x], dtype=float), app.x_scale)[0])
                    y_t = float(app._fwd(np.asarray([y], dtype=float), app.y_scale)[0])
                    verts_t = finite_point_pairs(vx_t, vy_t)
                    if len(verts_t) >= 3 and is_finite_point(x_t, y_t):
                        path = MplPath(verts_t + [verts_t[0]])
                        inside = path.contains_point((x_t, y_t))
                        area = polygon_area(verts_t)
                except Exception:
                    pass
        best, best_area = smaller_area_hit(
            best, best_area, gate, inside=inside, area=area)
    return best


def test_interior_hit_matches_legacy_reference_randomized_supported_scales():
    rng = np.random.default_rng(42003)
    app = _App()
    app.cofactor = 150.0
    app._fwd = lambda values, scale: forward_transform(values, scale, app.cofactor)
    gates = []
    for gid in range(30):
        kind = ("rectangle", "ellipse", "polygon")[gid % 3]
        cx, cy = rng.uniform(1, 1000, size=2)
        if kind in ("rectangle", "ellipse"):
            dx, dy = rng.uniform(0.5, 80, size=2)
            gate = {
                "id": gid, "applied": True, "type": kind,
                "x0": cx - dx, "x1": cx + dx,
                "y0": cy - dy, "y1": cy + dy,
            }
        else:
            count = int(rng.integers(3, 12))
            angles = np.sort(rng.uniform(0, 2*np.pi, count))
            radii = rng.uniform(2, 80, count)
            gate = {
                "id": gid, "applied": True, "type": "polygon",
                "vertices": [
                    (cx + r*np.cos(a), cy + r*np.sin(a))
                    for a, r in zip(angles, radii)
                ],
            }
        gates.append(gate)
    app.gates = gates

    for scale in ("linear", "asinh", "biexp", "logicle"):
        app.x_scale = scale
        app.y_scale = scale
        for _ in range(120):
            event = _DataEvent(*rng.uniform(1, 1000, size=2))
            assert FlowApp._hit_test_gate_interior(app, event) == _legacy_interior_hit(app, event)


class _FwdCounter:
    def __init__(self):
        self.calls = 0

    def __call__(self, values, scale):
        self.calls += 1
        return np.asarray(values, dtype=float)


def test_outside_rectangle_and_ellipse_skip_transform_space_area_work():
    counter = _FwdCounter()
    app = _App()
    app._fwd = counter
    app.x_scale = app.y_scale = "linear"
    app.gates = [
        {"id": 1, "applied": True, "type": "rectangle",
         "x0": 10.0, "x1": 20.0, "y0": 10.0, "y1": 20.0},
        {"id": 2, "applied": True, "type": "ellipse",
         "x0": 30.0, "x1": 40.0, "y0": 30.0, "y1": 40.0},
    ]
    assert FlowApp._hit_test_gate_interior(app, _DataEvent(-10.0, -10.0)) is None
    assert counter.calls == 0


def test_polygon_raw_bbox_rejection_skips_all_transforms():
    counter = _FwdCounter()
    app = _App()
    app._fwd = counter
    app.x_scale = app.y_scale = "linear"
    app.gates = [{
        "id": 3, "applied": True, "type": "polygon",
        "vertices": [(10.0, 10.0), (20.0, 10.0), (15.0, 20.0)],
    }]
    assert FlowApp._hit_test_gate_interior(app, _DataEvent(100.0, 100.0)) is None
    assert counter.calls == 0


def test_polygon_event_transform_is_reused_across_candidates():
    counter = _FwdCounter()
    app = _App()
    app._fwd = counter
    app.x_scale = app.y_scale = "linear"
    app.gates = [
        {"id": 4, "applied": True, "type": "polygon",
         "vertices": [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]},
        {"id": 5, "applied": True, "type": "polygon",
         "vertices": [(-5.0, -5.0), (15.0, -5.0), (15.0, 15.0), (-5.0, 15.0)]},
    ]
    assert FlowApp._hit_test_gate_interior(app, _DataEvent(5.0, 5.0))["id"] == 4
    # 2 vertex transforms per polygon + one X and one Y event transform total.
    assert counter.calls == 6


def test_handle_cache_entries_batch_matches_scalar_entries():
    from vflow.core.gates import handle_cache_entries, handle_cache_entry

    handles = [
        {"x": 1.0, "y": 2.0, "handle": "nw", "idx": 0},
        {"x": 3.0, "y": 4.0, "handle": "se", "idx": 1},
        {"x": -2.0, "y": 5.0, "handle": "center", "idx": 2},
    ]

    def transform(points):
        arr = np.asarray(points, dtype=float)
        return arr * np.array([2.0, -3.0]) + np.array([7.0, 11.0])

    expected = [handle_cache_entry(handle, transform) for handle in handles]
    assert handle_cache_entries(handles, transform) == expected


def test_handle_cache_entries_uses_one_batch_transform_on_success():
    from vflow.core.gates import handle_cache_entries

    handles = [
        {"x": float(i), "y": float(i + 1), "handle": "vertex", "idx": i}
        for i in range(25)
    ]
    shapes = []

    def transform(points):
        arr = np.asarray(points, dtype=float)
        shapes.append(arr.shape)
        return arr + 10.0

    entries = handle_cache_entries(handles, transform)
    assert len(entries) == 25
    assert shapes == [(25, 2)]


def test_handle_cache_entries_batch_failure_falls_back_per_handle_fail_closed():
    from vflow.core.gates import handle_cache_entries

    handles = [
        {"x": 1.0, "y": 2.0, "handle": "a", "idx": 0},
        {"x": 99.0, "y": 3.0, "handle": "bad", "idx": 1},
        {"x": 4.0, "y": 5.0, "handle": "c", "idx": 2},
    ]
    calls = []

    def transform(points):
        arr = np.asarray(points, dtype=float)
        calls.append(arr.shape)
        if arr.ndim == 2:
            raise RuntimeError("batch unavailable")
        if arr[0] == 99.0:
            raise RuntimeError("one bad handle")
        return arr + 1.0

    assert handle_cache_entries(handles, transform) == [
        (2.0, 3.0, "a", 0),
        (5.0, 6.0, "c", 2),
    ]
    assert calls == [(3, 2), (2,), (2,), (2,)]


def test_rectangle_and_polygon_line_hits_use_one_batch_transform_each():
    for gate in (
        {"id": 10, "applied": True, "type": "rectangle",
         "x0": 0.0, "y0": 0.0, "x1": 10.0, "y1": 8.0},
        {"id": 11, "applied": True, "type": "polygon",
         "vertices": [(0.0, 0.0), (10.0, 0.0), (8.0, 8.0), (1.0, 6.0)]},
    ):
        transform = _CountingTransform()
        app = _App()
        app.ax = _Axes(transform)
        app.gates = [gate]
        FlowApp._hit_test_gate_line(app, _Event(150.0, 100.0), threshold_px=8)
        assert transform.calls == 1
