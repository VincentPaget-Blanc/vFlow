"""Tk-free ownership for vFlow loaded/excluded dataset mappings.

This module is a structural v4.2 refactor seam.  It deliberately preserves the
exact mutable-dict behavior of the frozen v4.1.11 ``FlowApp.loaded_files`` and
``FlowApp.excluded_files`` attributes.  File registration, exclusion moves,
column normalization, generation tokens, and UI row creation remain in their
legacy call sites for now so scientific/application behavior is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DatasetState:
    """Own the active and excluded file mappings without any Tk dependency.

    Values are intentionally untyped beyond ``dict`` at this boundary because
    v4.1.11 stores pandas DataFrames for loaded files and either DataFrames or
    ``None`` placeholders for exclusion-list entries that were never loaded.
    Preserving that representation avoids a semantic migration during the pure
    structural refactor.
    """

    loaded_files: dict = field(default_factory=dict)
    excluded_files: dict = field(default_factory=dict)


    def inherit_excluded_files(self, excluded_files: dict | None) -> None:
        """Replace exclusions with the exact shallow-copy semantics used by child tabs."""
        self.excluded_files = dict(excluded_files or {})

    def commit_loaded_file(self, path: str, data) -> None:
        """Commit a successfully registered file to the active dataset mapping."""
        self.loaded_files[path] = data

    def exclude_loaded_file(self, path: str) -> bool:
        """Move an active file to exclusions, preserving the legacy mapping semantics."""
        if path not in self.loaded_files:
            return False
        self.excluded_files[path] = self.loaded_files.pop(path)
        return True

    def restore_excluded_file(self, path: str):
        """Restore an excluded entry and return ``(found, data)``.

        ``None`` data is the legacy placeholder for a path loaded from an
        exclusion-list CSV but never opened in this session. Such an entry is
        removed from exclusions but is intentionally not added to loaded_files.
        """
        if path not in self.excluded_files:
            return False, None
        data = self.excluded_files.pop(path)
        if data is not None:
            self.loaded_files[path] = data
        return True, data

    def register_unloaded_exclusion(self, path: str) -> bool:
        """Register the legacy ``None`` exclusion placeholder if not already present."""
        if path in self.excluded_files:
            return False
        self.excluded_files[path] = None
        return True

    def clear_files(self) -> None:
        """Clear active and excluded mappings in place, preserving mapping identity."""
        self.loaded_files.clear()
        self.excluded_files.clear()
