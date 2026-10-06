"""Uncaptured child output with timed main-thread stacks and a bounded deadline."""
import argparse, faulthandler, os, runpy, signal, subprocess, sys, time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--interval',type=float,default=60);p.add_argument('--timeout',type=float,default=3600);p.add_argument('--child',action='store_true');p.add_argument('script');p.add_argument('args',nargs=argparse.REMAINDER);a=p.parse_args()
if a.child:
    faulthandler.enable()
    if hasattr(signal,'SIGUSR1'):faulthandler.register(signal.SIGUSR1,all_threads=False)
    else:faulthandler.dump_traceback_later(a.interval,repeat=True)
    sys.argv=[a.script,*a.args];runpy.run_path(a.script,run_name='__main__')
else:
    child=subprocess.Popen([sys.executable,'-u',str(Path(__file__).resolve()),'--interval',str(a.interval),'--child',a.script,*a.args])
    started=time.monotonic();next_dump=started+a.interval
    print('SUPERVISOR START child='+str(child.pid)+' timeout='+str(a.timeout),flush=True)
    try:
        while child.poll() is None:
            now=time.monotonic()
            if now-started>a.timeout:
                print('SUPERVISOR DEADLINE EXCEEDED',flush=True);child.terminate()
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:child.kill()
                break
            if now>=next_dump:
                print('SUPERVISOR TIMED STACK elapsed='+str(round(now-started,1)),flush=True)
                if hasattr(signal,'SIGUSR1'):child.send_signal(signal.SIGUSR1)
                next_dump=now+a.interval
            time.sleep(.25)
    finally:
        if child.poll() is None:child.terminate();child.wait(timeout=10)
    raise SystemExit(child.returncode)
