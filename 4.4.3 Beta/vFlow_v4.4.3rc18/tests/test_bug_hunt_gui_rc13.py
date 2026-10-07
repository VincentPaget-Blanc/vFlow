"""Real Tk regressions for relink identity and malformed saved UI."""
import json, os, shutil
from pathlib import Path
import pytest
from tests.test_workspace_gui import experiment, new_gate
pytestmark = pytest.mark.skipif(not os.environ.get('DISPLAY') and os.name != 'nt' and os.sys.platform != 'darwin', reason='Tk display required')

def test_locate_loaded_source_retains_identity_and_population(experiment, tmp_path, monkeypatch):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    gate = new_gate(app); app._open_subgate(50., 50.); child = manager._apps[-1]
    sid = owner.sample_id(paths[0]); original_ids = set(owner.document.samples)
    child_id = child._workspace_tab_id
    copy = tmp_path / 'relocated' / 'A.csv'; copy.parent.mkdir(); shutil.copy2(paths[0], copy)
    monkeypatch.setattr('tkinter.filedialog.askopenfilename', lambda **k: str(copy))
    owner.locate_reference('sample:' + sid); root.update(); owner.capture(app)
    assert set(owner.document.samples) == original_ids
    assert owner.path_for(sid) == str(copy)
    assert len(app.loaded_files) == 3 and paths[0] not in app.loaded_files
    owner.refresh_child(child)
    assert str(copy) in child.loaded_files and len(child.loaded_files[str(copy)]) == 3
    assert sid in owner.document.tabs[child_id]['sample_ids']
    dest = tmp_path / 'relocated.vflow'; assert owner.save(path=dest); assert owner.open(dest)
    assert set(owner.document.samples) == original_ids and len(app.loaded_files) == 3

def test_locate_dialog_cannot_apply_after_workspace_replacement(experiment, tmp_path, monkeypatch):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    sid = owner.sample_id(paths[0]); calls = []
    def choose(**k): owner.clear(); return paths[0]
    monkeypatch.setattr('tkinter.filedialog.askopenfilename', choose)
    monkeypatch.setattr(owner, 'reload_resources', lambda: calls.append(True))
    owner.locate_reference('sample:' + sid)
    assert calls == [] and len(owner.document.samples) == 0

@pytest.mark.parametrize('ui', [{'current_sample_id': []}, {'selected_sample_ids': None}])
def test_malformed_ui_open_keeps_live_samples(experiment, tmp_path, ui):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    doc = owner.document; data = doc.payload(); data['tabs']['main']['ui_state'].update(ui)
    p = tmp_path / 'bad.vflow'; p.write_text(json.dumps(data))
    assert owner.open(p) is False
    assert owner.document is doc and list(app.loaded_files) == paths
    assert errors; errors.clear()

def test_missing_unloaded_exclusion_can_be_saved_and_reopened(experiment, tmp_path, monkeypatch):
    import pandas as pd
    root, manager, app, paths, errors = experiment; owner = app._workspace
    absent = str(tmp_path / 'moved-away.csv'); listing = tmp_path / 'exclusions.csv'
    pd.DataFrame({'Path': [absent]}).to_csv(listing, index=False)
    monkeypatch.setattr('tkinter.filedialog.askopenfilename', lambda **k: str(listing))
    app.load_excluded_list(); root.update()
    assert absent in app.excluded_files and app.excluded_files[absent] is None
    sid = owner.sample_id(absent); assert sid and owner.document.samples[sid].excluded
    dest = tmp_path / 'exclusions.vflow'; assert owner.save(path=dest); assert owner.open(dest)
    assert sid in owner.document.samples and owner.document.samples[sid].excluded
    assert absent in app.excluded_files and app.excluded_files[absent] is None
    assert 'sample:' + sid in owner.missing
    app._restore_file(absent); owner.capture(app)
    assert absent not in app.excluded_files and sid not in owner.document.samples

def test_population_audit_lists_only_member_samples(experiment):
    from vflow.ui.statistical_audit_dialog import StatisticalAuditDialog
    root, manager, app, paths, errors = experiment; owner = app._workspace
    new_gate(app); app.file_vars[paths[2]].set(False); app._on_active_files_changed()
    app._open_subgate(50., 50.); child = manager._apps[-1]
    members = set(owner.document.tabs[child._workspace_tab_id]['sample_ids'])
    assert owner.sample_id(paths[2]) not in members
    dialog = StatisticalAuditDialog(owner, child)
    try: assert set(dialog.samples.get_children()) == members
    finally: dialog.close()

def test_population_capture_refuses_nonmember_even_with_parent_source(experiment):
    from vflow.statistics.workspace_audit import prepare_samples
    root, manager, app, paths, errors = experiment; owner = app._workspace
    new_gate(app); app.file_vars[paths[2]].set(False); app._on_active_files_changed()
    app._open_subgate(50., 50.); child = manager._apps[-1]
    with pytest.raises(ValueError, match='population'):
        prepare_samples(owner, child, [owner.sample_id(paths[2])])

@pytest.mark.parametrize('kind', ['symlink', 'relative_missing'])
def test_unloaded_exclusion_identity_survives_repeated_capture(experiment, tmp_path, monkeypatch, kind):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    monkeypatch.chdir(tmp_path)
    if kind == 'symlink':
        raw = tmp_path / 'not-loaded.csv'; raw.write_text('X,Y\n1,2\n')
        alias = tmp_path / 'alias.csv'; alias.symlink_to(raw); path = str(alias)
    else: path = 'relative-missing.csv'
    app._dataset_state_obj().register_unloaded_exclusion(path)
    owner.capture(app); sid = owner.sample_id(path)
    assert sid and owner.document.samples[sid].excluded
    for _ in range(2):
        owner.capture(app)
        assert owner.sample_id(path) == sid and len(owner.document.samples) == 4
        assert owner.path_for(sid) == path

def test_repeated_population_reopen_does_not_add_temporary_tabs(experiment, tmp_path):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    new_gate(app); app._open_subgate(50., 50.); root.update()
    expected = set(owner.document.tabs); assert len(expected) == 2
    dest = tmp_path / 'populations.vflow'; assert owner.save(path=dest)
    for _ in range(3):
        assert owner.open(dest); root.update()
        assert set(owner.document.tabs) == expected and len(manager._apps) == 2
        assert owner.save()

def test_relink_refreshes_every_child_and_preserves_inactive_choice(experiment, tmp_path, monkeypatch):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    new_gate(app); app._open_subgate(50., 50.); first = manager._apps[-1]
    app._open_subgate(50., 50.); second = manager._apps[-1]
    first.file_vars[paths[0]].set(False); first._on_active_files_changed()
    sid = owner.sample_id(paths[0]); dest = tmp_path / 'children.vflow'; assert owner.save(path=dest)
    moved = tmp_path / 'moved.csv'; shutil.copy2(paths[0], moved)
    monkeypatch.setattr('tkinter.filedialog.askopenfilename', lambda **k: str(moved))
    owner.locate_reference('sample:' + sid)
    assert owner.save()
    assert str(moved) in first.loaded_files and str(moved) in second.loaded_files
    assert not first.file_vars[str(moved)].get()
    for tab in owner.document.tabs.values():
        assert all(isinstance(value, str) for value in tab.get('ui_state', {}).get('active_sample_ids', []))
    assert owner.open(dest) and len(manager._apps) == 3
