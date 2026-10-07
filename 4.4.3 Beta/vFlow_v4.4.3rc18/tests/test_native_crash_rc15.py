"""Run fatal-error regressions in disposable interpreters, never the pytest process."""
import json, os, subprocess, sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
pytestmark=pytest.mark.skipif(sys.platform.startswith('linux') and not os.environ.get('DISPLAY'),reason='Tk display required')
@pytest.mark.parametrize('scenario',['main_gc','kde','audit','scan'])
def test_retired_interpreter_collected_on_gui_thread(scenario):
    result=subprocess.run([sys.executable,'-X','faulthandler',str(ROOT/'validation/native_crash_probe_rc15.py'),'--scenario',scenario],cwd=ROOT,env=os.environ.copy(),capture_output=True,text=True,timeout=45)
    assert result.returncode==0,(result.returncode,result.stdout,result.stderr)
    assert not result.stderr,result.stderr
    final=json.loads(result.stdout.splitlines()[-1])
    assert final['stage']=='passed' and final['finalizer_threads']
    assert all(thread==final['main_thread'] for thread in final['finalizer_threads'])
