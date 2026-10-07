"""Atomic, collision-safe proprietary derivatives with original-source provenance."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from vflow.workspace.model import fingerprint, matches_fingerprint, atomic_json
from .models import FlowReadResult, FlowSamplePayload

DECODER_VERSION = 'embedded-fcs-1'
_LOCK = threading.RLock()

def sidecar(path): return Path(path).with_suffix('.meta.json')

def read_meta(path):
    try:
        m=json.loads(sidecar(path).read_text(encoding='utf-8'))
        return m if isinstance(m,dict) and m.get('generated_by')=='vFlow' and m.get('schema')==1 else None
    except (OSError,ValueError,TypeError): return None

def derivative_is_owned(path):
    m = read_meta(path)
    if not m: return False
    try:
        source = Path(path).parent / m.get('source_path_basename','')
        if not source.is_file():source=Path(m.get('source_absolute_path',''))
        return source.is_file() and source.suffix.lower() in ('.lmd','.mqd') and matches_fingerprint(path,m.get('generated_csv_fingerprint'))
    except (OSError,TypeError,ValueError):return False

def _base_meta(source,fmt):
    return {'schema':1,'generated_by':'vFlow','vflow_version':'4.4.3rc18','decoder_version':DECODER_VERSION,
        'source_format':fmt,'source_absolute_path':str(source),'source_path_basename':source.name,'source_size':source.stat().st_size,
        'source_fingerprint':fingerprint(source)}

def _candidates(source,folder,meta):
    stem = source.stem
    return sorted(folder.glob(stem+'*.vflow*.csv'))

def _reuse(source,folder,meta):
    # A cache is disposable. Malformed sidecars/CSV/dtypes must not prevent
    # decoding the original acquisition or cause unverified files to be used.
    try:return _reuse_checked(source,folder,meta)
    except (OSError,ValueError,KeyError,TypeError,AttributeError):return None

def _reuse_checked(source,folder,meta):
    from vflow.core.data_io import smart_read_csv
    good = []
    for path in _candidates(source,folder,meta):
        m=read_meta(path)
        if not m or any(m.get(k)!=v for k,v in meta.items()): continue
        if not matches_fingerprint(path,m.get('generated_csv_fingerprint')): continue
        good.append((path,m))
    if not good: return None
    members = good[0][1].get('member_ids',[])
    selected = {m['source_member_id']:(p,m) for p,m in good if m.get('member_ids')==members}
    if not isinstance(members,list) or not members or any(not isinstance(m,str) for m in members) or len(set(members))!=len(members) or set(selected)!=set(members): return None
    samples = []
    for member in members:
        path,m=selected[member]
        df=smart_read_csv(str(path))
        if list(df.columns)!=m['columns'] or len(df)!=m['event_count']: return None
        # Restore per-column dtypes and round-trip binary floating values.
        import pandas as pd
        df=pd.read_csv(path, float_precision='round_trip', dtype=m.get('dtypes'))
        df.attrs.update(m.get('dataframe_attrs',{}))
        df.attrs.update(vflow_source_path=str(source),vflow_source_format=meta['source_format'],
                        vflow_source_member_id=member,vflow_materialized_path=str(path),vflow_derivative_reused=True)
        samples.append(FlowSamplePayload(df,m['logical_name'],str(source),member,meta['source_format'],m.get('metadata',{}),str(path)))
    return FlowReadResult(samples)

def _name(source,folder,meta,member,index,count):
    suffix='' if count==1 else f'__dataset-{index+1:02d}'
    default=folder/(source.stem+suffix+'.vflow.csv')
    # Regenerate only files whose exact CSV identity is still provably ours.
    if not default.exists() and not sidecar(default).exists(): return default
    old=read_meta(default)
    if old and old.get('source_path_basename')==source.name and old.get('source_member_id')==member and default.is_file() and matches_fingerprint(default,old.get('generated_csv_fingerprint')): return default
    token=hashlib.sha256((str(source)+meta['source_fingerprint']+str(member)).encode()).hexdigest()[:12]
    for n in range(10000):
        p=folder/(source.stem+suffix+'.vflow-'+token+('' if n==0 else '-'+str(n))+'.csv')
        if not p.exists() and not sidecar(p).exists(): return p
        old=read_meta(p)
        if old and all(old.get(k)==v for k,v in meta.items()) and p.is_file() and matches_fingerprint(p,old.get('generated_csv_fingerprint')): return p
    raise OSError('Could not find an unused derivative filename.')

def _write(source,folder,meta,result):
    folder.mkdir(parents=True,exist_ok=True)
    members=[s.source_member_id for s in result.samples]
    for i,sample in enumerate(result.samples):
        p=_name(source,folder,meta,sample.source_member_id,i,len(members))
        fd,tmp=tempfile.mkstemp(prefix='.'+p.name,dir=folder)
        try:
            with os.fdopen(fd,'w',encoding='utf-8',newline='') as f:
                sample.dataframe.to_csv(f,index=False);f.flush();os.fsync(f.fileno())
            m={**meta,'source_member_id':sample.source_member_id,'member_ids':members,'event_count':len(sample.dataframe),
               'columns':list(sample.dataframe.columns),'dtypes':{c:str(t) for c,t in sample.dataframe.dtypes.items()},
               'logical_name':sample.logical_name,'metadata':sample.metadata,'dataframe_attrs':sample.dataframe.attrs,
               'generated_csv_fingerprint':fingerprint(tmp)}
            if p.exists():
                prior=read_meta(p)
                if not prior or prior.get('source_path_basename')!=source.name or not matches_fingerprint(p,prior.get('generated_csv_fingerprint')):
                    p=_name(source,folder,meta,sample.source_member_id,i,len(members))
                    os.link(tmp,p)
                else:os.replace(tmp,p)
            else:
                try:os.link(tmp,p)
                except FileExistsError:
                    p=_name(source,folder,meta,sample.source_member_id,i,len(members));os.link(tmp,p)
            atomic_json(sidecar(p),m)
            sample.materialized_path=str(p)
            sample.dataframe.attrs.update(vflow_source_path=str(source),vflow_source_format=meta['source_format'],
                vflow_source_member_id=sample.source_member_id,vflow_materialized_path=str(p),vflow_derivative_reused=False)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
    return result

def load_or_materialize(path,fmt,decode,cache_dir=None):
    source=Path(path).resolve();meta=_base_meta(source,fmt)
    key=hashlib.sha256((str(source)+meta['source_fingerprint']).encode()).hexdigest()
    cache=Path(cache_dir or os.environ.get('VFLOW_CACHE_DIR',Path.home()/'.cache/vflow/derivatives'))/key
    with _LOCK:
        result=_reuse(source,source.parent,meta) or _reuse(source,cache,meta)
        if result: return result
        result=decode(str(source))
        if _base_meta(source,fmt)!=meta: raise ValueError('Source changed while decoding; no derivative was committed.')
        try: return _write(source,source.parent,meta,result)
        except OSError:
            result=_write(source,cache,meta,result)
            result.warnings.append('Source folder is not writable; decoded events are stored in the application cache.')
            for s in result.samples:s.dataframe.attrs['vflow_ingestion_warnings']=tuple(result.warnings)
            return result
