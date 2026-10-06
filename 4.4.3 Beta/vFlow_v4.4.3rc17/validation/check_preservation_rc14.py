"""Constrain RC14 changes against the verified delivered RC13 archive."""
from pathlib import Path
import ast, hashlib, json, zipfile
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / 'vFlow_v4.4.3rc13_Followup_Bug_Hunt.zip'
ALLOWED = {'vflow/workspace/controller.py', 'vflow/ui/statistical_audit_dialog.py'}
def sha(data): return hashlib.sha256(data).hexdigest()
records = []
with zipfile.ZipFile(BASE) as z:
    prefix = 'vFlow_v4.4.3rc13/'
    originals = {n[len(prefix):]: z.read(n) for n in z.namelist() if n.startswith(prefix+'vflow/') and n.endswith('.py')}
    for name, before in sorted(originals.items()):
        after = (ROOT/name).read_bytes(); normalized = after.replace(b'4.4.3rc14', b'4.4.3rc13')
        kind = 'unchanged' if before == after else 'release version only' if before == normalized else 'bug fix'
        assert kind != 'bug fix' or name in ALLOWED, name
        records.append(dict(path=name, change=kind, rc13_sha256=sha(before), rc14_sha256=sha(after)))
    assert {p.relative_to(ROOT).as_posix() for p in (ROOT/'vflow').rglob('*.py')} == set(originals)
    core = [n for n in originals if n.startswith('vflow/core/')]
    kernels = [n for n in originals if n.startswith('vflow/statistics/')]
    assert all((ROOT/n).read_bytes() == originals[n] for n in core)
    assert all((ROOT/n).read_bytes().replace(b'4.4.3rc14', b'4.4.3rc13') == originals[n] for n in kernels)
    def methods(data):
        return {c.name+'.'+f.name: ast.dump(f,include_attributes=False) for c in ast.parse(data).body
                if isinstance(c,ast.ClassDef) for f in c.body if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef))}
    old = methods(originals['vflow/legacy/vflow_app.py'])
    new = methods((ROOT/'vflow/legacy/vflow_app.py').read_bytes())
    assert old == new
    for name in ALLOWED: assert not set(methods(originals[name])) - set(methods((ROOT/name).read_bytes()))
    launcher = z.read(prefix+'run_vflow.py'); assert (ROOT/'run_vflow.py').read_bytes() == launcher
report = dict(baseline='4.4.3rc13', candidate='4.4.3rc14', original_modules=len(records), new_modules=[],
    unchanged_modules=sum(r['change']=='unchanged' for r in records),
    version_only_modules=sum(r['change']=='release version only' for r in records),
    bug_fix_modules=sum(r['change']=='bug fix' for r in records), unchanged_core_modules=len(core),
    protected_statistical_modules=len(kernels), no_original_methods_removed=True,
    all_legacy_methods_unchanged=True, secondary_numerical_bodies_unchanged=True,
    population_capture_unchanged=True, source_launcher_changed=False, launcher_sha256=sha(launcher),
    analysis_version='audit-4', review_policy='review-3', modules=records)
(ROOT/'validation/preservation_rc14.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='modules'},indent=2))
