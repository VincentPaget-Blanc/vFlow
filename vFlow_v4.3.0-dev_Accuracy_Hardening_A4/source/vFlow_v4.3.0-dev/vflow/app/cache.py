"""Central ownership for vFlow analysis/render caches.

The original cache extraction preserves the exact legacy scientific cache
payloads and key formats. Architecture / Performance 02 adds one independent,
render-only density payload cache; Architecture / Performance 03 adds an
independent marginal-histogram payload cache; Architecture / Performance 05
adds an independent Contour numerical-render payload cache. Architecture /
Performance 06 stores gate-region masks in packed-bit form internally and
bounds gate-mask/scatter caches by retained payload bytes as well as a generous
entry-count safeguard. Public scientific callers still receive ordinary boolean
region arrays and unchanged colour payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import itertools

import numpy as np

from vflow.config.constants import (
    _GMC_MAX_BYTES,
    _SCATTER_CACHE_MAX,
    _SCATTER_CACHE_MAX_BYTES,
)


@dataclass(frozen=True)
class _PackedGateMaskPayload:
    """Private compact representation of one cached gate evaluation."""

    length: int
    regions: tuple[tuple[object, np.ndarray], ...]
    colors: object


@dataclass(frozen=True)
class CompactScatterPayload:
    """Compact retained representation of one gated-scatter draw payload.

    ``indices`` address the original X/Y arrays supplied to ``_plot_gated_multi``;
    ``color_codes`` index the exact float32 RGBA rows in ``palette``.  The full
    coordinate and RGBA arrays therefore exist only transiently while drawing.
    """

    indices: np.ndarray
    color_codes: np.ndarray
    palette: np.ndarray

    def materialize(self, x_values, y_values):
        x = np.asarray(x_values)
        y = np.asarray(y_values)
        return x[self.indices], y[self.indices], self.palette[self.color_codes]


def _payload_nbytes(payload) -> int:
    """Best-effort retained numeric byte size for cache-budget accounting.

    The gate/scatter caches are dominated by NumPy arrays.  Container/object
    overhead is deliberately not estimated: budgets are conservative numeric
    payload limits, while entry-count safeguards separately cap object growth.
    Unknown legacy/test payloads therefore contribute zero bytes rather than
    breaking compatibility with direct diagnostic cache injection.
    """
    if isinstance(payload, np.ndarray):
        return int(payload.nbytes)
    if isinstance(payload, _PackedGateMaskPayload):
        return sum(int(bits.nbytes) for _, bits in payload.regions)
    if isinstance(payload, CompactScatterPayload):
        return int(payload.indices.nbytes + payload.color_codes.nbytes + payload.palette.nbytes)
    if isinstance(payload, dict):
        return sum(_payload_nbytes(v) for v in payload.values())
    if isinstance(payload, (tuple, list)):
        return sum(_payload_nbytes(v) for v in payload)
    return 0


def _cache_numeric_nbytes(cache: dict) -> int:
    return sum(_payload_nbytes(value) for value in cache.values())


def _pack_gate_mask_result(result) -> _PackedGateMaskPayload | None:
    regions, colors = result
    if not regions:
        return None
    packed_regions = []
    length = None
    for name, mask in regions.items():
        arr = np.asarray(mask, dtype=np.bool_)
        if arr.ndim != 1:
            raise ValueError("Cached gate masks must be one-dimensional.")
        if length is None:
            length = len(arr)
        elif len(arr) != length:
            raise ValueError("Cached gate-region masks must have equal length.")
        bits = np.packbits(arr, bitorder="little")
        bits.flags.writeable = False
        packed_regions.append((name, bits))
    return _PackedGateMaskPayload(
        length=int(length or 0),
        regions=tuple(packed_regions),
        colors=colors,
    )


def _unpack_gate_mask_payload(payload: _PackedGateMaskPayload):
    regions = {}
    for name, bits in payload.regions:
        # unpackbits returns uint8 zeros/ones.  Viewing the one-byte values as
        # bool preserves exact mask semantics without another full-array copy.
        mask = np.unpackbits(
            bits, count=payload.length, bitorder="little"
        ).view(np.bool_)
        regions[name] = mask
    return regions, payload.colors


def _evict_oldest_until_within_budget(
    cache: dict,
    *,
    incoming_key,
    incoming_payload,
    max_entries: int,
    max_bytes: int,
) -> bool:
    """Make room for ``incoming_payload`` using insertion-order eviction.

    Returns ``False`` when a single payload itself exceeds the byte budget; in
    that case it is intentionally left uncached.  Existing-key replacement does
    not count as a new entry and its previous bytes are excluded from the
    projected total.
    """
    incoming_bytes = _payload_nbytes(incoming_payload)
    if incoming_bytes > max_bytes:
        cache.pop(incoming_key, None)
        return False

    replacing = incoming_key in cache
    current_bytes = _cache_numeric_nbytes(cache)
    if replacing:
        current_bytes -= _payload_nbytes(cache[incoming_key])

    # Count is a secondary object-growth safeguard.  Preserve the historical
    # half-cache eviction contract when callers explicitly provide a tiny entry
    # cap (used by compatibility tests/fixtures); production AP06's large cap is
    # normally governed by bytes instead.
    if not replacing and len(cache) >= max_entries:
        evict_count = max(1, max_entries // 2)
        for old_key in list(itertools.islice(cache, evict_count)):
            current_bytes -= _payload_nbytes(cache[old_key])
            del cache[old_key]

    while cache and current_bytes + incoming_bytes > max_bytes:
        old_key = next(iter(cache))
        if old_key == incoming_key and replacing:
            # The existing value is already excluded from current_bytes; leave
            # it in place until the final overwrite while evicting other keys.
            keys = iter(cache)
            next(keys, None)
            old_key = next(keys, None)
            if old_key is None:
                break
        current_bytes -= _payload_nbytes(cache[old_key])
        del cache[old_key]

    return current_bytes + incoming_bytes <= max_bytes


@dataclass
class AnalysisCache:
    """Own scientific caches plus bounded render-only derived payload caches."""

    transforms: dict = field(default_factory=dict)
    gate_masks: dict = field(default_factory=dict)
    scatter: dict = field(default_factory=dict)
    density: dict = field(default_factory=dict)
    marginals: dict = field(default_factory=dict)
    contours: dict = field(default_factory=dict)
    # One transient uncompressed hit preserves the historical immediate-cache
    # object-identity contract without retaining full boolean arrays for every
    # durable gate-mask entry.
    _gate_mask_hot_key: object = field(default=None, init=False, repr=False)
    _gate_mask_hot_result: object = field(default=None, init=False, repr=False)

    def _clear_gate_mask_hot(self) -> None:
        self._gate_mask_hot_key = None
        self._gate_mask_hot_result = None

    def clear_all(self) -> None:
        """Invalidate scientific plus Density/Marginal/Contour render payloads together."""
        self.transforms.clear()
        self.gate_masks.clear()
        self._clear_gate_mask_hot()
        self.scatter.clear()
        self.density.clear()
        self.marginals.clear()
        self.contours.clear()

    def clear_gate_dependent(self) -> None:
        """Invalidate gate-mask and scatter payloads after gate geometry changes."""
        self.gate_masks.clear()
        self._clear_gate_mask_hot()
        self.scatter.clear()

    def clear_scatter(self) -> None:
        """Invalidate only render/scatter payloads."""
        self.scatter.clear()

    def gate_mask_numeric_nbytes(self) -> int:
        """Return retained NumPy bytes in the gate-mask cache."""
        return _cache_numeric_nbytes(self.gate_masks)

    def scatter_numeric_nbytes(self) -> int:
        """Return retained NumPy bytes in the gated-scatter cache."""
        return _cache_numeric_nbytes(self.scatter)

    def get_density_render(self, key):
        """Return a cached density-display payload, or ``None`` on miss."""
        return self.density.get(key)

    def put_density_render(
        self, key, payload, *, max_entries: int = 128, evict_count: int = 64
    ) -> None:
        """Store one bounded, style-independent density display payload."""
        if len(self.density) >= max_entries:
            for old_key in list(itertools.islice(self.density, evict_count)):
                del self.density[old_key]
        self.density[key] = payload

    def get_marginal_render(self, key):
        """Return a cached marginal-histogram payload, or ``None`` on miss."""
        return self.marginals.get(key)

    def put_marginal_render(
        self, key, payload, *, max_entries: int = 128, evict_count: int = 64
    ) -> None:
        """Store one bounded, style-independent marginal histogram payload."""
        if len(self.marginals) >= max_entries:
            for old_key in list(itertools.islice(self.marginals, evict_count)):
                del self.marginals[old_key]
        self.marginals[key] = payload

    def get_contour_render(self, key):
        """Return a cached Contour numerical render payload, or ``None`` on miss."""
        return self.contours.get(key)

    def put_contour_render(
        self, key, payload, *, max_entries: int = 128, evict_count: int = 64
    ) -> None:
        """Store one bounded, style-independent Contour render payload."""
        if key not in self.contours and len(self.contours) >= max_entries:
            for old_key in list(itertools.islice(self.contours, evict_count)):
                del self.contours[old_key]
        self.contours[key] = payload

    def get_gate_mask(self, key, *, expected_length: int):
        """Return a cached gate-mask payload only when mask length still matches.

        AP06 transparently unpacks private bit-packed entries.  Direct legacy or
        diagnostic payloads injected into ``gate_masks`` remain accepted with
        the historical stale-length and empty-region behavior.
        """
        if key not in self.gate_masks:
            return None
        payload = self.gate_masks[key]
        if isinstance(payload, _PackedGateMaskPayload):
            if payload.length != expected_length or not payload.regions:
                return None
            if self._gate_mask_hot_key == key and self._gate_mask_hot_result is not None:
                return (self._gate_mask_hot_result[0], self._gate_mask_hot_result[1])
            result = _unpack_gate_mask_payload(payload)
            self._gate_mask_hot_key = key
            self._gate_mask_hot_result = result
            return result

        cached_regions, cached_colors = payload
        if cached_regions:
            first_mask = next(iter(cached_regions.values()))
            if len(first_mask) == expected_length:
                return cached_regions, cached_colors
        return None

    def put_gate_mask(
        self,
        key,
        result,
        *,
        max_entries: int,
        max_bytes: int = _GMC_MAX_BYTES,
    ) -> None:
        """Pack and store a gate-mask payload under byte + entry safeguards."""
        packed = _pack_gate_mask_result(result)
        if packed is None:
            return
        if not _evict_oldest_until_within_budget(
            self.gate_masks,
            incoming_key=key,
            incoming_payload=packed,
            max_entries=max_entries,
            max_bytes=max_bytes,
        ):
            return
        self.gate_masks[key] = packed
        self._gate_mask_hot_key = key
        self._gate_mask_hot_result = result

    def get_scatter_render(self, key):
        """Return one cached gated-scatter render payload, or ``None``."""
        return self.scatter.get(key)

    def put_scatter_render(
        self,
        key,
        payload,
        *,
        max_entries: int = _SCATTER_CACHE_MAX,
        max_bytes: int = _SCATTER_CACHE_MAX_BYTES,
    ) -> None:
        """Store a gated-scatter payload under byte + entry safeguards."""
        if not _evict_oldest_until_within_budget(
            self.scatter,
            incoming_key=key,
            incoming_payload=payload,
            max_entries=max_entries,
            max_bytes=max_bytes,
        ):
            return
        self.scatter[key] = payload
