"""Pure helpers for explicit vFlow channel-name reconciliation.

The helpers in this module only discover/rank label structure. They never alter
DataFrames or numeric event values and never auto-apply fuzzy matches.
"""

from __future__ import annotations

import difflib
import re


def axis_name_compact(name: str) -> str:
    """Conservative comparison key used only for suggesting aliases."""
    text = str(name).strip().casefold()
    return ''.join(ch for ch in text if ch.isalnum())


def axis_name_similarity(a: str, b: str) -> float:
    """Return a [0, 1] advisory similarity score; never an auto-rename rule."""
    sa = str(a).strip().casefold()
    sb = str(b).strip().casefold()
    if sa == sb:
        return 1.0
    ca = axis_name_compact(sa)
    cb = axis_name_compact(sb)
    if ca and ca == cb:
        return 0.995
    r1 = difflib.SequenceMatcher(None, sa, sb).ratio()
    r2 = difflib.SequenceMatcher(None, ca, cb).ratio() if ca and cb else 0.0
    return max(r1, r2)


def discover_channel_schema(columns):
    """Return ``{channel: {exact templates}}`` for a sequence of labels.

    Templates contain one literal ``{channel}`` slot. Coordinate labels are the
    strongest source of full channel names, and repeated multi-token suffixes
    are preserved so e.g. ``VGLUT1_Venus`` is not reduced to ``Venus``.
    """
    labels = [str(c) for c in columns]
    coord_channels = set()
    coord_rows = {}
    coord_re = re.compile(r'^(X|Y)_(.+)_microns$')
    for label in labels:
        m = coord_re.match(label)
        if m and m.group(2):
            ch = m.group(2)
            coord_channels.add(ch)
            coord_rows[label] = (ch, f'{m.group(1)}_{{channel}}_microns')

    ignored = {
        'microns', 'micron', 'um', 'um2', 'px', 'pixel', 'pixels',
        'file', 'filename', 'path', 'index', 'id', 'label', 'source'
    }
    suffix_support = {}
    for label in labels:
        if label in coord_rows or '_' not in label or label.endswith('_'):
            continue
        positions = [i for i, ch in enumerate(label) if ch == '_']
        for pos in positions:
            token = label[pos + 1:]
            if not token or token.casefold() in ignored:
                continue
            suffix_support.setdefault(token, set()).add(label)

    measurement_leads = {
        'intensity', 'mean', 'median', 'avg', 'average', 'sum', 'total',
        'area', 'width', 'height', 'perimeter', 'background', 'bkgd',
        'corr', 'corrected', 'max', 'min', 'std', 'stdev', 'cv',
        'centroid', 'position', 'coordinate', 'coords', 'signal'
    }
    repeated = {
        token for token, rows in suffix_support.items()
        if len(rows) >= 2 and (
            '_' not in token
            or token.split('_', 1)[0].casefold() not in measurement_leads)
    }
    repeated_pruned = set(repeated)
    for token in repeated:
        support_n = len(suffix_support[token])
        if any(other != token and other.endswith('_' + token)
               and len(suffix_support[other]) >= support_n
               for other in repeated):
            repeated_pruned.discard(token)

    fallback = set(repeated_pruned)
    for label in labels:
        if label in coord_rows or '_' not in label or label.endswith('_'):
            continue
        if any(label.endswith('_' + token) for token in repeated_pruned):
            continue
        token = label.rsplit('_', 1)[-1]
        if not token or token.casefold() in ignored:
            continue
        if any(ch != token and ch.endswith('_' + token) for ch in coord_channels):
            continue
        fallback.add(token)

    candidates = sorted(coord_channels | fallback,
                        key=lambda x: (-len(x), x.casefold()))
    result = {}
    for label in labels:
        if label in coord_rows:
            ch, template = coord_rows[label]
            result.setdefault(ch, set()).add(template)
            continue
        for ch in candidates:
            suffix = '_' + ch
            if label.endswith(suffix) and len(label) > len(suffix):
                prefix = label[:-len(ch)]
                result.setdefault(ch, set()).add(prefix + '{channel}')
                break
    return result


def replace_channel_in_template(template: str, channel: str) -> str:
    return str(template).replace('{channel}', str(channel))


def extract_channel_from_template(label: str, template: str):
    """Extract the literal substring occupying the one ``{channel}`` slot."""
    marker = '{channel}'
    template = str(template)
    label = str(label)
    if template.count(marker) != 1:
        return None
    prefix, suffix = template.split(marker, 1)
    if not label.startswith(prefix):
        return None
    if suffix and not label.endswith(suffix):
        return None
    start = len(prefix)
    end = len(label) - len(suffix) if suffix else len(label)
    if end <= start:
        return None
    channel = label[start:end]
    return channel if channel else None


def channel_relation(canonical: str, candidate: str) -> str:
    """Human-readable relation used only to explain/rank suggestions."""
    a = str(canonical).strip()
    b = str(candidate).strip()
    if not a or not b:
        return 'manual'
    if a.casefold() == b.casefold():
        return 'case only'
    ca = axis_name_compact(a)
    cb = axis_name_compact(b)
    if ca and ca == cb:
        return 'separator only'
    if ca and cb and (ca.endswith(cb) or cb.endswith(ca)):
        return 'partial/suffix'
    return 'manual'


def summarise_names(names, limit=4):
    names = [str(x) for x in names]
    if not names:
        return ''
    if len(names) <= limit:
        return ', '.join(names)
    return ', '.join(names[:limit]) + f' … +{len(names)-limit}'
