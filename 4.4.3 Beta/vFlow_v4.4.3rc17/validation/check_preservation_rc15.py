"""Constrain RC15 changes against the verified delivered RC14 archive."""
from pathlib import Path
import ast, hashlib, json, zipfile
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / 'vFlow_v4.4.3rc14_Final_Bug_Hunt.zip'
ALLOWED = {'vflow/workspace/controller.py', 'vflow/ui/statistical_audit_dialog.py', 'vflow/plotting/kde_payloads.py'}
def sha(data): return hashlib.sha256(data).hexdigest()
records = []
with zipfile.ZipFile(BASE) as z:
    prefix = 'vFlow_v4.4.3rc14/'
    originals = {n[len(prefix):]: z.read(n) for n in z.namelist() if n.startswith(prefix+'vflow/') and n.endswith('.py')}
    for name, before in sorted(originals.items()):
        after = (ROOT/name).read_bytes(); normalized = after.replace(b'4.4.3rc15', b'4.4.3rc14')
        kind = 'unchanged' if before == after else 'release version only' if before == normalized else 'bug fix'
        assert kind != 'bug fix' or name in ALLOWED, name
        records.append(dict(path=name, change=kind, rc14_sha256=sha(before), rc15_sha256=sha(after)))
    assert {p.relative_to(ROOT).as_posix() for p in (ROOT/'vflow').rglob('*.py')} == set(originals)
    core = [n for n in originals if n.startswith('vflow/core/')]
    kernels = [n for n in originals if n.startswith('vflow/statistics/')]
    assert all((ROOT/n).read_bytes() == originals[n] for n in core)
    assert all((ROOT/n).read_bytes().replace(b'4.4.3rc15', b'4.4.3rc14') == originals[n] for n in kernels)
    def methods(data):
        return {c.name+'.'+f.name: ast.dump(f,include_attributes=False) for c in ast.parse(data).body
                if isinstance(c,ast.ClassDef) for f in c.body if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef))}
    old = methods(originals['vflow/legacy/vflow_app.py'])
    new = methods((ROOT/'vflow/legacy/vflow_app.py').read_bytes())
    assert old == new
    for name in ALLOWED: assert not set(methods(originals[name])) - set(methods((ROOT/name).read_bytes()))
    def functions(data):
        return {f.name:ast.dump(f,include_attributes=False) for f in ast.parse(data).body if isinstance(f,ast.FunctionDef)}
    kde_before=functions(originals['vflow/plotting/kde_payloads.py'])
    kde_after=functions((ROOT/'vflow/plotting/kde_payloads.py').read_bytes())
    for name in ('compute_density_render_payload','compute_contour_surface_payload','_capture_job'):
        assert kde_before[name]==kde_after[name],name
    before_tree=ast.parse(originals['vflow/plotting/kde_payloads.py'])
    after_tree=ast.parse((ROOT/'vflow/plotting/kde_payloads.py').read_bytes())
    before_fn=next(f for f in before_tree.body if isinstance(f,ast.FunctionDef) and f.name=='compute_kde_jobs_parallel')
    after_fn=next(f for f in after_tree.body if isinstance(f,ast.FunctionDef) and f.name=='compute_kde_jobs_parallel')
    # Apart from main-thread collection before constructing the pool, preserve
    # scheduling, input arguments, numerical jobs, ordering and error handling.
    after_fn.body=[n for n in after_fn.body if not (isinstance(n,ast.If) and 'gc.collect' in ast.unparse(n))]
    assert ast.dump(before_fn,include_attributes=False)==ast.dump(after_fn,include_attributes=False)
    for name in ('auto_gate_data','capture','gate_bundle'):
        assert methods(originals['vflow/workspace/controller.py'])['WorkspaceController.'+name]==methods((ROOT/'vflow/workspace/controller.py').read_bytes())['WorkspaceController.'+name]
    launcher = z.read(prefix+'run_vflow.py'); assert (ROOT/'run_vflow.py').read_bytes() == launcher
report = dict(baseline='4.4.3rc14', candidate='4.4.3rc15', original_modules=len(records), new_modules=[],
    unchanged_modules=sum(r['change']=='unchanged' for r in records),
    version_only_modules=sum(r['change']=='release version only' for r in records),
    bug_fix_modules=sum(r['change']=='bug fix' for r in records), unchanged_core_modules=len(core),
    protected_statistical_modules=len(kernels), no_original_methods_removed=True,
    all_legacy_methods_unchanged=True, secondary_numerical_bodies_unchanged=True,
    population_capture_unchanged=True, source_launcher_changed=False, launcher_sha256=sha(launcher),
    analysis_version='audit-4', review_policy='review-3', modules=records)
(ROOT/'validation/preservation_rc15.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='modules'},indent=2))
