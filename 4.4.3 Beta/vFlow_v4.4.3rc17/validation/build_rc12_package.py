"""Gate RC12 delivery on frozen-source tests and exact wheel/payload identity."""
from pathlib import Path
import hashlib, json, os, shutil, zipfile
ROOT = Path(__file__).resolve().parents[1]
VERSION = '4.4.3rc12'
def sha(data): return hashlib.sha256(data).hexdigest()
def record(name): return json.loads((ROOT / 'validation' / name).read_text())
def passing_log(name, phrase):
    text = (ROOT / 'validation' / name).read_text()
    assert phrase in text and 'failed' not in text and 'Traceback' not in text, name
passing_log('full_suite_rc12_release_frozen.txt', '1556 passed')
passing_log('rc12_secondary_window_tests_final.txt', '62 passed')
passing_log('frozen_benchmark_rc12.txt', '53/53 scientific checks passed')
assert record('expanded_benchmark_rc12.json')['passed'] == 35
passing_log('frozen_integrity_rc12.txt', '39 frozen files')
passing_log('benchmark_workflow_rc12.txt', 'PASS 23 real benchmark app workflow checks')
workflow = record('bug_hunt_rc12/workflow_result.json')
assert workflow['passed'] == 23 and workflow['events'] == 48000
assert workflow['raw_hashes_unchanged'] and not workflow['errors']
audit = record('audit_selection_rc12/benchmark_result.json')
assert audit['events_loaded'] == 48000 and audit['audited_events'] == 24000
assert audit['audited_sample_count'] == 2 and audit['selected_variables'] == ['FSC-A', 'SSC-A']
assert audit['exports_and_workspace_reopen_passed'] and audit['raw_hashes_unchanged']
assert audit['no_automatic_exclusion'] and not audit['errors']
views = record('audit_selection_rc12/layout_inventory.json')
assert len(views['views']) == 2 and not views['errors']
persistence = (ROOT / 'validation/workspace_persistence_rc12.txt').read_text()
assert all('PASS ' + phase in persistence for phase in ('create', 'verify_initial', 'edit_again', 'verify_final'))
assert 'Traceback' not in persistence
spyder = (ROOT / 'validation/spyder_cached_rc5_rc12_tk9.txt').read_text()
assert 'Kernel cached RC5' in spyder and spyder.count('PASS isolated Spyder launch ') == 2
assert spyder.count('"version": "4.4.3rc12"') == 2 and 'Traceback' not in spyder
preservation = record('preservation_rc12.json')
assert preservation['unchanged_core_modules'] == 19
assert preservation['unchanged_audit_numerical_modules'] == 10
assert preservation['no_original_methods_removed'] and not preservation['source_launcher_changed']
assert preservation['secondary_numerical_bodies_unchanged_after_session_guard']
for row in preservation['modules']:
    assert sha((ROOT / row['path']).read_bytes()) == row['rc12_sha256'], row['path']
assert sha((ROOT / 'run_vflow.py').read_bytes()) == preservation['launcher_sha256']
assert (ROOT / 'CHANGELOG.md').read_text().startswith('# vFlow ' + VERSION + '\n')
baseline = ROOT.parent / 'research/rc12_authoritative_changelog.md'
assert (ROOT / 'CHANGELOG.md').read_text().endswith(baseline.read_text()), 'changelog history changed'
wheel = ROOT / 'dist' / f'vflow-{VERSION}-py3-none-any.whl'
verified = []
with zipfile.ZipFile(wheel) as z:
    assert z.testzip() is None
    for source in sorted((ROOT / 'vflow').rglob('*.py')):
        name = source.relative_to(ROOT).as_posix()
        assert z.read(name) == source.read_bytes(), name
        verified.append(name)
    assert len(verified) == 122
    assert f'Version: {VERSION}\n' in z.read(f'vflow-{VERSION}.dist-info/METADATA').decode()
contents = dict(version=VERSION, full_suite_passed=1556, new_regression_cases=58,
    final_focused_cases=62, verified_before_fix_failures=33, scientific_checks=88,
    frozen_hashes=39, benchmark_app_checks=23, benchmark_events=48000,
    fresh_process_persistence_passed=True, cached_rc5_spyder_launches=2,
    platform='Linux/Python3.12/Tk9.0.4/Xvfb; actual Spyder runner',
    native_windows_macos_tested=False, fresh_tk86_tested=False,
    numerical_changes=False, analysis_version='audit-4', review_policy='review-3',
    source_launcher_changed=False, unchanged_core_modules=19,
    wheel=wheel.name, wheel_sha256=sha(wheel.read_bytes()),
    verified_wheel_python_sources=len(verified), wheel_matches_source=True)
(ROOT / 'validation/package_contents_rc12.json').write_text(json.dumps(contents, indent=2) + '\n')
excluded = {'__pycache__', '.pytest_cache', 'build', 'vflow.egg-info', '.git'}
def include(p):
    rel = p.relative_to(ROOT)
    if any(part in excluded or part.endswith('_run') for part in rel.parts) or p.suffix == '.pyc': return False
    if rel.parts[0] == 'dist' and p != wheel: return False
    if rel.parts[0] == 'validation' and p.suffix.lower() in ('.png', '.jpg', '.jpeg'):
        return len(rel.parts) > 2 and rel.parts[1] in {'audit_selection_rc12', 'bug_hunt_rc12'}
    return p.name not in {'SOURCE_SHA256.json', 'package_build_rc12.txt'}
payload = sorted(p for p in ROOT.rglob('*') if p.is_file() and include(p))
assert not any(p.name == 'sitecustomize.py' for p in payload)
manifest = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in payload}
manifest_path = ROOT / 'SOURCE_SHA256.json'
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
archive = ROOT.parent / 'vFlow_v4.4.3rc12_Full_Bug_Hunt.zip'
staged = archive.with_name(archive.name + '.tmp')
with zipfile.ZipFile(staged, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for p in payload + [manifest_path]:
        z.write(p, f'vFlow_v{VERSION}/' + p.relative_to(ROOT).as_posix())
with staged.open('r+b') as f: os.fsync(f.fileno())
with zipfile.ZipFile(staged) as z:
    assert z.testzip() is None and len(z.namelist()) == len(manifest) + 1
    for name, digest in manifest.items():
        assert sha(z.read(f'vFlow_v{VERSION}/' + name)) == digest, name
staged.replace(archive)
for name in ('BUG_HUNT_REPORT_v4.4.3rc12.md', 'CHANGELOG.md'):
    shutil.copy2(ROOT / name, ROOT.parent / name)
shutil.copy2(ROOT / 'validation/bug_hunt_rc12/Benchmark_Data_Panel_RC12.png',
             ROOT.parent / 'vFlow_RC12_Benchmark_Data_Panel.png')
receipt = dict(archive=str(archive), archive_bytes=archive.stat().st_size,
    archive_sha256=sha(archive.read_bytes()), payload_files=len(manifest) + 1,
    wheel_sha256=contents['wheel_sha256'], verified_wheel_sources=122,
    full_suite_passed=1556, benchmark_app_checks=23, scientific_checks=88,
    changelog_updated=True, all_checks_passed=True)
(ROOT.parent / 'research/rc12_package_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
