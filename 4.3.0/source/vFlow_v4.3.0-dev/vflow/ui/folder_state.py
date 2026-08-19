"""Session-level folder state shared by vFlow file dialogs."""

from __future__ import annotations


_last_folder_dir: str = ""


def get_last_folder() -> str:
    """Return the last folder selected in this process."""
    return _last_folder_dir


def set_last_folder(path: str) -> None:
    """Remember the last selected folder for subsequent dialogs."""
    global _last_folder_dir
    _last_folder_dir = path or ""


__all__ = ["get_last_folder", "set_last_folder"]

