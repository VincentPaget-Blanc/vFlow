"""Native reproductions of RC12 workspace/export/relink lifecycle bugs."""
import json,os,threading,time
from pathlib import Path
import pytest
from tests.test_workspace_gui import experiment,new_gate
pytestmark=pytest.mark.skipif(not os.environ.get('DISPLAY') and os.name!='nt' and os.sys.platform!='darwin',reason='Tk display required')

@pytest.mark.parametrize('method',['export_stats','export_gated_data','save_gates','export_figure'])
def test_export_cannot_overwrite_loaded_source(experiment,monkeypatch,method):
 root,manager,app,paths,errors=experiment;new_gate(app)
 before=Path(paths[0]).read_bytes()
 monkeypatch.setattr('tkinter.filedialog.asksaveasfilename',lambda **k:paths[0])
 getattr(app,method)();root.update()
 assert Path(paths[0]).read_bytes()==before
 assert errors and 'replace' in str(errors[-1]).lower();errors.clear()

def test_workspace_save_as_cannot_replace_source(experiment):
 root,manager,app,paths,errors=experiment;owner=app._workspace;before=Path(paths[0]).read_bytes()
 assert not owner.save(save_as=True,path=paths[0])
 assert Path(paths[0]).read_bytes()==before and owner.path is None
 assert errors;errors.clear()

@pytest.mark.parametrize('method',['_do_concat_save','_do_concat_save_load'])
def test_concat_cannot_replace_selected_acquisition(experiment,monkeypatch,method):
 from vflow.ui.folder_scan_dialog import FolderScanDialog
 root,manager,app,paths,errors=experiment;before=Path(paths[0]).read_bytes()
 dialog=FolderScanDialog(root,app.T)
 monkeypatch.setattr(dialog,'_selected_paths',lambda:paths)
 monkeypatch.setattr(dialog,'_build_concat_save_path',lambda:paths[0])
 getattr(dialog,method)();assert Path(paths[0]).read_bytes()==before
 assert not dialog.result and errors;errors.clear();dialog.destroy()

def test_relink_preserves_gate_edits_made_during_scan(experiment,tmp_path,monkeypatch):
 root,manager,app,paths,errors=experiment;owner=app._workspace;new_gate(app)
 dest=tmp_path/'old.vflow';assert owner.save(path=dest)
 moved=tmp_path/'moved';moved.mkdir();Path(paths[0]).rename(moved/'A.csv');assert owner.open(dest);root.update()
 entered=threading.Event();release=threading.Event()
 def scan(refs,folder,recursive=True):entered.set();release.wait(3);return {refs[0][0]:[str(moved/'A.csv')]}
 monkeypatch.setattr('vflow.workspace.controller.scan_candidates',scan)
 monkeypatch.setattr('tkinter.filedialog.askdirectory',lambda **k:str(moved))
 owner.find_missing();assert entered.wait(1)
 app._sel_gate()['x1']=75.;app.refresh_plot();assert owner.gates_dirty;release.set()
 deadline=time.monotonic()+2
 while owner._scan_running and time.monotonic()<deadline:root.update();time.sleep(.01)
 assert not owner._scan_running and app._sel_gate()['x1']==75.
 assert owner.stores['main'].resolve_gate(None,app._sel_gate_id)['x1']==75.

@pytest.mark.parametrize('kind',['batch','polar'])
@pytest.mark.parametrize('replacement',['new','reopen','close_tab'])
def test_secondary_window_cannot_export_after_session_replacement(experiment,tmp_path,kind,replacement):
 from vflow.legacy.vflow_app import BatchPlotWindow,PolarAnalysisWindow
 root,manager,app,paths,errors=experiment;owner=app._workspace;new_gate(app)
 target=app
 if replacement=='close_tab':
  app._open_subgate(50.,50.);target=manager._apps[-1]
 window=(BatchPlotWindow if kind=='batch' else PolarAnalysisWindow)(root,target.T,target);root.update()
 if replacement=='new':owner.clear()
 elif replacement=='reopen':
  p=tmp_path/'same.vflow';assert owner.save(path=p);assert owner.open(p)
 else:manager._close_tab(len(manager._apps)-1)
 original=target._active
 def forbidden():raise AssertionError('Stale analysis tried to read the replacement data')
 target._active=forbidden
 try:window._compute_and_plot()
 finally:target._active=original
 window._export_stats();root.update()
 assert errors and 'workspace' in str(errors[-1]).lower();errors.clear()
 if hasattr(window,'_on_close'):window._on_close()
 else:window.destroy()

def test_reset_current_sample_view_takes_effect(experiment):
 root,manager,app,paths,errors=experiment;owner=app._workspace
 sid=owner.sample_id(paths[0]);owner.show_sample(app,sid)
 app.x_var.set('U');app.y_var.set('V');app.apply_axes();owner.capture(app)
 owner.reset_view(app,sid);root.update()
 assert (app.x_channel,app.y_channel)==('X','Y')

def test_malformed_open_does_not_replace_live_workspace(experiment,tmp_path):
 root,manager,app,paths,errors=experiment;owner=app._workspace;original=owner.document
 d=owner.document.payload();d['tabs']=[];p=tmp_path/'bad.vflow';p.write_text(json.dumps(d))
 assert owner.open(p) is False
 assert owner.document is original and len(app.loaded_files)==3
 assert errors;errors.clear()

@pytest.mark.parametrize('action',['clear','dispose'])
def test_relink_worker_cannot_finish_in_replaced_or_disposed_workspace(experiment,tmp_path,monkeypatch,action):
 root,manager,app,paths,errors=experiment;owner=app._workspace
 dest=tmp_path/'old.vflow';assert owner.save(path=dest)
 sid=owner.sample_id(paths[0]);moved=tmp_path/'moved';moved.mkdir();Path(paths[0]).rename(moved/'A.csv')
 assert owner.open(dest);root.update();assert owner.missing
 entered=threading.Event();release=threading.Event();calls=[]
 def scan(refs,folder,recursive=True):
  entered.set();release.wait(3);return {refs[0][0]:[str(moved/'A.csv')]}
 monkeypatch.setattr('vflow.workspace.controller.scan_candidates',scan)
 monkeypatch.setattr('tkinter.filedialog.askdirectory',lambda **k:str(moved))
 owner.find_missing();assert entered.wait(1)
 getattr(owner,action)();monkeypatch.setattr(owner,'reload_resources',lambda:calls.append(True))
 release.set()
 deadline=time.monotonic()+.35
 while time.monotonic()<deadline:root.update();time.sleep(.01)
 assert not calls and not owner._scan_running
 assert not errors
