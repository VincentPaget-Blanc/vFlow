#!/usr/bin/env python3
"""Launch this source checkout, including from Spyder's shared kernel."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile


def main():
    source = Path(__file__).resolve().parent
    # Keep the selected checkout ahead of another installed vFlow version.
    sys.path.insert(0, str(source))
    in_spyder = 'spyder_kernels.console.shell' in sys.modules
    if (in_spyder and os.environ.get('VFLOW_IN_PROCESS') != '1'
            and os.environ.get('VFLOW_LAUNCH_CHILD') != '1'):
        # Tk/Matplotlib belong to the app's interpreter. A shared IDE kernel may
        # already own another GUI loop or have imported a different RC's code.
        env = os.environ.copy()
        env.pop('PYTHONSTARTUP', None)
        # Some IDE environments import their hooks through sitecustomize in
        # every interpreter. Never turn a child launch into another child.
        env['VFLOW_LAUNCH_CHILD'] = '1'
        with tempfile.NamedTemporaryFile(mode='w', prefix='vflow-startup-', suffix='.log',
                                         encoding='utf-8', delete=False) as log:
            log.write(f'vFlow source: {source}\nPython: {sys.executable}\n')
            log.flush()
            process = subprocess.Popen([sys.executable, '-u', str(source/'run_vflow.py')],
                cwd=str(source), env=env, stdout=log, stderr=subprocess.STDOUT)
            print(f'vFlow started in a separate process (PID {process.pid}).')
            print(f'Startup output: {log.name}')
            return process
    from vflow.main import main as run_app
    return run_app()


if __name__ == '__main__':
    main()
