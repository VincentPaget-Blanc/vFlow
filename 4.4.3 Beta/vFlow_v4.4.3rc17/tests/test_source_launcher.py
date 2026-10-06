"""Source launch selects its checkout and isolates the IDE's GUI lifetime."""
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_spyder_launch_uses_same_python_and_checkout_and_captures_errors(monkeypatch,tmp_path,capsys):
    namespace=runpy.run_path(str(ROOT/'run_vflow.py'))
    monkeypatch.setitem(sys.modules,'spyder_kernels.console.shell',SimpleNamespace())
    monkeypatch.delenv('VFLOW_IN_PROCESS',raising=False)
    monkeypatch.delenv('VFLOW_LAUNCH_CHILD',raising=False)
    monkeypatch.setenv('PYTHONSTARTUP','old_startup.py')
    monkeypatch.setattr(sys,'path',sys.path.copy())
    import tempfile,subprocess
    real_log=tempfile.NamedTemporaryFile
    monkeypatch.setattr(tempfile,'NamedTemporaryFile',lambda **kw:real_log(dir=tmp_path,**kw))
    calls=[]
    def spawn(command,**options):
        calls.append((command,options))
        options['stdout'].write('startup diagnostic\n')
        return SimpleNamespace(pid=123)
    monkeypatch.setattr(subprocess,'Popen',spawn)
    result=namespace['main']()
    assert result.pid==123 and len(calls)==1
    command,options=calls[0]
    assert command==[sys.executable,'-u',str(ROOT/'run_vflow.py')]
    assert options['cwd']==str(ROOT)
    assert 'PYTHONSTARTUP' not in options['env']
    assert options['env']['VFLOW_LAUNCH_CHILD']=='1'
    assert options['stderr']==subprocess.STDOUT
    log=Path(options['stdout'].name)
    assert 'startup diagnostic' in log.read_text()
    assert str(log) in capsys.readouterr().out


@pytest.mark.parametrize('ide,child',[(False,False),(True,False),(True,True)])
def test_normal_launch_and_explicit_spyder_debugging_run_in_process(monkeypatch,ide,child):
    namespace=runpy.run_path(str(ROOT/'run_vflow.py'))
    monkeypatch.setattr(sys,'path',sys.path.copy())
    if ide:
        monkeypatch.setitem(sys.modules,'spyder_kernels.console.shell',SimpleNamespace())
        if child:
            monkeypatch.delenv('VFLOW_IN_PROCESS',raising=False)
            monkeypatch.setenv('VFLOW_LAUNCH_CHILD','1')
        else:monkeypatch.setenv('VFLOW_IN_PROCESS','1')
    else:
        monkeypatch.delitem(sys.modules,'spyder_kernels.console.shell',raising=False)
    import vflow.main
    calls=[]
    monkeypatch.setattr(vflow.main,'main',lambda:calls.append('app'))
    namespace['main']()
    assert calls==['app'] and sys.path[0]==str(ROOT)
