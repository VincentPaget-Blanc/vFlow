"""Immutable external bundles and append-only decisions in workspace references."""
import gzip
import json
import os
import re
import math
import shutil
import hashlib
from pathlib import Path
import tempfile
from datetime import datetime,timezone
from vflow.workspace.model import FileReference, AuditReference
from .audit_runner import clean

def validate_bundle(bundle):
    try:
        if not isinstance(bundle,dict) or bundle['audit_schema']!=1 or not re.fullmatch(r'[A-Za-z0-9_-]+',bundle['audit_id']):
            raise ValueError('Unsupported audit identity/schema.')
        for key in ('name','audit_type','created_at','population_label','vflow_version','analysis_version','interpretation','transformation'):
            if not isinstance(bundle[key],str):raise ValueError('Invalid '+key+'.')
        for key in ('samples','variables','excluded_variables','sample_qc','variable_qc','variable_distances','hierarchy','variance_components','influence','equal_bio_centers','warnings'):
            if not isinstance(bundle[key],list):raise ValueError('Invalid '+key+'.')
        for key in ('scaling','policy','dependencies','variable_matrices','hierarchy_mapping'):
            if not isinstance(bundle[key],dict):raise ValueError('Invalid '+key+'.')
        if bundle['audit_type'] not in ('qc','hierarchy'):raise ValueError('Unknown audit type.')
        ids=[s['sample_id'] for s in bundle['samples']]
        if not ids or len(set(ids))!=len(ids) or any(not isinstance(s,str) or not s for s in ids):
            raise ValueError('Invalid selected sample IDs.')
        if [r['sample_id'] for r in bundle['sample_qc']]!=ids:raise ValueError('Sample results do not match the recorded selection.')
        for row in bundle['sample_qc']:
            for key in ('sample_name','status','isolation_condition','original_source'):
                if not isinstance(row[key],str):raise ValueError('Invalid sample result: '+key+'.')
            for key in ('global_peer_distance','global_isolation_ratio','robust_z'):
                if row[key] is not None and (not isinstance(row[key],(int,float)) or not math.isfinite(row[key])):
                    raise ValueError('Invalid sample score.')
            for key in ('event_count','multivariate_complete_count'):
                if not isinstance(row[key],int) or row[key]<0:raise ValueError('Invalid event count.')
            if not isinstance(row['reason_codes'],list) or row['projection_stability'] not in (True,False,None):raise ValueError('Invalid sample classification.')
            for contributor in row['contributors']:
                if not isinstance(contributor['variable'],str):raise ValueError('Invalid contributor variable.')
        matrices=[bundle['global_distance_matrix'],*bundle['variable_matrices'].values()]
        if bundle['projection_repeat_matrix'] is not None:matrices.append(bundle['projection_repeat_matrix'])
        for matrix in matrices:
            if len(matrix)!=len(ids) or any(len(row)!=len(ids) for row in matrix):raise ValueError('Invalid distance matrix dimensions.')
            if any(value is not None and (not isinstance(value,(int,float)) or not math.isfinite(value) or value<0) for row in matrix for value in row):
                raise ValueError('Invalid distance matrix value.')
        for sample in bundle['samples']:
            if sample['source']:FileReference(**sample['source']).validate()
            if not isinstance(sample['population_snapshot'],dict):raise ValueError('Invalid population snapshot.')
            if not isinstance(sample['display_name'],str) or not isinstance(sample['population_sha256'],str):raise ValueError('Invalid sample provenance.')
        _validate_tables_and_provenance(bundle)
    except (KeyError,TypeError,AttributeError,IndexError,OverflowError) as exc:
        raise ValueError('Incomplete or malformed audit bundle.') from exc
    return bundle

def _validate_tables_and_provenance(bundle):
    """Check relationships used by the UI/export, not just JSON field presence."""
    ids=[s['sample_id'] for s in bundle['samples']];variables=bundle['variables'];policy=bundle['policy']
    def number(value,nonnegative=False):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or (nonnegative and value<0):
            raise ValueError('Invalid numeric audit value.')
    def count(value):
        if type(value) is not int or value<0:raise ValueError('Invalid audit count.')
    if not variables or any(not isinstance(v,str) or not v for v in variables) or len(set(variables))!=len(variables):
        raise ValueError('Invalid measurement selection.')
    if set(bundle['scaling'])!=set(variables) or set(bundle['variable_matrices'])!=set(variables):raise ValueError('Measurement tables do not match the selection.')
    for key in ('isolation_threshold','robust_z_threshold','influence_threshold'):
        number(policy[key]);
        if policy[key]<=0:raise ValueError('Invalid stored review threshold.')
    for key,minimum in (('n_projections',1),('min_finite',3),('seed',0)):
        count(policy[key])
        if policy[key]<minimum:raise ValueError('Invalid stored calculation setting.')
    if any(not isinstance(w,str) for w in bundle['warnings']):raise ValueError('Invalid audit warning.')
    for variable,scale in bundle['scaling'].items():
        number(scale['center']);number(scale['scale'])
        if scale['scale']<=0 or not isinstance(scale['method'],str):raise ValueError('Invalid measurement scaling.')
    qc={r['sample_id']:r for r in bundle['sample_qc']}
    available=[]
    for sid,row in qc.items():
        count(row['event_count']);count(row['multivariate_complete_count'])
        if row['multivariate_complete_count']>row['event_count']:raise ValueError('Complete rows exceed the population count.')
        available.append(row['multivariate_complete_count']>=3)
        if {c['variable'] for c in row['contributors']}!=set(variables) or len(row['contributors'])!=len(variables):
            raise ValueError('Variable contributors do not match the selection.')
    for matrix,joint in [(bundle['global_distance_matrix'],True),*[(m,False) for m in bundle['variable_matrices'].values()]]+([(bundle['projection_repeat_matrix'],True)] if bundle['projection_repeat_matrix'] is not None else []):
        for i,row in enumerate(matrix):
            for j,value in enumerate(row):
                if value!=matrix[j][i]:raise ValueError('Distance matrix is not symmetric.')
                if joint and (not available[i] or not available[j]):
                    if value is not None:raise ValueError('Joint distance exists for an unavailable population.')
                elif value is None or (i==j and value!=0):raise ValueError('Invalid available distance or diagonal.')
                else:number(value,True)
    seen=set()
    for row in bundle['variable_qc']:
        pair=(row['sample_id'],row['variable'])
        if pair in seen or pair[0] not in qc or pair[1] not in variables:raise ValueError('Invalid or duplicated variable result.')
        seen.add(pair);count(row['count']);count(row['missing_count'])
        if row['count']<policy['min_finite'] or row['count']+row['missing_count']!=qc[pair[0]]['event_count']:
            raise ValueError('Variable counts do not match the population.')
        if row['count']<qc[pair[0]]['multivariate_complete_count']:raise ValueError('Joint rows exceed finite variable values.')
        for key in ('mean','median','std','mad','q05','q25','q75','q95','iqr','min','max'):number(row[key],key in ('std','mad','iqr'))
    if seen!={(sid,v) for sid in ids for v in variables}:raise ValueError('Variable results are incomplete.')
    indexes={sid:i for i,sid in enumerate(ids)};seen=set()
    for row in bundle['variable_distances']:
        v,a,b=row['variable'],row['sample_a'],row['sample_b']
        if v not in variables or a not in indexes or b not in indexes or a==b:raise ValueError('Invalid variable distance identifiers.')
        pair=(v,min(indexes[a],indexes[b]),max(indexes[a],indexes[b]))
        if pair in seen:raise ValueError('Duplicated variable distance.')
        seen.add(pair);number(row['raw_w1'],True);number(row['normalized_w1'],True)
        if row['normalized_w1']!=bundle['variable_matrices'][v][indexes[a]][indexes[b]]:raise ValueError('Variable distance and matrix disagree.')
    if len(seen)!=len(variables)*len(ids)*(len(ids)-1)//2:raise ValueError('Variable distances are incomplete.')
    for sample in bundle['samples']:
        digest=hashlib.sha256(json.dumps(sample['population_snapshot'],sort_keys=True,allow_nan=False).encode()).hexdigest()
        if digest!=sample['population_sha256']:raise ValueError('Population snapshot fingerprint mismatch.')
    mapping=bundle['hierarchy_mapping']
    if bundle['audit_type']=='hierarchy':
        if set(mapping)!=set(ids) or any(not isinstance(b,str) or not b.strip() for b in mapping.values()):raise ValueError('Invalid biological replicate mapping.')
        bios=set(mapping.values())
        if len(bundle['hierarchy'])!=len(ids) or {r['sample_id'] for r in bundle['hierarchy']}!=set(ids):raise ValueError('Hierarchy selection mismatch.')
        for row in bundle['hierarchy']:
            if row['biological_replicate']!=mapping[row['sample_id']]:raise ValueError('Hierarchy mapping mismatch.')
        if len(bundle['variance_components'])!=len(variables) or {r['variable'] for r in bundle['variance_components']}!=set(variables):raise ValueError('Variance component selection mismatch.')
        for row in bundle['variance_components']:
            _validate_model(row)
        if len(bundle['influence'])!=len(variables)*len(bios) or {(r['variable'],r['omitted_bio']) for r in bundle['influence']}!={(v,b) for v in variables for b in bios}:
            raise ValueError('Biological influence selection mismatch.')
        for row in bundle['influence']:
            _validate_model(row['full_variance_components']);_validate_model(row['loo_variance_components'])
    elif mapping or any(bundle[key] for key in ('hierarchy','variance_components','influence','equal_bio_centers')):
        raise ValueError('Hierarchy output exists in a QC-only audit.')

def _validate_model(model):
    if model['model_status'] not in ('converged','boundary','boundary_zero','failed','unidentifiable') or not isinstance(model['reason'],str):raise ValueError('Invalid variance model status.')
    for key in ('n_biological','n_nested','n_particles'):
        if type(model[key]) is not int or model[key]<0:raise ValueError('Invalid variance model count.')
    for key in ('sigma2_bio','sigma2_nested_sample','sigma2_particle','icc_bio','icc_same_nested_sample'):
        value=model[key]
        if value is not None and (isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or value<0 or (key.startswith('icc') and value>1)):
            raise ValueError('Invalid variance model estimate.')

def copy_bundle(source,path):
    """Relocate immutable bytes without changing gzip headers or compression."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as out,open(source,'rb') as inp:
            shutil.copyfileobj(inp,out);out.flush();os.fsync(out.fileno())
        os.link(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def write_bundle(path,bundle):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(clean(bundle),ensure_ascii=False,allow_nan=False,sort_keys=True).encode('utf-8')
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(gzip.compress(data,mtime=0));f.flush();os.fsync(f.fileno())
        # Exclusive link publishes a complete immutable file; never overwrite history.
        os.link(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return path

def read_bundle(reference,workspace_path=None):
    path=reference.result.resolve(workspace_path)
    if not path:raise ValueError('Audit bundle missing or changed. Use Find Missing Files to relink the recorded bundle.')
    try:
        with gzip.open(path,'rt',encoding='utf-8') as f:bundle=validate_bundle(json.load(f))
    except (EOFError,UnicodeError,OSError,ValueError) as exc:
        raise ValueError('Audit bundle is corrupt or unsupported: '+str(exc)) from exc
    if bundle.get('audit_schema')!=1 or bundle.get('audit_id')!=reference.audit_id:
        raise ValueError('Audit bundle identity/schema mismatch.')
    if [s['sample_id'] for s in bundle['samples']]!=reference.selected_sample_ids or bundle['audit_type']!=reference.audit_type:
        raise ValueError('Audit bundle selection/type does not match the workspace reference.')
    return bundle

def commit_bundle(workspace,bundle,workspace_path=None,state_dir=None):
    validate_bundle(bundle)
    if bundle['audit_id'] in workspace.audits:raise ValueError('Audit ID already exists.')
    folder=Path(workspace_path).with_name(Path(workspace_path).stem+'_audits') if workspace_path else Path(state_dir or Path.home()/'.vflow')/'audits'/workspace.workspace_id
    path=write_bundle(folder/(bundle['audit_id']+'.vflowaudit.json.gz'),bundle)
    ref=AuditReference(bundle['audit_id'],bundle['name'],bundle['audit_type'],bundle['created_at'],
        FileReference.create(path,workspace_path,kind='audit'),[s['sample_id'] for s in bundle['samples']],bundle['population_label'],
        {status:sum(r['status']==status for r in bundle['sample_qc']) for status in set(r['status'] for r in bundle['sample_qc'])})
    workspace.audits[ref.audit_id]=ref
    return ref

def append_decision(reference,sample_id,action,reason_code='no_reason_supplied',note=''):
    if sample_id not in reference.selected_sample_ids:raise ValueError('Sample was not part of this audit.')
    if action not in ('keep','exclude','restore','note'):raise ValueError('Unknown review decision.')
    reference.decision_history.append({'timestamp':datetime.now(timezone.utc).isoformat(),'sample_id':sample_id,
        'action':action,'reason_code':reason_code or 'no_reason_supplied','note':note})

def source_identity_warnings(bundle,workspace,workspace_path=None):
    warnings=[]
    for item in bundle['samples']:
        source=FileReference(**item['source']) if item['source'] else None
        current=workspace.samples.get(item['sample_id'])
        member=item['population_snapshot'].get('source_member_id')
        if source and (not source.resolve(workspace_path) or (current and (current.source.identity_fingerprint != source.identity_fingerprint
                or ('source_member_id' in item['population_snapshot'] and current.source_member_id!=member)))):
            warnings.append(item['display_name']+': current source differs or is missing; historical results refer to the recorded snapshot.')
    return warnings
