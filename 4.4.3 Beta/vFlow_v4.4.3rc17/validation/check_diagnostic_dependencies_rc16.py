"""Prove the portable helper needs no pytest/test modules in an app-only environment."""
import importlib.abc,runpy,sys
from pathlib import Path
class NoTests(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path,target=None):
  if fullname.split('.')[0] in ('pytest','tests'):raise ImportError('Test-only import blocked: '+fullname)
sys.meta_path.insert(0,NoTests())
ROOT=Path(__file__).resolve().parents[1]
sys.argv=[str(ROOT/'validation/release_edges_rc16.py'),'verify_after','--folder',str(ROOT/'validation/native_release_rc16_final_v2/moved')]
runpy.run_path(sys.argv[0],run_name='__main__')
print('PASS standalone helper: pytest/tests imports blocked')
