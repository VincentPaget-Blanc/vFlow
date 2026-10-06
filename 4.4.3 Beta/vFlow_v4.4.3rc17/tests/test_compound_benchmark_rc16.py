"""Seeded mixed workflows against full benchmark events and pandas row oracles."""
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import zipfile
import pandas as pd
import pytest
from tests.test_workspace_gui import experiment
from vflow.statistics import run_audit
from vflow.statistics.workspace_audit import prepare_samples,commit,decide
from vflow.statistics.audit_serialization import read_bundle
from vflow.statistics.audit_export import export_csv_package,export_xlsx
ROOT=Path(__file__).resolve().parents[1]
pytestmark=pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='Tk display required')

@pytest.mark.parametrize('seed',[1601,1602,1603,1604])
def test_compound_benchmark(experiment,tmp_path,monkeypatch,seed):
    root,manager,app,_,errors=experiment;owner=app._workspace;owner.clear();rng=random.Random(seed)
    paths=[];raw={};hashes={}
    for name in ('Control_01','Control_02','Treatment_01','Treatment_02'):
        p=tmp_path/(name+'.csv');shutil.copy2(ROOT/'benchmark_extensions/frozen_v1/cytometry'/p.name,p)
        paths.append(str(p));raw[str(p)]=pd.read_csv(p);hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    app._load_paths(paths);app.x_var.set('FSC-A');app.y_var.set('SSC-A');app.apply_axes();app.x_scale_var.set('linear');app.y_scale_var.set('linear')
    assert sum(map(len,app.loaded_files.values()))==48000
    definition=json.loads((ROOT/'benchmark_extensions/frozen_v1/references/benchmark_gate_definitions.json').read_text())['gates'][0]
    app._add_gate(auto_type='rectangle');g=app._sel_gate();g.update({k:definition[k] for k in ('x0','x1','y0','y1')});g['applied']=True;gid=g['id']
    app._bind_gate_context(g);app.refresh_plot();ids=[owner.sample_id(p) for p in paths]
    def oracle(df,gate):return df[df['FSC-A'].between(gate['x0'],gate['x1']) & df['SSC-A'].between(gate['y0'],gate['y1'])]
    def verify():
        app.refresh_plot()
        for sid in ids:
            if sid not in owner.document.samples or owner.document.samples[sid].excluded:continue
            p=owner.path_for(sid);gate=owner.stores['main'].resolve_gate(sid,gid)
            if not app.file_vars[p].get():
                assert p not in app.gate_stats.get(gid,{})
                continue
            assert app.gate_stats[gid][p]['stats']['IN']['count']==len(oracle(raw[p],gate))
        for child in manager._apps[1:]:
            child.refresh_plot()
            for p,df in child.loaded_files.items():
                sid=owner.sample_id(p);gate=owner.stores['main'].resolve_gate(sid,gid);expected=oracle(raw[p],gate)
                if len(child.population_lineage)>1:
                    second=owner.stores[manager._apps[1]._workspace_tab_id].resolve_gate(sid,child_gid);expected=oracle(expected,second)
                pd.testing.assert_frame_equal(df.reset_index(drop=True),expected.reset_index(drop=True))
    verify();bundle=run_audit(prepare_samples(owner,app,ids[:2]),variables=['FSC-A','SSC-A']);ref=commit(owner,bundle)
    decide(owner,ref,ids[0],'note',note='Compound benchmark review');snapshot=copy.deepcopy(bundle)
    app._sel_gate_id=gid;app._open_subgate(75000.,30000.);child=manager._apps[1]
    child.plot_type_var.set('Dot Plot');child.show_marginals_var.set(False)
    child._add_gate(auto_type='rectangle');cg=child._sel_gate();cg.update(x0=55000.,x1=95000.,y0=10000.,y1=45000.,applied=True);child_gid=cg['id']
    child._bind_gate_context(cg);child.refresh_plot();child._open_subgate(75000.,30000.);manager._apps[-1].plot_type_var.set('Dot Plot');verify()
    owner.show_sample(app,ids[1]);app.gate_scope_var.set('Current sample');owner.scope_changed(app);app._sel_gate_id=gid
    app._sel_gate()['x1']=90000.;app.refresh_plot();owner.capture(app);verify()
    owner.gate_action(app,'undo',gid);verify()
    app.view_mode_var.set('overlay');app._on_view_mode_change();dest=tmp_path/'mixed.vflow';assert owner.save(path=dest)
    operations=[]
    for i in range(20):
        sid=rng.choice(ids);p=owner.path_for(sid);action=rng.choice(('toggle_exclusion','active','save_reopen'))
        if action=='toggle_exclusion':
            if owner.document.samples[sid].excluded:app._restore_file(p)
            else:app._exclude_file(p)
        elif action=='active' and p in app.file_vars:app.file_vars[p].set(not app.file_vars[p].get());app._on_active_files_changed()
        else:assert owner.save() and owner.open(dest)
        owner.capture(app);operations.append([sid,action]);verify()
    for sid in ids:
        p=owner.path_for(sid)
        if owner.document.samples[sid].excluded:app._restore_file(p)
        app.file_vars[p].set(True)
    app._on_active_files_changed();verify()
    moved=tmp_path/'relocated'/Path(paths[0]).name;moved.parent.mkdir();shutil.copy2(paths[0],moved)
    monkeypatch.setattr('tkinter.filedialog.askopenfilename',lambda **k:str(moved));owner.locate_reference('sample:'+ids[0]);raw[str(moved)]=raw[paths[0]]
    assert owner.path_for(ids[0])==str(moved);verify();owner.remove_sample(ids[3]);assert owner.save() and owner.open(dest);verify()
    stored=owner.document.audits[ref.audit_id];assert read_bundle(stored,owner.path)==snapshot and len(stored.decision_history)==1
    exports=tmp_path/'historical.zip';export_csv_package(snapshot,exports,stored,owner.document);export_xlsx(snapshot,tmp_path/'historical.xlsx',stored,owner.document)
    with zipfile.ZipFile(exports) as z:assert json.loads(z.read('canonical_audit.json'))==snapshot
    app._sel_gate_id=gid;app._rebuild_gate_manager();app.stats_mode_var.set('perfile');app.refresh_plot()
    csv=tmp_path/'current.csv';monkeypatch.setattr('tkinter.filedialog.asksaveasfilename',lambda **k:str(csv));app.export_stats();table=pd.read_csv(csv)
    for row in table[table.Population=='IN'].itertuples():
        p=row.Source_Path;sid=owner.sample_id(p);gate=owner.stores['main'].resolve_gate(sid,gid)
        assert row.Count==len(oracle(raw[p],gate))
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items()) and not errors
    out=ROOT/'validation/compound_benchmark_rc16';out.mkdir(exist_ok=True)
    (out/(str(seed)+'.json')).write_text(json.dumps({'seed':seed,'events':48000,'operations':operations,'nested_populations':2,
        'historical_events':sum(s['event_count'] for s in snapshot['sample_qc']),'raw_hashes_unchanged':True,'passed':True},indent=2))
