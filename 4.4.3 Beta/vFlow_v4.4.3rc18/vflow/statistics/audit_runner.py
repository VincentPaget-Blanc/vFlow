"""Transactional, Tk-free within-group audit engine."""
import copy
from datetime import datetime,timezone
import hashlib
import json
import uuid
from numbers import Integral,Real
import numpy as np
from .models import POLICY,ANALYSIS_VERSION,checkpoint
from .variable_eligibility import eligible_variables,describe
from .wasserstein import sorted_w1,isolation
from .sliced_wasserstein import sliced_distances
from .discordance import score_samples
from .hierarchy import analyze_hierarchy

CAVEAT='Distributional discordance does not establish a technical or biological cause. Flags recommend review; no sample is automatically excluded. Biological units, nested samples and particles are distinct replication levels.'

def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)):return [clean(v) for v in value]
    if isinstance(value,(np.bool_,)):return bool(value)
    if isinstance(value,(np.integer,)):return int(value)
    if isinstance(value,(float,np.floating)):return float(value) if np.isfinite(value) else None
    return value

def run_audit(samples,variables=None,audit_type='qc',name=None,population_label='All events',hierarchy_mapping=None,
              policy=None,cancel=None,progress=None):
    if audit_type not in ('qc','hierarchy'):raise ValueError('Unknown audit type.')
    if not samples:raise ValueError('Select unique sample IDs.')
    if any(not isinstance(s.sample_id,str) or not s.sample_id.strip() or not isinstance(s.display_name,str) or not s.display_name.strip() for s in samples):raise ValueError('Samples need non-empty string IDs and display names.')
    if (name is not None and not isinstance(name,str)) or not isinstance(population_label,str):raise ValueError('Audit name and population label must be text.')
    if audit_type=='qc' and hierarchy_mapping:raise ValueError('Biological replicate mapping applies only to hierarchical audits.')
    if not samples or len({s.sample_id for s in samples})!=len(samples):raise ValueError('Select unique sample IDs.')
    params={**POLICY,**(policy or {})}
    if any(k not in POLICY or (isinstance(POLICY[k],str) and v!=POLICY[k]) for k,v in (policy or {}).items()):
        raise ValueError('Unknown or unsupported audit policy setting.')
    for key,minimum in [('n_projections',1),('min_finite',3),('seed',0)]:
        if isinstance(params[key],bool) or not isinstance(params[key],Integral) or params[key]<minimum:
            raise ValueError('Invalid audit policy: '+key+' must be an integer >= '+str(minimum)+'.')
    for key in ('isolation_threshold','robust_z_threshold','influence_threshold','low_n_extreme_isolation_multiplier'):
        if isinstance(params[key],bool) or not isinstance(params[key],Real) or not np.isfinite(params[key]) or params[key]<=0:
            raise ValueError('Invalid audit policy: '+key+' must be finite and positive.')
    if audit_type=='hierarchy':
        if not hierarchy_mapping or set(hierarchy_mapping)!={s.sample_id for s in samples} or any(v is None or not str(v).strip() for v in hierarchy_mapping.values()):
            raise ValueError('Assign exactly one non-empty biological replicate ID to every selected sample.')
        hierarchy_mapping={sid:str(bio).strip() for sid,bio in hierarchy_mapping.items()}
    checkpoint(cancel,progress,'Validating variables')
    eligible,excluded,scales=eligible_variables(samples,params['min_finite'])
    variables=eligible if variables is None else list(variables)
    if not variables or len(set(variables))!=len(variables) or any(v not in eligible for v in variables):
        raise ValueError('Select shared eligible numeric variables; no variable was silently dropped.')
    for v in eligible:
        if v not in variables:excluded.append({'variable':v,'reason':'user_deselected'})
    matrices={};distances=[];descriptions=[]
    size=len(samples)
    for variable in variables:
        checkpoint(cancel,progress,'Per-variable distributions: '+str(variable))
        arrays=[]
        for sample in samples:
            x=sample.dataframe[variable].to_numpy(dtype=float,na_value=np.nan);arrays.append(np.sort(x[np.isfinite(x)]))
            summary=describe(x)
            if any(isinstance(v,float) and not np.isfinite(v) for v in summary.values()):
                raise ValueError(str(variable)+': descriptive statistics exceed the supported numeric range. Rescale the measurements and rerun.')
            descriptions.append({'sample_id':sample.sample_id,'sample_name':sample.display_name,'variable':variable,**summary})
        m=np.zeros((size,size))
        for i in range(size):
            for j in range(i+1,size):
                checkpoint(cancel)
                raw=sorted_w1(arrays[i],arrays[j]);normalized=raw/scales[variable]['scale'];m[i,j]=m[j,i]=normalized
                if not np.isfinite(normalized):raise ValueError(str(variable)+': normalized distance exceeds the supported numeric range.')
                distances.append({'variable':variable,'sample_a':samples[i].sample_id,'sample_b':samples[j].sample_id,'raw_w1':raw,'normalized_w1':normalized})
        matrices[variable]=m
        for i,s in enumerate(samples):
            row=next(r for r in descriptions if r['sample_id']==s.sample_id and r['variable']==variable)
            score,ratio,condition=isolation(m,i);row.update(peer_distance=score,isolation_ratio=ratio,isolation_condition=condition,
                robust_pooled_scale=scales[variable]['scale'],scale_method=scales[variable]['method'],
                raw_peer_distance=score*scales[variable]['scale'] if score is not None else None)
    global_matrix,complete=sliced_distances(samples,variables,scales,params['n_projections'],params['seed'],cancel,progress)
    repeat=None
    if size>=3:
        checkpoint(cancel,progress,'Projection stability validation')
        repeat,_=sliced_distances(samples,variables,scales,params['n_projections'],params['seed']+1,cancel,progress)
    sample_rows=score_samples(samples,global_matrix,matrices,repeat,params)
    warnings=[]
    for i,row in enumerate(sample_rows):
        row.update(event_count=len(samples[i].dataframe),multivariate_complete_count=complete[i],
            multivariate_complete_fraction=complete[i]/len(samples[i].dataframe) if len(samples[i].dataframe) else 0,
            original_source=samples[i].source.get('absolute_path',''),source_format=samples[i].dataframe.attrs.get('vflow_source_format','csv'))
        if complete[i]<len(samples[i].dataframe):warnings.append(samples[i].display_name+': incomplete rows excluded only from multivariate distances; finite univariate values retained.')
    hierarchy=[];components=[];influence=[];centers=[]
    if audit_type=='hierarchy':
        hierarchy,components,influence,centers=analyze_hierarchy(samples,variables,hierarchy_mapping or {},params,cancel,progress)
        warnings.extend(str(r['variable'])+': '+r['model_status'] for r in components if r['model_status'] not in ('converged','boundary'))
    created=datetime.now(timezone.utc).isoformat();audit_id=('QC' if audit_type=='qc' else 'HIER')+'-'+datetime.now(timezone.utc).strftime('%Y%m%d')+'-'+uuid.uuid4().hex[:12]
    snapshots=[{'sample_id':s.sample_id,'display_name':s.display_name,'source':s.source,'population_snapshot':s.population_snapshot,
        'population_sha256':hashlib.sha256(json.dumps(clean(s.population_snapshot),sort_keys=True,allow_nan=False).encode()).hexdigest()} for s in samples]
    import importlib.metadata
    dependencies={p:importlib.metadata.version(p) for p in ('numpy','pandas','scipy','openpyxl')}
    result=clean({'audit_schema':1,'audit_id':audit_id,'name':name or audit_id,'audit_type':audit_type,'created_at':created,
        'vflow_version':'4.4.3rc18','analysis_version':ANALYSIS_VERSION,'population_label':population_label,
        'samples':snapshots,'variables':variables,'excluded_variables':excluded,'scaling':{v:scales[v] for v in variables},
        'policy':params,'dependencies':dependencies,'transformation':'source measurement values; raw W1 in measurement units, W1 divided by pooled robust scale, SWD on pooled robust centered/scaled complete rows',
        'global_distance_matrix':global_matrix,'projection_repeat_matrix':repeat,'variable_matrices':matrices,
        'sample_qc':sample_rows,'variable_qc':descriptions,'variable_distances':distances,'hierarchy':hierarchy,
        'hierarchy_mapping':hierarchy_mapping or {},'variance_components':components,'influence':influence,
        'equal_bio_centers':centers,'warnings':warnings,'interpretation':CAVEAT,'event_subsampling':False})
    checkpoint(cancel,progress,'Calculation complete')
    return result
