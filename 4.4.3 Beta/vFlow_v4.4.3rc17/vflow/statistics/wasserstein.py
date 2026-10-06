"""Exact empirical W1. Inputs are sorted once per measurement/projection."""
import numpy as np

def stable_median(values):
    return float(np.median(np.asarray(values,dtype=np.longdouble)))

def sorted_w1(a,b):
    if not len(a) or not len(b):return None
    knots=np.sort(np.concatenate((a,b)))
    # Ordinary audits retain the float64 sort/dot fast path. Only extreme
    # magnitudes need wider subtraction to avoid inf gaps and 0 * inf.
    magnitude=max(abs(knots[0]),abs(knots[-1]))
    if magnitude>np.finfo(float).max/2 or (0<magnitude<np.finfo(float).tiny):
        knots=knots.astype(np.longdouble)
    intervals=np.diff(knots)
    fa=np.searchsorted(a,knots[:-1],side='right')/len(a)
    fb=np.searchsorted(b,knots[:-1],side='right')/len(b)
    weights=np.abs(fa-fb)
    # Zero-weight infinite gaps contribute nothing, including on platforms
    # where longdouble has no wider exponent range than float64.
    positive=weights>0
    if not positive.any():return 0.
    wide=np.dot(weights[positive],intervals[positive]);result=float(wide)
    if not np.isfinite(result) or (result==0 and np.any(intervals[positive]>0)):raise ValueError('Distance exceeds the supported numeric range. Rescale the measurements and rerun.')
    return result

def isolation(matrix,i):
    peers=[j for j in range(len(matrix)) if j!=i and np.isfinite(matrix[i,j])]
    if not peers:return None,None,'unavailable'
    score=stable_median(matrix[i,peers])
    baseline=[matrix[a,b] for k,a in enumerate(peers) for b in peers[k+1:] if np.isfinite(matrix[a,b])]
    if not baseline:return score,None,'insufficient_peers'
    base=stable_median(baseline)
    if base==0:
        return score,(1e6 if score>0 else 1.0),('identical_peers_isolated' if score>0 else 'identical_peers')
    return score,min(1e6,score/base),'finite'
