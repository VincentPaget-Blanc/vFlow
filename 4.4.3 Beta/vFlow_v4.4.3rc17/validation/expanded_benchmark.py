#!/usr/bin/env python3
"""Replay frozen files and full-event statistical truth; record time and peak RSS."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import shutil
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from vflow.io.registry import read_flow_source
from vflow.statistics import AuditSample,run_audit
from vflow.statistics.hierarchy import sufficient_stats,estimate
from tests.test_statistical_audit import samples,hierarchical
from tests.format_fixtures import write_fixture

def run(corpus,output):
    results=[];timings=[]
    def check(label,condition,**details):
        results.append({'check':label,'pass':bool(condition),**details})
        if not condition:raise AssertionError(label)
    def audit(label,s,**kwargs):
        start=time.perf_counter();result=run_audit(s,**kwargs)
        timings.append({'scenario':label,'seconds':time.perf_counter()-start,'samples':len(s),'rows':sum(len(a.dataframe) for a in s),'variables':len(result['variables']),'projections':result['policy']['n_projections'],'subsampling':result['event_subsampling']})
        print(label,round(timings[-1]['seconds'],3),'seconds',flush=True)
        return result
    extension=Path(__file__).resolve().parents[1]/'benchmark_extensions'
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        truth=json.loads((extension/'lmd/reference_values.json').read_text())['fixtures']
        for expected in truth:
            source=td/expected['file'];shutil.copyfile(extension/'lmd'/source.name,source)
            result=read_flow_source(source);values=np.asarray(result.samples[0].dataframe,dtype='<f8')
            check('real_LMD:'+source.name,len(result.samples)==1 and hashlib.sha256(values.tobytes()).hexdigest()==expected['canonical_float64_sha256'],events=len(values))
        for version in ('FCS1.0','FCS2.0','FCS3.0','FCS3.1'):
            source,values=write_fixture(td/(version+'.fcs'),version=version,types=('I','I'),bits=(16,16),names=('X','Y'),rows=[(1,2),(3,4),(5,6)])
            check('synthetic:'+version,np.array_equal(read_flow_source(source).samples[0].dataframe.to_numpy(),values))
        for order in ('<','>'):
            source,values=write_fixture(td/('mixed'+str(ord(order))+'.fcs'),endian=order)
            df=read_flow_source(source).samples[0].dataframe
            check('synthetic:FCS3.2 mixed '+order,df.iloc[0,0]==9007199254740993 and df['Index'].dtype==np.uint64 and all(np.array_equal(df.iloc[:,i].to_numpy(),[r[i] for r in values]) for i in range(3)))
    r=audit('concordant',samples())
    check('concordant_no_false_flags',all(x['status']=='concordant' for x in r['sample_qc']))
    s=samples();s[-1].dataframe+=8;r=audit('multivariable shift',s)
    check('shifted_peer_flagged',r['sample_qc'][-1]['status']=='flagged_for_review' and r['sample_qc'][-1]['projection_stability'])
    x=np.linspace(-3,3,500);s=[AuditSample(str(i),str(i),pd.DataFrame({'a':x,'b':x if i<4 else x[::-1]})) for i in range(5)]
    r=audit('joint only covariance',s)
    check('identical_marginals_joint_flag',all(d['raw_w1']==0 for d in r['variable_distances']) and r['sample_qc'][-1]['status']=='flagged_for_review')
    for n,status in ((1,'insufficient_peers'),(2,'pairwise_only'),(3,'low_n_review_candidate'),(4,'low_n_review_candidate')):
        s=samples(n=n)
        if n>2:s[-1].dataframe+=8
        r=audit('small N='+str(n),s);check('small_N_semantics:'+str(n),r['sample_qc'][-1]['status']==status)
    s=samples();s[0].dataframe.loc[:9,'Distance']=np.nan;r=audit('missing values',s)
    check('complete_cases_no_imputation',r['sample_qc'][0]['multivariate_complete_count']==len(s[0].dataframe)-10)
    for folder,pattern in (('cytometry','Control_0[12].csv'),('microscopy','Microscopy_0[123].csv')):
        s=[AuditSample(p.stem,p.stem,read_flow_source(p).samples[0].dataframe) for p in sorted((corpus/folder).glob(pattern))]
        r=audit('frozen '+folder+' audit',s)
        shared=set.intersection(*(set(a.dataframe.select_dtypes(include='number').columns) for a in s))
        check(folder+':shared_attribute_coverage',set(r['variables'])==shared-set(d['variable'] for d in r['excluded_variables']))
        check(folder+':all_events',all(q['event_count']==len(s[i].dataframe) for i,q in enumerate(r['sample_qc'])) and not r['event_subsampling'])
    s,m=hierarchical();fit=estimate(sufficient_stats(s,'x',m))
    check('known_hierarchy_variance_recovery',fit['model_status']=='converged' and abs(fit['sigma2_bio']-4)<2 and abs(fit['sigma2_nested_sample']-1)<.5 and abs(fit['sigma2_particle']-1)<.08,estimate=fit)
    s,m=hierarchical(bios=5,nested=3,particles=30)
    s=[sample for sample in s if sample.sample_id!='0-2']
    m={sample.sample_id:m[sample.sample_id] for sample in s}
    for a in s:
        if m[a.sample_id]=='4':a.dataframe.x+=25
        if m[a.sample_id]=='0':a.dataframe=pd.concat([a.dataframe]*10,ignore_index=True)
    r=audit('unbalanced hierarchical influence',s,audit_type='hierarchy',hierarchy_mapping=m)
    biggest=max(r['influence'],key=lambda a:a['absolute_change'])
    check('equal_bio_influential_shift',biggest['omitted_bio']=='4' and biggest['influence_status']=='influential')
    rng=np.random.default_rng(443)
    s=[AuditSample(str(i),str(i),pd.DataFrame(rng.normal(size=(50000,3)),columns=['a','b','c'])) for i in range(5)]
    r=audit('250000-event full-data profile',s)
    check('large_full_event_counts',all(x['multivariate_complete_count']==50000 for x in r['sample_qc']) and not r['event_subsampling'])
    report={'passed':sum(r['pass'] for r in results),'checks':len(results),'results':results,'timings':timings,'peak_process_rss_MiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,'MQD':'blocked: verified same-acquisition native/export corpus unavailable','FCS1.0':'synthetic only: real reference acceptance blocked','FCS3.2':'synthetic mixed numeric truth; external/vendor acquisition acceptance pending'}
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(f"{report['passed']}/{report['checks']} expanded checks passed; peak RSS {report['peak_process_rss_MiB']:.1f} MiB",flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('corpus',type=Path);p.add_argument('--output',type=Path,default=Path(__file__).with_name('expanded_benchmark_results.json'));a=p.parse_args();run(a.corpus,a.output)
