"""Targeted release regressions for unavailable members and modal Save As."""
import os
from pathlib import Path
import pytest
from tests.test_workspace_gui import experiment, new_gate
from tests.format_fixtures import write_fixture

pytestmark = pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='Tk display required')

@pytest.mark.parametrize('failure', ['missing', 'decode'])
@pytest.mark.parametrize('remove_index', [0, 1])
def test_unavailable_members_stay_independent(experiment, tmp_path, monkeypatch, failure, remove_index):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    a, _ = write_fixture(tmp_path/'a.fcs', types=('I','I'), bits=(16,16), names=('X','Y'), rows=[(1,2),(3,4),(5,6)])
    b, _ = write_fixture(tmp_path/'b.fcs', types=('I','I'), bits=(16,16), names=('X','Y'), rows=[(9,8),(7,6),(5,4)])
    source = tmp_path/'plate.lmd'; raw = a.read_bytes()+b.read_bytes(); source.write_bytes(raw)
    app._load_paths([str(source)]); owner.capture(app)
    ids = [s.sample_id for s in owner.document.samples.values() if s.source.absolute_path == str(source)]
    assert len(ids) == 2
    for sid in ids: app._exclude_file(owner.path_for(sid))
    expected = set(owner.document.samples); dest = tmp_path/'members.vflow'; assert owner.save(path=dest)
    moved = tmp_path/'moved.lmd'
    if failure == 'missing': source.rename(moved)
    import vflow.io.registry as registry
    reader = registry.read_flow_source
    def unavailable(path):
        if str(path) == str(source): raise ValueError('Temporary container decoder failure')
        return reader(path)
    with monkeypatch.context() as patch:
        if failure == 'decode': patch.setattr(registry, 'read_flow_source', unavailable)
        assert owner.open(dest)
        keys = [owner.path_for(sid) for sid in ids]
        assert len(set(keys)) == 2 and len(app.excluded_files) == 2
        assert all(app.excluded_files[k] is None and owner.sample_id(k) == sid for k, sid in zip(keys, ids))
        for _ in range(2):
            owner.capture(app); assert set(owner.document.samples) == expected
            assert owner.save() and owner.open(dest)
        removed = ids[remove_index]; remaining = ids[1-remove_index]
        app._restore_file(owner.path_for(removed)); owner.capture(app)
        assert removed not in owner.document.samples and remaining in owner.document.samples
        assert len(app.excluded_files) == 1 and owner.document.samples[remaining].excluded
        assert owner.save()
    if failure == 'missing': moved.rename(source)
    monkeypatch.setattr('tkinter.filedialog.askopenfilename', lambda **k: str(source))
    owner.locate_reference('sample:'+remaining)
    assert len(app.excluded_files[owner.path_for(remaining)]) == 3
    app._restore_file(owner.path_for(remaining)); owner.capture(app)
    assert removed not in owner.document.samples and remaining in owner.document.samples
    assert len(app.loaded_files) == 4 and not app.excluded_files
    assert owner.save() and owner.open(dest) and set(owner.document.samples) == expected-{removed}
    assert source.read_bytes() == raw

@pytest.mark.parametrize('replacement', ['clear', 'reopen'])
def test_save_as_modal_rechecks_workspace(experiment, tmp_path, monkeypatch, replacement):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    old = tmp_path/'original.vflow'; assert owner.save(path=old)
    target = tmp_path/'stale-dialog.vflow'
    def choose(**k):
        if replacement == 'clear': owner.clear()
        else: assert owner.open(old)
        return str(target)
    monkeypatch.setattr('tkinter.filedialog.asksaveasfilename', choose)
    assert owner.save(save_as=True) is False
    assert not target.exists() and not owner.dirty
    assert owner.path == (str(old) if replacement == 'reopen' else None)

def test_failed_workspace_replace_keeps_saved_revision_and_edits(experiment, tmp_path, monkeypatch):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    new_gate(app); dest = tmp_path/'atomic.vflow'; assert owner.save(path=dest)
    before = dest.read_bytes(); previous = Path(owner.document.default_gate_session.absolute_path)
    old_gate = previous.read_bytes(); owner.rename('Unsaved edited name')
    app._sel_gate()['x1'] = 70.; app.refresh_plot(); owner.capture(app)
    import vflow.workspace.model as model
    replace = model.os.replace
    def fail(source, target):
        if Path(target) == dest: raise OSError('Injected workspace replace failure')
        return replace(source, target)
    with monkeypatch.context() as patch:
        patch.setattr(model.os, 'replace', fail)
        assert owner.save() is False
    assert dest.read_bytes() == before and previous.read_bytes() == old_gate
    assert owner.workspace_name() == 'Unsaved edited name' and owner.dirty and owner.gates_dirty
    assert errors and 'Injected' in str(errors[-1]); errors.clear()
    assert owner.save() and owner.open(dest) and owner.workspace_name() == 'Unsaved edited name'

def test_save_as_includes_edits_made_while_dialog_is_open(experiment, tmp_path, monkeypatch):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    gate = new_gate(app); gid = gate['id']; sid = owner.sample_id(paths[0])
    dest = tmp_path/'edited-during-dialog.vflow'
    def choose(**k):
        app._workspace_name_entry.focus_force(); app._workspace_name_var.set('Edited while choosing destination')
        app.file_vars[paths[0]].set(False); app._sel_gate()['x1'] = 70.
        return str(dest)
    monkeypatch.setattr('tkinter.filedialog.asksaveasfilename', choose)
    assert owner.save(save_as=True) and owner.open(dest)
    assert owner.workspace_name() == 'Edited while choosing destination'
    assert not app.file_vars[paths[0]].get() and not owner.document.samples[sid].active
    assert owner.stores['main'].resolve_gate(sid,gid)['x1'] == 70.
