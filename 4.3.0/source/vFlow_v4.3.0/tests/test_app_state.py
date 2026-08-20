from __future__ import annotations

from vflow.app.state import AnalysisState


def test_analysis_state_defaults_match_v411_context():
    state = AnalysisState()
    assert state.x_channel is None
    assert state.y_channel is None
    assert state.x_scale == "asinh"
    assert state.y_scale == "asinh"
    assert state.cofactor == 150.0
    assert state.data_generation == 0
    assert state.parent_gate is None
    assert state.parent_region is None
    assert state.population_lineage == []
    assert state.context_dict() == {
        "x_channel": "",
        "y_channel": "",
        "x_scale": "asinh",
        "y_scale": "asinh",
        "cofactor": 150.0,
    }


def test_analysis_state_context_preserves_legacy_cofactor_rule():
    state = AnalysisState(
        x_channel="X",
        y_channel="Y",
        x_scale="linear",
        y_scale="biexp",
        cofactor=321.0,
    )
    # Frozen v4.1.11 only records the cofactor in gate context when an axis is
    # asinh/logicle.  Do not silently reinterpret legacy biexp during refactor.
    assert state.context_dict() == {
        "x_channel": "X",
        "y_channel": "Y",
        "x_scale": "linear",
        "y_scale": "biexp",
        "cofactor": None,
    }
    state.y_scale = "logicle"
    assert state.context_dict()["cofactor"] == 321.0


def test_analysis_state_generation_is_monotonic():
    state = AnalysisState()
    assert state.advance_data_generation() == 1
    assert state.advance_data_generation() == 2
    assert state.data_generation == 2


def test_analysis_state_instances_do_not_share_lineage():
    a = AnalysisState()
    b = AnalysisState()
    a.population_lineage.append({"region": "IN"})
    assert b.population_lineage == []


def test_analysis_state_context_equality_matches_v411_cofactor_tolerance():
    base = {
        'x_channel': 'X', 'y_channel': 'Y',
        'x_scale': 'asinh', 'y_scale': 'linear', 'cofactor': 150.0,
    }
    close = dict(base, cofactor=150.0 + 5e-13)
    far = dict(base, cofactor=150.0 + 2e-12)
    assert AnalysisState.contexts_equal(base, close)
    assert not AnalysisState.contexts_equal(base, far)
    assert not AnalysisState.contexts_equal(base, dict(base, x_channel='Other'))


def test_analysis_state_binds_gate_context_once_and_does_not_drift():
    state = AnalysisState(
        x_channel='X', y_channel='Y', x_scale='linear', y_scale='linear')
    gate = {'id': 1, 'type': 'rectangle'}
    assert state.gate_context_matches(gate)
    original = dict(gate['_analysis_context'])
    state.x_channel = 'Other'
    assert not state.gate_context_matches(gate)
    assert gate['_analysis_context'] == original


def test_analysis_state_explicit_context_binding_preserves_legacy_mapping():
    state = AnalysisState()
    gate = {'id': 1}
    context = {
        'x_channel': 'A', 'y_channel': 'B',
        'x_scale': 'log', 'y_scale': 'biexp', 'cofactor': None,
    }
    state.bind_gate_context(gate, context)
    assert gate['_analysis_context'] == context


def test_analysis_state_child_population_context_is_deep_copied():
    state = AnalysisState()
    parent_gate = {'id': 1, 'vertices': [(1.0, 2.0)]}
    lineage = [{'gate': {'id': 1}, 'region': 'IN', 'context': {'x_channel': 'X'}}]
    state.set_population_context(
        parent_gate=parent_gate,
        parent_region='IN',
        population_lineage=lineage,
    )
    parent_gate['vertices'][0] = (99.0, 99.0)
    lineage[0]['gate']['id'] = 999
    assert state.parent_gate['vertices'][0] == (1.0, 2.0)
    assert state.parent_region == 'IN'
    assert state.population_lineage[0]['gate']['id'] == 1


def test_gate_transform_change_rebinds_on_same_channels_but_channel_change_stays_incompatible():
    state = AnalysisState(
        x_channel="X", y_channel="Y", x_scale="asinh", y_scale="asinh", cofactor=150.0)
    gate = {"id": 7, "type": "rectangle"}
    state.bind_gate_context(gate)

    state.x_scale = "linear"
    assert state.gate_context_matches(gate)
    assert gate["_analysis_context"]["x_scale"] == "linear"

    state.cofactor = 300.0
    state.x_scale = "asinh"
    assert state.gate_context_matches(gate)
    assert gate["_analysis_context"]["cofactor"] == 300.0

    saved = dict(gate["_analysis_context"])
    state.y_channel = "Other"
    assert not state.gate_context_matches(gate)
    assert gate["_analysis_context"] == saved


def test_gate_returns_after_temporary_other_channel_even_if_scale_changed_there():
    state = AnalysisState(
        x_channel="X", y_channel="Y", x_scale="asinh", y_scale="asinh")
    gate = {"id": 8}
    state.bind_gate_context(gate)

    state.y_channel = "Z"
    assert not state.gate_context_matches(gate)
    state.x_scale = "linear"
    assert not state.gate_context_matches(gate)

    state.y_channel = "Y"
    assert state.gate_context_matches(gate)
    assert gate["_analysis_context"]["x_scale"] == "linear"
