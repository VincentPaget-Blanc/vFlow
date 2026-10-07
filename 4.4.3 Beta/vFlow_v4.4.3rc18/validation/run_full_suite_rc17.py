"""Ordinary pytest, uncaptured output, externally timed stacks, source-bound receipt."""
import argparse, faulthandler, hashlib, json, os, platform, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pytest
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--receipt',type=Path,default=ROOT/'validation/full_suite_rc17_receipt.json');args=p.parse_args()
    sources={q.relative_to(ROOT).as_posix():hashlib.sha256(q.read_bytes()).hexdigest() for q in sorted((ROOT/'vflow').rglob('*.py'))}
    faulthandler.enable();start=time.monotonic()
    print('SOURCE SHA256 '+hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest(),flush=True)
    code=pytest.main(['-s','-vv','-o','faulthandler_timeout=0','--durations=20','--junitxml='+str(args.receipt.with_suffix('.xml'))])
    unchanged=all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==sha for n,sha in sources.items())
    args.receipt.write_text(json.dumps({'exitcode':code,'source_unchanged':unchanged,'seconds':round(time.monotonic()-start,3),
        'python':sys.version,'platform':platform.platform(),'display':os.environ.get('DISPLAY'),
        'threads':{k:os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')},'sources':sources},indent=2)+'\n')
    raise SystemExit(code if unchanged else 99)
