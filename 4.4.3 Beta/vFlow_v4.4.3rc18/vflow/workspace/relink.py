"""Identity-verified relocation shared by sources and gate sessions."""
from pathlib import Path


def scan_candidates(references, folder, recursive=True):
    """One directory walk, bounded fingerprint reads; ambiguity is returned to UI."""
    refs = dict(references)
    by_name = {}
    for key, ref in refs.items(): by_name.setdefault(ref.filename, []).append((key, ref))
    result = {key: [] for key in refs}
    root = Path(folder)
    for p in (root.rglob('*') if recursive else root.iterdir()):
        if p.name not in by_name or not p.is_file(): continue
        for key, ref in by_name[p.name]:
            if ref.matches(p): result[key].append(str(p.resolve()))
    return result


def bulk_remap(references, old_root, new_root):
    """Only verified suffix matches are accepted, never name-only substitutions."""
    found = {}
    for key, ref in references:
        try: suffix = Path(ref.absolute_path).relative_to(old_root)
        except ValueError: continue
        p = Path(new_root) / suffix
        if ref.matches(p): found[key] = str(p.resolve())
    return found
