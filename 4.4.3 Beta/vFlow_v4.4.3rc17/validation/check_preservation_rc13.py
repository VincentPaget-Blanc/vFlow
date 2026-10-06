"""Verify RC13 changes against delivered RC12; constrain kernels and launcher."""
from pathlib import Path
import ast, hashlib, json, zipfile
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'vFlow_v4.4.3rc12_Full_Bug_Hunt.zip'
ALLOWED={'vflow/workspace/model.py','vflow/workspace/controller.py','vflow/legacy/vflow_app.py',
    'vflow/services/batch_stats_runner.py','vflow/statistics/workspace_audit.py','vflow/ui/statistical_audit_dialog.py'}
def sha(data):return hashlib.sha256(data).hexdigest()
def methods(data):
    tree=ast.parse(data)
    return {f'{c.name}.{f.name}':f for c in tree.body if isinstance(c,ast.ClassDef)
        for f in c.body if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef))}
records=[]
with zipfile.ZipFile(BASE) as z:
    prefix='vFlow_v4.4.3rc12/'
    originals={n[len(prefix):]:z.read(n) for n in z.namelist() if n.startswith(prefix+'vflow/') and n.endswith('.py')}
    for name,before in sorted(originals.items()):
        after=(ROOT/name).read_bytes();normalized=after.replace(b'4.4.3rc13',b'4.4.3rc12')
        kind='unchanged' if before==after else 'release version only' if before==normalized else 'bug fix'
        assert kind!='bug fix' or name in ALLOWED,name
        records.append(dict(path=name,change=kind,rc12_sha256=sha(before),rc13_sha256=sha(after)))
    assert {p.relative_to(ROOT).as_posix() for p in (ROOT/'vflow').rglob('*.py')}==set(originals)
    core=[n for n in originals if n.startswith('vflow/core/')]
    kernels=[n for n in originals if n.startswith('vflow/statistics/') and n!='vflow/statistics/workspace_audit.py']
    assert all((ROOT/n).read_bytes()==originals[n] for n in core)
    assert all((ROOT/n).read_bytes().replace(b'4.4.3rc13',b'4.4.3rc12')==originals[n] for n in kernels)
    old=methods(originals['vflow/legacy/vflow_app.py']);new=methods((ROOT/'vflow/legacy/vflow_app.py').read_bytes())
    assert not set(old)-set(new)
    changes=[name for name in old if ast.dump(old[name],include_attributes=False)!=ast.dump(new[name],include_attributes=False)]
    assert changes==['FlowApp._restore_file'],changes
    for name in ('PolarAnalysisWindow._compute_and_plot','BatchPlotWindow._compute_and_plot'):
        assert ast.dump(old[name],include_attributes=False)==ast.dump(new[name],include_attributes=False)
    before=ast.parse(originals['vflow/statistics/workspace_audit.py'])
    after=ast.parse((ROOT/'vflow/statistics/workspace_audit.py').read_bytes())
    first=next(n for n in before.body if isinstance(n,ast.FunctionDef) and n.name=='capture_population_inputs')
    second=next(n for n in after.body if isinstance(n,ast.FunctionDef) and n.name=='capture_population_inputs')
    assert isinstance(second.body[1],ast.Assign) and isinstance(second.body[2],ast.If)
    del second.body[1:3]
    assert ast.dump(first,include_attributes=False)==ast.dump(second,include_attributes=False)
    launcher=z.read(prefix+'run_vflow.py');assert (ROOT/'run_vflow.py').read_bytes()==launcher
report=dict(baseline='4.4.3rc12',candidate='4.4.3rc13',original_modules=len(records),new_modules=[],
    unchanged_modules=sum(r['change']=='unchanged' for r in records),
    version_only_modules=sum(r['change']=='release version only' for r in records),
    bug_fix_modules=sum(r['change']=='bug fix' for r in records),unchanged_core_modules=len(core),
    protected_statistical_modules=len(kernels),no_original_methods_removed=True,
    secondary_numerical_bodies_unchanged=True,population_capture_unchanged_after_membership_guard=True,
    source_launcher_changed=False,launcher_sha256=sha(launcher),analysis_version='audit-4',review_policy='review-3',modules=records)
(ROOT/'validation/preservation_rc13.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='modules'},indent=2))
