"""Independent edge oracles; no numerical implementation changes."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
import pytest
from tests.test_workspace_gui import experiment,new_gate
from vflow.workspace.model import Workspace,FileReference,fingerprint

def test_legacy_identity_kept_but_full_content_pinned(tmp_path):
    p=tmp_path/'data';p.write_bytes(b'a'*400000)
    r=FileReference(str(p),identity_fingerprint=fingerprint(p,'sampled-sha256'))
    old=r.identity_fingerprint;r.accept(p,None)
    assert r.identity_fingerprint==old and r.content_sha256==hashlib.sha256(p.read_bytes()).hexdigest()
    raw=bytearray(p.read_bytes());raw[90000]=98;p.write_bytes(raw)
    assert fingerprint(p,'sampled-sha256')==old and not r.matches(p)

def test_external_write_during_fsync_refused(tmp_path,monkeypatch):
    import vflow.workspace.model as model
    p=tmp_path/'study.vflow';Workspace().save(p);w=Workspace.load(p);fsync=model.os.fsync
    external=p.read_bytes()+b' '
    def change(fd):p.write_bytes(external);fsync(fd)
    monkeypatch.setattr(model.os,'fsync',change)
    with pytest.raises(ValueError,match='changed'):w.save(p)
    assert p.read_bytes()==external

def test_actual_two_process_writers_one_winner(tmp_path):
    p=tmp_path/'study.vflow';Workspace().save(p)
    script="""import sys,time
from pathlib import Path
from vflow.workspace.model import Workspace
p,folder,tag=map(Path,sys.argv[1:]);w=Workspace.load(p);w.ui_state['workspace_name']=str(tag)
(folder/(str(tag)+'.ready')).touch()
deadline=time.monotonic()+15
while not (folder/'start').exists():
 if time.monotonic()>deadline:raise RuntimeError('barrier timeout')
 time.sleep(.01)
try:w.save(p);(folder/(str(tag)+'.won')).touch()
except ValueError:(folder/(str(tag)+'.refused')).touch()
"""
    children=[];logs=[]
    try:
        for tag in ('a','b'):
            log=(tmp_path/(tag+'.log')).open('w');logs.append(log)
            # Child diagnostics remain in files even when parent pytest is uncaptured.
            env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
            code="import faulthandler;faulthandler.enable();faulthandler.dump_traceback_later(10,repeat=True)\n"+script
            children.append(subprocess.Popen([sys.executable,'-u','-c',code,str(p),str(tmp_path),tag],
                stdout=log,stderr=log,env=env,cwd=Path(__file__).resolve().parents[1]))
        deadline=time.monotonic()+45
        while not all((tmp_path/(tag+'.ready')).exists() for tag in ('a','b')):
            assert all(c.poll() is None for c in children), 'Writer exited before barrier'
            assert time.monotonic()<deadline, 'Writer readiness timeout; see a.log / b.log'
            time.sleep(.01)
        (tmp_path/'start').touch()
        results=[c.wait(timeout=45) for c in children]
        assert results==[0,0]
        assert len(list(tmp_path.glob('*.won')))==len(list(tmp_path.glob('*.refused')))==1
    finally:
        for c in children:
            if c.poll() is None:c.kill()
            c.wait(timeout=5)
        for log in logs:log.close()

def test_lock_released_after_abrupt_process_exit(tmp_path):
    from vflow.workspace.file_guard import workspace_lock
    p=tmp_path/'study.vflow'
    r=subprocess.run([sys.executable,'-c','import os,sys;from vflow.workspace.file_guard import workspace_lock\nwith workspace_lock(sys.argv[1]):os._exit(87)',str(p)],timeout=15)
    assert r.returncode==87
    with workspace_lock(p):Workspace().save(tmp_path/'other.vflow')

def test_windows_lock_adapter_contract(tmp_path,monkeypatch):
    import vflow.workspace.file_guard as guard
    calls=[];stub=SimpleNamespace(LK_NBLCK=2,LK_UNLCK=0,locking=lambda fd,kind,size:calls.append((kind,size)))
    monkeypatch.setitem(sys.modules,'msvcrt',stub);monkeypatch.setattr(guard,'os',SimpleNamespace(name='nt'))
    with guard.workspace_lock(tmp_path/'study.vflow'):pass
    assert calls==[(2,1),(0,1)]

def test_source_change_while_csv_decode_is_rejected(tmp_path,monkeypatch):
    import vflow.core.data_io as io
    from vflow.io.registry import read_flow_source
    p=tmp_path/'a.csv';p.write_text('X,Y\n1,2\n3,4\n');read=io.smart_read_csv
    def changing(path):
        df=read(path);p.write_text('X,Y\n9,2\n3,4\n');return df
    monkeypatch.setattr(io,'smart_read_csv',changing)
    with pytest.raises(ValueError,match='changed'):read_flow_source(p)

def test_ingestion_identity_survives_later_file_edit(tmp_path):
    from vflow.io.registry import read_flow_source
    from vflow.workspace.controller import WorkspaceController
    p=tmp_path/'a.csv';p.write_text('X,Y\n1,2\n3,4\n');result=read_flow_source(p);df=result.samples[0].dataframe
    old=fingerprint(p);p.write_text('X,Y\n9,2\n3,4\n')
    main=SimpleNamespace(loaded_files={str(p):df},excluded_files={},file_vars={},axis_aliases={})
    owner=WorkspaceController(main);owner.sync_sources();r=next(iter(owner.document.samples.values())).source
    assert r.identity_fingerprint==old and not r.matches(p)

def test_legacy_derivative_ownership(tmp_path):
    from vflow.io.derivatives import derivative_is_owned,sidecar
    source=tmp_path/'plate.lmd';source.write_bytes(b'original')
    csv=tmp_path/'plate.vflow.csv';csv.write_text('X,Y\n1,2\n')
    sidecar(csv).write_text(json.dumps({'generated_by':'vFlow','schema':1,'source_path_basename':source.name,
        'generated_csv_fingerprint':fingerprint(csv,'sampled-sha256')}))
    assert derivative_is_owned(csv)

@pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='Tk display required')
def test_live_audit_state_and_immutable_snapshot(experiment,tmp_path):
    from vflow.statistics import run_audit
    from vflow.statistics.workspace_audit import prepare_samples,commit
    from vflow.ui.statistical_audit_dialog import AuditResultsDialog
    root,manager,app,paths,errors=experiment;owner=app._workspace
    b=run_audit(prepare_samples(owner,app,[owner.sample_id(p) for p in paths]),variables=['X','Y']);ref=commit(owner,b)
    data=Path(ref.result.absolute_path).read_bytes();saved=copy.deepcopy(b);sid=ref.selected_sample_ids[0]
    d=AuditResultsDialog(owner,ref,b);d.tree.selection_set(sid);app._exclude_file(paths[0]);root.update()
    deadline=time.monotonic()+2
    while d.tree.item(sid,'values')[-1]!='Excluded' and time.monotonic()<deadline:root.update();time.sleep(.01)
    assert d.tree.item(sid,'values')[-1]=='Excluded' and d.tree.selection()==(sid,)
    assert b==saved and Path(ref.result.absolute_path).read_bytes()==data
    owner.clear();deadline=time.monotonic()+2
    while d.tree.item(sid,'values')[-1]!='Unknown (workspace changed)' and time.monotonic()<deadline:root.update();time.sleep(.01)
    assert d.tree.item(sid,'values')[-1]=='Unknown (workspace changed)';d.destroy()

@pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='Tk display required')
def test_true_zero_display_not_unavailable(experiment):
    from vflow.statistics import run_audit
    from vflow.statistics.workspace_audit import prepare_samples,commit
    from vflow.ui.statistical_audit_dialog import AuditResultsDialog
    root,manager,app,paths,errors=experiment;owner=app._workspace
    b=run_audit(prepare_samples(owner,app,[owner.sample_id(p) for p in paths]),variables=['X','Y']);ref=commit(owner,b)
    # Identical real samples produce a true zero numeric discordance.
    d=AuditResultsDialog(owner,ref,b)
    assert all(d.tree.item(sid,'values')[1]=='0' for sid in ref.selected_sample_ids)
    d.destroy()

@pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='Tk display required')
@pytest.mark.parametrize('failure',['before_commit','after_commit'])
def test_recovery_failure_preserves_correct_geometry(experiment,tmp_path,monkeypatch,failure):
    import vflow.workspace.controller as controller
    import vflow.workspace.model as model
    root,manager,app,paths,errors=experiment;owner=app._workspace;new_gate(app);p=tmp_path/'study.vflow';assert owner.save(path=p)
    app._sel_gate()['x1']=70.;app.refresh_plot();owner.capture(app);owner.autosave()
    checkpoint=owner.recovery_path;previous=checkpoint.read_bytes();old_gate=owner._recovery_gate_path
    app._sel_gate()['x1']=60.;app.refresh_plot();owner.capture(app)
    original=controller.atomic_json
    def failing(path,payload,*a,**k):
        if Path(path)==checkpoint:
            if failure=='after_commit':original(path,payload,*a,**k)
            raise OSError('Injected checkpoint failure')
        return original(path,payload,*a,**k)
    with monkeypatch.context() as patch:patch.setattr(controller,'atomic_json',failing);owner.autosave()
    w=Workspace.load(checkpoint);g=Path(w.default_gate_session.absolute_path)
    assert g.is_file()
    if failure=='before_commit':assert checkpoint.read_bytes()==previous and g==old_gate
    else:assert checkpoint.read_bytes()!=previous and owner._recovery_gate_path==g

@pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='Tk display required')
def test_older_recovery_refuses_new_external_winner(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace;p=tmp_path/'study.vflow';assert owner.save(path=p)
    owner.rename('Recovered edits');owner.autosave();checkpoint=owner.recovery_path
    other=Workspace.load(p);other.ui_state['workspace_name']='External winner';other.save(p);before=p.read_bytes()
    # Checkpoint ordering alone is not enough to establish a safe overwrite.
    later=p.stat().st_mtime_ns+1000000;os.utime(checkpoint,ns=(later,later));owner.dirty=False
    assert owner.open(p) and owner.workspace_name()=='Recovered edits' and owner.dirty
    assert owner.save() is False and p.read_bytes()==before and errors;errors.clear()
    assert owner.save(save_as=True,path=tmp_path/'recovered-copy.vflow')

@pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='Tk display required')
def test_corrupt_newest_recovery_falls_back(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace;p=tmp_path/'study.vflow';assert owner.save(path=p)
    owner.rename('Valid recovery');owner.autosave();checkpoint=owner.recovery_path
    corrupt=Path(str(p)+'.recovery.corrupt.vflow');corrupt.write_text('{bad')
    later=checkpoint.stat().st_mtime_ns+1000000;os.utime(corrupt,ns=(later,later));owner.dirty=False
    assert owner.open(p) and owner.workspace_name()=='Valid recovery' and owner.dirty

@pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='Tk display required')
def test_corrupt_unsaved_recovery_falls_back(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace
    new_gate(app);owner.rename('Valid unsaved');owner.autosave();checkpoint=owner.recovery_path
    corrupt=checkpoint.with_name('corrupt.vflow');corrupt.write_text('{bad')
    later=checkpoint.stat().st_mtime_ns+1000000;os.utime(corrupt,ns=(later,later))
    owner.clear();owner.offer_unsaved_recovery()
    assert owner.path is None and owner.workspace_name()=='Valid unsaved' and owner.dirty and owner.gates_dirty and app.gates
