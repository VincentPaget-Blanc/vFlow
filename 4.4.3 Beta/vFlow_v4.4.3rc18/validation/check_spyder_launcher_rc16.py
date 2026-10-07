"""Exercise the real Spyder runner and real isolated app subprocess twice."""
from pathlib import Path
import os,subprocess,sys,tempfile,json
ROOT=Path(__file__).resolve().parents[1]
from spyder_kernels.console.shell import SpyderShell
os.environ['SPY_UMR_ENABLED']='false'
shell=SpyderShell.instance()
# Seed the kernel with the last known working checkout when available.
import argparse
p=argparse.ArgumentParser();p.add_argument('--cached-root',type=Path,required=True);old=p.parse_args().cached_root.resolve()
assert (old/'vflow/__init__.py').is_file(), 'Original RC5 package is required'
if (old/'vflow/__init__.py').exists():
    sys.path.insert(0,str(old))
    import vflow
    assert vflow.__version__=='4.4.3rc5'
    import importlib
    cached_app=importlib.import_module('vflow.legacy.vflow_app')
    assert Path(cached_app.__file__).resolve().is_relative_to(old)
    assert cached_app.FlowApp
    print('Kernel cached RC5 package and legacy application module; child must load RC16.')
created=[]
original=subprocess.Popen

def launch(*args,**kwargs):
    process=original(*args,**kwargs)
    created.append((process,Path(kwargs['stdout'].name)))
    return process
subprocess.Popen=launch
with tempfile.TemporaryDirectory(prefix='vflow-launch-probe-') as temp:
    shim=Path(temp)/'sitecustomize.py'
    shim.write_text('from validation import startup_probe_rc16\n')
    prior=os.environ.get('PYTHONPATH','')
    os.environ['PYTHONPATH']=str(shim.parent)+os.pathsep+str(ROOT)+os.pathsep+prior
    os.environ.pop('VFLOW_IN_PROCESS',None)
    for attempt in range(2):
        probe=Path(temp)/f'result_{attempt}.json'
        os.environ['VFLOW_STARTUP_PROBE_FILE']=str(probe)
        before=len(created)
        shell.run_line_magic('runfile',str(ROOT/'run_vflow.py')+' --wdir '+str(ROOT))
        assert len(created)==before+1,'Spyder did not launch an isolated app'
        process,log=created[-1]
        assert process.wait(timeout=35)==0,log.read_text()
        output=log.read_text()
        assert probe.exists(),output
        checked=json.loads(probe.read_text())
        assert checked['stage']=='closed' and not checked['errors'],checked
        assert len(checked['observations'])==1,checked
        row=checked['observations'][0]
        assert row['mapped'] and row['events']==48000 and row['version']=='4.4.3rc16',row
        assert 'ERROR ' not in output and 'Traceback' not in output,output
        print(f'PASS isolated Spyder launch {attempt+1}: '+json.dumps(checked['observations']))
