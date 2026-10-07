"""Deterministic SWD using all complete rows, one projection at a time."""
import numpy as np
from .models import checkpoint
from .wasserstein import sorted_w1

def sliced_distances(samples,variables,scales,n_projections=64,seed=443,cancel=None,progress=None):
    arrays=[];counts=[]
    center=np.array([scales[v]['center'] for v in variables]);scale=np.array([scales[v]['scale'] for v in variables])
    for sample in samples:
        x=sample.dataframe[variables].to_numpy(dtype=float,na_value=np.nan)
        valid=np.isfinite(x).all(axis=1)
        with np.errstate(over='ignore',invalid='ignore'):
            x=np.asarray((x[valid].astype(np.longdouble)-center)/scale,dtype=float)
        if not np.isfinite(x).all():raise ValueError('Standardized measurements exceed the supported numeric range. Rescale or deselect the affected variables.')
        arrays.append(x);counts.append(len(x))
    size=len(arrays);mat=np.zeros((size,size))
    unavailable=[i for i,n in enumerate(counts) if n<3]
    for i in unavailable:mat[i,:]=np.nan;mat[:,i]=np.nan
    rng=np.random.default_rng(seed)
    directions=rng.normal(size=(n_projections,len(variables)))
    directions/=np.linalg.norm(directions,axis=1)[:,None]
    for k,direction in enumerate(directions):
        checkpoint(cancel,progress,f'Multivariate distances: projection {k+1}/{n_projections}')
        projections=[np.sort(x@direction) if len(x)>=3 else None for x in arrays]
        if any(p is not None and not np.isfinite(p).all() for p in projections):
            raise ValueError('Projected measurements exceed the supported numeric range. Rescale the measurements and rerun.')
        for i in range(size):
            if projections[i] is None:continue
            for j in range(i+1,size):
                checkpoint(cancel)
                if projections[j] is None:continue
                mat[i,j]+=sorted_w1(projections[i],projections[j])/n_projections;mat[j,i]=mat[i,j]
    if np.isinf(mat).any():raise ValueError('Joint distance exceeds the supported numeric range. Rescale the measurements and rerun.')
    return mat,counts
