"""Gate RC14 delivery on frozen-source tests and exact wheel/payload identity."""
from pathlib import Path
import hashlib, json, os, shutil, zipfile
ROOT = Path(__file__).resolve().parents[1]
VERSION = '4.4.3rc14'
def sha(data): return hashlib.sha256(data).hexdigest()
def record(name): return json.loads((ROOT / 'validation' / name).read_text())
def passing_log(name, phrase):
    text = (ROOT / 'validation' / name).read_text()
    assert phrase in text and 'failed' not in text and 'Traceback' not in text, name
passing_log('full_suite_rc14_final.txt', '1617 passed')
passing_log('rc14_focus_final.txt', '64 passed')
baseline_log=(ROOT/'validation/rc14_verified_baseline.txt').read_text()
assert 'Verified all 122 package sources identical to delivered RC13' in baseline_log
assert '11 failed, 3 passed' in baseline_log
passing_log('metadata_rc14.txt','18 passed')
passing_log('frozen_benchmark_rc14.txt', '53/53 scientific checks passed')
assert record('expanded_benchmark_rc14.json')['passed'] == 35
passing_log('frozen_integrity_rc14.txt', '39 frozen files')
passing_log('benchmark_workflow_rc14.txt', 'PASS 36 real benchmark app workflow checks')
workflow = record('bug_hunt_rc14/workflow_result.json')
assert workflow['passed'] == 36 and workflow['events'] == 48000
assert workflow['raw_hashes_unchanged'] and not workflow['errors']
audit = record('audit_selection_rc14/benchmark_result.json')
assert audit['events_loaded'] == 48000 and audit['audited_events'] == 24000
assert audit['audited_sample_count'] == 2 and audit['selected_variables'] == ['FSC-A', 'SSC-A']
assert audit['exports_and_workspace_reopen_passed'] and audit['raw_hashes_unchanged']
assert audit['no_automatic_exclusion'] and not audit['errors']
views = record('audit_selection_rc14/layout_inventory.json')
assert len(views['views']) == 2 and not views['errors']
persistence = (ROOT / 'validation/workspace_persistence_rc14.txt').read_text()
assert all('PASS ' + phase in persistence for phase in ('create', 'verify_initial', 'edit_again', 'verify_final'))
assert 'Traceback' not in persistence
spyder = (ROOT / 'validation/spyder_cached_rc5_rc14_tk9.txt').read_text()
assert 'Kernel cached RC5' in spyder and spyder.count('PASS isolated Spyder launch ') == 2
assert spyder.count('"version": "4.4.3rc14"') == 2 and 'Traceback' not in spyder
preservation = record('preservation_rc14.json')
assert preservation['unchanged_core_modules'] == 19
assert preservation['protected_statistical_modules'] == 11
assert preservation['no_original_methods_removed'] and not preservation['source_launcher_changed']
assert preservation['secondary_numerical_bodies_unchanged']
assert preservation['population_capture_unchanged']
for row in preservation['modules']:
    assert sha((ROOT / row['path']).read_bytes()) == row['rc14_sha256'], row['path']
assert sha((ROOT / 'run_vflow.py').read_bytes()) == preservation['launcher_sha256']
assert (ROOT / 'CHANGELOG.md').read_text().startswith('# vFlow ' + VERSION + '\n')
baseline = ROOT.parent / 'research/rc14_authoritative_changelog.md'
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
contents = dict(version=VERSION, full_suite_passed=1617, new_regression_cases=14,
    final_focused_cases=64, verified_before_fix_failures=11, scientific_checks=88,
    frozen_hashes=39, benchmark_app_checks=36, benchmark_events=48000,
    fresh_process_persistence_passed=True, cached_rc5_spyder_launches=2,
    platform='Linux/Python3.12/Tk9.0.4/Xvfb; actual Spyder runner',
    native_windows_macos_tested=False, fresh_tk86_tested=False,
    numerical_changes=False, analysis_version='audit-4', review_policy='review-3',
    source_launcher_changed=False, unchanged_core_modules=19,
    full_suite_runner='ordinary pytest with faulthandler; no NativeCleanup plugin',
    wheel=wheel.name, wheel_sha256=sha(wheel.read_bytes()),
    verified_wheel_python_sources=len(verified), wheel_matches_source=True)
(ROOT / 'validation/package_contents_rc14.json').write_text(json.dumps(contents, indent=2) + '\n')
excluded = {'__pycache__', '.pytest_cache', 'build', 'vflow.egg-info', '.git'}
def include(p):
    rel = p.relative_to(ROOT)
    if any(part in excluded or part.endswith('_run') for part in rel.parts) or p.suffix == '.pyc': return False
    if rel.parts[0] == 'dist' and p != wheel: return False
    if rel.parts[0] == 'validation' and p.suffix.lower() in ('.png', '.jpg', '.jpeg'):
        return len(rel.parts) > 2 and rel.parts[1] in {'audit_selection_rc14', 'bug_hunt_rc14'}
    return p.name not in {'SOURCE_SHA256.json', 'package_build_rc14.txt', 'rc14_before_fix.txt'}
payload = sorted(p for p in ROOT.rglob('*') if p.is_file() and include(p))
assert not any(p.name == 'sitecustomize.py' for p in payload)
manifest = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in payload}
manifest_path = ROOT / 'SOURCE_SHA256.json'
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
archive = ROOT.parent / 'vFlow_v4.4.3rc14_Final_Bug_Hunt.zip'
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
for name in ('BUG_HUNT_REPORT_v4.4.3rc14.md', 'CHANGELOG.md'):
    shutil.copy2(ROOT / name, ROOT.parent / name)
shutil.copy2(ROOT / 'validation/bug_hunt_rc14/Benchmark_Data_Panel_RC14.png',
             ROOT.parent / 'vFlow_RC14_Benchmark_Data_Panel.png')
receipt = dict(archive=str(archive), archive_bytes=archive.stat().st_size,
    archive_sha256=sha(archive.read_bytes()), payload_files=len(manifest) + 1,
    wheel_sha256=contents['wheel_sha256'], verified_wheel_sources=122,
    full_suite_passed=1617, benchmark_app_checks=36, scientific_checks=88,
    changelog_updated=True, all_checks_passed=True)
(ROOT.parent / 'research/rc14_package_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
