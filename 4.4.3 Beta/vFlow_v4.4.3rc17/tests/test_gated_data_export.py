import pytest

np = pytest.importorskip("numpy")

from vflow.services.gated_data_export import (
    assign_gated_cells,
    build_gated_export_frames,
    gate_export_order,
)


def test_gate_export_order_shapes_before_crosshair():
    crosshair = {"name": "Cross", "type": "crosshair"}
    rectangle = {"name": "Rect", "type": "rectangle"}
    polygon = {"name": "Poly", "type": "polygon"}

    assert gate_export_order([crosshair, rectangle, polygon]) == [
        rectangle,
        polygon,
        crosshair,
    ]


def test_shape_gates_take_priority_over_crosshair_assignment():
    crosshair = {"name": "Cross", "type": "crosshair"}
    rectangle = {"name": "Rect", "type": "rectangle"}

    masks = {
        "Cross": {
            "Q1": np.array([True, True, True, True]),
        },
        "Rect": {
            "IN": np.array([False, True, True, False]),
            "OUT": np.array([True, False, False, True]),
        },
    }

    assignment = assign_gated_cells(
        [crosshair, rectangle],
        4,
        lambda gate: masks[gate["name"]],
    )

    assert assignment["mask"].tolist() == [True, True, True, True]
    assert assignment["gate"].tolist() == ["Cross", "Rect", "Rect", "Cross"]
    assert assignment["region"].tolist() == ["Q1", "IN", "IN", "Q1"]
    assert assignment["type"].tolist() == [
        "crosshair",
        "rectangle",
        "rectangle",
        "crosshair",
    ]


def test_shape_out_region_is_not_exported():
    rectangle = {"name": "Rect", "type": "rectangle"}

    assignment = assign_gated_cells(
        [rectangle],
        3,
        lambda _gate: {
            "IN": np.array([True, False, False]),
            "OUT": np.array([False, True, True]),
        },
    )

    assert assignment["mask"].tolist() == [True, False, False]
    assert assignment["gate"].tolist() == ["Rect", "", ""]


def test_build_gated_export_frames_no_gates_exports_raw_with_source_file():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"X": [1.0, 2.0]})

    frames = build_gated_export_frames(
        active_files={"/tmp/sample.csv": df},
        applied_gates=[],
        x_channel="X",
        y_channel="Y",
        regions_for_gate=lambda *_args: {},
    )

    assert len(frames) == 1
    assert frames[0]["Source_File"].tolist() == ["sample.csv", "sample.csv"]
    assert frames[0]["Source_Path"].tolist() == ["/tmp/sample.csv", "/tmp/sample.csv"]
    assert frames[0]["X"].tolist() == [1.0, 2.0]


def test_build_gated_export_frames_rejects_missing_axes():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"X": [1.0]})

    with pytest.raises(ValueError, match="required gate axes"):
        build_gated_export_frames(
            active_files={"/tmp/sample.csv": df},
            applied_gates=[{"id": 1, "name": "Gate", "type": "rectangle"}],
            x_channel="X",
            y_channel="Y",
            regions_for_gate=lambda *_args: {},
        )


def test_build_gated_export_frames_keeps_only_assigned_cells():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"X": [1.0, 2.0, 3.0], "Y": [1.0, 2.0, 3.0]})
    gate = {"id": 7, "name": "Gate", "type": "rectangle"}

    frames = build_gated_export_frames(
        active_files={"/tmp/sample.csv": df},
        applied_gates=[gate],
        x_channel="X",
        y_channel="Y",
        regions_for_gate=lambda _path, _gate, _x, _y: {
            "IN": np.array([False, True, False]),
            "OUT": np.array([True, False, True]),
        },
    )

    assert frames[0]["Source_File"].tolist() == ["sample.csv"]
    assert frames[0]["Source_Path"].tolist() == ["/tmp/sample.csv"]
    assert frames[0]["X"].tolist() == [2.0]
    assert frames[0]["Y"].tolist() == [2.0]
    assert frames[0]["Gate_ID"].tolist() == [7]
    assert frames[0]["Gate_Name"].tolist() == ["Gate"]
    assert frames[0]["Gate_Region"].tolist() == ["IN"]
    assert frames[0]["Gate_Type"].tolist() == ["rectangle"]


def test_assignment_rejects_wrong_length_region_mask():
    with pytest.raises(ValueError, match="mask length"):
        assign_gated_cells(
            [{"id": 1, "name": "Gate", "type": "rectangle"}], 3,
            lambda _gate: {"IN": np.array([True, False])},
        )


def test_gated_export_disambiguates_duplicate_basenames():
    pd = pytest.importorskip("pandas")
    frames = build_gated_export_frames(
        active_files={
            "/a/run/sample.csv": pd.DataFrame({"X": [1.0]}),
            "/b/run/sample.csv": pd.DataFrame({"X": [2.0]}),
        },
        applied_gates=[],
        x_channel="X", y_channel="Y", regions_for_gate=lambda *_args: {},
    )
    labels = [frame["Source_File"].iloc[0] for frame in frames]
    assert len(set(labels)) == 2
    assert all("sample.csv" in label for label in labels)
