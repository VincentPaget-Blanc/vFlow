"""Advisory review classification; never changes dataset state."""
import numpy as np
from .wasserstein import isolation,stable_median

def _robust_z_scores(scores,joint_n):
    finite=[s for s in scores if s is not None]
    med=stable_median(finite) if finite else 0
    mad=stable_median(np.abs(np.asarray(finite,dtype=np.longdouble)-med)) if finite else 0
    return [None if score is None or joint_n<5 else
            (min(1e6,max(-1e6,0.67448975*((score-med)/mad))) if mad>0 else
             (1e6 if score>med else 0.0)) for score in scores]

def _review_candidate(score,ratio,z,agree,joint_n,policy):
    if score is None or joint_n<3:return False
    isolated=ratio is not None and ratio>=policy['isolation_threshold']
    if joint_n>=5:
        return bool((z is not None and z>=policy['robust_z_threshold']) or (isolated and agree>=2))
    extreme=ratio is not None and ratio>=policy['low_n_extreme_isolation_multiplier']*policy['isolation_threshold']
    return bool(isolated and (agree>=2 or extreme))

def score_samples(samples,matrix,variable_matrices,repeat,policy):
    size=len(samples);scores=[isolation(matrix,i)[0] for i in range(size)]
    available=np.isfinite(np.diag(matrix));joint_n=int(available.sum())
    z_scores=_robust_z_scores(scores,joint_n)
    finite_scores=[s for s in scores if s is not None]
    zero_mad=bool(finite_scores) and stable_median(np.abs(np.asarray(finite_scores,dtype=np.longdouble)-stable_median(finite_scores)))==0
    repeat_scores=[isolation(repeat,i)[0] for i in range(size)] if repeat is not None else None
    repeat_n=int(np.isfinite(np.diag(repeat)).sum()) if repeat is not None else 0
    repeat_z=_robust_z_scores(repeat_scores,repeat_n) if repeat_scores is not None else None
    rows=[]
    for i,sample in enumerate(samples):
        score,ratio,condition=isolation(matrix,i)
        z=z_scores[i]
        contributors=[]
        for v,m in variable_matrices.items():
            peer,ir,ic=isolation(m,i)
            contributors.append({'variable':v,'peer_distance':peer,'isolation_ratio':ir,'isolation_condition':ic})
        contributors.sort(key=lambda r:(r['isolation_ratio'] or 0,r['peer_distance'] or 0),reverse=True)
        agree=sum((r['isolation_ratio'] or 0)>=policy['isolation_threshold'] for r in contributors)
        reasons=[];stable=None
        if not available[i]:status='multivariate_unavailable'
        elif joint_n==1:status='insufficient_peers'
        elif joint_n==2:status='pairwise_only'
        elif score is None:status='multivariate_unavailable'
        else:
            candidate=_review_candidate(score,ratio,z,agree,joint_n,policy)
            if candidate:
                if z is not None and z>=policy['robust_z_threshold']:reasons.append('robust_z_high')
                if agree>=2:reasons.append('multiple_variables_isolated')
            if candidate and repeat is not None:
                rep_score,rep_ratio,_=isolation(repeat,i)
                # Repeat the same OR policy, including the robust-z path. An
                # unchanged matrix must not be called unstable merely because
                # its candidate meets z but not the isolation threshold.
                stable=_review_candidate(rep_score,rep_ratio,repeat_z[i],agree,repeat_n,policy)
            if candidate and stable:
                status='low_n_review_candidate' if joint_n<5 else 'flagged_for_review'
                reasons.append('stable_multivariate_review')
            else:
                status='mildly_discordant' if candidate or (ratio is not None and ratio>=policy['isolation_threshold']) else 'concordant'
                if candidate and not stable:reasons.append('projection_unstable')
        rows.append({'sample_id':sample.sample_id,'sample_name':sample.display_name,'global_peer_distance':score,
            'global_isolation_ratio':ratio,'isolation_condition':condition,'robust_z':z,
            'robust_z_condition':'insufficient_samples' if joint_n<5 else ('zero_mad' if zero_mad else 'finite'),
            'low_n':joint_n<5,
            'multivariate_sample_count':joint_n,'global_peer_count':sum(j!=i and np.isfinite(matrix[i,j]) for j in range(size)),
            'projection_stability':stable,'status':status,'reason_codes':reasons,'contributors':contributors})
    return rows
