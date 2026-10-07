"""Build atomic RC8 app/review archives only after final validation passes."""
from pathlib import Path
import hashlib,json,zipfile,os,shutil
ROOT=Path(__file__).resolve().parents[1];VERSION='4.4.3rc8'
def digest(data):return hashlib.sha256(data).hexdigest()
wheel=ROOT/'dist'/f'vflow-{VERSION}-py3-none-any.whl';verified=[]
with zipfile.ZipFile(wheel) as z:
 assert z.testzip() is None
 for p in sorted((ROOT/'vflow').rglob('*.py')):
  name=p.relative_to(ROOT).as_posix();assert z.read(name)==p.read_bytes(),name;verified.append(name)
 assert len(verified)==120
 assert f'Version: {VERSION}\n' in z.read(f'vflow-{VERSION}.dist-info/METADATA').decode()
full=(ROOT/'validation/full_suite_rc8_final.txt').read_text();assert '1455 passed' in full and 'failed' not in full
assert '25 passed' in (ROOT/'validation/adaptive_samples_rc8_new_cases.txt').read_text()
assert '20 passed' in (ROOT/'validation/channel_contract_rc8.txt').read_text()
expanded=json.loads((ROOT/'validation/expanded_benchmark_rc8_final.json').read_text());assert expanded['passed']==35
assert '53/53 scientific checks passed' in (ROOT/'validation/frozen_benchmark_rc8_final.txt').read_text()
assert '39 frozen files' in (ROOT/'validation/frozen_integrity_rc8.txt').read_text()
main_dir=ROOT/'validation/ui_review_rc8_after';adaptive_dir=ROOT/'validation/adaptive_review_rc8'
main=json.loads((main_dir/'inventory.json').read_text());assert len(main['views'])==47 and not main['errors'] and not main['notes']
adaptive=json.loads((adaptive_dir/'inventory.json').read_text());assert len(adaptive['views'])==10 and not adaptive['errors']
persistence=(ROOT/'validation/workspace_persistence_rc8.txt').read_text();assert all('PASS '+phase in persistence for phase in ('create','verify_initial','edit_again','verify_final'))
preservation=json.loads((ROOT/'validation/preservation_rc8.json').read_text());assert not preservation['unexpected_changes'] and preservation['unchanged_modules']==110
contents={'version':VERSION,'tests_passed':1455,'new_native_layout_cases':25,'frozen_scientific_checks':53,'frozen_fixture_incompatibilities':6,'expanded_checks':35,'frozen_hashes':39,'current_native_views':57,'native_general_views':47,'native_adaptive_views':10,'fresh_process_persistence_passed':True,'analysis_version':'audit-4','review_policy':'review-3','wheel':wheel.name,'wheel_sha256':digest(wheel.read_bytes()),'verified_wheel_python_sources':len(verified),'wheel_matches_source':True,'numerical_changes':False,'original_core_modules_preserved':19,'protected_statistics_ingestion_service_modules':41,'historical_screenshots':'Earlier PNG/JPG sets are available in their original versioned archives; inventories/logs remain.','platform':'Python 3.12 / Linux / Tk 9 / Xvfb','remaining_format_acceptance':['MQD native/export truth','real FCS1.0 acquisition','external FCS3.2 acquisition']}
(ROOT/'validation/package_contents_rc8.json').write_text(json.dumps(contents,indent=2)+'\n')
excluded={'__pycache__','.pytest_cache','build','vflow.egg-info','.git'}
def include(p):
 rel=p.relative_to(ROOT)
 if any(part in excluded for part in rel.parts) or p.suffix=='.pyc' or (rel.parts[0]=='dist' and p!=wheel):return False
 if rel.parts[0]=='validation' and p.suffix.lower() in ('.png','.jpg','.jpeg'):
  return len(rel.parts)>2 and rel.parts[1] in ('ui_review_rc8_after','adaptive_review_rc8')
 return True
payload=sorted(p for p in ROOT.rglob('*') if p.is_file() and include(p) and p.name!='SOURCE_SHA256.json')
manifest={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in payload}
manifest_path=ROOT/'SOURCE_SHA256.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
def atomic_archive(path,writer):
 staged=path.with_name(path.name+'.tmp')
 with zipfile.ZipFile(staged,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:writer(z)
 with staged.open('r+b') as f:os.fsync(f.fileno())
 staged.replace(path)
 with zipfile.ZipFile(path) as z:assert z.testzip() is None
archive=ROOT.parent/'vFlow_v4.4.3rc8_Adaptive_Samples.zip'
def write_app(z):
 for p in payload+[manifest_path]:z.write(p,f'vFlow_v{VERSION}/'+p.relative_to(ROOT).as_posix())
atomic_archive(archive,write_app)
with zipfile.ZipFile(archive) as z:
 assert len(z.namelist())==len(manifest)+1
 for name,sha in manifest.items():assert digest(z.read(f'vFlow_v{VERSION}/'+name))==sha,name
screens=ROOT.parent/'vFlow_v4.4.3rc8_UI_Review.zip'
def write_screens(z):
 for folder,label in ((main_dir,'general'),(adaptive_dir,'adaptive')):
  for p in sorted(folder.iterdir()):
   if p.is_file():z.write(p,f'vFlow_v{VERSION}_UI_Review/'+label+'/'+p.name)
 z.writestr(f'vFlow_v{VERSION}_UI_Review/README.md','# Native UI review\n\n57 native Linux/Tk views: 47 general app/menu/dialog/analysis views and 10 adaptive sample-list views. The main app uses four frozen cytometry files with 48,000 events; Polar/Batch views use the microscopy benchmark. The long list adds 56 labeled 250-row benchmark subsets for 60 visible sample entries and 62,000 total events, solely for UI stress. These are not independent acquisitions. Adaptive views include initial list, settings navigation, export end, scaled fonts, manual resizing and automatic reopen. PNGs are native captures; eight JPG contact sheets aid inspection. Inventories record view measurements. Native Windows/macOS/Retina acceptance remains outstanding.\n')
atomic_archive(screens,write_screens)
with zipfile.ZipFile(screens) as z:
 for folder,label in ((main_dir,'general'),(adaptive_dir,'adaptive')):
  for p in folder.iterdir():
   if p.is_file():assert z.read(f'vFlow_v{VERSION}_UI_Review/'+label+'/'+p.name)==p.read_bytes()
preview=ROOT.parent/'vFlow_v4.4.3rc8_Adaptive_Sample_List.png';shutil.copy2(adaptive_dir/'02_Long_List_1080.png',preview)
report=ROOT.parent/'IMPLEMENTATION_REPORT_v4.4.3rc8.md';shutil.copy2(ROOT/report.name,report)
receipt={'archive':archive.name,'archive_bytes':archive.stat().st_size,'archive_sha256':digest(archive.read_bytes()),'payload_files':len(manifest)+1,'screenshots_archive':screens.name,'screenshots_bytes':screens.stat().st_size,'screenshots_sha256':digest(screens.read_bytes()),'current_native_views':57,'wheel_sha256':contents['wheel_sha256'],'verified_wheel_python_sources':len(verified),'all_checks_passed':True}
(ROOT.parent/'research/rc8_package_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
