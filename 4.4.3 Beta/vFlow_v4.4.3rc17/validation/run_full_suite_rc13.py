"""Full native suite with retired Tk roots finalized on the GUI thread.

The suite creates hundreds of independent Tk interpreters. Collect unreachable
objects at GUI test boundaries so numerical worker threads do not inherit garbage
from prior interpreters. No application behavior or test assertions are changed.
"""
import gc
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
class NativeCleanup:
    previous_gui=False
    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_setup(self,item):
        gui='experiment' in item.fixturenames or 'gui' in item.path.stem
        if gui or self.previous_gui:gc.collect()
        self.previous_gui=gui
if __name__=='__main__':
    raise SystemExit(pytest.main(['-q'],plugins=[NativeCleanup()]))
