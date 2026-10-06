"""User-facing explanations shared by preparation, results and detail views."""
import tkinter as tk
from tkinter import ttk
from vflow.statistics.models import POLICY

def show_interpretation(parent,bundle=None):
    policy=(bundle or {}).get('policy',POLICY)
    dialog=tk.Toplevel(parent);dialog.title('How to interpret the audit');dialog.geometry('780x670');dialog.minsize(540,400)
    frame=ttk.Frame(dialog,padding=14);frame.pack(fill='both',expand=True)
    text=tk.Text(frame,wrap='word',padx=12,pady=12,font='TkDefaultFont')
    scroll=ttk.Scrollbar(frame,command=text.yview);text.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right',fill='y');text.pack(fill='both',expand=True)
    sections=[]
    if bundle and bundle.get('analysis_version') in ('audit-1','audit-2'):
        sections.append(('Historical calculation settings',
            'This saved audit used an older analysis version. It treated peer distances and score MAD at or below 1e-12 as zero, and overall data variance at or below 1e-20 as identical values. Those absolute cutoffs could depend on measurement units. Its saved scores and flags remain unchanged. Run a new audit with this version to apply the corrected numerical handling; compare the recorded results and settings before revising a decision.'))
    if bundle and bundle.get('analysis_version')=='audit-3':
        sections.append(('Historical extreme-range handling',
            'This saved audit used analysis audit-3. Extremely small within-sample variances could round to zero before fitting, and some very large centers could overflow. Saved results remain unchanged. If your measurement units approach these numeric extremes, rescale the measurements and run a new audit with this version before interpreting a zero variance or unavailable center.'))
    sections.extend([
        ('Start with the comparison group',
         'Compare samples from the same condition, procedure and population. The audit uses the selected variables and the recorded gates. A flag asks for review; it does not identify a cause or automatically exclude a sample. These are descriptive within-group checks, not p-values, confidence intervals or between-condition tests.'),
        ('Distribution distances',
         'Wasserstein distance (W1) measures how far the measurement distributions differ, including location and spread. Raw W1 is in the variable’s measurement units. Normalized W1 divides that distance by the pooled interquartile range (IQR), with MAD or standard deviation as a fallback. Zero means matching empirical distributions; larger values mean greater differences. Compare normalized values within the same audit, rather than using a universal cutoff.\n\n'
         'Global discordance is the median sliced Wasserstein distance to the other available samples. It combines the selected variables after pooled robust centering and scaling, and can detect changes in their joint relationships even when each variable’s distribution matches. The global and variable distances have different definitions and need not have the same values. Pairwise matrices are symmetric; the diagonal is zero when joint distances are available.'),
        ('Isolation, robust z and projection stability',
         f'Isolation divides a sample’s median peer distance by the median distance among its peers. Around 1 means comparable separation; a value of 3 means three times the peers’ typical separation. The stored review threshold is {policy["isolation_threshold"]:g}. When peer distances are exactly zero, the ratio is undefined: a separated sample is represented by the capped value 1,000,000. This is a special case, not a literal million-fold estimate.\n\n'
         f'Robust z compares peer scores with their median using MAD. It is available with at least five samples that have joint distances. The stored threshold is {policy["robust_z_threshold"]:g}; it is not a significance test or a number of Gaussian standard deviations. With zero MAD, a score above the median is represented by 1,000,000; extreme finite z values are also capped.\n\n'
         'Projection stability repeats the review criteria with a second set of random directions. “Yes” means the review recommendation persisted in that repeat. It is not a confidence estimate, a bootstrap, or evidence of independent biological replication.'),
        ('Read the status with the available sample count',
         'Concordant: no review threshold was met; this does not prove equivalence. Mildly discordant: some separation or an unstable review recommendation deserves inspection. Flagged for review: the recommendation persisted in the second projection run.\n\n'
         'With three or four available joint samples, the result can only be a low-N review candidate. With two, distances are pairwise only. With one, there are insufficient peers. Multivariate unavailable means fewer than three rows have finite values for every selected variable. Finite values are still used for each variable independently. Check complete-row counts and missing values before interpreting a distance. A large missing fraction can change which events the global score represents.'),
        ('Hierarchy: three replication levels',
         'You assign biological replicate IDs. Multiple samples under one biological ID are nested samples; events within a sample are particles or cells, not additional biological replicates. Do not combine different conditions in this model.\n\n'
         'The nested random-intercept REML model separates biological, nested-sample and particle variance. Variances are in squared measurement units. Variance proportions divide each component by their total. Biological ICC is the biological variance fraction: modeled correlation for events from the same biological unit in different nested samples. Within-sample ICC combines biological and nested variance: modeled correlation for events from the same nested sample.\n\n'
         'The model assumes additive random intercepts, independent biological units, approximately Gaussian effects and homogeneous residual variance. Boundary means a component was estimated near zero, not proof that the source has no variability. Unidentifiable means replication cannot separate the components; unavailable values must not be read as zero. Failed means optimization did not yield an accepted fit. Low biological N means fewer than three biological units; estimates can be unstable. Model status and reason are shown in Details.'),
        ('Biological influence',
         'The full center gives equal weight to biological units and equal weight to nested-sample means within each unit. Event counts do not increase a biological unit’s weight. Leave-one-out removes one biological unit and recomputes that center and the variance model. A positive signed change means the center increased after removing that unit.\n\n'
         f'Standardized change divides the signed change by the robust spread of biological centers (IQR, then MAD, then SD). The stored influence threshold is an absolute change of {policy["influence_threshold"]:g} spread units. If there is no spread, standardized change is unavailable. Relative change divides by the absolute full center and is unavailable at zero; it can be very large near zero. Influence identifies dependence on a biological unit, not an invalid replicate. Removing a unit can make the leave-one-out variance model unidentifiable.'),
        ('Review and history',
         'Inspect variable distributions, complete-row counts and provenance before keeping, excluding or restoring a sample. These actions record your decision and affect current workspace inclusion; they do not recalculate the saved audit. Run another audit to compare a revised selection or population. Exports retain the original calculations plus current states and review history. Long notes are retained in the export’s review-context JSON (numbered chunks in Excel). Historical audits use their recorded settings, including the review thresholds shown here.')])
    text.tag_configure('heading',font=('TkDefaultFont',11,'bold'),spacing1=14,spacing3=5)
    for title,body in sections:
        text.insert('end',title+'\n','heading');text.insert('end',body+'\n\n')
    text.configure(state='disabled')
    ttk.Button(dialog,text='Close',command=dialog.destroy).pack(pady=(0,12))
    return dialog
