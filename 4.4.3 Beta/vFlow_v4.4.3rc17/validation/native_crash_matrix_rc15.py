"""Explicit destructive-control diagnostics, strictly confined to subprocesses."""
import argparse, hashlib, json, os, subprocess, sys, time, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--allow-unsafe-controls',action='store_true');args=p.parse_args()
if not args.allow_unsafe_controls:raise SystemExit('These controls deliberately crash disposable processes. Use --allow-unsafe-controls explicitly.')
roots={'rc13':ROOT.parent/'vFlow_v4.4.3rc13_candidate','rc14':ROOT.parent/'vFlow_v4.4.3rc14_candidate','rc15':ROOT}
archives={'rc13':ROOT.parent/'vFlow_v4.4.3rc13_Followup_Bug_Hunt.zip','rc14':ROOT.parent/'vFlow_v4.4.3rc14_Final_Bug_Hunt.zip'}
verified={}
for version,archive in archives.items():
 with zipfile.ZipFile(archive) as z:
  prefix=f'vFlow_v4.4.3{version}/';names=[n for n in z.namelist() if n.startswith(prefix+'vflow/') and n.endswith('.py')]
  assert len(names)==122 and all(z.read(n)==(roots[version]/n[len(prefix):]).read_bytes() for n in names)
  verified[version]={'identical_package_sources':122,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
rows=[]
for version,root in roots.items():
 for scenario in ('kde','audit','scan'):
  for repeat in range(3):
   start=time.monotonic();r=subprocess.run([sys.executable,'-X','faulthandler',str(ROOT/'validation/native_crash_probe_rc15.py'),'--package-root',str(root),'--scenario',scenario],cwd=ROOT,env=os.environ.copy(),capture_output=True,text=True,timeout=45)
   passed=(r.returncode==0 and not r.stderr) if version=='rc15' else r.returncode<0 and 'Tcl_AsyncDelete: async handler deleted by the wrong thread' in r.stderr
   row=dict(version=version,scenario=scenario,repeat=repeat+1,returncode=r.returncode,signal=-r.returncode if r.returncode<0 else None,expected_observation=passed,stdout=r.stdout,stderr=r.stderr,seconds=round(time.monotonic()-start,3));rows.append(row)
   print(json.dumps({k:v for k,v in row.items() if k not in ('stdout','stderr')}),flush=True)
for scenario in ('worker_gc','main_gc'):
 for repeat in range(3):
  r=subprocess.run([sys.executable,'-X','faulthandler',str(ROOT/'validation/native_crash_probe_rc15.py'),'--scenario',scenario],cwd=ROOT,env=os.environ.copy(),capture_output=True,text=True,timeout=45)
  passed=(r.returncode<0 and 'Tcl_AsyncDelete' in r.stderr) if scenario=='worker_gc' else r.returncode==0 and not r.stderr
  rows.append(dict(version='control',scenario=scenario,repeat=repeat+1,returncode=r.returncode,expected_observation=passed,stdout=r.stdout,stderr=r.stderr))
result=dict(python=sys.version,baseline_sources=verified,total=len(rows),all_expected=len(rows)==33 and all(r['expected_observation'] for r in rows),rows=rows,historical_sigsegv_identically_reproduced=False)
(ROOT/'validation/native_crash_matrix_rc15.json').write_text(json.dumps(result,indent=2)+'\n')
assert result['all_expected'];print('PASS 33 isolated crash/control comparisons; old SIGSEGV remains unproved.')
