#!/usr/bin/env python3
"""Create the handoff's three-sample experiment, referencing the frozen CSV corpus."""
import argparse,copy,json,sys
from pathlib import Path
from dataclasses import asdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from vflow.app.state import AnalysisState
from vflow.workspace.model import Workspace,FileReference,SampleReference,ViewState,atomic_json
from vflow.workspace.controller import session_payload
from vflow.workspace.gates import GateStore,filter_lineage,resolve_lineage_for_sample
from vflow.core.data_io import read_flow_data_file
from vflow.services.population_evaluation import regions_in_explicit_context

def build(corpus,output):
    output.mkdir(parents=True,exist_ok=True)
    path=output/'Golden_Experiment.vflow';w=Workspace()
    ids=['sample_A','sample_B','sample_C'];names=['Control_01','Control_02','Treatment_01']
    views=[ViewState('FSC-A','SSC-A',plot_mode='Dot Plot'),ViewState('CD3-A','CD4-A','logicle_gml2','logicle_gml2',plot_mode='Dot Plot'),ViewState('CD4-A','CD8-A',plot_mode='Dot Plot')]
    for sid,name,view in zip(ids,names,views):
        source=corpus/'cytometry'/(name+'.csv')
        w.samples[sid]=SampleReference(sid,name+'.csv',FileReference.create(source,path),view=view)
    w.overlay_view=ViewState('FSC-A','SSC-A',plot_mode='Dot Plot')
    def rectangle(gid,name,x,y,x0,x1,y0,y1):
        return {'id':gid,'name':name,'type':'rectangle','applied':True,'color':'#00a6a6',
            'x0':x0,'x1':x1,'y0':y0,'y1':y1,'_analysis_context':AnalysisState(x,y,'asinh','asinh',150).context_dict()}
    parent=rectangle(0,'Lymphocytes','FSC-A','SSC-A',45000.,105000.,5000.,55000.)
    main=GateStore([parent]);custom=copy.deepcopy(parent);custom['x1']=85000.
    main.sample_overrides['sample_B']={0:custom}
    child_gate=rectangle(0,'CD3+ CD4+','CD3-A','CD4-A',1000.,1e6,1000.,1e6)
    child=GateStore([child_gate]);custom_child=copy.deepcopy(child_gate);custom_child['x0']=2000.
    child.sample_overrides['sample_C']={0:custom_child}
    lineage=[{'workspace_tab_id':'main','gate':parent,'context':parent['_analysis_context'],'region':'IN'}]
    w.tabs['main']={'title':'Main','lineage':[],'overlay_view':asdict(w.overlay_view),
        'sample_views':{sid:asdict(view) for sid,view in zip(ids,views)},'ui_state':{'view_mode':'cycle','current_sample_id':'sample_A'},'sections':{},'sample_ids':None}
    child_view=ViewState('CD3-A','CD4-A',plot_mode='Dot Plot')
    w.tabs['child']={'title':'Lymphocytes','lineage':[{'workspace_tab_id':'main','gate_id':0,'region':'IN'}],
        'overlay_view':asdict(child_view),'sample_views':{},'ui_state':{'view_mode':'overlay'},'sections':{},'sample_ids':ids}
    w.ui_state={'view_mode':'cycle','current_sample_id':'sample_A'}
    bundle={'vflow_workspace_gates':1,'workspace_id':w.workspace_id,'tabs':{}}
    stores={'main':main,'child':child}
    for tab_id,store in stores.items():
        bundle['tabs'][tab_id]={'global_session':session_payload(store.global_gates),
            'sample_sessions':{sid:session_payload(list(gates.values())) for sid,gates in store.sample_overrides.items()},
            'sample_deleted_gate_ids':{},'population_lineage':lineage if tab_id=='child' else []}
    gate_path=output/'Golden_Experiment_gates.json';atomic_json(gate_path,bundle)
    w.default_gate_session=FileReference.create(gate_path,path,'gates');w.save(path)
    expected={}
    for sid,sample in w.samples.items():
        df=read_flow_data_file(sample.source.absolute_path)
        df=filter_lineage(df,resolve_lineage_for_sample(sid,lineage,stores))
        gate=child.resolve_gate(sid,0);ctx=gate['_analysis_context']
        regions,_=regions_in_explicit_context(gate,df[ctx['x_channel']].to_numpy(float),df[ctx['y_channel']].to_numpy(float),ctx,fallback_cofactor=150.)
        expected[sid]={'parent_denominator':len(df),'child_IN':int(regions['IN'].sum())}
    atomic_json(output/'Golden_Experiment_expected_counts.json',expected)
    print(path);print(json.dumps(expected,indent=2));return path

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('corpus',type=Path);p.add_argument('output',type=Path);a=p.parse_args();build(a.corpus.resolve(),a.output.resolve())
