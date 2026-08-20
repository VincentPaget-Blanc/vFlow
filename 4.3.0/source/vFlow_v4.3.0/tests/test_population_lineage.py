import copy
import json

from vflow.app.lineage import (
    LineageStage,
    PopulationLineage,
    append_legacy_stage,
    copy_legacy_lineage,
)
from vflow.legacy.vflow_app import FlowApp


def _stage_payload():
    return {
        'gate': {
            'id': 3,
            'name': 'Gate 3',
            'type': 'rectangle',
            'vertices': [(1.0, 2.0), (3.0, 4.0)],
            '_analysis_context': {'x_channel': 'X', 'y_channel': 'Y'},
        },
        'region': 'IN',
        'context': {
            'x_channel': 'X',
            'y_channel': 'Y',
            'x_scale': 'asinh',
            'y_scale': 'linear',
            'cofactor': 150.0,
        },
    }


def test_typed_lineage_round_trip_preserves_legacy_payload_exactly():
    legacy = [_stage_payload()]
    typed = PopulationLineage.from_legacy_list(legacy)
    out = typed.to_legacy_list()
    assert out == legacy
    assert out is not legacy
    assert out[0] is not legacy[0]
    assert out[0]['gate'] is not legacy[0]['gate']


def test_lineage_stage_from_components_emits_exact_legacy_schema():
    payload = _stage_payload()
    stage = LineageStage.from_components(
        gate=payload['gate'], region=payload['region'], context=payload['context'])
    assert list(stage.to_legacy_dict()) == ['gate', 'region', 'context']
    assert stage.to_legacy_dict() == payload


def test_append_legacy_stage_matches_v411_deepcopy_plus_append_semantics():
    source = [_stage_payload()]
    new_payload = _stage_payload()
    new_payload['region'] = 'OUT'
    stage = LineageStage.from_components(
        gate=new_payload['gate'], region=new_payload['region'], context=new_payload['context'])
    expected = copy.deepcopy(source) + [stage.to_legacy_dict()]
    actual = append_legacy_stage(source, stage)
    assert actual == expected
    actual[0]['gate']['name'] = 'changed'
    assert source[0]['gate']['name'] == 'Gate 3'


def test_copy_legacy_lineage_retains_legacy_container_contract():
    source = [_stage_payload()]
    copied = copy_legacy_lineage(source)
    assert isinstance(copied, list)
    assert isinstance(copied[0], dict)
    assert copied == source
    copied[0]['context']['x_channel'] = 'Other'
    assert source[0]['context']['x_channel'] == 'X'


def test_lineage_signature_is_byte_for_byte_equivalent_to_v411_algorithm():
    lineage = [_stage_payload()]
    expected = json.dumps(
        lineage or [], sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, default=str)
    assert PopulationLineage.legacy_signature(lineage) == expected
    assert FlowApp._lineage_signature(lineage) == expected
