"""Workspace conflict, identity, relocation, and recovery regressions."""
import copy
import json
import os
from pathlib import Path
import time
import pytest
from vflow.workspace.model import Workspace, FileReference, SampleReference, fingerprint
from tests.test_workspace_gui import experiment, new_gate

@pytest.mark.parametrize('change', ['second_writer', 'edit', 'delete'])
def test_stale_save_refused(tmp_path, change):
    p=tmp_path/'study.vflow';Workspace().save(p);a=Workspace.load(p);b=Workspace.load(p)
    a.ui_state['workspace_name']='My unsaved edits'
    if change=='second_writer':b.ui_state['workspace_name']='Other writer';b.save(p)
    elif change=='edit':p.write_bytes(p.read_bytes()+b' ')
    else:p.unlink()
    expected=p.read_bytes() if p.exists() else None
    with pytest.raises(ValueError,match='changed'):a.save(p)
    assert (p.read_bytes() if p.exists() else None)==expected
    a.save(tmp_path/'copy.vflow');assert Workspace.load(tmp_path/'copy.vflow').ui_state['workspace_name']=='My unsaved edits'

@pytest.mark.parametrize('kind',['source','gates','audit'])
def test_unsampled_same_size_edit_rejected(tmp_path,kind):
    p=tmp_path/'bytes.bin';p.write_bytes(b'a'*400000);r=FileReference.create(p,kind=kind)
    data=bytearray(p.read_bytes());data[90000]=98;p.write_bytes(data)
    assert not r.matches(p)

def test_retargeted_symlink_save_refused(tmp_path):
    a=tmp_path/'a.vflow';b=tmp_path/'b.vflow';Workspace().save(a);Workspace().save(b)
    alias=tmp_path/'alias.vflow';alias.symlink_to(a);w=Workspace.load(alias);w.ui_state['workspace_name']='Unsaved'
    ba,bb=a.read_bytes(),b.read_bytes();alias.unlink();alias.symlink_to(b)
    with pytest.raises(ValueError,match='changed'):w.save(alias)
    assert a.read_bytes()==ba and b.read_bytes()==bb and alias.is_symlink()
    w.save(tmp_path/'copy.vflow')

def test_symlink_alias_tracks_physical_revision(tmp_path):
    p=tmp_path/'study.vflow';Workspace().save(p);alias=tmp_path/'alias.vflow';alias.symlink_to(p)
    a=Workspace.load(alias);b=Workspace.load(p);b.ui_state['workspace_name']='Winner';b.save(p)
    before=p.read_bytes()
    with pytest.raises(ValueError,match='changed'):a.save(alias)
    assert p.read_bytes()==before and alias.is_symlink()

@pytest.mark.parametrize('save_as',[False,True])
def test_missing_relative_only_reference_survives_save(tmp_path,save_as):
    p=tmp_path/'study.vflow';w=Workspace();w.samples['s']=SampleReference('s','Missing',FileReference(relative_path='missing.csv'),excluded=True)
    # Simulate an older portable document with no absolute locator.
    p.write_text(json.dumps(w.payload()));loaded=Workspace.load(p)
    dest=tmp_path/'other'/'copy.vflow' if save_as else p;loaded.save(dest);again=Workspace.load(dest)
    r=again.samples['s'].source
    assert r.absolute_path==str(tmp_path/'missing.csv') and again.samples['s'].excluded
    assert (dest.parent/r.relative_path).resolve()==tmp_path/'missing.csv'

def test_symlink_source_portability_after_tree_move(tmp_path):
    folder=tmp_path/'original';folder.mkdir();source=folder/'a.csv';source.write_text('X,Y\n1,2\n')
    p=folder/'study.vflow';w=Workspace();w.samples['s']=SampleReference('s','A',FileReference.create(source));w.save(p)
    aliases=tmp_path/'aliases';aliases.mkdir();alias=aliases/'study.vflow';alias.symlink_to(p)
    loaded=Workspace.load(alias);loaded.save(alias)
    moved=tmp_path/'moved';folder.rename(moved);again=Workspace.load(moved/'study.vflow')
    assert again.samples['s'].source.resolve(moved/'study.vflow')==str(moved/'a.csv')

@pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='Tk display required')
def test_recovery_retains_geometry_and_marks_restored_dirty(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace;g=new_gate(app);gid=g['id']
    p=tmp_path/'study.vflow';assert owner.save(path=p);before=p.read_bytes()
    app._sel_gate()['x1']=70.;app.refresh_plot();owner.capture(app);owner.autosave()
    checkpoint=owner.recovery_path;owner.dirty=False;owner.gates_dirty=False
    assert owner.open(p)
    assert app.gates[0]['x1']==70. and owner.dirty and owner.gates_dirty and p.read_bytes()==before
    assert owner.save() and not checkpoint.exists() and owner.open(p)
    assert app.gates[0]['x1']==70.

@pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='Tk display required')
def test_open_same_workspace_reads_after_close_save(experiment,tmp_path,monkeypatch):
    root,manager,app,paths,errors=experiment;owner=app._workspace;p=tmp_path/'study.vflow';assert owner.save(path=p)
    owner.rename('Saved during close');monkeypatch.setattr('tkinter.messagebox.askyesnocancel',lambda **k:True)
    # The prompt also receives positional arguments.
    monkeypatch.setattr('tkinter.messagebox.askyesnocancel',lambda *a,**k:True)
    assert owner.open(p) and owner.workspace_name()=='Saved during close'

@pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='Tk display required')
def test_gui_retarget_guard_and_metadata_after_initial_save(experiment,tmp_path):
    root,manager,app,paths,errors=experiment;owner=app._workspace;a=tmp_path/'a.vflow';b=tmp_path/'b.vflow'
    Workspace().save(b);alias=tmp_path/'alias.vflow';alias.symlink_to(a);assert owner.save(path=alias)
    ba,bb=a.read_bytes(),b.read_bytes();alias.unlink();alias.symlink_to(b);owner.rename('Unsaved')
    assert owner.save() is False and a.read_bytes()==ba and b.read_bytes()==bb and owner.dirty
    assert errors and 'changed' in str(errors[-1]);errors.clear();assert owner.save(save_as=True,path=tmp_path/'copy.vflow')
