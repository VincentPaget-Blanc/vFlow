"""Rebuild the delivery archives and verify source, wheel and payload integrity."""
from pathlib import Path
import hashlib,json,zipfile,sys,os
ROOT=Path(__file__).resolve().parents[1]
VERSION='4.4.3rc5'
def digest(data):return hashlib.sha256(data).hexdigest()
wheel=ROOT/'dist'/f'vflow-{VERSION}-py3-none-any.whl'
with zipfile.ZipFile(wheel) as z:
    assert z.testzip() is None
    verified=[]
    for source in sorted((ROOT/'vflow').rglob('*.py')):
        name=source.relative_to(ROOT).as_posix()
        assert z.read(name)==source.read_bytes(),name
        verified.append(name)
    metadata=z.read(f'vflow-{VERSION}.dist-info/METADATA').decode()
    assert f'Version: {VERSION}\n' in metadata
    assert not {n for n in z.namelist() if n.startswith('vflow/') and n.endswith('.py')}-set(verified)
full=(ROOT/'validation/full_suite_rc5_final.txt').read_text()
assert '1371 passed' in full and 'failed' not in full
expanded=json.loads((ROOT/'validation/expanded_benchmark_rc5_final.json').read_text())
assert expanded['passed']==35 and all(r['pass'] for r in expanded['results'])
assert '53/53 scientific checks passed' in (ROOT/'validation/frozen_benchmark_rc5_final.txt').read_text()
assert '39 frozen files' in (ROOT/'validation/frozen_integrity_rc5.txt').read_text()
capture=json.loads((ROOT/'validation/sidebar_capture_rc5.json').read_text())
assert not capture['errors'] and sum(capture['events'].values())==48000 and len(capture['screenshots'])==5
preservation=json.loads((ROOT/'validation/task_tabs_preservation_rc5.json').read_text())
assert not preservation['unexpected_changes'] and preservation['unchanged_modules']==105
contents={'version':VERSION,'analysis_version':'audit-4','policy_version':'review-3','tests_passed':1371,
 'new_regression_cases':22,'frozen_scientific_checks':53,'frozen_fixture_incompatibilities':6,
 'expanded_checks':35,'frozen_source_hashes':39,'sidebar_screenshots':6,'task_views':5,'sidebar_events':48000,
 'wheel':wheel.name,'wheel_sha256':digest(wheel.read_bytes()),'verified_wheel_python_sources':len(verified),
 'wheel_matches_source':True,'platform':'Python 3.12 / Linux / Tk through Xvfb',
 'scientific_changes_in_rc5':False,'sidebar_task_tabs':['Data','Plot','Gates','Analysis'],
 'remaining_format_acceptance':['MQD native/export truth','real FCS1.0 acquisition','external FCS3.2 acquisition']}
(ROOT/'validation/package_contents_rc5.json').write_text(json.dumps(contents,indent=2)+'\n')
excluded={'__pycache__','.pytest_cache','build','vflow.egg-info','.git'}
def include(path):
    rel=path.relative_to(ROOT)
    if any(part in excluded for part in rel.parts) or path.suffix=='.pyc':return False
    if rel.parts[0]=='dist' and path!=wheel:return False
    return True
payload=sorted(p for p in ROOT.rglob('*') if p.is_file() and include(p) and p.name!='SOURCE_SHA256.json')
manifest={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in payload}
manifest_path=ROOT/'SOURCE_SHA256.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
archive=ROOT.parent/'vFlow_v4.4.3rc5_Task_Tabs_and_Control_Preservation.zip'
staged=archive.with_name(archive.name+'.tmp')
with zipfile.ZipFile(staged,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for path in payload+[manifest_path]:z.write(path,f'vFlow_v{VERSION}/'+path.relative_to(ROOT).as_posix())
with staged.open('r+b') as handle:handle.flush();os.fsync(handle.fileno())
staged.replace(archive)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert len(z.namelist())==len(manifest)+1
    for name,sha in manifest.items():assert digest(z.read(f'vFlow_v{VERSION}/'+name))==sha,name
    assert z.read(f'vFlow_v{VERSION}/dist/'+wheel.name)==wheel.read_bytes()
folder=ROOT.parent/'vFlow_v4.4.3rc5_Task_Tabs_Screenshots'
shots=sorted(folder.glob('*.png'))
assert len(shots)==6
screenshot_zip=folder.parent/(folder.name+'.zip')
with zipfile.ZipFile(screenshot_zip,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for path in shots+[folder/'README.md']:z.write(path,folder.name+'/'+path.name)
with zipfile.ZipFile(screenshot_zip) as z:
    assert z.testzip() is None and len(z.namelist())==7
    for path in shots:assert z.read(folder.name+'/'+path.name)==path.read_bytes()
receipt={'archive':archive.name,'archive_bytes':archive.stat().st_size,'archive_sha256':digest(archive.read_bytes()),
 'payload_files':len(manifest)+1,'screenshots_archive':screenshot_zip.name,'screenshots_bytes':screenshot_zip.stat().st_size,
 'screenshots_sha256':digest(screenshot_zip.read_bytes()),'wheel_sha256':contents['wheel_sha256'],
 'verified_wheel_python_sources':len(verified),'all_checks_passed':True}
(ROOT.parent/'research/rc5_package_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
