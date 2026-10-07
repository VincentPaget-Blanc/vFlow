"""Build atomic delivery archives after source, wheel and verification checks."""
from pathlib import Path
import hashlib,json,zipfile,os
ROOT=Path(__file__).resolve().parents[1];VERSION='4.4.3rc6'
def digest(data):return hashlib.sha256(data).hexdigest()
wheel=ROOT/'dist'/f'vflow-{VERSION}-py3-none-any.whl'
verified=[]
with zipfile.ZipFile(wheel) as z:
 assert z.testzip() is None
 for p in sorted((ROOT/'vflow').rglob('*.py')):
  name=p.relative_to(ROOT).as_posix();assert z.read(name)==p.read_bytes(),name;verified.append(name)
 assert len(verified)==118
 assert f'Version: {VERSION}\n' in z.read(f'vflow-{VERSION}.dist-info/METADATA').decode()
full=(ROOT/'validation/full_suite_rc6_final.txt').read_text();assert '1396 passed' in full and 'failed' not in full
assert '25 passed' in (ROOT/'validation/ui_restoration_rc6.txt').read_text()
expanded=json.loads((ROOT/'validation/expanded_benchmark_rc6_final.json').read_text());assert expanded['passed']==35
assert '53/53 scientific checks passed' in (ROOT/'validation/frozen_benchmark_rc6_final.txt').read_text()
assert '39 frozen files' in (ROOT/'validation/frozen_integrity_rc6.txt').read_text()
capture=json.loads((ROOT/'validation/ui_review_rc6_after/inventory.json').read_text());assert len(capture['views'])==38 and not capture['errors']
preservation=json.loads((ROOT/'validation/ui_preservation_rc6.json').read_text());assert not preservation['unexpected_changes'] and preservation['unchanged_modules']==100
contents={'version':VERSION,'tests_passed':1396,'new_native_ui_cases':25,'frozen_scientific_checks':53,'frozen_fixture_incompatibilities':6,'expanded_checks':35,'frozen_hashes':39,'native_after_views':38,'native_before_views':33,'analysis_version':'audit-4','review_policy':'review-3','wheel':wheel.name,'wheel_sha256':digest(wheel.read_bytes()),'verified_wheel_python_sources':len(verified),'wheel_matches_source':True,'scientific_changes_in_rc6':False,'platform':'Python 3.12 / Linux / Tk 9 / Xvfb','protected_scientific_and_ingestion_modules':59,'remaining_format_acceptance':['MQD native/export truth','real FCS1.0 acquisition','external FCS3.2 acquisition']}
(ROOT/'validation/package_contents_rc6.json').write_text(json.dumps(contents,indent=2)+'\n')
excluded={'__pycache__','.pytest_cache','build','vflow.egg-info','.git'}
def include(p):
 rel=p.relative_to(ROOT)
 return not(any(part in excluded for part in rel.parts) or p.suffix=='.pyc' or (rel.parts[0]=='dist' and p!=wheel))
payload=sorted(p for p in ROOT.rglob('*') if p.is_file() and include(p) and p.name!='SOURCE_SHA256.json')
manifest={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in payload}
manifest_path=ROOT/'SOURCE_SHA256.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
archive=ROOT.parent/'vFlow_v4.4.3rc6_UI_Restoration.zip';staged=archive.with_name(archive.name+'.tmp')
with zipfile.ZipFile(staged,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in payload+[manifest_path]:z.write(p,f'vFlow_v{VERSION}/'+p.relative_to(ROOT).as_posix())
with staged.open('r+b') as f:f.flush();os.fsync(f.fileno())
staged.replace(archive)
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None and len(z.namelist())==len(manifest)+1
 for name,sha in manifest.items():assert digest(z.read(f'vFlow_v{VERSION}/'+name))==sha,name
screenshot_zip=ROOT.parent/'vFlow_v4.4.3rc6_Visual_Review.zip';staged=screenshot_zip.with_name(screenshot_zip.name+'.tmp')
with zipfile.ZipFile(staged,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for phase in ('before','after'):
  for p in sorted((ROOT/'validation'/('ui_review_rc6_'+phase)).iterdir()):
   if p.is_file():z.write(p,'vFlow_v4.4.3rc6_Visual_Review/'+phase+'/'+p.name)
 z.writestr('vFlow_v4.4.3rc6_Visual_Review/README.md','# Native visual review\n\nBefore: 33 native views of RC5. After: 38 native views of RC6, including scroll endpoints and advanced resolvers. The main app loads 48,000 cytometry events; Polar/Batch plots load 15,000 microscopy events. PNGs are native Linux/Tk captures; JPG contact sheets are annotated thumbnails for inspection. inventory.json records controls and menu entries.\n')
with staged.open('r+b') as f:f.flush();os.fsync(f.fileno())
staged.replace(screenshot_zip)
with zipfile.ZipFile(screenshot_zip) as z:assert z.testzip() is None
receipt={'archive':archive.name,'archive_bytes':archive.stat().st_size,'archive_sha256':digest(archive.read_bytes()),'payload_files':len(manifest)+1,'screenshots_archive':screenshot_zip.name,'screenshots_bytes':screenshot_zip.stat().st_size,'screenshots_sha256':digest(screenshot_zip.read_bytes()),'wheel_sha256':contents['wheel_sha256'],'verified_wheel_python_sources':len(verified),'all_checks_passed':True}
(ROOT.parent/'research/rc6_package_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
