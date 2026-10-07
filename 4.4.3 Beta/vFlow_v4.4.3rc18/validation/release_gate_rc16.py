"""Refuse RC16 release packaging without every source-matched acceptance receipt."""
import argparse,hashlib,json,re,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];V=ROOT/'validation'
p=argparse.ArgumentParser();p.add_argument('--baseline-root',type=Path,required=True);a=p.parse_args()
def data(name):return json.loads((V/name).read_text())
def summary(name,count):
    s=(V/name).read_text();assert re.search(r'\b'+str(count)+r' passed\b',s),name
    assert not re.search(r'\b(?:FAILED|ERROR|[1-9]\d* failed|[1-9]\d* skipped)\b',s),name
sources={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'vflow').rglob('*.py'))}
full=data('full_suite_rc16_receipt.json');assert full['exitcode']==0 and full['source_unchanged'] and full['sources']==sources
xml=ET.parse(V/'full_suite_rc16_receipt.xml').getroot();suites=xml.findall('testsuite')
assert sum(int(s.get('tests','0')) for s in suites)==1663
assert all(int(s.get(k,'0'))==0 for s in suites for k in ('errors','failures','skipped'))
summary('full_suite_rc16_final.txt',1663);summary('recovered_focus_native_rc16.txt',34);summary('focus_fonts_rc16_final.txt',30)
summary('ingestion_rc16_final.txt',61);summary('source_integrity_rc16_final.txt',13)
assert data('frozen_benchmark_rc16_final.json')['passed']==53
assert data('expanded_benchmark_rc16_final.json')['passed']==35
assert '39 frozen files' in (V/'frozen_integrity_rc16_final.txt').read_text()
raw=data('raw_preservation_rc16_final.json');assert raw['all_unchanged'] and raw['files']==57
assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==sha for n,sha in raw['hashes'].items())
for seed in (1601,1602,1603,1604):assert data(f'compound_benchmark_rc16/{seed}.json')['passed']
workflow=data('bug_hunt_rc16/workflow_result.json');assert workflow['passed']==36 and workflow['raw_hashes_unchanged'] and not workflow['errors']
native=data('native_release_rc16_final_v2/result.json');assert native['passed'] and len(native['results'])==15 and not native['unsafe_controls_run']
persist=(V/'workspace_persistence_rc16_final.txt').read_text();assert all('PASS '+phase in persist for phase in ('create','verify','edit_again','verify_final'))
spy=(V/'spyder_cached_rc5_rc16_final.txt').read_text();assert 'Kernel cached RC5' in spy and spy.count('PASS isolated Spyder launch')==2
assert 'PASS standalone helper' in (V/'app_only_diagnostic_rc16_final.txt').read_text()
endurance=data('endurance_rc16_final_receipt.json');assert endurance['passed'] and endurance['sources']==sources and endurance['result']['active_seconds']>=1200
matched=data('matched_timing_rc16_final.json');assert matched['passed'] and matched['numerical_results_identical'] and matched['measured_runs_per_version']==5
layout=data('audit_selection_rc16/layout_inventory.json');assert len(layout['views'])==3 and not layout['errors']
assert 'PASS 3 layout reviews' in (V/'layout_review_fonts_rc16_final.txt').read_text()
assert (ROOT/'CHANGELOG.md').read_bytes().endswith((a.baseline_root/'CHANGELOG.md').read_bytes())
protected=data('preservation_rc16.json');assert protected['unchanged_core_modules']==19 and protected['protected_statistical_modules']==11 and protected['no_original_methods_removed']
assert protected['all_legacy_methods_unchanged'] and protected['population_capture_unchanged'] and not protected['source_launcher_changed']
receipt={'all_checks_passed':True,'version':'4.4.3rc16','ordinary_tests':1663,'focused_tests':34,'font_aware_native_focused_tests':30,
    'ingestion_tests':61,'source_integrity_tests':13,'compound_scenarios':4,'scientific_checks':88,'benchmark_files_preserved':57,
    'frozen_manifest_files':39,'native_release_phases':15,'workspace_persistence_phases':4,'actual_cached_RC5_Spyder_launches':2,
    'endurance_active_seconds':endurance['result']['active_seconds'],'endurance_cycles':endurance['result']['cycles'],
    'matched_timing_repeats_per_version':5,'numerical_timing_results_identical':True,'source_count':len(sources),'sources':sources}
(V/'release_gate_rc16_final.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='sources'},indent=2))
