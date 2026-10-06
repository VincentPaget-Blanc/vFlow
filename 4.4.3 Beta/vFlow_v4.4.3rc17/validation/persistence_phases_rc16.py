import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'validation/workspace_persistence_rc16_final_run'
for phase in ('create','verify','edit_again','verify_final'):
    subprocess.run([sys.executable,'-u',str(ROOT/'validation/supervise_rc16.py'),str(ROOT/'validation/check_workspace_persistence_rc16.py'),phase,str(folder)],check=True,timeout=120)
