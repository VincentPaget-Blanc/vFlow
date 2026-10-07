"""Build verified RC7 source/wheel and native review archives atomically."""
from pathlib import Path
import hashlib,json,zipfile,os,shutil
ROOT=Path(__file__).resolve().parents[1];VERSION='4.4.3rc7'
def digest(data):return hashlib.sha256(data).hexdigest()
wheel=ROOT/'dist'/f'vflow-{VERSION}-py3-none-any.whl'
verified=[]
with zipfile.ZipFile(wheel) as z:
 assert z.testzip() is None
 for p in sorted((ROOT/'vflow').rglob('*.py')):
  name=p.relative_to(ROOT).as_posix();assert z.read(name)==p.read_bytes(),name;verified.append(name)
 assert len(verified)==119
 assert f'Version: {VERSION}\n' in z.read(f'vflow-{VERSION}.dist-info/METADATA').decode()
full=(ROOT/'validation/full_suite_rc7_final.txt').read_text();assert '1430 passed' in full and 'failed' not in full
assert '43 passed' in (ROOT/'validation/threshold_deletion_rc7.txt').read_text()
expanded=json.loads((ROOT/'validation/expanded_benchmark_rc7_final.json').read_text());assert expanded['passed']==35
assert '53/53 scientific checks passed' in (ROOT/'validation/frozen_benchmark_rc7_final.txt').read_text()
assert '39 frozen files' in (ROOT/'validation/frozen_integrity_rc7.txt').read_text()
capture_dir=ROOT/'validation/ui_review_rc7_after'
capture=json.loads((capture_dir/'inventory.json').read_text());assert len(capture['views'])==47 and not capture['errors'] and not capture['notes']
preservation=json.loads((ROOT/'validation/preservation_rc7.json').read_text());assert not preservation['unexpected_changes'] and preservation['unchanged_modules']==102
contents={'version':VERSION,'tests_passed':1430,'new_regression_cases':34,'focused_cases_passed':43,'frozen_scientific_checks':53,'frozen_fixture_incompatibilities':6,'expanded_checks':35,'frozen_hashes':39,'native_views':47,'analysis_version':'audit-4','review_policy':'review-3','wheel':wheel.name,'wheel_sha256':digest(wheel.read_bytes()),'verified_wheel_python_sources':len(verified),'wheel_matches_source':True,'numerical_estimators_changed':False,'intentional_empty_gate_serialization_extended':True,'platform':'Python 3.12 / Linux / Tk 9 / Xvfb','protected_statistics_ingestion_service_modules':41,'remaining_format_acceptance':['MQD native/export truth','real FCS1.0 acquisition','external FCS3.2 acquisition']}
(ROOT/'validation/package_contents_rc7.json').write_text(json.dumps(contents,indent=2)+'\n')
excluded={'__pycache__','.pytest_cache','build','vflow.egg-info','.git'}
def include(p):
 rel=p.relative_to(ROOT)
 return not(any(part in excluded for part in rel.parts) or p.suffix=='.pyc' or (rel.parts[0]=='dist' and p!=wheel))
payload=sorted(p for p in ROOT.rglob('*') if p.is_file() and include(p) and p.name!='SOURCE_SHA256.json')
manifest={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in payload}
manifest_path=ROOT/'SOURCE_SHA256.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
def atomic_archive(path,write):
 staged=path.with_name(path.name+'.tmp')
 with zipfile.ZipFile(staged,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:write(z)
 with staged.open('r+b') as f:f.flush();os.fsync(f.fileno())
 staged.replace(path)
 with zipfile.ZipFile(path) as z:assert z.testzip() is None
archive=ROOT.parent/'vFlow_v4.4.3rc7_Threshold_Deletion_and_UX.zip'
def write_app(z):
 for p in payload+[manifest_path]:z.write(p,f'vFlow_v{VERSION}/'+p.relative_to(ROOT).as_posix())
atomic_archive(archive,write_app)
with zipfile.ZipFile(archive) as z:
 assert len(z.namelist())==len(manifest)+1
 for name,sha in manifest.items():assert digest(z.read(f'vFlow_v{VERSION}/'+name))==sha,name
screens=ROOT.parent/'vFlow_v4.4.3rc7_UI_Review.zip'
def write_screens(z):
 for p in sorted(capture_dir.iterdir()):
  if p.is_file():z.write(p,'vFlow_v4.4.3rc7_UI_Review/'+p.name)
 z.writestr('vFlow_v4.4.3rc7_UI_Review/README.md','# Native UI review\n\n47 native Linux/Tk views with benchmark data, including all task pages, menus/dialogs, scroll endpoints, analysis windows, real Otsu/GMM thresholds, Delete, empty-state recovery and Undo. The main app uses 48,000 frozen cytometry events; Polar/Batch views use 15,000 microscopy events. Six labeled JPG contact sheets aid inspection; PNGs are native captures. inventory.json records controls and menu entries. Native macOS/Windows visual acceptance is not claimed.\n')
atomic_archive(screens,write_screens)
with zipfile.ZipFile(screens) as z:
 for p in capture_dir.iterdir():
  if p.is_file():assert z.read('vFlow_v4.4.3rc7_UI_Review/'+p.name)==p.read_bytes()
preview=ROOT.parent/'vFlow_v4.4.3rc7_Threshold_Controls.png';shutil.copy2(capture_dir/'35_GMM_Thresholds.png',preview)
report=ROOT.parent/'IMPLEMENTATION_REPORT_v4.4.3rc7.md';shutil.copy2(ROOT/report.name,report)
receipt={'archive':archive.name,'archive_bytes':archive.stat().st_size,'archive_sha256':digest(archive.read_bytes()),'payload_files':len(manifest)+1,'screenshots_archive':screens.name,'screenshots_bytes':screens.stat().st_size,'screenshots_sha256':digest(screens.read_bytes()),'native_views':47,'wheel_sha256':contents['wheel_sha256'],'verified_wheel_python_sources':len(verified),'all_checks_passed':True}
(ROOT.parent/'research/rc7_package_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
