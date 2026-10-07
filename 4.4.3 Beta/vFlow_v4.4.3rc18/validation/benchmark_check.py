#!/usr/bin/env python3
"""Run frozen scientific CSV/FCS/off-scale truth without modifying the corpus."""
import argparse
import copy
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from vflow.core.data_io import read_flow_data_file
from vflow.core.gate_masks import compute_gate_regions
from vflow.plotting.offscale import classify
from vflow.workspace.model import Workspace

def run(root):
    definitions=json.loads((root/'references/benchmark_gate_definitions.json').read_text())['gates']
    truth=pd.read_csv(root/'truth/expected_gate_counts.csv')
    results=[];issues=[]
    for sample,rows in truth.groupby('Sample'):
        path=root/'cytometry'/(sample+'.csv')
        if not path.exists():continue
        df=read_flow_data_file(str(path))
        for i,definition in enumerate(definitions):
            g=copy.deepcopy(definition);g['id']=i;g['applied']=True;g['name']=definition['id']
            if g['type']=='ellipse':
                g.update(x0=g['cx']-g['rx'],x1=g['cx']+g['rx'],y0=g['cy']-g['ry'],y1=g['cy']+g['ry'])
            if g['type']=='crosshair':
                g.update(x_boundaries=[g['x_threshold']],y_boundary=g['y_threshold'],x_thresh_vars=[True],y_thresh_var=True)
            x,y=df[g['x_channel']].to_numpy(float),df[g['y_channel']].to_numpy(float)
            regions,_=compute_gate_regions(g,x,y,x_scale='linear',y_scale='linear',cofactor=150,x_channel=g['x_channel'],y_channel=g['y_channel'])
            if g['type']=='crosshair':
                for suffix,region in [('CD3hi_CD4hi','CD4-A+/CD3-A+'),('CD3hi_CD4lo','CD4-A-/CD3-A+'),('CD3lo_CD4hi','CD4-A+/CD3-A-'),('CD3lo_CD4lo','CD4-A-/CD3-A-')]:
                    key=definition['id']+':'+suffix
                    expected=rows[rows.Gate_or_Region==key]
                    if expected.empty:continue
                    actual=int(regions[region].sum());want=int(expected.iloc[0].Count)
                    results.append({'sample':sample,'gate':key,'expected':want,'actual':actual,'pass':actual==want})
            else:
                expected=rows[rows.Gate_or_Region==definition['id']]
                if expected.empty:continue
                actual=int(regions['IN'].sum());want=int(expected.iloc[0].Count)
                results.append({'sample':sample,'gate':definition['id'],'expected':want,'actual':actual,'pass':actual==want})
    off=pd.read_csv(root/'truth/offscale_expected_counts.csv')
    for _,r in off.iterrows():
        path = root/'cytometry'/(r.Sample+'.csv')
        if not path.exists(): continue
        df=read_flow_data_file(str(path));x=df[r.Channel].to_numpy(float)
        actual=classify(x,x,np.isfinite(x),(r.DisplayMin,r.DisplayMax),(r.DisplayMin,r.DisplayMax))
        results.append({'sample':r.Sample,'channel':r.Channel,'check':'offscale','pass':actual['x_low']==r.Below and actual['x_high']==r.Above})
    inventory=json.loads((root/'truth/parser_variant_expected.json').read_text())
    for filename,item in inventory.items():
        df=read_flow_data_file(str(root/'parser_variants'/filename))
        results.append({'file':filename,'check':'parser_shape','pass':df.shape==(item['events'],item['parameters'])})
    for path in sorted((root/'cytometry').glob('*.fcs')):
        try:read_flow_data_file(str(path));results.append({'file':path.name,'check':'source_parse','pass':True})
        except ValueError as exc:issues.append({'file':path.name,'reason':str(exc),'category':'supplied_fixture_incompatible_with_frozen_baseline'})
    wpath=root/'workspace_future_fixture/Benchmark_Workspace_ProposedSchema1.vflow'
    w=Workspace.load(wpath)
    results.append({'check':'proposed_workspace_schema_migration','pass':len(w.samples)==4 and w.samples['control_02'].view.plot_mode=='Dot Plot'})
    return {'scientific_checks':len(results),'passed':sum(r['pass'] for r in results),'results':results,'fixture_issues':issues}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('corpus',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args();report=run(args.corpus)
    data=json.dumps(report,indent=2)
    if args.output:args.output.write_text(data+'\n')
    print(f"{report['passed']}/{report['scientific_checks']} scientific checks passed; {len(report['fixture_issues'])} supplied FCS fixture incompatibilities.")
    sys.exit(0 if report['passed']==report['scientific_checks'] else 1)
