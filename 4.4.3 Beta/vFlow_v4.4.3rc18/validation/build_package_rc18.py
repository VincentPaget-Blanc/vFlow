"""Validate final receipts, preserve acquisitions and assemble the RC18 source release."""
import ast
import difflib
import hashlib
import json
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
V = ROOT/'validation'
BASE = ROOT.parent/'vFlow_v4.4.3rc17_UI_Interaction_Fixes.zip'
OUT = ROOT.parent/'vFlow_v4.4.3rc18_UI_Cleanup.zip'
sha = lambda data: hashlib.sha256(data).hexdigest()
sources = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in (ROOT/'vflow').rglob('*.py')}
plan = json.loads((V/'rc18_shard_plan.json').read_text())
modules = [n for group in plan['groups'] for n in group]
assert len(modules) == len(set(modules))
assert set(modules) == {p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').glob('test_*.py')}
cases = set()
for i, group in enumerate(plan['groups']):
    receipt = json.loads((V/f'full_suite_rc18_shard_{i}.json').read_text())
    assert receipt['exitcode'] == 0 and receipt['source_unchanged']
    assert receipt['sources'] == sources and receipt['test_files'] == group
    xml = ET.parse(V/f'full_suite_rc18_shard_{i}.xml')
    for case in xml.iter('testcase'):
        assert all(case.find(k) is None for k in ('failure','error','skipped'))
        key = (case.get('classname'), case.get('name'))
        assert key not in cases
        cases.add(key)
assert len(cases) == 1693
assert json.loads((V/'frozen_benchmark_rc18.json').read_text())['passed'] == 53
assert json.loads((V/'expanded_benchmark_rc18.json').read_text())['passed'] == 35
visual = json.loads((V/'ui_visual_rc18/result.json').read_text())
assert visual['passed'] == 9 and not visual['errors'] and len(visual['views']) == 7
assert visual['tk'] == '8.6.14'
assert '53 passed' in (V/'ui_cleanup_rc18_focused.txt').read_text()
wheel = ROOT/'dist/vflow-4.4.3rc18-py3-none-any.whl'
with zipfile.ZipFile(wheel) as z:
    assert {n for n in z.namelist() if n.startswith('vflow/') and n.endswith('.py')} == set(sources)
    assert all(sha(z.read(n)) == digest for n, digest in sources.items())
    assert z.read('vflow-4.4.3rc18.dist-info/METADATA').decode().split('\n\n',1)[1].rstrip() == (ROOT/'README.md').read_text().rstrip()
raw = json.loads((V/'raw_preservation_rc17.json').read_text())['hashes']
assert len(raw) == 57
assert all(sha((ROOT/name).read_bytes()) == digest for name,digest in raw.items())
patch = []
changed = []
with zipfile.ZipFile(BASE) as baseline:
    prefix = 'vFlow_v4.4.3rc17/'
    for name in sources:
        old = baseline.read(prefix+name)
        current = (ROOT/name).read_bytes()
        if old != current: changed.append(name)
        if name.startswith('vflow/core/') or name == 'vflow/io/registry.py': assert old == current
        if name.startswith('vflow/statistics/'):
            assert old.decode().replace('4.4.3rc17','4.4.3rc18') == current.decode()
    assert baseline.read(prefix+'run_vflow.py') == (ROOT/'run_vflow.py').read_bytes()
    for name in raw: assert sha(baseline.read(prefix+name)) == raw[name]
    def methods(data):
        tree = ast.parse(data)
        return {n.name: ast.dump(n, include_attributes=False) for c in tree.body if isinstance(c, ast.ClassDef) for n in c.body if isinstance(n,(ast.FunctionDef, ast.AsyncFunctionDef))}
    name = 'vflow/legacy/vflow_app.py'
    before, after = methods(baseline.read(prefix+name)), methods((ROOT/name).read_bytes())
    assert set(before) <= set(after)
    assert all(before[n] == after[n] for n in before if n != '_select_gate')
    names = set(sources) | {p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').glob('test_*.py')}
    names |= {'README.md','CHANGELOG.md','CITATION.cff','.zenodo.json','pyproject.toml','UI_CLEANUP_v4.4.3rc18.md','README_FIRST_v4.4.3rc18.md'}
    names |= {p.relative_to(ROOT).as_posix() for p in V.glob('*rc18.py')}
    names.add('validation/rc18_shard_plan.json')
    for name in sorted(names):
        old = baseline.read(prefix+name).decode() if prefix+name in baseline.namelist() else ''
        current = (ROOT/name).read_text()
        patch.extend(difflib.unified_diff(old.splitlines(True),current.splitlines(True),fromfile='a/'+name,tofile='b/'+name))
(ROOT/'vFlow_v4.4.3rc18_UI_Cleanup.patch').write_text(''.join(patch))
result = {'version':'4.4.3rc18','all_checks_passed':True,'ordinary_tests':len(cases),'test_modules':len(modules),'focused_tests':53,'scientific_checks':88,'visual_checks':9,'screenshots':7,'raw_files_preserved':57,'native_runtime':'Linux/Python 3.12/Tk 8.6.14','native_macos_windows_verified':False,'changed_application_modules':sorted(changed),'scientific_algorithms_unchanged':True,'legacy_methods_unchanged_except_select_gate_presentation':True,'wheel_sha256':sha(wheel.read_bytes()),'sources':sources}
(V/'release_gate_rc18.json').write_text(json.dumps(result,indent=2)+'\n')
(V/'release_gate_rc18.txt').write_text(json.dumps({k:v for k,v in result.items() if k!='sources'},indent=2)+'\n')
excluded = {'__pycache__','.pytest_cache','build','vflow.egg-info'}
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file(): continue
        relative = p.relative_to(ROOT)
        if relative.as_posix() == 'validation/package_build_rc18.txt': continue
        if any(part in excluded for part in relative.parts): continue
        if relative.parts[0] == 'dist' and p != wheel: continue
        z.write(p,'vFlow_v4.4.3rc18/'+relative.as_posix())
with zipfile.ZipFile(OUT) as z:
    assert z.testzip() is None
    assert all(sha(z.read('vFlow_v4.4.3rc18/'+n)) == h for n,h in {**sources,**raw}.items())
print(json.dumps({'file':str(OUT),'bytes':OUT.stat().st_size,'sha256':sha(OUT.read_bytes()),'tests':len(cases),'checks_passed':True},indent=2))
