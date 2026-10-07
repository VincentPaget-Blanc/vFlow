import copy

from vflow.app.state import AnalysisState
from vflow.services.gate_session import (
    build_gate_session_payload,
    validate_gate_context_payload,
)


def test_build_gate_session_payload_v3_adds_transform_provenance_without_changing_linear_context():
    state = AnalysisState(
        x_channel='X', y_channel='Y', x_scale='linear', y_scale='linear', cofactor=150.0)
    gate_with_context = {
        'id': 1, 'name': 'A', 'type': 'rectangle', 'applied': True,
        'x0': 0.0, 'y0': 0.0, 'x1': 1.0, 'y1': 1.0,
        '_analysis_context': {
            'x_channel': 'X', 'y_channel': 'Y',
            'x_scale': 'linear', 'y_scale': 'linear', 'cofactor': None,
        },
    }
    gate_without_context = {
        'id': 2, 'name': 'B', 'type': 'ellipse', 'applied': False,
        'x0': 0.0, 'y0': 0.0, 'x1': 2.0, 'y1': 2.0,
    }
    lineage = [{'gate': {'id': 9}, 'region': 'IN', 'context': {'x_channel': 'A'}}]
    payload = build_gate_session_payload(
        [gate_with_context, gate_without_context],
        analysis_state=state, population_lineage=lineage)
    assert payload['version'] == 3
    assert payload['x_channel'] == 'X'
    assert payload['y_channel'] == 'Y'
    assert payload['x_scale'] == 'linear'
    assert payload['y_scale'] == 'linear'
    assert payload['cofactor'] is None
    assert payload['x_transform_params'] is None
    assert payload['y_transform_params'] is None
    assert payload['gate_contexts']['1'] == gate_with_context['_analysis_context']
    assert payload['gate_contexts']['2'] == state.context_dict()
    assert payload['population_lineage'] == lineage


def test_build_gate_session_payload_deep_copies_lineage():
    state = AnalysisState()
    lineage = [{'gate': {'vertices': [(1.0, 2.0)]}, 'region': 'IN', 'context': {}}]
    payload = build_gate_session_payload([], analysis_state=state, population_lineage=lineage)
    lineage[0]['gate']['vertices'][0] = (99.0, 99.0)
    assert payload['population_lineage'][0]['gate']['vertices'][0] == (1.0, 2.0)


def test_validate_gate_context_payload_exact_v411_rules():
    ok, why = validate_gate_context_payload({
        'x_channel': 'X', 'y_channel': 'Y',
        'x_scale': 'linear', 'y_scale': 'linear', 'cofactor': None,
    })
    assert ok, why
    ok, why = validate_gate_context_payload({
        'x_channel': 'X', 'y_channel': 'Y',
        'x_scale': 'asinh', 'y_scale': 'linear', 'cofactor': None,
    })
    assert not ok and why == 'missing/non-numeric cofactor'
    ok, why = validate_gate_context_payload({
        'x_channel': 'X', 'y_channel': 'Y',
        'x_scale': 'logicle', 'y_scale': 'linear', 'cofactor': float('inf'),
    })
    assert not ok and why == 'cofactor must be finite and > 0'
    ok, why = validate_gate_context_payload({
        'x_channel': '', 'y_channel': 'Y',
        'x_scale': 'linear', 'y_scale': 'linear', 'cofactor': None,
    })
    assert not ok and why == 'missing X channel'

from vflow.services.gate_session import prepare_gate_session_load


def test_prepare_gate_session_load_v2_sanitizes_and_validates_contexts_without_tk():
    payload = {
        'version': 2,
        'gates': [
            {'id': 7, 'name': 'Good', 'type': 'rectangle', 'applied': True,
             'x0': 0, 'y0': 0, 'x1': 1, 'y1': 1},
            {'id': 8, 'name': 'Bad geometry', 'type': 'polygon', 'applied': True,
             'vertices': [(0, 0), (1, 1)]},
        ],
        'gate_contexts': {
            '7': {'x_channel': 'X', 'y_channel': 'Y',
                  'x_scale': 'linear', 'y_scale': 'linear', 'cofactor': None},
        },
    }
    prep = prepare_gate_session_load(payload, gate_file_version=2, current_next_id=3)
    assert [g['id'] for g in prep.clean_gates] == [7]
    assert prep.skipped_count == 1
    assert prep.contexts_container_valid is True
    assert prep.context_errors == ()
    assert prep.saved_contexts == payload['gate_contexts']


def test_prepare_gate_session_load_v2_reports_missing_context_for_surviving_gate():
    payload = {
        'gates': [{'id': 4, 'name': 'A', 'type': 'ellipse', 'applied': True,
                   'x0': 0, 'y0': 0, 'x1': 2, 'y1': 2}],
        'gate_contexts': {},
    }
    prep = prepare_gate_session_load(payload, gate_file_version=2, current_next_id=0)
    assert prep.contexts_container_valid is True
    assert prep.context_errors == ('Gate A: context is not an object',)


def test_prepare_gate_session_load_rejects_nonobject_v2_context_container_without_mutating_gates():
    payload = {
        'gates': [{'id': 1, 'name': 'A', 'type': 'crosshair', 'applied': False}],
        'gate_contexts': [],
    }
    prep = prepare_gate_session_load(payload, gate_file_version=2, current_next_id=0)
    assert len(prep.clean_gates) == 1
    assert prep.contexts_container_valid is False
    assert prep.saved_contexts is None
    assert prep.context_errors == ()


def test_prepare_gate_session_load_v1_does_not_require_contexts():
    payload = {'gates': [{'id': 2, 'name': 'A', 'type': 'crosshair', 'applied': False}]}
    prep = prepare_gate_session_load(payload, gate_file_version=1, current_next_id=0)
    assert len(prep.clean_gates) == 1
    assert prep.saved_contexts is None
    assert prep.contexts_container_valid is True


def test_loaded_gate_is_transposed_only_for_same_channel_pair_reversed():
    from vflow.services.gate_session import transpose_loaded_gate_for_current_axes

    gate = {
        'id': 7, 'name': 'R', 'type': 'rectangle', 'applied': True,
        'x0': 1.0, 'y0': 10.0, 'x1': 3.0, 'y1': 20.0,
        'x_boundaries': [], 'y_boundary': None,
        'x_thresh_active': [], 'y_thresh_active': True,
        'y_boundaries': None, 'y_thresh_actives': [], 'vertices': [],
    }
    context = {
        'x_channel': 'A', 'y_channel': 'B',
        'x_scale': 'logicle_gml2', 'y_scale': 'asinh', 'cofactor': 150.0,
        'x_transform_params': {'T': 262144.0, 'W': 0.5, 'M': 4.5, 'A': 0.0},
    }
    moved, moved_ctx, swapped = transpose_loaded_gate_for_current_axes(
        gate, context, current_x='B', current_y='A')
    assert swapped is True
    assert (moved['x0'], moved['y0'], moved['x1'], moved['y1']) == (10.0, 1.0, 20.0, 3.0)
    assert moved_ctx['x_channel'] == 'B'
    assert moved_ctx['y_channel'] == 'A'
    assert moved_ctx['x_scale'] == 'asinh'
    assert moved_ctx['y_scale'] == 'logicle_gml2'
    assert moved_ctx['y_transform_params'] == context['x_transform_params']

    unchanged, unchanged_ctx, swapped = transpose_loaded_gate_for_current_axes(
        gate, context, current_x='C', current_y='A')
    assert swapped is False
    assert unchanged == gate
    assert unchanged_ctx == context
