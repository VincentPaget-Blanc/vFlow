from vflow.core.gates import (
    active_x_boundaries,
    active_y_boundaries,
    append_polygon_vertex,
    begin_gate_draw,
    bounded_horizontal_line_distance,
    bounded_vertical_line_distance,
    clicked_subgate_region,
    closed_polygon_points,
    crosshair_corner_label_position,
    crosshair_preview_boundaries,
    ellipse_area,
    ellipse_center_radii,
    ellipse_preview_geometry,
    ellipse_perimeter_points,
    finite_point_pairs,
    gate_by_id,
    gate_control_points,
    gate_geometry_summary_lines,
    gate_handles,
    gate_preview_style,
    gate_snapshot,
    handle_cache_entry,
    handle_display_mode,
    handle_marker_style,
    hover_cursor_for_cached_handles,
    hover_state_changed,
    is_degenerate_shape_gate,
    is_finite_point,
    line_hover_test_plan,
    manual_crosshair_gate,
    nearest_cached_handle,
    new_gate_dict,
    point_distance,
    point_in_ellipse,
    point_in_rectangle,
    point_to_segment_distance,
    polygon_area,
    polygon_gate_can_finish,
    polygon_preview_points,
    polygon_rubber_band_points,
    rectangle_area,
    rectangle_bounds,
    rectangle_preview_geometry,
    rectangle_line_segments,
    remove_gate_and_select_neighbor,
    should_draw_gate_preview,
    smaller_area_hit,
    subgate_candidate_order,
    update_gate_from_control_points,
    update_gate_draw,
    update_gate_from_handle_drag,
    visible_handle_gate_ids,
)


class Flag:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def test_gate_by_id():
    gates = [{"id": 1}, {"id": 2, "name": "two"}]

    assert gate_by_id(gates, 2) == {"id": 2, "name": "two"}
    assert gate_by_id(gates, 3) is None


def test_manual_crosshair_gate_returns_only_non_auto_crosshair():
    auto = {"id": 1, "type": "crosshair", "auto_method": "gmm"}
    manual = {"id": 2, "type": "crosshair", "auto_method": None}
    rectangle = {"id": 3, "type": "rectangle", "auto_method": None}

    assert manual_crosshair_gate([auto, rectangle, manual]) is manual
    assert manual_crosshair_gate([auto, rectangle]) is None


def test_subgate_candidate_order_selected_first_then_applied():
    selected = {"id": 1, "applied": False}
    applied = {"id": 2, "applied": True}
    other = {"id": 3, "applied": True}
    unapplied = {"id": 4, "applied": False}

    assert subgate_candidate_order([applied, selected, other, unapplied], selected) == [
        selected,
        applied,
        other,
    ]
    assert subgate_candidate_order([applied, unapplied, other], None) == [applied, other]


def test_clicked_subgate_region_skips_empty_and_shape_out():
    crosshair = {"type": "crosshair"}
    rectangle = {"type": "rectangle"}

    assert clicked_subgate_region(
        crosshair,
        {"A": [False, False], "B": [False, True]},
    ) == "B"
    assert clicked_subgate_region(
        rectangle,
        {"OUT": [True], "IN": [False]},
    ) is None
    assert clicked_subgate_region(
        rectangle,
        {"OUT": [True], "IN": [True]},
    ) == "IN"


def test_remove_gate_and_select_neighbor():
    gates = [{"id": 1}, {"id": 2}, {"id": 3}]

    remaining, selected = remove_gate_and_select_neighbor(
        gates,
        gate_id_value=2,
        selected_gate_id=2,
    )
    assert remaining == [{"id": 1}, {"id": 3}]
    assert selected == 3

    remaining, selected = remove_gate_and_select_neighbor(
        gates,
        gate_id_value=3,
        selected_gate_id=3,
    )
    assert remaining == [{"id": 1}, {"id": 2}]
    assert selected == 2

    remaining, selected = remove_gate_and_select_neighbor(
        gates,
        gate_id_value=1,
        selected_gate_id=3,
    )
    assert remaining == [{"id": 2}, {"id": 3}]
    assert selected == 3

    remaining, selected = remove_gate_and_select_neighbor(
        [{"id": 1}],
        gate_id_value=1,
        selected_gate_id=1,
    )
    assert remaining == []
    assert selected is None


def test_active_boundaries_accept_tk_like_flags():
    gate = {
        "type": "crosshair",
        "x_boundaries": [1.0, 2.0, 3.0],
        "x_thresh_vars": [Flag(True), Flag(False), Flag(True)],
        "y_boundaries": [4.0, 5.0],
        "y_thresh_vars": [Flag(False), Flag(True)],
    }

    assert active_x_boundaries(gate) == [1.0, 3.0]
    assert active_y_boundaries(gate) == [5.0]


def test_active_boundaries_fall_back_when_flag_lengths_mismatch():
    gate = {
        "type": "crosshair",
        "x_boundaries": [1.0, 2.0],
        "x_thresh_vars": [Flag(False)],
        "y_boundary": 0.0,
        "y_thresh_var": Flag(True),
    }

    assert active_x_boundaries(gate) == [1.0, 2.0]
    assert active_y_boundaries(gate) == [0.0]


def test_gate_snapshot_skips_excluded_value_types():
    gate = {
        "id": 1,
        "x0": 2.0,
        "flag": Flag(True),
    }

    assert gate_snapshot(gate, excluded_types=(Flag,)) == {"id": 1, "x0": 2.0}
    assert gate_snapshot(gate)["flag"] is gate["flag"]


def test_new_gate_dict_preserves_legacy_defaults_and_mutable_lists_are_fresh():
    gate = new_gate_dict(
        gate_id_value=2,
        gate_type_value="rectangle",
        color="#123456",
        auto_method="gmm",
    )
    other = new_gate_dict(
        gate_id_value=3,
        gate_type_value="crosshair",
        color="#abcdef",
    )

    assert gate == {
        "id": 2,
        "name": "Gate 3",
        "type": "rectangle",
        "applied": False,
        "auto_method": "gmm",
        "color": "#123456",
        "linestyle": "-",
        "linewidth": 0.5,
        "x_boundaries": [],
        "y_boundary": None,
        "x_thresh_vars": [],
        "y_thresh_var": None,
        "y_boundaries": None,
        "y_thresh_vars": [],
        "x0": 0.0,
        "y0": 0.0,
        "x1": 0.0,
        "y1": 0.0,
        "vertices": [],
    }
    gate["x_boundaries"].append(1.0)
    assert other["x_boundaries"] == []


def test_gate_handles_for_rectangle_and_polygon():
    rectangle = {
        "type": "rectangle",
        "x0": 0.0,
        "y0": 1.0,
        "x1": 4.0,
        "y1": 5.0,
    }
    polygon = {"type": "polygon", "vertices": [(1.0, 2.0), (3.0, 4.0)]}

    assert gate_handles(rectangle) == [
        {"x": 0.0, "y": 1.0, "handle": "nw", "idx": 0},
        {"x": 4.0, "y": 1.0, "handle": "ne", "idx": 1},
        {"x": 4.0, "y": 5.0, "handle": "se", "idx": 2},
        {"x": 0.0, "y": 5.0, "handle": "sw", "idx": 3},
        {"x": 2.0, "y": 3.0, "handle": "center", "idx": 4},
    ]
    assert gate_handles(polygon) == [
        {"x": 1.0, "y": 2.0, "handle": "vertex", "idx": 0},
        {"x": 3.0, "y": 4.0, "handle": "vertex", "idx": 1},
    ]
    assert gate_handles({"type": "crosshair"}) == []


def test_handle_cache_entry():
    handle = {"x": 1.0, "y": 2.0, "handle": "nw", "idx": 0}

    assert handle_cache_entry(handle, lambda point: (point[0] + 10, point[1] + 20)) == (
        11.0,
        22.0,
        "nw",
        0,
    )

    def raises(_point):
        raise RuntimeError("no transform")

    assert handle_cache_entry(handle, raises) is None


def test_gate_control_points():
    rectangle = {"type": "rectangle", "x0": 1.0, "y0": 2.0, "x1": 3.0, "y1": 4.0}
    ellipse = {"type": "ellipse", "x0": 5.0, "y0": 6.0, "x1": 7.0, "y1": 8.0}
    polygon = {"type": "polygon", "vertices": [(1.0, 2.0), (3.0, 4.0)]}

    assert gate_control_points(rectangle) == [(1.0, 2.0), (3.0, 4.0)]
    assert gate_control_points(ellipse) == [(5.0, 6.0), (7.0, 8.0)]
    assert gate_control_points(polygon) == [(1.0, 2.0), (3.0, 4.0)]
    assert gate_control_points({"type": "crosshair"}) == []


def test_crosshair_corner_label_position():
    assert crosshair_corner_label_position("TH+/D1R-") == (
        0.02,
        0.97,
        "left",
        "top",
    )
    assert crosshair_corner_label_position("TH-/D1R+") == (
        0.98,
        0.03,
        "right",
        "bottom",
    )
    assert crosshair_corner_label_position("TH(m)/D1R+") is None
    assert crosshair_corner_label_position("IN") is None


def test_point_to_segment_distance():
    assert point_distance(0.0, 0.0, 3.0, 4.0) == 5.0
    assert point_to_segment_distance(5.0, 3.0, 0.0, 0.0, 10.0, 0.0) == 3.0
    assert point_to_segment_distance(13.0, 4.0, 0.0, 0.0, 10.0, 0.0) == 5.0
    assert point_to_segment_distance(3.0, 4.0, 0.0, 0.0, 0.0, 0.0) == 5.0
    assert bounded_vertical_line_distance(8.0, 5.0, 3.0, y_min=1.0, y_max=9.0) == 5.0
    assert bounded_vertical_line_distance(
        8.0, 10.0, 3.0, y_min=1.0, y_max=9.0
    ) == float("inf")
    assert bounded_horizontal_line_distance(8.0, 5.0, 3.0, x_min=1.0, x_max=9.0) == 2.0
    assert bounded_horizontal_line_distance(
        10.0, 5.0, 3.0, x_min=1.0, x_max=9.0
    ) == float("inf")


def test_update_gate_from_handle_drag_for_shape_and_polygon():
    rect = {"type": "rectangle", "x0": 0.0, "y0": 0.0, "x1": 4.0, "y1": 4.0}
    orig = dict(rect)

    update_gate_from_handle_drag(rect, handle="ne", idx=1, orig=orig, x=6.0, y=1.0)
    assert rect == {"type": "rectangle", "x0": 0.0, "y0": 1.0, "x1": 6.0, "y1": 4.0}

    update_gate_from_handle_drag(rect, handle="center", idx=4, orig=orig, x=3.0, y=5.0)
    assert rect == {"type": "rectangle", "x0": 1.0, "y0": 3.0, "x1": 5.0, "y1": 7.0}

    poly = {"type": "polygon", "vertices": [(0.0, 0.0), (1.0, 1.0)]}
    update_gate_from_handle_drag(poly, handle="vertex", idx=1, orig={}, x=2.0, y=3.0)
    assert poly["vertices"] == [(0.0, 0.0), (2.0, 3.0)]


def test_update_gate_from_control_points():
    rect = {"type": "rectangle"}
    update_gate_from_control_points(rect, [(1, 2), (3, 4)])
    assert rect == {"type": "rectangle", "x0": 1.0, "y0": 2.0, "x1": 3.0, "y1": 4.0}

    poly = {"type": "polygon"}
    update_gate_from_control_points(poly, [(1, 2), (3, 4), (5, 6)])
    assert poly["vertices"] == [(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)]


def test_draw_geometry_helpers():
    crosshair = {}
    begin_gate_draw(crosshair, "crosshair", 1.0, 2.0)
    assert crosshair == {"type": "crosshair", "x_boundaries": [1.0], "y_boundary": 2.0}
    update_gate_draw(crosshair, 3.0, 4.0)
    assert crosshair["x_boundaries"] == [3.0]
    assert crosshair["y_boundary"] == 4.0

    rect = {}
    begin_gate_draw(rect, "rectangle", 5.0, 6.0)
    assert rect == {
        "type": "rectangle",
        "x0": 5.0,
        "y0": 6.0,
        "x1": 5.0,
        "y1": 6.0,
    }
    assert is_degenerate_shape_gate(rect)
    update_gate_draw(rect, 7.0, 8.0)
    assert rect["x1"] == 7.0
    assert rect["y1"] == 8.0
    assert not is_degenerate_shape_gate(rect)

    poly = {}
    begin_gate_draw(poly, "polygon", 1.0, 2.0)
    append_polygon_vertex(poly, 3.0, 4.0)
    assert poly == {"type": "polygon", "vertices": [(1.0, 2.0), (3.0, 4.0)]}
    assert not is_degenerate_shape_gate(poly)


def test_polygon_gate_can_finish():
    assert not polygon_gate_can_finish(None)
    assert not polygon_gate_can_finish({"type": "rectangle", "vertices": [(1, 2)] * 3})
    assert not polygon_gate_can_finish({"type": "polygon", "vertices": [(1, 2), (3, 4)]})
    assert polygon_gate_can_finish(
        {"type": "polygon", "vertices": [(1, 2), (3, 4), (5, 6)]}
    )


def test_gate_geometry_summary_lines():
    rectangle = {
        "type": "rectangle",
        "applied": True,
        "x0": 5.0,
        "y0": 9.0,
        "x1": 1.0,
        "y1": 3.0,
    }
    ellipse = {
        "type": "ellipse",
        "applied": False,
        "x0": 0.0,
        "y0": 2.0,
        "x1": 4.0,
        "y1": 8.0,
    }
    polygon = {
        "type": "polygon",
        "applied": True,
        "vertices": [(1.0, 2.0), (3.0, 4.0)],
    }

    assert gate_geometry_summary_lines(rectangle) == (
        ["  X: 1.0 → 5.0", "  Y: 3.0 → 9.0"],
        ["  Drag ◼ handles to reshape"],
    )
    assert gate_geometry_summary_lines(ellipse) == (
        ["  Centre: (2.0, 5.0)", "  a=2.0  b=3.0"],
        [],
    )
    assert gate_geometry_summary_lines(polygon, polygon_active=True) == (
        ["  2 vertices  (drawing…)"],
        ["  Click ✓ Close Polygon or dbl-click", "  Drag ◼ handles to reshape"],
    )


def test_gate_preview_helpers():
    empty_polygon = {"type": "polygon", "vertices": [], "applied": False}
    empty_rectangle = {
        "id": 2,
        "type": "rectangle",
        "x0": 1.0,
        "y0": 2.0,
        "x1": 1.0,
        "y1": 2.0,
        "applied": False,
    }
    applied_rectangle = dict(empty_rectangle, applied=True, color="#123456")

    assert not should_draw_gate_preview(empty_polygon)
    assert not should_draw_gate_preview(empty_rectangle)
    assert should_draw_gate_preview(applied_rectangle)
    assert gate_preview_style(
        applied_rectangle,
        selected_gate_id=2,
        default_color="#000000",
    ) == {"color": "#123456", "linestyle": "-", "linewidth": 1.3}
    assert gate_preview_style(
        empty_rectangle,
        selected_gate_id=None,
        default_color="#000000",
    ) == {"color": "#000000", "linestyle": "--", "linewidth": 0.5}

    rect = {"type": "rectangle", "x0": 5.0, "y0": 6.0, "x1": 1.0, "y1": 2.0}
    ellipse = {"type": "ellipse", "x0": 0.0, "y0": 2.0, "x1": 4.0, "y1": 8.0}
    assert rectangle_preview_geometry(rect) == (1.0, 2.0, 4.0, 4.0)
    assert ellipse_preview_geometry(ellipse) == (2.0, 5.0, 4.0, 6.0)

    polygon = {"type": "polygon", "vertices": [(1.0, 2.0), (3.0, 4.0)]}
    assert polygon_preview_points(polygon) == ([1.0, 3.0], [2.0, 4.0])
    polygon["applied"] = True
    assert polygon_preview_points(polygon) == ([1.0, 3.0, 1.0], [2.0, 4.0, 2.0])


def test_gate_interior_geometry_helpers():
    rectangle = {"type": "rectangle", "x0": 5.0, "y0": 6.0, "x1": 1.0, "y1": 2.0}
    ellipse = {"type": "ellipse", "x0": 0.0, "y0": 0.0, "x1": 4.0, "y1": 2.0}

    bounds = rectangle_bounds(rectangle)
    assert bounds == (1.0, 5.0, 2.0, 6.0)
    assert point_in_rectangle(3.0, 4.0, bounds)
    assert not point_in_rectangle(6.0, 4.0, bounds)
    assert rectangle_area(bounds) == 16.0

    center_radii = ellipse_center_radii(ellipse)
    assert center_radii == (2.0, 1.0, 2.0, 1.0)
    assert point_in_ellipse(2.0, 1.0, center_radii)
    assert not point_in_ellipse(5.0, 1.0, center_radii)
    assert ellipse_area(2.0, 1.0) == 2.0 * 3.141592653589793
    assert polygon_area([(0.0, 0.0), (4.0, 0.0), (4.0, 3.0)]) == 6.0
    assert polygon_area([(0.0, 0.0), (1.0, 1.0)]) == 0.0
    assert is_finite_point(1.0, "2.0")
    assert not is_finite_point(float("nan"), 2.0)
    assert finite_point_pairs([1.0, float("inf"), "3.0"], [2.0, 4.0, "5.0"]) == [
        (1.0, 2.0),
        (3.0, 5.0),
    ]


def test_smaller_area_hit():
    best = {"id": 1}
    candidate = {"id": 2}

    assert smaller_area_hit(best, 10.0, candidate, inside=False, area=1.0) == (best, 10.0)
    assert smaller_area_hit(best, 10.0, candidate, inside=True, area=12.0) == (best, 10.0)
    assert smaller_area_hit(best, 10.0, candidate, inside=True, area=2.0) == (
        candidate,
        2.0,
    )


def test_gate_line_geometry_helpers():
    rectangle = {"type": "rectangle", "x0": 1.0, "y0": 2.0, "x1": 4.0, "y1": 6.0}
    ellipse = {"type": "ellipse", "x0": 0.0, "y0": 0.0, "x1": 4.0, "y1": 2.0}
    polygon = {"type": "polygon", "vertices": [(1.0, 2.0), (3.0, 4.0)]}

    assert rectangle_line_segments(rectangle) == [
        ((1.0, 2.0), (4.0, 2.0)),
        ((4.0, 2.0), (4.0, 6.0)),
        ((4.0, 6.0), (1.0, 6.0)),
        ((1.0, 6.0), (1.0, 2.0)),
    ]
    pts = ellipse_perimeter_points(ellipse, n_points=4)
    assert pts[0] == (4.0, 1.0)
    assert round(pts[1][0], 12) == 2.0
    assert pts[1][1] == 2.0
    assert round(pts[2][0], 12) == 0.0
    assert round(pts[2][1], 12) == 1.0
    assert closed_polygon_points(polygon) == [(1.0, 2.0), (3.0, 4.0), (1.0, 2.0)]
    assert closed_polygon_points({"type": "polygon", "vertices": [(1.0, 2.0)]}) == []


def test_polygon_rubber_band_points():
    gate = {"id": 2, "type": "polygon"}
    xs = [1.0, 3.0]
    ys = [2.0, 4.0]

    assert polygon_rubber_band_points(
        gate,
        xs,
        ys,
        polygon_active=True,
        polygon_cursor=(5.0, 6.0),
        draw_gate_id=2,
    ) == ([3.0, 5.0], [4.0, 6.0])
    assert polygon_rubber_band_points(
        gate,
        xs,
        ys,
        polygon_active=False,
        polygon_cursor=(5.0, 6.0),
        draw_gate_id=2,
    ) is None
    assert polygon_rubber_band_points(
        gate,
        xs,
        ys,
        polygon_active=True,
        polygon_cursor=(5.0, 6.0),
        draw_gate_id=3,
    ) is None


def test_crosshair_preview_boundaries():
    applied = {
        "type": "crosshair",
        "applied": True,
        "x_boundaries": [1.0, 2.0],
        "x_thresh_vars": [Flag(True), Flag(False)],
        "y_boundaries": [3.0, 4.0],
        "y_thresh_vars": [Flag(False), Flag(True)],
    }
    in_progress_single = {
        "type": "crosshair",
        "applied": False,
        "x_boundaries": [5.0],
        "y_boundary": 6.0,
    }
    in_progress_multi = {
        "type": "crosshair",
        "applied": False,
        "x_boundaries": [7.0],
        "y_boundary": 8.0,
        "y_boundaries": [9.0, 10.0],
    }

    assert crosshair_preview_boundaries(applied) == ([1.0], [4.0])
    assert crosshair_preview_boundaries(in_progress_single) == ([5.0], [6.0])
    assert crosshair_preview_boundaries(in_progress_multi) == ([7.0], [9.0, 10.0])


def test_handle_display_mode_priority():
    assert handle_display_mode(
        2,
        drag_gate_id=2,
        interior_hover_gate_id=2,
        hover_gate_id=2,
        hover_handle_key=(2, "nw", 0),
    ) == "drag"
    assert handle_display_mode(
        2,
        interior_hover_gate_id=2,
        hover_gate_id=2,
        hover_handle_key=(2, "nw", 0),
    ) == "interior"
    assert handle_display_mode(2, hover_gate_id=2, hover_handle_key=(2, "nw", 0)) == (
        "handle_hover"
    )
    assert handle_display_mode(2, hover_gate_id=2) == "line_hover"
    assert handle_display_mode(2) == "pinned"


def test_visible_handle_gate_ids_preserves_legacy_truthy_filter():
    assert visible_handle_gate_ids(
        drag_gate_id=1,
        hover_gate_id=2,
        pinned_gate_id=3,
        interior_hover_gate_id=4,
    ) == {1, 2, 3, 4}
    assert visible_handle_gate_ids(
        drag_gate_id=0,
        hover_gate_id=None,
        pinned_gate_id=0,
        interior_hover_gate_id=None,
    ) == set()


def test_handle_marker_style():
    key = (2, "nw", 0)
    inactive_key = (2, "ne", 1)

    assert handle_marker_style(
        "drag",
        handle_key=key,
        color="#123456",
        drag_handle_key=key,
    ) == {"marker": "s", "ms": 9, "mfc": "#123456", "mew": 1.5}
    assert handle_marker_style(
        "drag",
        handle_key=inactive_key,
        color="#123456",
        drag_handle_key=key,
    ) == {"marker": "o", "ms": 7, "mfc": "none", "mew": 0.5}
    assert handle_marker_style("interior", handle_key=key, color="#123456") == {
        "marker": "o",
        "ms": 8,
        "mfc": "#123456",
        "mew": 1.5,
    }
    assert handle_marker_style(
        "handle_hover",
        handle_key=inactive_key,
        color="#123456",
        hover_handle_key=key,
    ) is None
    assert handle_marker_style(
        "handle_hover",
        handle_key=key,
        color="#123456",
        hover_handle_key=key,
    ) == {"marker": "s", "ms": 9, "mfc": "#123456", "mew": 1.5}
    assert handle_marker_style("line_hover", handle_key=key, color="#123456") == {
        "marker": "o",
        "ms": 7,
        "mfc": "none",
        "mew": 0.5,
    }
    assert handle_marker_style("pinned", handle_key=key, color="#123456") == {
        "marker": "o",
        "ms": 8,
        "mfc": "#12345655",
        "mew": 2.0,
    }


def test_cached_handle_helpers():
    entries = [
        (0.0, 0.0, "center", 4),
        (10.0, 0.0, "ne", 1),
        (20.0, 0.0, "sw", 3),
    ]

    assert nearest_cached_handle(
        entries,
        gate_id_value=7,
        x=11.0,
        y=0.0,
        threshold=3.0,
    ) == ((7, "ne", 1), 1.0)
    assert nearest_cached_handle(
        entries,
        gate_id_value=7,
        x=15.0,
        y=0.0,
        threshold=3.0,
    ) is None
    assert hover_cursor_for_cached_handles(
        entries,
        x=0.5,
        y=0.0,
        threshold=3.0,
    ) == "fleur"
    assert hover_cursor_for_cached_handles(
        entries,
        x=10.5,
        y=0.0,
        threshold=3.0,
    ) == "sizing"
    assert hover_cursor_for_cached_handles(
        entries,
        x=15.0,
        y=0.0,
        threshold=3.0,
    ) == "hand2"


def test_line_hover_test_plan():
    assert line_hover_test_plan(
        new_hover=2,
        current_hover_gate_id=None,
        current_pos=(10.0, 10.0),
        last_line_test_pos=None,
    ) == (False, None)
    assert line_hover_test_plan(
        new_hover=None,
        current_hover_gate_id=2,
        current_pos=(10.0, 10.0),
        last_line_test_pos=(1.0, 1.0),
    ) == (True, (1.0, 1.0))
    assert line_hover_test_plan(
        new_hover=None,
        current_hover_gate_id=None,
        current_pos=(10.0, 10.0),
        last_line_test_pos=None,
    ) == (True, (10.0, 10.0))
    assert line_hover_test_plan(
        new_hover=None,
        current_hover_gate_id=None,
        current_pos=(15.0, 12.0),
        last_line_test_pos=(10.0, 10.0),
    ) == (False, (10.0, 10.0))
    assert line_hover_test_plan(
        new_hover=None,
        current_hover_gate_id=None,
        current_pos=(22.0, 12.0),
        last_line_test_pos=(10.0, 10.0),
    ) == (True, (22.0, 12.0))


def test_hover_state_changed():
    assert not hover_state_changed(
        new_hover=1,
        old_hover=1,
        new_hover_handle_key=(1, "nw", 0),
        old_hover_handle_key=(1, "nw", 0),
        new_interior=None,
        old_interior=None,
    )
    assert hover_state_changed(
        new_hover=2,
        old_hover=1,
        new_hover_handle_key=(1, "nw", 0),
        old_hover_handle_key=(1, "nw", 0),
        new_interior=None,
        old_interior=None,
    )
    assert hover_state_changed(
        new_hover=1,
        old_hover=1,
        new_hover_handle_key=(1, "ne", 1),
        old_hover_handle_key=(1, "nw", 0),
        new_interior=None,
        old_interior=None,
    )
    assert hover_state_changed(
        new_hover=1,
        old_hover=1,
        new_hover_handle_key=(1, "nw", 0),
        old_hover_handle_key=(1, "nw", 0),
        new_interior=3,
        old_interior=None,
    )
