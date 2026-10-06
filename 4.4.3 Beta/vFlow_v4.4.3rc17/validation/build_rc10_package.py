"""Gate RC10 packaging on current evidence, source preservation and wheel identity."""
from pathlib import Path
import hashlib,json,os,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1];VERSION='4.4.3rc10'
def sha(data):return hashlib.sha256(data).hexdigest()
full=(ROOT/'validation/full_suite_rc10_final.txt').read_text()
assert '1474 passed' in full and 'failed' not in full
for name in ('workspace_actions_rc10_final_fonts.txt','workspace_actions_rc10_tk86_final.txt'):
 text=(ROOT/'validation'/name).read_text();assert '11 passed' in text and 'failed' not in text
assert '53/53 scientific checks passed' in (ROOT/'validation/frozen_benchmark_rc10.txt').read_text()
assert json.loads((ROOT/'validation/expanded_benchmark_rc10.json').read_text())['passed']==35
assert '39 frozen files' in (ROOT/'validation/frozen_integrity_rc10.txt').read_text()
persistence=(ROOT/'validation/workspace_persistence_rc10_final.txt').read_text()
assert all('PASS '+phase in persistence for phase in ('create','verify_initial','edit_again','verify_final'))
assert 'Traceback' not in persistence
preservation=json.loads((ROOT/'validation/preservation_rc10.json').read_text())
assert preservation['unchanged_modules']==111 and preservation['changed_feature_and_ui_modules']==4
assert preservation['version_only_modules']==5 and not preservation['unexpected_changes']
assert not preservation['source_launcher']['changed']
views=json.loads((ROOT/'validation/workspace_actions_rc10/inventory.json').read_text())
assert len(views['views'])==4 and not views['errors'] and views['events']==48000
assert views['source_hashes_unchanged'] and views['save_close_open_controls_passed']
assert views['views'][1]['state']=='Saved'
for name in ('spyder_cached_rc5_tk9_rc10.txt','spyder_cached_rc5_tk86_rc10_final.txt'):
 text=(ROOT/'validation'/name).read_text()
 assert 'Kernel cached RC5' in text and text.count('PASS isolated Spyder launch ')==2
 assert text.count('"version": "4.4.3rc10"')==2 and text.count('"events": 48000')==2
 assert 'Traceback' not in text and 'ERROR ' not in text
assert (ROOT/'CHANGELOG.md').read_text().startswith('# vFlow '+VERSION+'\n')
wheel=ROOT/'dist'/f'vflow-{VERSION}-py3-none-any.whl'
verified=[]
with zipfile.ZipFile(wheel) as z:
 assert z.testzip() is None
 for source in sorted((ROOT/'vflow').rglob('*.py')):
  name=source.relative_to(ROOT).as_posix();assert z.read(name)==source.read_bytes(),name;verified.append(name)
 assert len(verified)==120
 assert f'Version: {VERSION}\n' in z.read(f'vflow-{VERSION}.dist-info/METADATA').decode()
contents={'version':VERSION,'full_suite_passed':1474,'workspace_ui_regressions_tk9':11,'workspace_ui_regressions_tk86':11,
 'frozen_scientific_checks':53,'expanded_checks':35,'frozen_hashes':39,'current_native_workspace_views':4,
 'cached_rc5_spyder_launches':{'Tk8.6':2,'Tk9':2},'benchmark_events_per_launch':48000,
 'fresh_process_persistence_passed':True,'analysis_version':'audit-4','review_policy':'review-3',
 'wheel':wheel.name,'wheel_sha256':sha(wheel.read_bytes()),'verified_wheel_python_sources':len(verified),
 'wheel_matches_source':True,'numerical_changes':False,'source_launcher_changed':False,
 'unchanged_core_modules':19,'protected_statistics_ingestion_service_modules':41,
 'platform':'Linux/Python3.12/Tk8.6.14+Tk9.0.4/Xvfb; actual Spyder runner, no native desktop frontend',
 'final_followup':'After full-suite collection, Open Recent semantic font/padding was corrected; all 11 workspace cases reran on Tk9/Tk8.6 and current screenshots use that final source.'}
(ROOT/'validation/package_contents_rc10.json').write_text(json.dumps(contents,indent=2)+'\n')
excluded={'__pycache__','.pytest_cache','build','vflow.egg-info','.git'}
def include(p):
 rel=p.relative_to(ROOT)
 if any(part in excluded or part.endswith('_run') for part in rel.parts) or p.suffix=='.pyc':return False
 if rel.parts[0]=='dist' and p!=wheel:return False
 if rel.parts[0]=='validation' and p.suffix.lower() in ('.png','.jpg','.jpeg'):
  return len(rel.parts)>2 and rel.parts[1]=='workspace_actions_rc10'
 return p.name!='SOURCE_SHA256.json'
payload=sorted(p for p in ROOT.rglob('*') if p.is_file() and include(p))
manifest={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in payload}
manifest_path=ROOT/'SOURCE_SHA256.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
archive=ROOT.parent/'vFlow_v4.4.3rc10_Workspace_Controls.zip';staged=archive.with_name(archive.name+'.tmp')
with zipfile.ZipFile(staged,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in payload+[manifest_path]:z.write(p,f'vFlow_v{VERSION}/'+p.relative_to(ROOT).as_posix())
with staged.open('r+b') as f:os.fsync(f.fileno())
with zipfile.ZipFile(staged) as z:
 assert z.testzip() is None and len(z.namelist())==len(manifest)+1
 for name,digest in manifest.items():assert sha(z.read(f'vFlow_v{VERSION}/'+name))==digest,name
staged.replace(archive)
report=ROOT.parent/f'IMPLEMENTATION_REPORT_v{VERSION}.md';shutil.copy2(ROOT/report.name,report)
shutil.copy2(ROOT/'CHANGELOG.md',ROOT.parent/'CHANGELOG.md')
preview=ROOT.parent/'vFlow_RC10_Data_Workspace.png';shutil.copy2(ROOT/'validation/workspace_actions_rc10/02_Saved_And_Reopened.png',preview)
receipt={'archive':str(archive),'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive.read_bytes()),
 'payload_files':len(manifest)+1,'wheel_sha256':contents['wheel_sha256'],'verified_wheel_sources':120,
 'full_suite_passed':1474,'workspace_cases_per_tk':11,'changelog_updated':True,'all_checks_passed':True}
(ROOT.parent/'research/rc10_package_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
