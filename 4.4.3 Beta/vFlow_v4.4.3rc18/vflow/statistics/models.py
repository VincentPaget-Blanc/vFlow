"""Versioned audit parameters and cancellation contract."""
from dataclasses import dataclass, field
import pandas as pd

ANALYSIS_VERSION = 'audit-4'
POLICY = {'version':'review-3','min_finite':3,'n_projections':64,'seed':443,
          'isolation_threshold':2.5,'robust_z_threshold':3.5,'influence_threshold':0.5,
          'low_n_extreme_isolation_multiplier':2.0,
          'projection_stability_rule':'repeat_same_review_criteria',
          'classification_n':'samples_with_available_multivariate_distances'}

class AuditCancelled(RuntimeError): pass

@dataclass
class AuditSample:
    sample_id: str
    display_name: str
    dataframe: pd.DataFrame
    source: dict = field(default_factory=dict)
    population_snapshot: dict = field(default_factory=dict)

def checkpoint(cancel=None, progress=None, stage=None):
    if cancel is not None and cancel.is_set(): raise AuditCancelled('Audit cancelled; no result committed.')
    if progress and stage: progress(stage)
