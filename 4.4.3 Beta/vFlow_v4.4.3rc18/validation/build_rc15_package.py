"""Gate RC15 delivery on frozen-source tests and exact wheel/payload identity."""
from pathlib import Path
import hashlib, json, os, shutil, zipfile
ROOT = Path(__file__).resolve().parents[1]
VERSION = '4.4.3rc15'
def sha(data): return hashlib.sha256(data).hexdigest()
def record(name): return json.loads((ROOT / 'validation' / name).read_text())
def passing_log(name, phrase):
    text = (ROOT / 'validation' / name).read_text()
    assert phrase in text and 'failed' not in text and 'Traceback' not in text, name
passing_log('full_suite_rc15_final.txt', '1629 passed')
passing_log('rc15_focus_final.txt', '46 passed')
baseline_log=(ROOT/'validation/rc15_verified_baseline.txt').read_text()
assert 'Verified all 122 package sources identical to delivered RC14' in baseline_log
assert '7 failed, 1 passed' in baseline_log
passing_log('metadata_rc15.txt','18 passed')
passing_log('frozen_benchmark_rc15.txt', '53/53 scientific checks passed')
assert record('expanded_benchmark_rc15.json')['passed'] == 35
passing_log('frozen_integrity_rc15.txt', '39 frozen files')
passing_log('benchmark_workflow_rc15.txt', 'PASS 36 real benchmark app workflow checks')
workflow = record('bug_hunt_rc15/workflow_result.json')
assert workflow['passed'] == 36 and workflow['events'] == 48000
assert workflow['raw_hashes_unchanged'] and not workflow['errors']
audit = record('audit_selection_rc15/benchmark_result.json')
assert audit['events_loaded'] == 48000 and audit['audited_events'] == 24000
assert audit['audited_sample_count'] == 2 and audit['selected_variables'] == ['FSC-A', 'SSC-A']
assert audit['exports_and_workspace_reopen_passed'] and audit['raw_hashes_unchanged']
assert audit['no_automatic_exclusion'] and not audit['errors']
views = record('audit_selection_rc15/layout_inventory.json')
assert len(views['views']) == 2 and not views['errors']
persistence = (ROOT / 'validation/workspace_persistence_rc15.txt').read_text()
assert all('PASS ' + phase in persistence for phase in ('create', 'verify_initial', 'edit_again', 'verify_final'))
assert 'Traceback' not in persistence
spyder = (ROOT / 'validation/spyder_cached_rc5_rc15_tk9.txt').read_text()
assert 'Kernel cached RC5' in spyder and spyder.count('PASS isolated Spyder launch ') == 2
assert spyder.count('"version": "4.4.3rc15"') == 2 and 'Traceback' not in spyder
native=record('native_crash_matrix_rc15.json')
assert native['total']==33 and native['all_expected']
assert not native['historical_sigsegv_identically_reproduced']
assert all(row['returncode']==0 and not row['stderr'] for row in native['rows'] if row['version']=='rc15')
release=record('release_readiness_rc15.json')
assert release['passed'] and len(release['results'])==11 and not release['unsafe_controls_run']
assert release['audit_bundle_and_review_history_preserved'] and release['saved_audit_events']==24000
assert release['standalone_no_pytest_required']
passing_log('diagnostic_dependencies_rc15.txt','PASS standalone helper')
long=release['phases']['long_session']
assert long['workspace_switches']==40 and long['real_audit_preparations']==20 and long['cancelled_closed_workers']==20
assert long['closed_dialogs_collected'] and not long['errors']
assert release['phases']['verify_before']['previous_revision_intact']
assert release['phases']['verify_after']['committed_revision_complete']
preservation = record('preservation_rc15.json')
assert preservation['unchanged_core_modules'] == 19
assert preservation['protected_statistical_modules'] == 11
assert preservation['no_original_methods_removed'] and not preservation['source_launcher_changed']
assert preservation['secondary_numerical_bodies_unchanged']
assert preservation['population_capture_unchanged']
for row in preservation['modules']:
    assert sha((ROOT / row['path']).read_bytes()) == row['rc15_sha256'], row['path']
assert sha((ROOT / 'run_vflow.py').read_bytes()) == preservation['launcher_sha256']
assert (ROOT / 'CHANGELOG.md').read_text().startswith('# vFlow ' + VERSION + '\n')
assert 'PENDING' not in (ROOT/'BUG_HUNT_REPORT_v4.4.3rc15.md').read_text()
baseline = ROOT.parent / 'research/rc15_authoritative_changelog.md'
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
    metadata = z.read(f'vflow-{VERSION}.dist-info/METADATA').decode()
    assert f'Version: {VERSION}\n' in metadata
    assert metadata.split('\n\n', 1)[1].rstrip() == (ROOT/'README.md').read_text().rstrip(), 'wheel README stale'
contents = dict(version=VERSION, full_suite_passed=1629, new_regression_cases=12,
    final_focused_cases=46, verified_before_fix_failures=7, scientific_checks=88,
    frozen_hashes=39, benchmark_app_checks=36, benchmark_events=48000,
    fresh_process_persistence_passed=True, cached_rc5_spyder_launches=2,
    platform='Linux/Python3.12/Tk9.0.4/Xvfb; actual Spyder runner',
    native_windows_macos_tested=False, fresh_tk86_tested=False,
    numerical_changes=False, analysis_version='audit-4', review_policy='review-3',
    source_launcher_changed=False, unchanged_core_modules=19,
    isolated_crash_comparisons=33, safe_release_phases=11, workspace_switches=40,
    historical_sigsegv_identically_reproduced=False,
    full_suite_runner='ordinary pytest with faulthandler; no NativeCleanup plugin',
    wheel=wheel.name, wheel_sha256=sha(wheel.read_bytes()),
    verified_wheel_python_sources=len(verified), wheel_matches_source=True)
(ROOT / 'validation/package_contents_rc15.json').write_text(json.dumps(contents, indent=2) + '\n')
excluded = {'__pycache__', '.pytest_cache', 'build', 'vflow.egg-info', '.git'}
def include(p):
    rel = p.relative_to(ROOT)
    if any(part in excluded or part.endswith('_run') for part in rel.parts) or p.suffix == '.pyc': return False
    if rel.parts[0] == 'dist' and p != wheel: return False
    if rel.parts[0] == 'validation' and p.suffix.lower() in ('.png', '.jpg', '.jpeg'):
        return len(rel.parts) > 2 and rel.parts[1] in {'audit_selection_rc15', 'bug_hunt_rc15'}
    return p.name not in {'SOURCE_SHA256.json', 'package_build_rc15.txt', 'rc15_before_fix.txt'}
payload = sorted(p for p in ROOT.rglob('*') if p.is_file() and include(p))
assert not any(p.name == 'sitecustomize.py' for p in payload)
manifest = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in payload}
manifest_path = ROOT / 'SOURCE_SHA256.json'
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
archive = ROOT.parent / 'vFlow_v4.4.3rc15_Native_Crash_Release_Check.zip'
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
for name in ('BUG_HUNT_REPORT_v4.4.3rc15.md', 'CHANGELOG.md'):
    shutil.copy2(ROOT / name, ROOT.parent / name)
shutil.copy2(ROOT / 'validation/bug_hunt_rc15/Benchmark_Data_Panel_RC15.png',
             ROOT.parent / 'vFlow_RC15_Benchmark_Data_Panel.png')
receipt = dict(archive=str(archive), archive_bytes=archive.stat().st_size,
    archive_sha256=sha(archive.read_bytes()), payload_files=len(manifest) + 1,
    wheel_sha256=contents['wheel_sha256'], verified_wheel_sources=122,
    full_suite_passed=1629, benchmark_app_checks=36, scientific_checks=88,
    changelog_updated=True, all_checks_passed=True)
(ROOT.parent / 'research/rc15_package_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
