import numpy as np

from vflow.core.gate_definition import GateDefinition
from vflow.core.gate_masks import compute_gate_regions
from vflow.core.gate_serialization import gate_to_json_dict


class FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _crosshair_live_gate():
    return {
        'id': 4,
        'name': 'Gate 5',
        'type': 'crosshair',
        'applied': True,
        'auto_method': None,
        'color': '#123456',
        'linestyle': '-',
        'linewidth': 0.5,
        'x_boundaries': [-0.5, 0.5],
        'y_boundary': 0.0,
        'x_thresh_vars': [FakeVar(True), FakeVar(False)],
        'y_thresh_var': FakeVar(True),
        'y_boundaries': None,
        'y_thresh_vars': [],
        'x0': 0.0,
        'y0': 0.0,
        'x1': 0.0,
        'y1': 0.0,
        'vertices': [],
        '_analysis_context': {
            'x_channel': 'X', 'y_channel': 'Y',
            'x_scale': 'linear', 'y_scale': 'linear', 'cofactor': None,
        },
    }


def _mask_counts(regions):
    return {name: mask.astype(bool).tolist() for name, mask in regions.items()}


def test_gate_definition_live_adapter_removes_variable_objects_and_keeps_aliases():
    definition = GateDefinition.from_live_dict(
        _crosshair_live_gate(), variable_types=(FakeVar,))
    plain = definition.to_plain_dict()
    assert plain['x_thresh_vars'] == [True, False]
    assert plain['y_thresh_var'] is True
    assert plain['x_thresh_active'] == [True, False]
    assert plain['y_thresh_active'] is True
    assert plain['y_thresh_actives'] == []
    assert definition.gate_id == 4
    assert definition.gate_type == 'crosshair'
    assert definition.applied is True


def test_gate_definition_snapshot_is_deep_and_preserves_context():
    live = _crosshair_live_gate()
    definition = GateDefinition.from_live_dict(live, variable_types=(FakeVar,))
    plain = definition.to_plain_dict()
    live['x_boundaries'][0] = -99
    live['_analysis_context']['x_channel'] = 'Changed'
    assert plain['x_boundaries'][0] == -0.5
    assert definition.analysis_context['x_channel'] == 'X'


def test_gate_definition_serializes_identically_to_live_gate():
    live = _crosshair_live_gate()
    plain = GateDefinition.from_live_dict(live, variable_types=(FakeVar,)).to_plain_dict()
    assert gate_to_json_dict(plain) == gate_to_json_dict(live)


def test_gate_definition_crosshair_masks_match_live_gate_exactly():
    live = _crosshair_live_gate()
    plain = GateDefinition.from_live_dict(live, variable_types=(FakeVar,)).to_plain_dict()
    x = np.array([-1.0, -0.25, 0.25, 1.0])
    y = np.array([-1.0, 1.0, -1.0, 1.0])
    live_regions, live_colors = compute_gate_regions(
        live, x, y, x_scale='linear', y_scale='linear', cofactor=150.0,
        x_channel='X', y_channel='Y')
    plain_regions, plain_colors = compute_gate_regions(
        plain, x, y, x_scale='linear', y_scale='linear', cofactor=150.0,
        x_channel='X', y_channel='Y')
    assert _mask_counts(plain_regions) == _mask_counts(live_regions)
    assert plain_colors == live_colors


def test_gate_definition_shape_gate_roundtrip_preserves_mask_membership():
    for gate in [
        {'id': 1, 'type': 'rectangle', 'applied': True, 'color': '#f00',
         'x0': -1.0, 'y0': -1.0, 'x1': 1.0, 'y1': 1.0},
        {'id': 2, 'type': 'ellipse', 'applied': True, 'color': '#0f0',
         'x0': -1.0, 'y0': -1.0, 'x1': 1.0, 'y1': 1.0},
        {'id': 3, 'type': 'polygon', 'applied': True, 'color': '#00f',
         'vertices': [(-1.0, -1.0), (1.0, -1.0), (0.0, 1.0)]},
    ]:
        plain = GateDefinition.from_plain_dict(gate).to_plain_dict()
        x = np.array([0.0, 0.8, 2.0])
        y = np.array([0.0, 0.8, 2.0])
        before, colors_before = compute_gate_regions(
            gate, x, y, x_scale='linear', y_scale='linear', cofactor=150.0)
        after, colors_after = compute_gate_regions(
            plain, x, y, x_scale='linear', y_scale='linear', cofactor=150.0)
        assert _mask_counts(after) == _mask_counts(before)
        assert colors_after == colors_before


def test_polygon_boundary_membership_is_inclusive_and_winding_independent():
    points = np.array([
        [0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0],
        [5.0, 0.0], [10.0, 5.0], [5.0, 10.0], [0.0, 5.0], [5.0, 5.0],
    ])
    ccw = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    cw = list(reversed(ccw))
    masks = []
    for vertices in (ccw, cw):
        regions, _ = compute_gate_regions(
            {"id": 1, "type": "polygon", "applied": True,
             "color": "#f00", "vertices": vertices},
            points[:, 0], points[:, 1],
            x_scale="linear", y_scale="linear", cofactor=150.0,
        )
        masks.append(regions["IN"])
    assert masks[0].tolist() == [True] * len(points)
    assert masks[1].tolist() == masks[0].tolist()


def test_polygon_with_transform_invalid_vertex_fails_closed_instead_of_reconnecting_shape():
    regions, colors = compute_gate_regions(
        {"id": 1, "type": "polygon", "applied": True, "color": "#f00",
         "vertices": [(-1.0, 1.0), (1.0, 1.0), (2.0, 2.0), (1.0, 3.0)]},
        np.array([1.0, 1.5, 2.0]), np.array([1.0, 2.0, 2.0]),
        x_scale="log", y_scale="linear", cofactor=150.0,
    )
    assert regions == {}
    assert colors == []
