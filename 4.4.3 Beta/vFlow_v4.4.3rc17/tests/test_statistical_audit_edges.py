"""Accuracy and data-loss regressions discovered during the RC3 bug hunt."""
import copy
import gzip
import json
import zipfile
import numpy as np
import pandas as pd
import pytest
from openpyxl import load_workbook
from tests.test_statistical_audit import samples,hierarchical
from vflow.statistics import AuditSample,run_audit
from vflow.statistics.hierarchy import sufficient_stats,estimate
from vflow.statistics.wasserstein import sorted_w1,isolation
from vflow.statistics.discordance import _robust_z_scores
from vflow.statistics.audit_export import export_xlsx,export_csv_package,tables
from vflow.statistics.audit_serialization import commit_bundle,append_decision,read_bundle
from vflow.workspace.model import Workspace,FileReference

def test_hierarchy_variance_and_icc_invariant_to_small_measurement_units():
    s,m=hierarchical(seed=14,bios=4,nested=3,particles=12)
    expected=estimate(sufficient_stats(s,'x',m))
    for sample in s:sample.dataframe.x*=1e-12
    actual=estimate(sufficient_stats(s,'x',m))
    assert actual['model_status']==expected['model_status']
    for key in ('sigma2_bio','sigma2_nested_sample','sigma2_particle'):
        assert actual[key]/1e-24==pytest.approx(expected[key],rel=2e-4,abs=1e-5)
    assert actual['icc_bio']==pytest.approx(expected['icc_bio'],rel=2e-4)

def test_distance_review_and_influence_are_unit_invariant():
    m=np.array([[0,1,6],[1,0,6],[6,6,0]],dtype=float)
    assert isolation(m,2)[1:]==isolation(m*1e-14,2)[1:]
    assert np.allclose(_robust_z_scores([1,2,3,4,9],5),_robust_z_scores(np.array([1,2,3,4,9])*1e-14,5))
    s,mapping=hierarchical(bios=3,nested=2,particles=8)
    a=run_audit(s,audit_type='hierarchy',hierarchy_mapping=mapping,policy={'n_projections':4})
    for sample in s:sample.dataframe*=1e-12
    b=run_audit(s,audit_type='hierarchy',hierarchy_mapping=mapping,policy={'n_projections':4})
    assert np.allclose(a['global_distance_matrix'],b['global_distance_matrix'])
    assert [r['status'] for r in a['sample_qc']]==[r['status'] for r in b['sample_qc']]
    assert [r['relative_change'] for r in b['influence']]==pytest.approx([r['relative_change'] for r in a['influence']])

def test_extreme_finite_ranges_do_not_silently_turn_into_missing_scores():
    x=np.array([-1e308,1e308])
    assert sorted_w1(x,x)==0
    matrix=np.full((3,3),1e308);np.fill_diagonal(matrix,0)
    score,ratio,condition=isolation(matrix,0)
    assert score==1e308 and ratio==1 and condition=='finite'
    s=[AuditSample(str(i),str(i),pd.DataFrame({'x':np.array([8e307,9e307,1e308])+i*1e306})) for i in range(2)]
    result=run_audit(s)
    assert np.isfinite(result['variable_qc'][0]['mean'])
    assert result['sample_qc'][0]['global_peer_distance']>0
    with pytest.raises(ValueError,match='numeric range'):
        sorted_w1(np.array([-1e308]),np.array([1e308]))

@pytest.mark.parametrize('policy',[{'seed':-1},{'seed':1.5},{'n_projections':2.5},{'n_projections':True},
    {'min_finite':3.5},{'isolation_threshold':np.nan},{'robust_z_threshold':0},
    {'influence_threshold':-1},{'unknown_key':3},{'version':'pretend'}])
def test_invalid_policies_fail_before_calculation(policy):
    with pytest.raises(ValueError,match='policy'):run_audit(samples(),policy=policy)

def test_duplicate_measurement_names_rejected_clearly():
    s=samples();s[0].dataframe.columns=['x','x','y']
    with pytest.raises(ValueError,match='unique'):run_audit(s)

def test_hierarchy_ids_are_canonical_in_results_and_export_summary():
    s,m=hierarchical(bios=3,nested=2,particles=5)
    m['0-1']=' 0 '
    b=run_audit(s,audit_type='hierarchy',hierarchy_mapping=m,policy={'n_projections':2})
    assert b['hierarchy_mapping']['0-1']=='0'
    assert dict((r['key'],r['value']) for r in tables(b)['Summary'])['n_biological']==3
    m['0-1']=None
    with pytest.raises(ValueError,match='biological'):run_audit(s,audit_type='hierarchy',hierarchy_mapping=m)

def test_reserved_sample_ids_cannot_replace_matrix_metadata():
    s=samples(n=3)
    for sample,sid in zip(s,['sample_id','variable','distance:sample_id']):sample.sample_id=sid
    b=run_audit(s)
    t=tables(b)
    assert t['Global_Distance_Matrix'][0]['sample_id']=='sample_id'
    assert t['Variable_Matrices'][0]['variable']==b['variables'][0]
    assert len(t['Global_Distance_Matrix'][0])==4
    assert t['Global_Distance_Matrix'][0]['distance:variable']==b['global_distance_matrix'][0][1]

def test_excel_and_csv_preserve_long_control_character_review_notes(tmp_path):
    b=run_audit(samples(n=2));w=Workspace();ref=commit_bundle(w,b,state_dir=tmp_path)
    note='=SUM(A1:A9)\x00\x0b'+('long note α '*5000)
    append_decision(ref,'0','note',note=note)
    xlsx=tmp_path/'review.xlsx';csv=tmp_path/'review.zip'
    export_xlsx(b,xlsx,ref,w);export_csv_package(b,csv,ref,w)
    book=load_workbook(xlsx,data_only=False)
    def reconstruct(prefix):
        return json.loads(''.join(row[1].value for row in book['Provenance'] if str(row[0].value).startswith(prefix+'_chunk_')))
    assert reconstruct('canonical_bundle')==b
    assert reconstruct('review_context')['decision_history'][0]['note']==note
    with zipfile.ZipFile(csv) as z:
        assert json.loads(z.read('review_context.json'))==reconstruct('review_context')
    assert all(c.data_type!='f' for sheet in book for row in sheet for c in row)

def test_excel_capacity_failure_preserves_existing_export(tmp_path,monkeypatch):
    import vflow.statistics.audit_export as module
    b=run_audit(samples(n=2));path=tmp_path/'existing.xlsx';path.write_bytes(b'old export')
    monkeypatch.setattr(module,'EXCEL_MAX_COLUMNS',2)
    with pytest.raises(ValueError,match='CSV'):export_xlsx(b,path)
    assert path.read_bytes()==b'old export'
    assert list(tmp_path.iterdir())==[path]

@pytest.mark.parametrize('payload',[b'not gzip',gzip.compress(b'{'),gzip.compress(b'[]'),gzip.compress(b'{"audit_schema":1}')])
def test_corrupt_audit_payloads_report_actionable_errors(tmp_path,payload):
    b=run_audit(samples(n=1));ref=commit_bundle(Workspace(),b,state_dir=tmp_path)
    path=tmp_path/'corrupt.gz';path.write_bytes(payload);ref.result=FileReference.create(path)
    with pytest.raises(ValueError,match='corrupt or unsupported'):read_bundle(ref)

def test_unsafe_audit_id_is_rejected_before_creating_files(tmp_path):
    b=run_audit(samples(n=1));b['audit_id']='../../outside'
    with pytest.raises(ValueError,match='identity'):commit_bundle(Workspace(),b,state_dir=tmp_path)
    assert not list(tmp_path.iterdir())
