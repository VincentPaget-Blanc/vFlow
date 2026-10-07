"""Reproduce the ordinary full RC15 suite on an available native display."""
import faulthandler
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
if __name__=='__main__':
    faulthandler.enable()
    raise SystemExit(pytest.main(['-q']))
