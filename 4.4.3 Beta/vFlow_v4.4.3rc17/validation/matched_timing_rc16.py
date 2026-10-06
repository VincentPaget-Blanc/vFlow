"""Matched RC15/RC16 workflows; run in fresh, alternating processes without concurrent validation."""
import argparse, hashlib, json, os, platform, shutil, statistics, subprocess, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,default=ROOT);p.add_argument('--worker',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if a.worker:
    sys.path.insert(0,str(a.candidate.resolve()))
    from vflow import __version__
    from vflow.io.registry import read_flow_source
    from vflow.workspace.model import Workspace,FileReference,SampleReference,fingerprint
    from vflow.statistics import AuditSample,run_audit
    from vflow.statistics.audit_export import export_csv_package,export_xlsx
    from vflow.core.gate_masks import compute_gate_regions
    import numpy as np
    import pandas as pd
    timings={}
    def measured(name,call):
        start=time.perf_counter();value=call();timings[name]=time.perf_counter()-start;return value
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);paths=[]
        for name in ('Control_01.csv','Control_02.csv','Treatment_01.csv','Treatment_02.csv'):
            target=td/name;shutil.copy2(ROOT/'benchmark_extensions/frozen_v1/cytometry'/name,target);paths.append(target)
        measured('source_fingerprints_48k',lambda:[fingerprint(path) for path in paths])
        data=measured('CSV_ingestion_48k',lambda:[read_flow_source(path).samples[0].dataframe for path in paths])
        lmd=td/'188-15.LMD';shutil.copy2(ROOT/'benchmark_extensions/lmd'/lmd.name,lmd)
        original=measured('LMD_decode_and_materialize',lambda:read_flow_source(lmd).samples[0])
        cached=measured('owned_CSV_redirect_cached',lambda:read_flow_source(original.materialized_path).samples[0])
        pd.testing.assert_frame_equal(original.dataframe,cached.dataframe)
        definition=json.loads((ROOT/'benchmark_extensions/frozen_v1/references/benchmark_gate_definitions.json').read_text())['gates'][0]
        definition.update(id=1,applied=True)
        counts=measured('rectangle_gates_48k',lambda:[int(compute_gate_regions(definition,df['FSC-A'].to_numpy(float),df['SSC-A'].to_numpy(float),x_scale='linear',y_scale='linear',cofactor=150.,x_channel='FSC-A',y_channel='SSC-A')[0]['IN'].sum()) for df in data])
        assert counts==[7273,7020,7081,7058]
        bundle=measured('audit_full_48k',lambda:run_audit([AuditSample(str(i),paths[i].name,df) for i,df in enumerate(data)],variables=['FSC-A','SSC-A']))
        w=Workspace();w.samples={str(i):SampleReference(str(i),path.name,FileReference.create(path)) for i,path in enumerate(paths)}
        measured('verified_references_48k',lambda:[r.source.accept(paths[int(i)],None) for i,r in w.samples.items()])
        def save_edit_reopen():
            path=td/'study.vflow';w.save(path);loaded=Workspace.load(path);loaded.ui_state['workspace_name']='Edited';loaded.save(path)
            assert Workspace.load(path).ui_state['workspace_name']=='Edited'
        measured('workspace_save_edit_reopen',save_edit_reopen)
        measured('audit_CSV_and_XLSX_exports',lambda:(export_csv_package(bundle,td/'audit.zip'),export_xlsx(bundle,td/'audit.xlsx')))
        numeric={k:bundle[k] for k in ('sample_qc','variable_qc','global_distance_matrix','projection_repeat_matrix','variable_matrices','variable_distances','scaling') if k in bundle}
        lmd_digest=hashlib.sha256(np.asarray(original.dataframe,dtype='<f8').tobytes()).hexdigest()
        receipt={'version':__version__,'timings':timings,'counts':counts,'LMD_float64_sha256':lmd_digest,
            'numerical_sha256':hashlib.sha256(json.dumps(numeric,sort_keys=True,allow_nan=False).encode()).hexdigest()}
        a.output.write_text(json.dumps(receipt,indent=2)+'\n')
else:
    rows=[];out=a.output.parent/'matched_timing';out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    for rep in range(6):
        for label,source in ((('rc15',a.baseline),('rc16',a.candidate)) if rep%2==0 else (('rc16',a.candidate),('rc15',a.baseline))):
            target=out/f'timing_{label}_{rep}.json'
            subprocess.run([sys.executable,'-u',str(Path(__file__).resolve()),'--worker','--baseline',str(a.baseline),
                '--candidate',str(source),'--output',str(target)],env=env,check=True,timeout=180)
            row=json.loads(target.read_text());row.update(repetition=rep,warmup=rep==0);rows.append(row);print(label,rep,json.dumps(row['timings']),flush=True)
    assert len({r['numerical_sha256'] for r in rows})==len({r['LMD_float64_sha256'] for r in rows})==1
    summary={}
    for task in rows[0]['timings']:
        left=statistics.median(r['timings'][task] for r in rows if r['version']=='4.4.3rc15' and not r['warmup'])
        right=statistics.median(r['timings'][task] for r in rows if r['version']=='4.4.3rc16' and not r['warmup'])
        summary[task]={'rc15_median_seconds':left,'rc16_median_seconds':right,'ratio_rc16_over_rc15':right/left}
    a.output.write_text(json.dumps({'passed':True,'python':sys.version,'platform':platform.platform(),'warmups_per_version':1,
        'measured_runs_per_version':5,'alternating_order':True,'threads':1,'subsampling':False,'events':48000,
        'numerical_results_identical':True,'summary':summary,'runs':rows},indent=2)+'\n')
