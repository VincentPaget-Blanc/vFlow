"""Actual benchmark acquisitions through the real app, review, exports and reopen."""
import copy
import hashlib
import os
import shutil
from pathlib import Path
import tkinter as tk
import pandas as pd
import pytest
from vflow.legacy.vflow_app import FlowTabManager
from vflow.statistics import run_audit
from vflow.statistics.workspace_audit import prepare_samples,commit,decide
from vflow.statistics.audit_export import export_xlsx,export_csv_package
from vflow.ui.statistical_audit_dialog import AuditResultsDialog
from vflow.core.data_io import read_flow_data_file

pytestmark=pytest.mark.skipif(not os.environ.get('DISPLAY'),reason='Tk display required')
ROOT=Path(__file__).resolve().parents[1]
CORPUS=ROOT/'benchmark_extensions/frozen_v1'

@pytest.mark.parametrize('domain,names',[
    ('cytometry',['Control_01.csv','Control_02.csv','Treatment_01.csv','Treatment_02.csv']),
    ('microscopy',['Microscopy_01.csv','Microscopy_02.csv','Microscopy_03.csv']),
    ('parser_variants',['FCS31_Float_BE.fcs','FCS30_Double_BE.fcs']),
    ('lmd',['SM239.LMD','188-15.LMD','240+S.LMD']),
])
def test_frozen_sources_in_app(domain,names,tmp_path,monkeypatch):
    from tkinter import messagebox
    errors=[]
    monkeypatch.setattr(messagebox,'showerror',lambda *a,**k:errors.append(a))
    for key in ('showwarning','showinfo'):monkeypatch.setattr(messagebox,key,lambda *a,**k:None)
    monkeypatch.setattr(messagebox,'askyesnocancel',lambda *a,**k:False)
    root=tk.Tk();root.geometry('1280x900');root.report_callback_exception=lambda *a:errors.append(a)
    manager=FlowTabManager(root);app=manager._apps[0];owner=app._workspace
    owner.state_dir=tmp_path/'state';owner.recent_path=tmp_path/'state/recent.json'
    sources=[str(CORPUS/domain/name) for name in names]
    if domain=='lmd':
        sources=[]
        for name in names:
            target=tmp_path/name;shutil.copyfile(ROOT/'benchmark_extensions/lmd'/name,target);sources.append(str(target))
    try:
        app._load_paths(sources);root.update();assert len(app.loaded_files)==len(names)
        originals={p:df.copy(deep=True) for p,df in app.loaded_files.items()}
        for p,df in originals.items():pd.testing.assert_frame_equal(df,read_flow_data_file(p))
        columns=list(originals[sources[0]].select_dtypes(include='number').columns)
        app.x_var.set(columns[0]);app.y_var.set(columns[1]);app.apply_axes();app.x_scale_var.set('linear');app.y_scale_var.set('linear')
        for mode in ('Dot Plot','Density','Contour Plot'):
            app.plot_type_var.set(mode);app.refresh_plot();root.update()
            for p,df in originals.items():pd.testing.assert_frame_equal(app.loaded_files[p],df)
        ids=[owner.sample_id(p) for p in sources]
        bundle=run_audit(prepare_samples(owner,app,ids));ref=commit(owner,bundle)
        result=AuditResultsDialog(owner,ref,bundle);root.update();assert len(result.tree.get_children())==len(names)
        result.tree.selection_set(ids[0]);result.details();root.update()
        if domain=='cytometry':
            from PIL import ImageGrab
            ImageGrab.grab(xdisplay=os.environ['DISPLAY']).save(ROOT/'validation/candidate_benchmark_app.png')
        result.destroy()
        before=Path(ref.result.absolute_path).read_bytes();decide(owner,ref,ids[0],'exclude',note='benchmark manual review');decide(owner,ref,ids[0],'restore')
        assert before==Path(ref.result.absolute_path).read_bytes()
        export_xlsx(bundle,tmp_path/'audit.xlsx',ref,owner.document);export_csv_package(bundle,tmp_path/'audit.zip',ref,owner.document)
        target=tmp_path/(domain+'.vflow');assert owner.save(path=str(target));assert owner.open(str(target));root.update()
        assert len(owner.document.audits)==1 and len(owner.document.audits[ref.audit_id].decision_history)==2
        for p,df in originals.items():pd.testing.assert_frame_equal(app.loaded_files[p],df)
        assert not errors
    finally:owner.dispose();root.destroy()
