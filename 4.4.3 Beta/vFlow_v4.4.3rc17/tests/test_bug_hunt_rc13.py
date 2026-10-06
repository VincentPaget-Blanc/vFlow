"""RC13 persistence and filtered batch acquisition regressions."""
import json
from pathlib import Path
import pytest
from vflow.workspace.model import Workspace

BAD_UI = [
    {'current_sample_id': []}, {'selected_sample_ids': None},
    {'selected_sample_ids': [None]}, {'active_sample_ids': None},
    {'active_sample_ids': [{}]}, {'view_mode': []},
    {'sidebar_width': 1e309}, {'sidebar_width': True},
    {'workspace_name': []}, {'interface_size': []},
    {'selected_gate_id': []}, {'active_tab_id': {}},
    {'sidebar_width': 1e100}, {'sample_panel_fraction': 1e308},
]
@pytest.mark.parametrize('ui', BAD_UI)
@pytest.mark.parametrize('where', ['workspace', 'tab'])
def test_workspace_ui_validated_before_restore(tmp_path, ui, where):
    d = Workspace().payload()
    if where == 'workspace': d['ui_state'].update(ui)
    else: d['tabs']['main'] = {'ui_state': ui}
    p = tmp_path / 'bad.vflow'; p.write_text(json.dumps(d))
    with pytest.raises(ValueError): Workspace.load(p)

@pytest.mark.parametrize('change', [
    {'overlay_view': {'transform_parameters': ['bad']}},
    {'overlay_view': {'x_transform_params': ['bad']}},
    {'axis_aliases': {'X': ['wrong']}},
    {'tabs': {'main': {'sections': {'PLOT': 'not-a-boolean'}}}},
    {'tabs': {'main': {'lineage': [{'workspace_tab_id': []}]}}},
    {'tabs': {'main': {'lineage': [{'gate_id': []}]}}},
    {'tabs': {'main': {'lineage': [{'region': []}]}}},
])
def test_nested_workspace_metadata_is_rejected(tmp_path, change):
    d = Workspace().payload(); d.update(change)
    p = tmp_path / 'bad.vflow'; p.write_text(json.dumps(d))
    with pytest.raises(ValueError): Workspace.load(p)

def test_family_excluded_acquisition_cannot_be_overwritten(tmp_path):
    from tests.test_v43_batch_stats_runner import _base_adapters, _request
    from vflow.services.batch_stats_runner import BatchStatsRunner
    excluded = tmp_path / 'family_1___CytoFile.csv'
    excluded.write_text('X,Y\n1,2\n3,4\n')
    protected = tmp_path / 'family_2___CytoFile.csv'
    protected.write_text('X,Y\n11,12\n13,14\n'); before = protected.read_bytes()
    (tmp_path / 'other___CytoFile.csv').write_text('X,Y\n1,2\n3,4\n')
    # The family member is skipped, so is absent from target_files and excluded_files.
    target = protected
    with pytest.raises(ValueError, match='replace'):
        BatchStatsRunner(_base_adapters()).run(_request(tmp_path, save_path=str(target), excluded_files={str(excluded)}))
    assert protected.read_bytes() == before
