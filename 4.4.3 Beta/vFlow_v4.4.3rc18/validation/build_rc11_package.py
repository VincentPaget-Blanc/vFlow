"""Gate RC11 packaging on final native evidence and exact source/wheel identity."""
from pathlib import Path
import hashlib,json,os,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1];VERSION='4.4.3rc11'
def sha(data):return hashlib.sha256(data).hexdigest()
def passing_log(name,phrase):
 text=(ROOT/'validation'/name).read_text()
 assert phrase in text and 'failed' not in text and 'Traceback' not in text,name
passing_log('full_suite_rc11_release_final_source.txt','1498 passed')
passing_log('audit_selection_rc11_last_layout.txt','39 passed')
passing_log('audit_workspace_adaptive_rc11_tk86_release.txt','75 passed')
passing_log('frozen_benchmark_rc11.txt','53/53 scientific checks passed')
assert json.loads((ROOT/'validation/expanded_benchmark_rc11.json').read_text())['passed']==35
passing_log('frozen_integrity_rc11.txt','39 frozen files')
persistence=(ROOT/'validation/workspace_persistence_rc11.txt').read_text()
assert all('PASS '+phase in persistence for phase in ('create','verify_initial','edit_again','verify_final'))
assert 'Traceback' not in persistence
preservation=json.loads((ROOT/'validation/preservation_rc11.json').read_text())
assert preservation['unchanged_modules']==112 and preservation['changed_feature_and_ui_modules']==3
assert preservation['version_only_modules']==5 and not preservation['unexpected_changes']
assert not preservation['source_launcher']['changed']
for row in preservation['modules']:
 assert sha((ROOT/row['path']).read_bytes())==row['rc11_sha256'],row['path']
views=json.loads((ROOT/'validation/audit_selection_rc11/layout_inventory.json').read_text())
assert len(views['views'])==2 and not views['errors'] and views['events']==48000
passing_log('layout_review_rc11.txt','PASS 2 layout reviews')
benchmark=json.loads((ROOT/'validation/audit_selection_rc11/benchmark_result.json').read_text())
assert benchmark['events_loaded']==48000 and benchmark['audited_events']==24000
assert benchmark['audited_sample_count']==2 and benchmark['selected_variables']==['FSC-A','SSC-A']
assert benchmark['exports_and_workspace_reopen_passed'] and benchmark['raw_hashes_unchanged']
assert benchmark['no_automatic_exclusion'] and not benchmark['errors']
for name in ('spyder_cached_rc5_tk9_rc11_final.txt','spyder_cached_rc5_tk86_rc11_final.txt'):
 text=(ROOT/'validation'/name).read_text()
 assert 'Kernel cached RC5' in text and text.count('PASS isolated Spyder launch ')==2
 assert text.count('"version": "4.4.3rc11"')==2 and text.count('"events": 48000')==2
 assert 'Traceback' not in text and 'ERROR ' not in text
assert (ROOT/'CHANGELOG.md').read_text().startswith('# vFlow '+VERSION+'\n')
wheel=ROOT/'dist'/f'vflow-{VERSION}-py3-none-any.whl';verified=[]
with zipfile.ZipFile(wheel) as z:
 assert z.testzip() is None
 for source in sorted((ROOT/'vflow').rglob('*.py')):
  name=source.relative_to(ROOT).as_posix();assert z.read(name)==source.read_bytes(),name;verified.append(name)
 assert len(verified)==120
 assert f'Version: {VERSION}\n' in z.read(f'vflow-{VERSION}.dist-info/METADATA').decode()
contents={'version':VERSION,'full_suite_passed':1498,'audit_selection_cases_tk9':39,
 'audit_workspace_adaptive_cases_tk86':75,'new_audit_selection_cases':24,
 'frozen_scientific_checks':53,'expanded_checks':35,'frozen_hashes':39,'current_native_views':3,
 'cached_rc5_spyder_launches':{'Tk8.6':2,'Tk9':2},'benchmark_events_per_launch':48000,
 'benchmark_audited_events':24000,'benchmark_selected_samples':2,'benchmark_selected_variables':['FSC-A','SSC-A'],
 'fresh_process_persistence_passed':True,'analysis_version':'audit-4','review_policy':'review-3',
 'wheel':wheel.name,'wheel_sha256':sha(wheel.read_bytes()),'verified_wheel_python_sources':len(verified),
 'wheel_matches_source':True,'numerical_changes':False,'source_launcher_changed':False,
 'unchanged_core_modules':19,'protected_statistics_ingestion_service_modules':41,
 'platform':'Linux/Python3.12/Tk8.6.14+Tk9.0.4/Xvfb; actual Spyder runner, no native desktop frontend',
 'final_followup':'Final full suite and both Tk audit checks include footer-wrap resize measurements and compact padding at Large/200%.'}
(ROOT/'validation/package_contents_rc11.json').write_text(json.dumps(contents,indent=2)+'\n')
excluded={'__pycache__','.pytest_cache','build','vflow.egg-info','.git'}
def include(p):
 rel=p.relative_to(ROOT)
 if any(part in excluded or part.endswith('_run') for part in rel.parts) or p.suffix=='.pyc':return False
 if rel.parts[0]=='dist' and p!=wheel:return False
 if rel.parts[0]=='validation' and p.suffix.lower() in ('.png','.jpg','.jpeg'):
  return len(rel.parts)>2 and rel.parts[1]=='audit_selection_rc11'
 return p.name!='SOURCE_SHA256.json'
payload=sorted(p for p in ROOT.rglob('*') if p.is_file() and include(p))
manifest={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in payload}
manifest_path=ROOT/'SOURCE_SHA256.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
archive=ROOT.parent/'vFlow_v4.4.3rc11_Audit_Selection_and_Edge_Cases.zip';staged=archive.with_name(archive.name+'.tmp')
with zipfile.ZipFile(staged,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in payload+[manifest_path]:z.write(p,f'vFlow_v{VERSION}/'+p.relative_to(ROOT).as_posix())
with staged.open('r+b') as f:os.fsync(f.fileno())
with zipfile.ZipFile(staged) as z:
 assert z.testzip() is None and len(z.namelist())==len(manifest)+1
 for name,digest in manifest.items():assert sha(z.read(f'vFlow_v{VERSION}/'+name))==digest,name
staged.replace(archive)
report=ROOT.parent/f'IMPLEMENTATION_REPORT_v{VERSION}.md';shutil.copy2(ROOT/report.name,report)
shutil.copy2(ROOT/'CHANGELOG.md',ROOT.parent/'CHANGELOG.md')
preview=ROOT.parent/'vFlow_RC11_Statistical_Audit.png';shutil.copy2(ROOT/'validation/audit_selection_rc11/01_Selected_Benchmark_Audit.png',preview)
receipt={'archive':str(archive),'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive.read_bytes()),
 'payload_files':len(manifest)+1,'wheel_sha256':contents['wheel_sha256'],'verified_wheel_sources':120,
 'full_suite_passed':1498,'audit_selection_cases_tk9':39,'audit_workspace_adaptive_cases_tk86':75,
 'changelog_updated':True,'all_checks_passed':True}
(ROOT.parent/'research/rc11_package_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
