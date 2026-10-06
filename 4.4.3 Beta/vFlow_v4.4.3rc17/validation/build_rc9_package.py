"""Build and verify the RC9 delivery only after final checks pass."""
from pathlib import Path
import hashlib,json,os,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION='4.4.3rc9'
def sha(data):return hashlib.sha256(data).hexdigest()
full=(ROOT/'validation/full_suite_rc9_final.txt').read_text()
assert '1463 passed' in full and 'failed' not in full
assert '54 passed' in (ROOT/'validation/targeted_rc9_second.txt').read_text()
assert '29 passed' in (ROOT/'validation/layout_tk86_rc9.txt').read_text()
assert '53/53 scientific checks passed' in (ROOT/'validation/frozen_benchmark_rc9_final.txt').read_text()
assert json.loads((ROOT/'validation/expanded_benchmark_rc9_final.json').read_text())['passed']==35
assert '39 frozen files' in (ROOT/'validation/frozen_integrity_rc9.txt').read_text()
for platform in ('tk86','tk9'):
    cached=(ROOT/f'validation/spyder_cached_rc5_{platform}_rc9.txt').read_text()
    assert 'Kernel cached RC5' in cached
    assert cached.count('PASS isolated Spyder launch ')==2
    assert cached.count('"version": "4.4.3rc9"')==2
    assert cached.count('"events": 48000')==2
    assert 'Traceback' not in cached and 'ERROR ' not in cached
    normal=(ROOT/f'validation/startup_{platform}_rc9_final.txt').read_text()
    for mode in ('source','module','console'):
        assert 'PASS [{"mode": "'+mode+'"' in normal
persistence=(ROOT/'validation/workspace_persistence_rc9.txt').read_text()
assert all('PASS '+phase in persistence for phase in ('create','verify_initial','edit_again','verify_final'))
preservation=json.loads((ROOT/'validation/preservation_rc9.json').read_text())
assert preservation['unchanged_modules']==113 and preservation['changed_feature_and_ui_modules']==2
assert preservation['version_only_modules']==5 and not preservation['unexpected_changes']
assert preservation['source_launcher']['changed']
views=json.loads((ROOT/'validation/adaptive_review_rc9/inventory.json').read_text())
assert len(views['views'])==10 and not views['errors']
assert (ROOT/'CHANGELOG.md').read_text().startswith('# vFlow '+VERSION+'\n')
wheel=ROOT/'dist'/f'vflow-{VERSION}-py3-none-any.whl'
verified=[]
with zipfile.ZipFile(wheel) as z:
    assert z.testzip() is None
    for source in sorted((ROOT/'vflow').rglob('*.py')):
        name=source.relative_to(ROOT).as_posix()
        assert z.read(name)==source.read_bytes(),name
        verified.append(name)
    assert len(verified)==120
    assert f'Version: {VERSION}\n' in z.read(f'vflow-{VERSION}.dist-info/METADATA').decode()
contents={'version':VERSION,'tests_passed':1463,'new_regression_cases':8,'tk86_native_layout_cases':29,
 'targeted_tk9_cases':54,'frozen_scientific_checks':53,'expanded_checks':35,'frozen_hashes':39,
 'current_native_adaptive_views':10,'cached_rc5_spyder_launches':{'Tk8.6':2,'Tk9':2},
 'benchmark_events_per_launch':48000,'fresh_process_persistence_passed':True,'analysis_version':'audit-4',
 'review_policy':'review-3','wheel':wheel.name,'wheel_sha256':sha(wheel.read_bytes()),
 'verified_wheel_python_sources':len(verified),'wheel_matches_source':True,'numerical_changes':False,
 'unchanged_core_modules':19,'protected_statistics_ingestion_service_modules':41,
 'direct_in_kernel_tk86_stress':'Native crash in diagnostic run; default isolated source launches passed.',
 'platform':'Linux/Python3.12/Tk8.6.14+Tk9.0.4/Xvfb; real spyder-kernels execution, no desktop frontend',
 'remaining_acceptance':['Native macOS/Windows Spyder desktop','MQD native/export truth','real FCS1.0','external/vendor FCS3.2']}
(ROOT/'validation/package_contents_rc9.json').write_text(json.dumps(contents,indent=2)+'\n')
excluded={'__pycache__','.pytest_cache','build','vflow.egg-info','.git'}
def include(p):
    rel=p.relative_to(ROOT)
    if any(part in excluded for part in rel.parts) or p.suffix=='.pyc':return False
    if rel.parts[0]=='dist' and p!=wheel:return False
    if rel.parts[0]=='validation' and p.suffix.lower() in ('.png','.jpg','.jpeg'):
        return len(rel.parts)>2 and rel.parts[1]=='adaptive_review_rc9'
    return p.name!='SOURCE_SHA256.json'
payload=sorted(p for p in ROOT.rglob('*') if p.is_file() and include(p))
manifest={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in payload}
manifest_path=ROOT/'SOURCE_SHA256.json'
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
archive=ROOT.parent/'vFlow_v4.4.3rc9_Startup_and_Spyder_Fix.zip'
staged=archive.with_name(archive.name+'.tmp')
with zipfile.ZipFile(staged,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in payload+[manifest_path]:z.write(p,f'vFlow_v{VERSION}/'+p.relative_to(ROOT).as_posix())
with staged.open('r+b') as f:os.fsync(f.fileno())
with zipfile.ZipFile(staged) as z:
    assert z.testzip() is None
    assert len(z.namelist())==len(manifest)+1
    for name,digest in manifest.items():assert sha(z.read(f'vFlow_v{VERSION}/'+name))==digest,name
staged.replace(archive)
report=ROOT.parent/f'IMPLEMENTATION_REPORT_v{VERSION}.md'
shutil.copy2(ROOT/report.name,report)
shutil.copy2(ROOT/'CHANGELOG.md',ROOT.parent/'CHANGELOG.md')
receipt={'archive':str(archive),'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive.read_bytes()),
 'payload_files':len(manifest)+1,'wheel_sha256':contents['wheel_sha256'],'verified_wheel_sources':120,
 'tests_passed':1463,'changelog_updated':True,'all_checks_passed':True}
(ROOT.parent/'research/rc9_package_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
