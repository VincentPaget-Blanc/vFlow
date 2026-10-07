from __future__ import annotations

import numpy as np

from vflow.app.cache import AnalysisCache


def _regions(n: int, *, offset: int = 0):
    base = (np.arange(n) + offset) % 3 == 0
    return {"IN": base, "OUT": ~base}, ["#f00", "#0f0"]


def test_gate_mask_storage_is_bit_packed_and_round_trips_exactly():
    cache = AnalysisCache()
    n = 1_000_003
    result = _regions(n)
    cache.put_gate_mask("k", result, max_entries=4096)

    stored = cache.gate_masks["k"]
    assert type(stored).__name__ == "_PackedGateMaskPayload"
    expected_packed_bytes = 2 * ((n + 7) // 8)
    assert cache.gate_mask_numeric_nbytes() == expected_packed_bytes
    assert expected_packed_bytes * 7 < 2 * n

    # First immediate hit preserves the historical region-dict identity contract.
    immediate = cache.get_gate_mask("k", expected_length=n)
    assert immediate is not result
    assert immediate[0] is result[0]

    # After another key displaces the one-entry hot payload, the durable packed
    # form reconstructs masks with exactly the same values/dtypes/order.
    cache.put_gate_mask("other", _regions(9, offset=1), max_entries=4096)
    hit = cache.get_gate_mask("k", expected_length=n)
    assert list(hit[0]) == ["IN", "OUT"]
    assert hit[0]["IN"].dtype == np.bool_
    assert hit[0]["OUT"].dtype == np.bool_
    assert np.array_equal(hit[0]["IN"], result[0]["IN"])
    assert np.array_equal(hit[0]["OUT"], result[0]["OUT"])
    assert hit[1] == result[1]


def test_packed_gate_mask_stale_length_guard_remains_fail_closed():
    cache = AnalysisCache()
    cache.put_gate_mask("k", _regions(101), max_entries=4096)
    assert cache.get_gate_mask("k", expected_length=101) is not None
    assert cache.get_gate_mask("k", expected_length=100) is None
    assert "k" in cache.gate_masks


def test_gate_mask_byte_budget_evicts_oldest_until_new_payload_fits():
    cache = AnalysisCache()
    # 80 booleans -> 10 packed bytes per region -> 20 bytes per entry.
    for key in range(3):
        cache.put_gate_mask(
            key, _regions(80, offset=key), max_entries=100, max_bytes=45
        )
    assert list(cache.gate_masks) == [1, 2]
    assert cache.gate_mask_numeric_nbytes() == 40


def test_gate_mask_single_payload_larger_than_budget_is_not_cached():
    cache = AnalysisCache()
    cache.put_gate_mask("too-big", _regions(800), max_entries=100, max_bytes=10)
    assert cache.gate_masks == {}
    assert cache.get_gate_mask("too-big", expected_length=800) is None


def test_gate_mask_legacy_small_entry_cap_keeps_half_eviction_contract():
    cache = AnalysisCache()
    for key in range(4):
        cache.put_gate_mask(key, _regions(8, offset=key), max_entries=4, max_bytes=10_000)
    cache.put_gate_mask(4, _regions(8), max_entries=4, max_bytes=10_000)
    assert list(cache.gate_masks) == [2, 3, 4]


def _scatter_payload(n: int):
    x = np.arange(n, dtype=np.float64)
    y = x + 0.5
    rgba = np.zeros((n, 4), dtype=np.float32)
    return x, y, rgba


def test_scatter_cache_is_bounded_by_numeric_bytes_and_keeps_newest_working_set():
    cache = AnalysisCache()
    # Each n=2 payload = 16 + 16 + 32 = 64 numeric bytes.
    for key in range(3):
        cache.put_scatter_render(key, _scatter_payload(2), max_entries=100, max_bytes=130)
    assert list(cache.scatter) == [1, 2]
    assert cache.scatter_numeric_nbytes() == 128
    assert cache.get_scatter_render(2) is cache.scatter[2]


def test_scatter_payload_larger_than_budget_is_used_uncached_not_retained():
    cache = AnalysisCache()
    cache.put_scatter_render("too-big", _scatter_payload(100), max_entries=100, max_bytes=64)
    assert cache.scatter == {}


def test_scatter_existing_key_replacement_does_not_evict_unnecessarily():
    cache = AnalysisCache()
    cache.put_scatter_render("a", _scatter_payload(1), max_entries=10, max_bytes=200)
    cache.put_scatter_render("b", _scatter_payload(1), max_entries=10, max_bytes=200)
    cache.put_scatter_render("b", _scatter_payload(2), max_entries=10, max_bytes=200)
    assert list(cache.scatter) == ["a", "b"]
    assert cache.scatter_numeric_nbytes() == 32 + 64


def test_compact_scatter_payload_materializes_exact_coordinates_and_rgba():
    from vflow.app.cache import CompactScatterPayload

    x = np.array([10.0, 20.0, 30.0, 40.0], dtype=np.float64)
    y = np.array([-1.0, -2.0, -3.0, -4.0], dtype=np.float64)
    idx = np.array([3, 1, 2], dtype=np.uint32)
    palette = np.array(
        [[0.1, 0.2, 0.3, 0.4], [0.9, 0.8, 0.7, 0.6]], dtype=np.float32
    )
    codes = np.array([1, 0, 1], dtype=np.uint8)
    payload = CompactScatterPayload(idx, codes, palette)
    xv, yv, rgba = payload.materialize(x, y)
    assert np.array_equal(xv, x[idx])
    assert np.array_equal(yv, y[idx])
    assert np.array_equal(rgba, palette[codes])
    assert xv.dtype == np.float64 and yv.dtype == np.float64
    assert rgba.dtype == np.float32


def test_compact_scatter_payload_is_accounted_at_retained_representation_size():
    from vflow.app.cache import CompactScatterPayload

    n = 1_000_000
    payload = CompactScatterPayload(
        np.arange(n, dtype=np.uint32),
        np.zeros(n, dtype=np.uint8),
        np.array([[1.0, 0.0, 0.0, 0.5]], dtype=np.float32),
    )
    cache = AnalysisCache()
    cache.put_scatter_render("k", payload, max_entries=100, max_bytes=10_000_000)
    assert cache.scatter_numeric_nbytes() == 5_000_016
    # Historical retained X/Y/RGBA payload would require 32 bytes/event.
    assert cache.scatter_numeric_nbytes() * 6 < 32_000_000


def test_plot_gated_multi_warm_compact_cache_replays_exact_cold_scatter_payload():
    from types import SimpleNamespace
    from vflow.legacy.vflow_app import FlowApp

    app = FlowApp.__new__(FlowApp)
    app.__dict__["_analysis_cache"] = AnalysisCache()
    app.__dict__["_analysis_state"] = SimpleNamespace(
        data_generation=0,
        x_channel="X", y_channel="Y",
        x_scale="linear", y_scale="linear", cofactor=150.0,
        gate_context_matches=lambda gate: True,
    )
    # FlowApp compatibility properties route through ApplicationSession; use
    # the normal analysis-state owner to bind context robustly.
    from vflow.app.state import AnalysisState
    state = AnalysisState()
    state.x_channel="X"; state.y_channel="Y"
    state.x_scale="linear"; state.y_scale="linear"; state.cofactor=150.0
    app.__dict__["_analysis_state"] = state
    app.x_channel="X"; app.y_channel="Y"; app.x_scale="linear"; app.y_scale="linear"; app.cofactor=150.0

    gate = {
        "id": 1, "name": "G1", "type": "rectangle", "applied": True,
        "color": "#ff0000", "x0": -0.5, "y0": -0.5, "x1": 0.5, "y1": 0.5,
    }
    state.bind_gate_context(gate)
    x = np.linspace(-2.0, 2.0, 20_001, dtype=np.float64)
    y = np.sin(x)
    calls = []
    class Ax:
        def scatter(self, xa, ya, **kwargs):
            calls.append((np.array(xa, copy=True), np.array(ya, copy=True), np.array(kwargs["c"], copy=True)))
    app.ax = Ax()

    app._plot_gated_multi(x, y, 4, 0.7, [gate], "#336699", path="sample", overlay=False)
    assert len(calls) == 1
    cached = next(iter(app._analysis_cache_obj().scatter.values()))
    assert type(cached).__name__ == "CompactScatterPayload"
    retained = app._analysis_cache_obj().scatter_numeric_nbytes()
    historical_retained = sum(arr.nbytes for arr in calls[0])
    assert retained < historical_retained / 4

    app._plot_gated_multi(x, y, 4, 0.7, [gate], "#336699", path="sample", overlay=False)
    assert len(calls) == 2
    for cold, warm in zip(calls[0], calls[1]):
        assert np.array_equal(cold, warm)
