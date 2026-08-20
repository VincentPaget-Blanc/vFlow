"""Filesystem identity helpers used to prevent accidental double counting."""

from __future__ import annotations

import os


def normalized_path(path: str) -> str:
    """Return a normalized, symlink-resolved absolute path for display/comparison."""
    return os.path.normcase(os.path.realpath(os.path.abspath(os.path.normpath(str(path)))))


def file_identity_key(path: str):
    """Return a stable physical-file key when possible.

    Device/inode identity catches symlink and hard-link aliases.  If stat is
    unavailable (e.g. a not-yet-created path), fall back to normalized path.
    """
    p = str(path)
    try:
        st = os.stat(p, follow_symlinks=True)
        return ("inode", int(st.st_dev), int(st.st_ino))
    except OSError:
        return ("path", normalized_path(p))
