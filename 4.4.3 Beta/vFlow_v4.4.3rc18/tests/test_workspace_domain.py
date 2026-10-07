import copy
import json
from dataclasses import asdict
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from matplotlib.figure import Figure
from vflow.app.state import AnalysisState
from vflow.app.cache import AnalysisCache
from vflow.core.gate_masks import compute_gate_regions
from vflow.core.transforms import VALID_SCALES, transform_xy
from vflow.services.gate_evaluation import evaluate_gate_regions
from vflow.workspace.model import Workspace, SampleReference, FileReference, ViewState, atomic_json
from vflow.workspace.relink import scan_candidates, bulk_remap
from vflow.workspace.gates import GateStore, filter_lineage, resolve_lineage_for_sample, decode_session
from vflow.workspace.controller import session_payload
from vflow.plotting.offscale import clamp_scatter_offsets, edge_histogram, classify


def gate(kind='rectangle', gid=0):
    g={'id':gid,'name':f'Gate {gid}','type':kind,'applied':True,'color':'#00aa88',
        'x0':20.,'x1':100.,'y0':20.,'y1':100.,'vertices':[(20,20),(100,20),(100,100),(20,100)],
        'x_boundaries':[60.], 'y_boundary':60.,'x_thresh_vars':[True], 'y_thresh_var':True,
        'y_boundaries':[], 'y_thresh_vars':[], '_analysis_context':AnalysisState('X','Y','linear','linear').context_dict()}
    return g


def test_workspace_roundtrip_references_only_and_atomic(tmp_path):
    source=tmp_path/'data.csv';source.write_text('X,Y\n1,2\n')
    session=tmp_path/'gates.json';atomic_json(session,session_payload([gate()]))
    w=Workspace();w.samples['A']=SampleReference('A','A',FileReference.create(source),view=ViewState('X','Y'))
    w.default_gate_session=FileReference.create(session,kind='gates')
    dest=tmp_path/'experiment.vflow';w.save(dest);loaded=Workspace.load(dest)
    assert loaded.samples['A'].source.resolve(dest)==str(source)
    assert loaded.samples['A'].view.x_channel=='X'
    assert loaded.default_gate_session.resolve(dest)==str(session)
    raw=json.loads(dest.read_text());assert 'gates' not in raw and 'vertices' not in dest.read_text()
    assert raw['samples']['A']['source']['relative_path']=='data.csv'
    assert not list(tmp_path.glob('*.tmp'))

@pytest.mark.parametrize('schema',[None,0,3,'1',True])
def test_rejects_unsupported_schema(tmp_path,schema):
    p=tmp_path/'bad.vflow';p.write_text(json.dumps({'workspace_schema':schema}))
    with pytest.raises(ValueError):Workspace.load(p)


def test_atomic_invalid_json_leaves_saved_bytes(tmp_path):
    p=tmp_path/'w.vflow';atomic_json(p,{'ok':1});before=p.read_bytes()
    with pytest.raises(ValueError):atomic_json(p,{'value':float('nan')})
    assert p.read_bytes()==before


def test_identity_rejects_wrong_same_name_and_preserves_ambiguity(tmp_path):
    old=tmp_path/'old';old.mkdir();p=old/'data.csv';p.write_text('X,Y\n1,2\n');r=FileReference.create(p)
    root=tmp_path/'new';root.mkdir()
    for name,content in [('a','X,Y\n1,2\n'),('b','X,Y\n1,2\n'),('c','X,Y\n9,8\n')]:
        d=root/name;d.mkdir();(d/'data.csv').write_text(content)
    p.unlink();matches=scan_candidates([('A',r)],root)
    assert len(matches['A'])==2
    assert len(bulk_remap([('A',r)],old,root/'a'))==1
    with pytest.raises(ValueError):r.accept(root/'c'/'data.csv',tmp_path/'w.vflow')


def test_relative_move_and_save_as(tmp_path):
    old=tmp_path/'old';old.mkdir();p=old/'data.csv';p.write_text('X,Y\n1,2\n')
    w=Workspace();w.samples['A']=SampleReference('A','A',FileReference.create(p));w.save(old/'w.vflow')
    new=tmp_path/'new';old.rename(new);loaded=Workspace.load(new/'w.vflow')
    assert loaded.samples['A'].source.resolve(new/'w.vflow')==str(new/'data.csv')
    loaded.samples['A'].source.accept(new/'data.csv',new/'w.vflow');loaded.save(tmp_path/'elsewhere.vflow')
    assert loaded.samples['A'].source.relative_path=='new/data.csv'

@pytest.mark.parametrize('kind',['rectangle','ellipse','polygon','crosshair'])
@pytest.mark.parametrize('scale',sorted(VALID_SCALES))
def test_no_override_identical_science_cache_and_display_only_limits(kind,scale):
    g=gate(kind);store=GateStore([g]);state=AnalysisState('X','Y',scale,scale);cache=AnalysisCache()
    x=np.array([-20.,0.,10.,30.,60.,80.,100.,120.,220.,np.nan,np.inf]);y=np.array([50.,0.,10.,30.,60.,80.,100.,120.,70.,50.,50.])
    before=x.copy();baseline,_=evaluate_gate_regions(copy.deepcopy(g),x,y,analysis_state=state,analysis_cache=cache,cache_path='baseline')
    for sample in ['A','B']:
        result,_=evaluate_gate_regions(store.resolve_gate(sample,0),x,y,analysis_state=state,analysis_cache=cache,cache_path=sample)
        for region in baseline:np.testing.assert_array_equal(result[region],baseline[region])
    replacement=gate(kind);replacement['x1']=200.;store.copy_to_sample(replacement,'B',['X','Y'])
    resolved=store.resolve_gate('B',0);assert resolved['x1']==200 and store.resolve_gate('A',0)['x1']==100
    fig=Figure();ax=fig.subplots()
    from vflow.core.scales import register_flow_scales
    register_flow_scales()
    for axis in ('x','y'):
        from vflow.core.transforms import scale_uses_cofactor, scale_uses_logicle_params
        from vflow.core.logicle import LogicleParameters
        params = LogicleParameters().as_dict() if scale_uses_logicle_params(scale) else ({'cofactor':150.} if scale_uses_cofactor(scale) else {})
        getattr(ax,'set_'+axis+'scale')(scale, **params)
    ax.set_xlim((1,100) if scale=='log' else (0,100));ax.set_ylim((1,100) if scale=='log' else (0,100))
    _,_,valid=transform_xy(x,y,scale,scale,150.)
    rendered=clamp_scatter_offsets(ax,np.c_[x[valid],y[valid]],inset_pixels=0)
    assert np.all(rendered<=100)
    after,_=evaluate_gate_regions(store.resolve_gate('A',0),x,y,analysis_state=state,analysis_cache=cache,cache_path='A')
    for region in baseline:np.testing.assert_array_equal(after[region],baseline[region])
    np.testing.assert_array_equal(x,before)


def test_sparse_copy_reset_promotion_and_exact_undo():
    store=GateStore([gate()]);before=store.snapshot()
    store.copy_to_sample(store.resolve_gate('A',0),'B',['X','Y'])
    store.commit(store.resolve_gate_set('B'),'B');assert 0 in store.sample_overrides['B']
    assert store.undo() and store.snapshot()==before
    changed=gate();changed['x1']=80;store.copy_to_sample(changed,'B',['X','Y'])
    store.promote('B',0);assert store.resolve_gate('A',0)['x1']==80
    assert store.undo() and store.resolve_gate('A',0)['x1']==100
    store.reset('B',0);assert store.resolve_gate('B',0)['x1']==100
    with pytest.raises(ValueError):store.copy_to_sample(changed,'C',['X'])


def test_sample_delete_tombstone_and_undo():
    store=GateStore([gate()]);store.checkpoint();store.commit([],'B')
    assert store.resolve_gate('B',0) is None and store.resolve_gate('A',0)
    assert store.undo() and store.resolve_gate('B',0)


def test_nested_lineage_resolves_per_sample_without_gate_id_collision():
    df=pd.DataFrame({'X':[30.,50.,90.,120.],'Y':[30.,50.,90.,120.]})
    parent=GateStore([gate()]);child=GateStore([gate(gid=0)])
    altered=gate();altered['x1']=70;parent.copy_to_sample(altered,'B',df.columns)
    lineage=[{'workspace_tab_id':'parent','gate':gate(),'context':gate()['_analysis_context'],'region':'IN'},
        {'workspace_tab_id':'child','gate':gate(),'context':gate()['_analysis_context'],'region':'IN'}]
    stores={'parent':parent,'child':child}
    assert len(filter_lineage(df,resolve_lineage_for_sample('A',lineage,stores)))==3
    assert len(filter_lineage(df,resolve_lineage_for_sample('B',lineage,stores)))==2
    parent.reset('B',0);assert len(filter_lineage(df,resolve_lineage_for_sample('B',lineage,stores)))==3
    assert lineage[0]['gate']['x1']==100
    with pytest.raises(ValueError):resolve_lineage_for_sample('B',lineage,{})

@pytest.mark.parametrize('scale',sorted(VALID_SCALES))
def test_edge_histograms_keep_valid_denominator(scale):
    raw=np.array([-20.,0.,50.,100.,120.,np.nan,np.inf]);_,_,valid=transform_xy(raw,raw,scale,scale,150.)
    limits=(1.,100.) if scale=='log' else (0.,100.)
    counts,edges=edge_histogram(raw,valid,limits,scale,150.,None,bins=4)
    assert counts.sum()==valid.sum()
    assert counts[-1]>=2
    assert edges[0]==pytest.approx(limits[0]) and edges[-1]==pytest.approx(limits[1])


def test_view_overlay_isolation_channel_failure_and_gate_session_validation():
    a=ViewState('FSC-A','SSC-A');b=ViewState('CD3-A','CD4-A',cofactor=50)
    w=Workspace(overlay_view=a);w.samples['B']=SampleReference('B','B',FileReference('/unavailable'),view=b)
    w.overlay_view.x_channel='Other';assert w.samples['B'].view.x_channel=='CD3-A'
    assert b.missing_channels(['CD3-A'])==['CD4-A']
    payload=session_payload([gate()]);decoded=decode_session(payload);assert decoded[0]['id']==0
    payload['version']=100
    with pytest.raises(ValueError):decode_session(payload)


def test_portable_gate_session_provenance_ignores_workspace_namespace():
    from vflow.services.gate_session import normalize_lineage_contexts
    original=[{'gate':gate(),'context':gate()['_analysis_context'],'region':'IN'}]
    workspace=copy.deepcopy(original);workspace[0]['workspace_tab_id']='parent'
    assert normalize_lineage_contexts(workspace)==normalize_lineage_contexts(original)
    assert 'workspace_tab_id' in workspace[0]
