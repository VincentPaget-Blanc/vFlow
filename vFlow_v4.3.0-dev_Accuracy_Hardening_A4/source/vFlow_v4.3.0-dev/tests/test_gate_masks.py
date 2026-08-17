import pytest

np = pytest.importorskip("numpy")

from vflow.core.gate_masks import (
    compute_gate_regions,
    region_masks,
    selected_region_mask,
)


def test_crosshair_region_masks_quadrants():
    x = np.array([-1.0, 1.0, -1.0, 1.0])
    y = np.array([-1.0, -1.0, 1.0, 1.0])

    regions, _ = region_masks(
        x,
        y,
        [0.0],
        0.0,
        x_channel="Intensity_X",
        y_channel="Intensity_Y",
    )

    assert list(regions) == ["Y+/X-", "Y+/X+", "Y-/X-", "Y-/X+"]
    assert regions["Y+/X-"].tolist() == [False, False, True, False]
    assert regions["Y-/X+"].tolist() == [False, True, False, False]


def test_crosshair_multi_boundary_grid():
    x = np.array([-2.0, 0.0, 2.0])
    y = np.array([-2.0, 0.0, 2.0])

    regions, _ = region_masks(
        x,
        y,
        [-1.0, 1.0],
        None,
        y_boundaries=[-1.0, 1.0],
        x_channel="X",
        y_channel="Y",
    )

    assert "Y+/X+" in regions
    assert "Y(m)/X(m)" in regions
    assert regions["Y(m)/X(m)"].tolist() == [False, True, False]


def test_rectangle_gate_mask():
    gate = {
        "applied": True,
        "type": "rectangle",
        "x0": 0.0,
        "x1": 2.0,
        "y0": 0.0,
        "y1": 2.0,
    }

    regions, _ = compute_gate_regions(
        gate,
        np.array([1.0, 3.0]),
        np.array([1.0, 1.0]),
        x_scale="linear",
        y_scale="linear",
        cofactor=150.0,
    )

    assert regions["IN"].tolist() == [True, False]
    assert regions["OUT"].tolist() == [False, True]


def test_ellipse_gate_mask_and_degenerate_skip():
    gate = {
        "applied": True,
        "type": "ellipse",
        "x0": -1.0,
        "x1": 1.0,
        "y0": -1.0,
        "y1": 1.0,
    }

    regions, _ = compute_gate_regions(
        gate,
        np.array([0.0, 2.0]),
        np.array([0.0, 0.0]),
        x_scale="linear",
        y_scale="linear",
        cofactor=150.0,
    )

    assert regions["IN"].tolist() == [True, False]

    gate["x1"] = gate["x0"]
    assert compute_gate_regions(
        gate,
        np.array([0.0]),
        np.array([0.0]),
        x_scale="linear",
        y_scale="linear",
        cofactor=150.0,
    ) == ({}, [])


def test_polygon_gate_mask_when_matplotlib_is_available():
    pytest.importorskip("matplotlib")

    gate = {
        "applied": True,
        "type": "polygon",
        "vertices": [(0.0, 0.0), (2.0, 0.0), (0.0, 2.0)],
    }

    regions, _ = compute_gate_regions(
        gate,
        np.array([0.25, 2.0]),
        np.array([0.25, 2.0]),
        x_scale="linear",
        y_scale="linear",
        cofactor=150.0,
    )

    assert regions["IN"].tolist() == [True, False]


def test_selected_region_mask_combines_crosshair_regions():
    regions = {
        "A": np.array([True, False, False]),
        "B": np.array([False, True, False]),
    }

    mask = selected_region_mask(regions, total=3, region_name="All regions")

    assert mask.tolist() == [True, True, False]


def test_selected_region_mask_excludes_shape_gate_out_from_all_regions():
    regions = {
        "IN": np.array([True, False, False]),
        "OUT": np.array([False, True, True]),
    }

    mask = selected_region_mask(
        regions,
        total=3,
        gate_type="rectangle",
        region_name="All regions",
    )

    assert mask.tolist() == [True, False, False]


def test_selected_region_mask_returns_named_region_and_rejects_unknown_region():
    regions = {"IN": np.array([True, False])}

    assert selected_region_mask(
        regions,
        total=2,
        region_name="IN",
    ).tolist() == [True, False]
    with pytest.raises(KeyError):
        selected_region_mask(
            regions,
            total=2,
            region_name="missing",
        )


def test_unknown_selected_region_fails_closed():
    with pytest.raises(KeyError):
        selected_region_mask(
            {"IN": np.array([True, False])}, total=2, region_name="MISSING"
        )

def test_shape_out_excludes_log_invalid_events():
    gate = {
        "type": "rectangle", "applied": True,
        "x0": 1.0, "x1": 10.0, "y0": 0.0, "y1": 10.0,
    }
    regions, _ = compute_gate_regions(
        gate, np.array([-1.0, 2.0, 20.0]), np.array([1.0, 1.0, 1.0]),
        x_scale="log", y_scale="linear", cofactor=150.0,
    )
    assert regions["IN"].tolist() == [False, True, False]
    assert regions["OUT"].tolist() == [False, False, True]

def test_gate_mask_rejects_mismatched_axis_lengths():
    gate = {"type": "rectangle", "applied": True, "x0": 0, "x1": 1, "y0": 0, "y1": 1}
    with pytest.raises(ValueError):
        compute_gate_regions(
            gate, np.array([0.0, 1.0]), np.array([0.0]),
            x_scale="linear", y_scale="linear", cofactor=150.0,
        )
