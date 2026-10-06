"""Cross-platform source-file reveal service.

This module only asks the platform file manager to reveal files/folders. It does
not open, execute, modify, move, rename, or delete scientific data files.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def file_manager_label(*, platform: str | None = None, os_name: str | None = None) -> str:
    platform = sys.platform if platform is None else platform
    os_name = os.name if os_name is None else os_name
    if platform == 'darwin':
        return 'Show in Finder'
    if os_name == 'nt':
        return 'Show in Explorer'
    return 'Show in File Manager'


def reveal_paths(paths, *, platform: str | None = None, os_name: str | None = None) -> bool:
    """Reveal existing paths with Finder/Explorer/Linux file manager.

    Returns ``False`` only when no requested paths exist or the platform action
    cannot be initiated. Exceptions are intentionally contained at this service
    boundary so callers can choose their own UI reporting policy.
    """
    platform = sys.platform if platform is None else platform
    os_name = os.name if os_name is None else os_name
    existing = [os.path.abspath(p) for p in dict.fromkeys(paths)
                if p and os.path.exists(p)]
    if not existing:
        return False
    try:
        devnull = subprocess.DEVNULL
        if platform == 'darwin':
            subprocess.Popen(['open', '-R', *existing], stdout=devnull, stderr=devnull)
        elif os_name == 'nt':
            if len(existing) == 1:
                subprocess.Popen(['explorer', f'/select,{existing[0]}'],
                                 stdout=devnull, stderr=devnull)
            else:
                for folder in dict.fromkeys(os.path.dirname(p) for p in existing):
                    subprocess.Popen(['explorer', folder], stdout=devnull, stderr=devnull)
        else:
            uris = [Path(p).as_uri() for p in existing]
            used_dbus = False
            try:
                array_arg = 'array:string:' + ','.join(uris)
                proc = subprocess.run([
                    'dbus-send', '--session', '--print-reply',
                    '--dest=org.freedesktop.FileManager1',
                    '--type=method_call', '/org/freedesktop/FileManager1',
                    'org.freedesktop.FileManager1.ShowItems', array_arg, 'string:'
                ], stdout=devnull, stderr=devnull, timeout=2, check=False)
                used_dbus = proc.returncode == 0
            except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
                used_dbus = False
            if not used_dbus:
                for folder in dict.fromkeys(os.path.dirname(p) for p in existing):
                    try:
                        subprocess.Popen(['xdg-open', folder], stdout=devnull, stderr=devnull)
                    except FileNotFoundError:
                        subprocess.Popen(['gio', 'open', folder], stdout=devnull, stderr=devnull)
        return True
    except Exception:
        return False
