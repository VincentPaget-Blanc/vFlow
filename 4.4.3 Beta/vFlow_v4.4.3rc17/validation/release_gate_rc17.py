"""Check final suite coverage, source identity, scientific truth and package inputs."""
import hashlib,json,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];V=ROOT/'validation'
def read(name):return json.loads((V/name).read_text())
sources={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'vflow').rglob('*.py'))}
plan=read('rc17_shard_plan.json');groups=plan['groups'];listed=[p for group in groups for p in group]
assert len(listed)==len(set(listed)) and set(listed)=={p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').glob('test_*.py')}
receipts=[];records={};count=0;seconds=[];original_failed=[]
for index,group in enumerate(groups):
 receipt=read(f'full_suite_rc17_shard_{index}.json')
 assert receipt['exitcode'] in (0,1) and receipt['source_unchanged'] and receipt['sources']==sources and receipt['test_files']==group
 xml=ET.parse(V/f'full_suite_rc17_shard_{index}.xml').getroot()
 for suite in xml.iter('testsuite'):
  count+=int(suite.get('tests','0'))
  assert all(int(suite.get(k,'0'))==0 for k in ('errors','skipped'))
 for case in xml.iter('testcase'):
  key=(case.get('classname'),case.get('name'));assert key not in records;records[key]=case
  if case.find('failure') is not None:original_failed.append(key)
 receipts.append(receipt);seconds.append(round(receipt['seconds'],3))
assert count==1690 and len(records)==count
# Preserve original run logs. Replace only the results from the four modules
# whose seven release/structural expectations were updated; no app code changed.
rechecked_modules={'tests.test_import_headless','tests.test_release_metadata','tests.test_release_metadata_files','tests.test_polygon_close_entry_planning_refactor'}
assert len(original_failed)==7 and all(key[0] in rechecked_modules for key in original_failed)
recheck=ET.parse(V/'release_expectation_recheck_rc17.xml').getroot();new_keys=set()
for case in recheck.iter('testcase'):
 key=(case.get('classname'),case.get('name'))
 assert key in records and key[0] in rechecked_modules and key not in new_keys
 assert all(case.find(k) is None for k in ('failure','error','skipped'))
 new_keys.add(key);records[key]=case
assert new_keys=={key for key in records if key[0] in rechecked_modules}
assert all(all(case.find(k) is None for k in ('failure','error','skipped')) for case in records.values())
raw=read('raw_preservation_rc17.json');assert raw['all_unchanged'] and raw['files']==57
assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==sha for n,sha in raw['hashes'].items())
protected=read('preservation_rc17.json')
assert protected['unchanged_core_modules']==19 and protected['statistical_modules_unchanged_except_version']==11
assert not protected['statistics_behavior_changes'] and not protected['removed_original_methods_or_classes']
assert protected['source_launcher_unchanged'] and protected['rc16_registry_unchanged']
frozen=read('frozen_benchmark_rc17.json');expanded=read('expanded_benchmark_rc17.json')
assert frozen['passed']==53 and expanded['passed']==35
workflow=read('bug_hunt_rc17/workflow_result.json');assert workflow['passed']==36 and workflow['raw_hashes_unchanged'] and not workflow['errors']
visual=read('ui_visual_rc17/result.json');assert visual['passed']==8 and len(visual['views'])==6 and not visual['errors'] and visual['tk']=='8.6.14'
assert '28 passed' in (V/'ui_interactions_rc17_final.txt').read_text()
assert '51 passed' in (V/'ui_interactions_tk86_rc17_final.txt').read_text()
wheel=ROOT/'dist/vflow-4.4.3rc17-py3-none-any.whl'
with zipfile.ZipFile(wheel) as z:
 assert {n for n in z.namelist() if n.startswith('vflow/') and n.endswith('.py')}==set(sources)
 assert all(z.read(n)==(ROOT/n).read_bytes() for n in sources)
 assert z.read('vflow-4.4.3rc17.dist-info/METADATA').decode().split('\n\n',1)[1].rstrip()==(ROOT/'README.md').read_text().rstrip()
result={'all_checks_passed':True,'version':'4.4.3rc17','ordinary_tests':count,'test_modules':len(listed),'shards':4,'shard_seconds':seconds,
 'release_expectation_cases_rechecked':len(new_keys),'outdated_expectations_corrected':7,'focused_interaction_tests':28,'new_interaction_tests':27,'tk86_interaction_and_audit_tests':51,'scientific_checks':88,'raw_benchmark_files_preserved':57,
 'benchmark_app_workflows':36,'visual_interaction_checks':8,'screenshots':6,'native_runtime':'Linux/Python 3.12/Tk 9.0.4; focused and visual Linux/Tk 8.6.14',
 'wheel_sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'source_count':len(sources),'sources':sources}
(V/'release_gate_rc17.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='sources'},indent=2))
