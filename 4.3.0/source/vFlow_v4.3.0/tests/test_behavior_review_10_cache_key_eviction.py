import numpy as np

from vflow.app.cache import AnalysisCache
from vflow.core.cache_keys import gate_signature
from vflow.legacy.vflow_app import FlowApp
from vflow.services.gate_evaluation import evaluate_gate_regions


class _State:
    data_generation = 17
    x_channel = "X"
    y_channel = "Y"
    x_scale = "linear"
    y_scale = "linear"
    cofactor = 150.0

    @staticmethod
    def gate_context_matches(gate):
        return True


def test_tiny_polygon_handle_drag_evicts_same_signature_mask_and_scatter_cache():
    eps = 1e-9
    gate = {
        "id": 42,
        "type": "polygon",
        "applied": True,
        "vertices": [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
    }
    cache = AnalysisCache()
    state = _State()
    xa = np.array([0.0, 0.5], dtype=np.float64)
    ya = np.array([0.5, 0.5], dtype=np.float64)

    before_regions, _ = evaluate_gate_regions(
        gate,
        xa,
        ya,
        analysis_state=state,
        analysis_cache=cache,
        cache_path="sample.fcs",
    )
    assert before_regions["IN"].tolist() == [True, True]

    before_sig = gate_signature(gate)
    scatter_key = (
        state.data_generation,
        "sample.fcs",
        state.x_channel,
        state.y_channel,
        state.x_scale,
        state.y_scale,
        state.cofactor,
        (before_sig,),
        4,
        0.5,
        "#ffffff",
        False,
    )
    cache.scatter[scatter_key] = "stale-render-payload"

    app = FlowApp.__new__(FlowApp)
    app.__dict__["_analysis_cache"] = cache
    app._handle_drag = {
        "gate": gate,
        "handle": "vertex",
        "idx": 0,
        "orig": {},
    }
    app._drag_handle_update(eps, 0.0)

    # Polygon signatures intentionally round to 8 decimals, so this real
    # geometry change shares the old signature and requires explicit eviction.
    assert gate_signature(gate) == before_sig
    assert cache.gate_masks == {}
    assert cache.scatter == {}

    after_regions, _ = evaluate_gate_regions(
        gate,
        xa,
        ya,
        analysis_state=state,
        analysis_cache=cache,
        cache_path="sample.fcs",
    )
    assert after_regions["IN"].tolist() == [False, True]
