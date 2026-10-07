"""Domain-neutral numeric eligibility and exact pooled robust scaling."""
import numpy as np
from pandas.api.types import is_numeric_dtype, is_bool_dtype, is_complex_dtype, is_integer_dtype

def stable_mean(values):
    values=np.asarray(values,dtype=np.longdouble);anchor=values[0]
    with np.errstate(over='ignore',invalid='ignore'):deviations=values-anchor
    if np.isfinite(deviations).all():
        magnitude=np.max(np.abs(deviations))
        return anchor+np.mean(deviations/magnitude)*magnitude if magnitude else anchor
    magnitude=np.max(np.abs(values))
    return np.mean(values/magnitude)*magnitude if magnitude else np.longdouble(0)

def stable_sd(values,ddof=0):
    values=np.asarray(values,dtype=np.longdouble)
    with np.errstate(over='ignore',invalid='ignore'):deviations=values-stable_mean(values)
    if not np.isfinite(deviations).all():return np.longdouble(np.inf)
    magnitude=np.max(np.abs(deviations))
    if magnitude==0:return np.longdouble(0)
    return np.sqrt(np.sum((deviations/magnitude)**2)/(len(values)-ddof))*magnitude

def robust_scale(values):
    values=np.asarray(values,dtype=np.longdouble)
    q25,median,q75=np.quantile(values,[.25,.5,.75])
    scale=float(q75-q25); method='pooled_iqr'
    if scale<=0:
        scale=float(1.4826*np.median(np.abs(values-median)));method='pooled_mad'
    if scale<=0:
        scale=float(stable_sd(values));method='pooled_sd'
    return float(median),scale,method

def eligible_variables(samples,min_finite=3):
    if not samples: raise ValueError('Select at least one sample.')
    if any(not sample.dataframe.columns.is_unique for sample in samples):
        raise ValueError('Measurement names must be unique within each sample.')
    if any(not isinstance(c,str) or not c for sample in samples for c in sample.dataframe.columns):
        raise ValueError('Measurement names must be non-empty strings.')
    union=list(dict.fromkeys(c for sample in samples for c in sample.dataframe.columns))
    eligible=[]; excluded=[]; scales={}
    for col in union:
        arrays=[];reason=None
        for sample in samples:
            df=sample.dataframe
            if col not in df: reason='missing_in_sample';break
            if not is_numeric_dtype(df[col]) or is_bool_dtype(df[col]) or is_complex_dtype(df[col]):reason='non_numeric';break
            if is_integer_dtype(df[col]) and any(abs(int(v)) > 2**53 for v in (df[col].min(),df[col].max()) if not __import__('pandas').isna(v)):
                reason='integer_precision_exceeds_float64';break
            x=df[col].to_numpy(dtype=float,na_value=np.nan); x=x[np.isfinite(x)]
            if len(x)<min_finite: reason='insufficient_finite_values';break
            if x.min()==x.max():reason='constant_or_zero_scale';break
            arrays.append(x)
        if not reason:
            center,scale,method=robust_scale(np.concatenate(arrays))
            if not np.isfinite(scale):reason='numeric_range_exceeds_float64'
            elif scale<=0:reason='constant_or_zero_scale'
            else:scales[col]={'center':center,'scale':scale,'method':method}
        if reason:excluded.append({'variable':col,'reason':reason})
        else:eligible.append(col)
    return eligible,excluded,scales

def describe(x,total=None):
    x=np.asarray(x,dtype=np.longdouble);total=len(x) if total is None else total;x=x[np.isfinite(x)]
    if not len(x):return {'count':0,'missing_count':total}
    q=np.quantile(x,[.05,.25,.5,.75,.95])
    return {'count':len(x),'missing_count':total-len(x),'mean':float(stable_mean(x)),
        'median':float(q[2]),'std':float(stable_sd(x,ddof=1)) if len(x)>1 else None,
        'mad':float(np.median(np.abs(x-q[2]))),'q05':float(q[0]),'q25':float(q[1]),
        'q75':float(q[3]),'q95':float(q[4]),'iqr':float(q[3]-q[1]),'min':float(x.min()),'max':float(x.max())}
