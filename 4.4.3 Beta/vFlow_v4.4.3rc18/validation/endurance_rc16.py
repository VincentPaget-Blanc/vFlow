"""Source-bound 20-minute final candidate exercise with timed stack diagnostics."""
import faulthandler, hashlib, json, os, runpy, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'validation/endurance_rc16_final_main_stack_run'
if folder.exists():raise SystemExit('Preserve prior run; choose a fresh folder.')
sources={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'vflow').rglob('*.py'))}
start=time.monotonic()
create=subprocess.run([sys.executable,'-u',str(ROOT/'validation/release_edges_rc16.py'),'create','--folder',str(folder)],check=True,timeout=120)
faulthandler.enable()
sys.argv=[str(ROOT/'validation/release_edges_rc16.py'),'long_session','--folder',str(folder),'--seconds','1200','--cycles','10000']
try:
    runpy.run_path(sys.argv[0],run_name='__main__')
finally:
    completed=folder/'long_session.json'
    result=json.loads(completed.read_text()) if completed.exists() else None
    same=all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==sha for n,sha in sources.items())
    (ROOT/'validation/endurance_rc16_final_receipt.json').write_text(json.dumps({'source_unchanged':same,'seconds':round(time.monotonic()-start,3),'sources':sources,
        'passed':bool(same and result and result['passed'] and result['active_seconds']>=1200),'result':result},indent=2)+'\n')
