"""One ordinary pytest shard; each process receives a separate native display."""
import faulthandler,hashlib,json,os,platform,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pytest
index=int(sys.argv[1]);out=ROOT/'validation'/f'full_suite_rc18_shard_{index}'
plan=json.loads((ROOT/'validation/rc18_shard_plan.json').read_text());files=plan['groups'][index]
sources={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'vflow').rglob('*.py'))}
faulthandler.enable();start=time.monotonic()
code=pytest.main(['-s','-vv','-o','faulthandler_timeout=0','--durations=10','--junitxml='+str(out.with_suffix('.xml')),*files])
unchanged=all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==sha for n,sha in sources.items())
out.with_suffix('.json').write_text(json.dumps({'exitcode':code,'source_unchanged':unchanged,'seconds':time.monotonic()-start,'python':sys.version,'platform':platform.platform(),'display':os.environ.get('DISPLAY'),'sources':sources,'test_files':files},indent=2)+'\n')
raise SystemExit(code if unchanged else 99)
