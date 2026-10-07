"""Export boundaries: protect acquisition/workspace files and publish CSV atomically."""
import os
from pathlib import Path
import tempfile

def validate_export_destination(path,protected_paths=()):
    target=Path(path).resolve()
    for source in protected_paths:
        if not source:continue
        original=Path(source).resolve()
        same=os.path.normcase(str(target))==os.path.normcase(str(original))
        if not same and target.exists() and original.exists():
            try:same=os.path.samefile(target,original)
            except OSError:pass
        if same:raise ValueError('An export cannot replace source data, a workspace, gate session or audit bundle. Choose a separate export filename.')

def protected_app_paths(app):
    owner=getattr(app,'_workspace',None)
    main=owner.main if owner else app
    paths=[]
    for host in (main,app):
        for key,df in {**getattr(host,'loaded_files',{}),**getattr(host,'excluded_files',{})}.items():
            paths.append(key)
            if df is not None:paths.extend(df.attrs.get(k) for k in ('vflow_source_path','vflow_materialized_path'))
    if owner:
        paths.extend((owner.path,owner.recovery_path))
        for _,ref in owner.document.references():paths.extend((ref.absolute_path,ref.resolve(owner.path)))
    return paths

def atomic_csv(dataframe,path,protected_paths=()):
    validate_export_destination(path,protected_paths)
    target=Path(path);target.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.'+target.name+'.',suffix='.tmp',dir=target.parent)
    os.close(fd)
    try:
        dataframe.to_csv(tmp,index=False)
        with open(tmp,'rb') as stream:os.fsync(stream.fileno())
        validate_export_destination(path,protected_paths)
        os.replace(tmp,target)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
