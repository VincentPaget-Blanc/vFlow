"""Byte revisions and nonblocking process locks for workspace commits."""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path

def byte_revision(data):
    return hashlib.sha256(data).hexdigest()

def file_revision(path):
    digest=hashlib.sha256()
    try:
        with open(path,'rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    except FileNotFoundError:return None
    return digest.hexdigest()

def check_revision(path, expected):
    if file_revision(path)!=expected:
        raise ValueError('The saved workspace changed or was removed outside this session. Your edits remain open. Use Save As to keep a separate copy, or reopen the current file.')

@contextmanager
def workspace_lock(path):
    # Keep the inode: removing a lock file lets another process lock a different
    # inode while the original holder is still committing.
    p=Path(path).resolve();p.parent.mkdir(parents=True,exist_ok=True)
    with p.with_name('.'+p.name+'.lock').open('a+b') as stream:
        locked=False
        try:
            if os.name=='nt':
                import msvcrt
                stream.seek(0,2)
                if stream.tell()==0:stream.write(b'0');stream.flush()
                stream.seek(0)
                try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
                except OSError as exc:raise ValueError('Another instance is saving this workspace. Your edits remain open; retry or use Save As.') from exc
            else:
                import fcntl
                try:fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                except OSError as exc:raise ValueError('Another instance is saving this workspace. Your edits remain open; retry or use Save As.') from exc
            locked=True
            yield
        finally:
            if locked:
                if os.name=='nt':
                    stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
                else:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
