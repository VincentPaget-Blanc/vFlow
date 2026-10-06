"""Safe native/Spyder diagnostic runner. Every test uses this interpreter in a subprocess.
Run: python validation/native_release_check_rc16.py --output /path/to/new-results
The intentionally fatal controls are excluded from this user-facing runner.
"""
import argparse, json, os, platform, shutil, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'validation/native_release_rc16_run');p.add_argument('--cycles',type=int,default=20);args=p.parse_args()
 out=args.output.resolve()
 if out.exists():raise SystemExit('Choose a new output directory so previous results are preserved.')
 out.mkdir(parents=True);rows=[]
 def run(name,argv,expected=0,timeout=300):
  start=time.monotonic();r=subprocess.run([sys.executable,'-X','faulthandler',*map(str,argv)],cwd=ROOT,env=os.environ.copy(),capture_output=True,text=True,timeout=timeout)
  (out/(name+'.stdout.txt')).write_text(r.stdout);(out/(name+'.stderr.txt')).write_text(r.stderr)
  row={'name':name,'returncode':r.returncode,'expected':expected,'passed':r.returncode==expected,'seconds':round(time.monotonic()-start,3)};rows.append(row);print(json.dumps(row),flush=True)
  assert row['passed'],f'{name} failed: {r.stderr}'
  if expected==0:assert not r.stderr,f'{name} stderr: {r.stderr}'
 try:
  for scenario in ('main_gc','kde','audit','scan'):run(scenario,[ROOT/'validation/native_crash_probe_rc16.py','--scenario',scenario],timeout=45)
  data=out/'data';helper=ROOT/'validation/release_edges_rc16.py'
  run('create',[helper,'create','--folder',data]);moved=out/'moved';data.rename(moved)
  run('moved_workspace',[helper,'verify','--folder',moved])
  run('long_session',[helper,'long_session','--folder',moved,'--cycles',args.cycles])
  run('interrupt_before',[helper,'interrupt_before','--folder',moved],83);run('verify_before',[helper,'verify_before','--folder',moved])
  run('interrupt_after',[helper,'interrupt_after','--folder',moved],84);run('verify_after',[helper,'verify_after','--folder',moved])
  recovery=ROOT/'validation/workspace_recovery_probe_rc16.py'
  for kind in ('saved','unsaved'):
   target=out/(kind+'_recovery')
   run(kind+'_crash',[recovery,kind+'_crash','--folder',target],85)
   run(kind+'_recovery',[recovery,kind+'_verify','--folder',target])
 finally:
  (out/'result.json').write_text(json.dumps({'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'results':rows,'passed':len(rows)==15 and all(r['passed'] for r in rows),'unsafe_controls_run':False},indent=2)+'\n')
if __name__=='__main__':main()
