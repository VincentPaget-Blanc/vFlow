"""Exact nested random-intercept REML from sufficient statistics.

Within-sample residual contrasts account for every finite event. Matrix
inversion/determinants use two applications of the rank-one Woodbury identity;
optimization cost depends on nested samples, not the number of events.
"""
import numpy as np
from scipy.optimize import minimize
from .models import checkpoint
from .variable_eligibility import robust_scale,stable_mean

ESTIMATOR='nested_random_intercept_sufficient_statistics_REML-1'

def sufficient_stats(samples,variable,mapping):
    stats=[]
    for sample in samples:
        y=sample.dataframe[variable].to_numpy(dtype=float,na_value=np.nan);y=y[np.isfinite(y)]
        if len(y):
            y=y.astype(np.longdouble);mean=stable_mean(y);stats.append({'sample_id':sample.sample_id,'bio_id':mapping[sample.sample_id],
                'count':len(y),'mean':mean,'sse':np.sum((y-mean)**2,dtype=np.longdouble)})
            if stats[-1]['sse']==0 and y.min()!=y.max():
                raise ValueError('Within-sample variance is below the supported numeric range. Rescale the measurements and rerun.')
    return stats

def estimate(stats,cancel=None):
    bio_ids=list(dict.fromkeys(r['bio_id'] for r in stats));m=len(stats);n=sum(r['count'] for r in stats)
    base={'estimator':ESTIMATOR,'n_biological':len(bio_ids),'n_nested':m,'n_particles':n,'low_biological_n':len(bio_ids)<3}
    missing={'sigma2_bio':None,'sigma2_nested_sample':None,'sigma2_particle':None,'icc_bio':None,'icc_same_nested_sample':None}
    if len(bio_ids)<2 or m<=len(bio_ids) or n<=m:
        return {**base,**missing,'model_status':'unidentifiable','reason':'Need at least two biological units, replicated nested samples, and within-sample repeated events.'}
    means=np.array([r['mean'] for r in stats],dtype=np.longdouble);counts=np.array([r['count'] for r in stats],dtype=float)
    residual=sum(r['sse'] for r in stats);grand=np.dot(means,counts)/n
    scale=(residual+np.dot(counts,(means-grand)**2))/max(1,n-1)
    if not np.isfinite(scale) or scale>np.finfo(float).max or (scale>0 and float(scale)==0):
        raise ValueError('Hierarchy variance exceeds the supported numeric range. Rescale the measurements and rerun.')
    if scale==0:
        return {**base,**{k:0. for k in missing if k.startswith('sigma')},'icc_bio':None,'icc_same_nested_sample':None,
            'bio_variance_proportion':None,'nested_variance_proportion':None,'particle_variance_proportion':None,
            'model_status':'boundary_zero','reason':'All finite values are identical.'}
    scale=float(scale);y=np.asarray((means-grand)/np.sqrt(scale),dtype=float);sse=residual/scale
    indices=[np.array([j for j,r in enumerate(stats) if r['bio_id']==b]) for b in bio_ids]
    def objective(theta):
        checkpoint(cancel)
        b,s,e=theta
        a=e+counts*s;w=counts/a
        determinant=(n-m)*np.log(e)+np.log(a).sum();q=sse/e;xx=0.;xy=0.
        for idx in indices:
            wb=w[idx];yb=y[idx];sw=wb.sum();sy=np.dot(wb,yb);den=1+b*sw
            determinant+=np.log(den);q+=np.dot(wb,yb*yb)-b*sy*sy/den
            xx+=sw/den;xy+=sy/den
        return float(.5*(determinant+np.log(xx)+max(0.,q-xy*xy/xx)))
    fits=[minimize(objective,start,method='L-BFGS-B',bounds=[(0,None),(0,None),(1e-10,None)],
                   options={'maxiter':500,'ftol':1e-12}) for start in ([.3,.3,.4],[.01,.1,.9],[1.,1.,1.])]
    successful=[f for f in fits if f.success and np.isfinite(f.fun)]
    if not successful:
        return {**base,**missing,'model_status':'failed','reason':'; '.join(str(f.message) for f in fits)}
    fit=min(successful,key=lambda f:f.fun)
    wide=fit.x.astype(np.longdouble)*scale
    with np.errstate(over='ignore',under='ignore'):values=np.asarray(wide,dtype=float)
    if not np.isfinite(values).all() or any(v>0 and f==0 for v,f in zip(wide,values)):
        raise ValueError('Fitted variance components exceed the supported numeric range. Rescale the measurements and rerun.')
    b,s,e=values;total=np.sum(values,dtype=np.longdouble)
    return {**base,'sigma2_bio':float(b),'sigma2_nested_sample':float(s),'sigma2_particle':float(e),
        'bio_variance_proportion':float(b/total),'nested_variance_proportion':float(s/total),'particle_variance_proportion':float(e/total),
        'icc_bio':float(b/total),'icc_same_nested_sample':float((b+s)/total),
        'model_status':'boundary' if min(b,s)<=scale*1e-7 else 'converged','reason':str(fit.message)}

def analyze_hierarchy(samples,variables,mapping,policy,cancel=None,progress=None):
    if set(mapping)!={s.sample_id for s in samples} or any(not str(v).strip() for v in mapping.values()):
        raise ValueError('Assign exactly one non-empty biological replicate ID to every selected sample.')
    mapping={s:str(v).strip() for s,v in mapping.items()};bio_ids=list(dict.fromkeys(mapping.values()))
    hierarchy=[{'sample_id':s.sample_id,'sample_name':s.display_name,'biological_replicate':mapping[s.sample_id],
        'particles':len(s.dataframe),'nested_samples_in_bio':sum(v==mapping[s.sample_id] for v in mapping.values())} for s in samples]
    components=[];influence=[];centers=[]
    for variable in variables:
        checkpoint(cancel,progress,'Hierarchy variance components: '+str(variable))
        stats=sufficient_stats(samples,variable,mapping);full=estimate(stats,cancel);components.append({'variable':variable,**full})
        # Equal standing at each sampling level: nested sample means within bio,
        # then equal biological means; particle count never changes biological weight.
        bio_centers={b:float(stable_mean([r['mean'] for r in stats if r['bio_id']==b])) for b in bio_ids}
        center=float(stable_mean(list(bio_centers.values())));_,std,standardization_method=robust_scale(list(bio_centers.values()))
        centers.append({'variable':variable,'equal_bio_center':center,'biological_centers':bio_centers})
        for b in bio_ids:
            checkpoint(cancel,progress,'Influence analysis: '+str(variable)+' / '+b)
            remaining=[v for k,v in bio_centers.items() if k!=b];loo=float(stable_mean(remaining)) if remaining else None
            delta=loo-center if loo is not None else None
            standard=delta/std if delta is not None and std>0 else None
            relative=delta/abs(center) if delta is not None and center!=0 else None
            relative_condition='finite' if relative is not None else ('insufficient_biological_units' if delta is None else 'zero_full_center')
            if relative is not None and not np.isfinite(relative):relative=None;relative_condition='numeric_range_exceeded'
            standard_condition='finite' if standard is not None else ('insufficient_biological_units' if delta is None else 'zero_biological_spread')
            if standard is not None and not np.isfinite(standard):
                raise ValueError('Standardized biological influence exceeds the supported numeric range. Rescale the measurements and rerun.')
            vc=estimate([r for r in stats if r['bio_id']!=b],cancel)
            influence.append({'variable':variable,'omitted_bio':b,'full_equal_bio_center':center,'loo_equal_bio_center':loo,
                'delta':delta,'absolute_change':abs(delta) if delta is not None else None,
                'relative_change':relative,'relative_change_condition':relative_condition,'standardized_change_condition':standard_condition,
                'standardized_change':standard,'standardization_method':standardization_method+' of equal-weight biological centers','influence_status':'influential' if standard is not None and abs(standard)>=policy['influence_threshold'] else 'descriptive',
                'low_biological_n':len(bio_ids)<3,'full_variance_components':full,'loo_variance_components':vc})
    return hierarchy,components,influence,centers
