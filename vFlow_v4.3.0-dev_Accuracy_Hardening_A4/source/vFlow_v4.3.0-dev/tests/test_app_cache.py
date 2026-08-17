from __future__ import annotations

from vflow.app.cache import AnalysisCache


def _filled_cache() -> AnalysisCache:
    cache = AnalysisCache()
    cache.transforms["t"] = 1
    cache.gate_masks["g"] = 2
    cache.scatter["s"] = 3
    return cache


def test_cache_instances_are_independent():
    a = AnalysisCache()
    b = AnalysisCache()
    a.transforms["x"] = 1
    assert b.transforms == {}


def test_clear_all_invalidates_all_three_legacy_cache_classes():
    cache = _filled_cache()
    cache.clear_all()
    assert cache.transforms == {}
    assert cache.gate_masks == {}
    assert cache.scatter == {}


def test_clear_gate_dependent_preserves_transform_cache():
    cache = _filled_cache()
    cache.clear_gate_dependent()
    assert cache.transforms == {"t": 1}
    assert cache.gate_masks == {}
    assert cache.scatter == {}


def test_clear_scatter_is_render_only():
    cache = _filled_cache()
    cache.clear_scatter()
    assert cache.transforms == {"t": 1}
    assert cache.gate_masks == {"g": 2}
    assert cache.scatter == {}


def test_gate_mask_cache_rejects_wrong_length_but_keeps_entry_until_overwritten():
    cache = AnalysisCache()
    key = ('k',)
    payload = ({'IN': [True, False, True]}, ['red'])
    cache.gate_masks[key] = payload
    hit = cache.get_gate_mask(key, expected_length=3)
    assert hit == payload
    assert hit[0] is payload[0]
    assert hit[1] is payload[1]
    assert cache.get_gate_mask(key, expected_length=2) is None
    assert key in cache.gate_masks


def test_gate_mask_cache_empty_regions_match_legacy_cache_miss_behavior():
    cache = AnalysisCache()
    key = ('empty',)
    cache.gate_masks[key] = ({}, [])
    assert cache.get_gate_mask(key, expected_length=0) is None


def test_gate_mask_cache_partial_eviction_preserves_newer_half_and_new_entry():
    cache = AnalysisCache()
    for i in range(4):
        cache.gate_masks[i] = ({'IN': [True]}, [str(i)])
    cache.put_gate_mask(4, ({'IN': [True]}, ['4']), max_entries=4)
    assert list(cache.gate_masks) == [2, 3, 4]
