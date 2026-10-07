"""Native regressions: unreadable exclusions, audit lifetimes and modal edits."""
import gc
import os
import threading
import time
import weakref
from pathlib import Path
import pandas as pd
import pytest
from tests.test_workspace_gui import experiment
from vflow.ui.statistical_audit_dialog import StatisticalAuditDialog, AuditResultsDialog
from vflow.statistics.workspace_audit import prepare_samples, commit
from vflow.statistics import run_audit
from vflow.statistics.models import AuditCancelled

pytestmark = pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='Tk display required')

@pytest.mark.parametrize('extension', ['csv', 'mqd'])
def test_unreadable_excluded_source_survives_reopen(experiment, tmp_path, extension):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    source = tmp_path / ('unreadable.' + extension); source.write_bytes(b'\xff\xfe\x00invalid source')
    listing = tmp_path / 'excluded.csv'; pd.DataFrame({'Path': [str(source)]}).to_csv(listing, index=False)
    from tkinter import filedialog
    old = filedialog.askopenfilename
    try:
        filedialog.askopenfilename = lambda **k: str(listing)
        app.load_excluded_list()
    finally: filedialog.askopenfilename = old
    sid = owner.sample_id(str(source)); dest = tmp_path / 'excluded.vflow'
    assert owner.save(path=dest) and owner.open(dest)
    assert owner.document.samples[sid].excluded and 'sample:' + sid in owner.missing
    assert str(source) in app.excluded_files and app.excluded_files[str(source)] is None
    assert list(app.loaded_files) == paths and source.read_bytes() == b'\xff\xfe\x00invalid source'
    assert owner.save() and owner.open(dest)
    assert sid in owner.document.samples and str(source) in app.excluded_files

@pytest.mark.parametrize('moved', [False, True])
def test_locate_missing_exclusion_can_restore_decoded_events(experiment, tmp_path, monkeypatch, moved):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    source = tmp_path / 'missing.csv'
    app._dataset_state_obj().register_unloaded_exclusion(str(source)); owner.capture(app)
    sid = owner.sample_id(str(source)); dest = tmp_path / 'missing.vflow'
    assert owner.save(path=dest) and owner.open(dest)
    found = tmp_path / 'found.csv' if moved else source
    found.write_text('X,Y\n1,2\n3,4\n5,6\n')
    monkeypatch.setattr('tkinter.filedialog.askopenfilename', lambda **k: str(found))
    owner.locate_reference('sample:' + sid)
    assert owner.document.samples[sid].excluded and 'sample:' + sid not in owner.missing
    assert app.excluded_files[str(found)] is not None
    app._restore_file(str(found)); owner.capture(app)
    assert sid in owner.document.samples and not owner.document.samples[sid].excluded
    assert len(app.loaded_files[str(found)]) == 3
    assert owner.save() and owner.open(dest) and sid in owner.document.samples

def test_retry_unreadable_exclusion_after_repair(experiment, tmp_path, monkeypatch):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    source = tmp_path / 'repair.csv'; source.write_text('X,Y\n1,2\n3,4\n5,6\n')
    app._dataset_state_obj().register_unloaded_exclusion(str(source)); owner.capture(app)
    sid = owner.sample_id(str(source)); dest = tmp_path / 'repair.vflow'
    assert owner.save(path=dest)
    reader = app._read_data_file
    def unavailable(path):
        if path == str(source): raise ValueError('Temporary decoder unavailable')
        return reader(path)
    with monkeypatch.context() as patch:
        patch.setattr(app, '_read_data_file', unavailable)
        assert owner.open(dest) and 'sample:' + sid in owner.missing
    owner.reload_resources()
    assert sid in owner.document.samples and app.excluded_files.get(str(source)) is not None
    assert 'sample:' + sid not in owner.missing

def test_unreadable_container_member_keeps_authoritative_identity(experiment, tmp_path, monkeypatch):
    from tests.format_fixtures import write_fixture
    root, manager, app, paths, errors = experiment; owner = app._workspace
    a, _ = write_fixture(tmp_path/'a.fcs', types=('I','I'), bits=(16,16), names=('X','Y'), rows=[(1,2),(3,4),(5,6)])
    b, _ = write_fixture(tmp_path/'b.fcs', types=('I','I'), bits=(16,16), names=('X','Y'), rows=[(9,8),(7,6),(5,4)])
    source = tmp_path/'plate.lmd'; raw = a.read_bytes()+b.read_bytes(); source.write_bytes(raw)
    app._load_paths([str(source)]); owner.capture(app)
    member = next(s for s in owner.document.samples.values() if s.source.absolute_path == str(source))
    sid = member.sample_id; member_id = member.source_member_id
    app._exclude_file(owner.path_for(sid)); expected = set(owner.document.samples)
    dest = tmp_path/'member.vflow'; assert owner.save(path=dest)
    aliases = app._apply_axis_aliases_to_df
    def unavailable(df, path):
        if df.attrs.get('vflow_source_member_id') == member_id: raise ValueError('Temporary member decode failure')
        return aliases(df, path)
    with monkeypatch.context() as patch:
        patch.setattr(app, '_apply_axis_aliases_to_df', unavailable)
        assert owner.open(dest)
        key=owner.path_for(sid)
        assert key in app.excluded_files and app.excluded_files[key] is None and owner.sample_id(key)==sid
        for _ in range(3):
            owner.capture(app)
            assert set(owner.document.samples) == expected
        assert 'sample:' + sid in owner.missing and owner.document.samples[sid].source_member_id == member_id
    owner.reload_resources(); owner.capture(app)
    assert set(owner.document.samples) == expected and len(app.excluded_files[owner.path_for(sid)]) == 3
    assert 'sample:' + sid not in owner.missing and source.read_bytes() == raw

def settle(root, dialog):
    deadline = time.monotonic() + 10
    while dialog.worker and dialog.worker.is_alive() and time.monotonic() < deadline:
        root.update(); time.sleep(.005)
    assert not dialog.worker.is_alive()
    dialog.poll(); root.update()

def test_prepare_publishes_state_only_when_main_thread_polls(experiment):
    root, manager, app, paths, errors = experiment
    dialog = StatisticalAuditDialog(app._workspace, app)
    try:
        dialog.prepare(); dialog.worker.join(timeout=10)
        assert not dialog.worker.is_alive() and dialog.prepared is None
        dialog.poll()
        assert dialog.prepared and dialog.variables.size() >= 4
    finally: dialog.close()

@pytest.mark.parametrize('operation', ['prepare', 'run'])
def test_closed_audit_is_not_retained_by_worker(experiment, monkeypatch, operation):
    root, manager, app, paths, errors = experiment
    dialog = StatisticalAuditDialog(app._workspace, app); root.update()
    if operation == 'run': dialog.prepare(); settle(root, dialog)
    entered = threading.Event(); release = threading.Event()
    def blocked(*args, **kwargs):
        entered.set(); release.wait(10); raise AuditCancelled('closed')
    target = 'materialize_population_inputs' if operation == 'prepare' else 'run_audit'
    monkeypatch.setattr('vflow.ui.statistical_audit_dialog.' + target, blocked)
    getattr(dialog, operation)(); worker = dialog.worker
    assert entered.wait(5)
    ref = weakref.ref(dialog); dialog.close(); del dialog
    try:
        gc.collect()
        assert ref() is None, 'Worker retains the destroyed Tk dialog and its interpreter'
    finally: release.set(); worker.join(timeout=5)
    assert not worker.is_alive() and not app._workspace.document.audits

def test_direct_destroy_cancels_audit_and_scheduled_callbacks(experiment):
    root, manager, app, paths, errors = experiment
    dialog = StatisticalAuditDialog(app._workspace, app); root.update()
    release = threading.Event(); dialog.start(lambda: release.wait(5)); worker = dialog.worker
    try:
        dialog.destroy()
        assert dialog.cancel_event.is_set() and dialog._closed
        assert dialog._poll_id is None and dialog._row_resize_id is None
    finally: release.set(); worker.join(timeout=5)
    root.update()

def test_audit_close_is_idempotent(experiment):
    root, manager, app, paths, errors = experiment
    dialog = StatisticalAuditDialog(app._workspace, app)
    dialog.close(); dialog.close(); dialog.destroy(); root.update()

@pytest.mark.parametrize('replacement', ['clear', 'reopen'])
def test_rename_audit_rechecks_identity_after_modal(experiment, tmp_path, monkeypatch, replacement):
    root, manager, app, paths, errors = experiment; owner = app._workspace
    bundle = run_audit(prepare_samples(owner, app, [owner.sample_id(p) for p in paths]), variables=['X', 'Y'])
    reference = commit(owner, bundle); old_name = reference.name
    dest = tmp_path / 'audits.vflow'; assert owner.save(path=dest)
    dialog = AuditResultsDialog(owner, reference, bundle)
    def choose(*a, **k):
        if replacement == 'reopen': assert owner.open(dest)
        else: owner.clear(); owner.dirty = False
        return 'Wrong workspace edit'
    monkeypatch.setattr('tkinter.simpledialog.askstring', choose)
    try:
        dialog.rename()
        assert reference.name == old_name and not owner.dirty
        if replacement == 'reopen': assert owner.document.audits[reference.audit_id].name == old_name
    finally: dialog.destroy()

def test_biological_id_modal_can_close_without_touching_dead_widgets(experiment, monkeypatch):
    root, manager, app, paths, errors = experiment
    dialog = StatisticalAuditDialog(app._workspace, app); dialog.kind.set('hierarchy'); dialog.update_hierarchy()
    sid = dialog.samples.get_children()[0]
    monkeypatch.setattr(dialog.samples, 'identify_column', lambda x: '#2')
    monkeypatch.setattr(dialog.samples, 'identify_row', lambda y: sid)
    def choose(*a, **k): dialog.close(); return 'bio'
    monkeypatch.setattr('tkinter.simpledialog.askstring', choose)
    class Event: x = 1; y = 1
    dialog.edit_bio(Event())
    assert dialog.mapping == {}
