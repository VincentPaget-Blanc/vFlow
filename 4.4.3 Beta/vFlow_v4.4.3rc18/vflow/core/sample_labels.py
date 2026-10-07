"""Sample label normalization helpers."""

from __future__ import annotations

import os

SAMPLE_LABEL_TAILS = (
    "_TH-488_Pooled_CytoFile",
    "_TH-488_Pooled",
    "_Pooled_CytoFile",
    "___Results",
    "___CytoFile",
    "__Results",
    "__CytoFile",
    "_Results",
    "_CytoFile",
)


def make_sample_label(source_file_value: str) -> str:
    """Derive a short, readable sample name from a Source_File/path value."""
    stem = os.path.splitext(os.path.basename(str(source_file_value)))[0]
    for tail in SAMPLE_LABEL_TAILS:
        if stem.endswith(tail):
            return stem[: -len(tail)]
    return stem


def shorten_common_prefix_labels(raw_labels: list) -> list:
    """Strip the longest common underscore-delimited prefix when useful."""
    if len(raw_labels) <= 1:
        return list(raw_labels)
    prefix = os.path.commonprefix(raw_labels)
    if "_" in prefix:
        prefix = prefix[: prefix.rfind("_") + 1]
    if len(prefix) > 4:
        shortened = [label[len(prefix) :] or label for label in raw_labels]
        # Avoid collapsing meaningful sample labels to bare replicate numbers,
        # e.g. plate_a_sample_1 / plate_a_sample_2 -> 1 / 2.  Retain the last
        # semantic underscore-delimited token from the shared prefix instead.
        if shortened and all(part.isdigit() for part in shortened):
            semantic = prefix.rstrip("_")
            cut = semantic.rfind("_")
            if cut >= 0:
                safer_prefix = semantic[: cut + 1]
                return [label[len(safer_prefix) :] or label for label in raw_labels]
        return shortened
    return list(raw_labels)



def unique_source_labels(paths: list[str]) -> dict[str, str]:
    """Return auditable labels for source paths without basename collisions.

    Unique basenames remain unchanged.  When the same basename occurs in
    multiple directories, the shortest distinguishing directory suffix is
    prepended (using forward slashes for stable CSV provenance).
    """
    paths = [str(path) for path in paths]
    groups: dict[str, list[str]] = {}
    for path in paths:
        groups.setdefault(os.path.basename(path).casefold(), []).append(path)

    out: dict[str, str] = {}
    for members in groups.values():
        if len(members) == 1:
            out[members[0]] = os.path.basename(members[0])
            continue

        split_dirs = []
        for path in members:
            directory = os.path.normpath(os.path.dirname(path))
            parts = [part for part in directory.split(os.sep) if part]
            split_dirs.append(parts)

        depth = 1
        labels = None
        max_depth = max((len(parts) for parts in split_dirs), default=1)
        while depth <= max_depth + 1:
            trial = []
            for path, parts in zip(members, split_dirs):
                suffix = parts[-depth:] if parts else []
                prefix = "/".join(suffix)
                base = os.path.basename(path)
                trial.append(f"{prefix}/{base}" if prefix else base)
            if len({label.casefold() for label in trial}) == len(trial):
                labels = trial
                break
            depth += 1

        if labels is None:
            labels = [f"source_{i+1}/{os.path.basename(path)}"
                      for i, path in enumerate(members)]
        for path, label in zip(members, labels):
            out[path] = label
    return out
