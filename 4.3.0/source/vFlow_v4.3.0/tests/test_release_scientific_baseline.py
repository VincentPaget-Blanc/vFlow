"""Release scientific-baseline behavior tests migrated from the frozen v4.1.11 launcher suite.

They now exercise the packaged v4.2 application authority directly; the expected
scientific semantics remain the certified v4.1.11 baseline unless explicitly changed
in the behavior-review record.
"""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from scipy.stats import gaussian_kde

import vflow.legacy.vflow_app as vf


class FakeVar:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value


def make_app():
    app = vf.FlowApp.__new__(vf.FlowApp)
    app.x_channel = "X"
    app.y_channel = "Y"
    app.x_scale = "linear"
    app.y_scale = "linear"
    app.cofactor = 150.0
    app._data_generation = 1
    app._tc = {}
    app._gmc = {}
    app._scatter_cache = {}
    app._minor_loc_cache = {}
    app.gate_stats = {}
    app.gates = []
    app.loaded_files = {}
    app.file_vars = {}
    return app


def rectangle_gate(gid=1, name="Gate", x0=-1.0, x1=1.0, y0=-1.0, y1=1.0):
    return {
        "id": gid,
        "name": name,
        "type": "rectangle",
        "applied": True,
        "color": "#ff0000",
        "linestyle": "-",
        "linewidth": 1.0,
        "x0": x0,
        "x1": x1,
        "y0": y0,
        "y1": y1,
    }


class HardeningTests(unittest.TestCase):
    def test_context_binding_survives_switch_back(self):
        app = make_app()
        gate = rectangle_gate()
        app.gates = [gate]
        app._bind_gate_context(gate)
        self.assertTrue(app._gate_context_matches(gate))
        app.x_channel = "OtherX"
        self.assertFalse(app._gate_context_matches(gate))
        app.x_channel = "X"
        self.assertTrue(app._gate_context_matches(gate))

    def test_duplicate_gate_names_use_ids(self):
        app = make_app()
        app.gates = [rectangle_gate(1, "Same"), rectangle_gate(2, "Same"),
                     rectangle_gate(3, "Unique")]
        for gate in app.gates:
            app._bind_gate_context(gate)
        self.assertEqual(
            app._gate_selector_labels(),
            ["All cells", "Same [#1]", "Same [#2]", "Unique"],
        )
        self.assertEqual(app._gate_from_selector("Same [#2]")["id"], 2)
        self.assertIsNone(app._gate_from_selector("Same"))

    def test_lineage_snapshot_is_deep_and_tk_free(self):
        app = make_app()
        gate = {
            **rectangle_gate(),
            "vertices": [(1.0, 2.0), (3.0, 4.0)],
            "x_thresh_vars": [FakeVar(True), FakeVar(False)],
            "y_thresh_var": FakeVar(True),
            "y_thresh_vars": [FakeVar(False)],
        }
        app._bind_gate_context(gate)
        snap = app._plain_gate_snapshot(gate)
        gate["vertices"][0] = (99.0, 99.0)
        self.assertEqual(snap["vertices"][0], (1.0, 2.0))
        self.assertEqual(snap["x_thresh_active"], [True, False])
        self.assertTrue(snap["y_thresh_active"])
        self.assertEqual(snap["y_thresh_actives"], [False])

    def test_gate_cache_is_separated_by_data_generation(self):
        app = make_app()
        gate = rectangle_gate()
        app.gates = [gate]
        app._bind_gate_context(gate)
        x = np.array([0.0, 2.0], dtype=float)
        y = np.array([0.0, 2.0], dtype=float)
        r1, _ = app._gate_mask_for(gate, x, y, _cache_path="same.csv")
        self.assertIn("IN", r1)
        keys1 = set(app._gmc)
        self.assertEqual(len(keys1), 1)
        app._data_generation += 1
        r2, _ = app._gate_mask_for(gate, x, y, _cache_path="same.csv")
        self.assertIn("IN", r2)
        self.assertEqual(len(app._gmc), 2)
        self.assertNotEqual(keys1, set(app._gmc))

    def test_scale_change_rebinds_and_recomputes_gate_mask_on_same_channels(self):
        app = make_app()
        gate = rectangle_gate()
        app.gates = [gate]
        app._bind_gate_context(gate)
        x = np.array([0.0], dtype=float)
        y = np.array([0.0], dtype=float)
        regions, _ = app._gate_mask_for(gate, x, y, _cache_path="same.csv")
        self.assertTrue(regions)
        app.x_scale = "asinh"
        regions2, _ = app._gate_mask_for(gate, x, y, _cache_path="same.csv")
        self.assertTrue(regions2)
        self.assertEqual(gate["_analysis_context"]["x_scale"], "asinh")

    def test_auto_gate_collectors_reject_partial_active_file_subset(self):
        app = make_app()
        app.loaded_files = {
            "complete.csv": pd.DataFrame({"X": [1.0], "Y": [2.0]}),
            "missing.csv": pd.DataFrame({"X": [3.0]}),
        }
        app.file_vars = {
            "complete.csv": FakeVar(True),
            "missing.csv": FakeVar(True),
        }
        self.assertEqual(app._collect_x_transform().size, 0)
        self.assertEqual(app._collect_y_transform().size, 0)

    def test_single_gate_stats_rejects_partial_active_file_subset(self):
        app = make_app()
        gate = rectangle_gate(x0=-10, x1=10, y0=-10, y1=10)
        app.gates = [gate]
        app._bind_gate_context(gate)
        app.loaded_files = {
            "complete.csv": pd.DataFrame({"X": [0.0], "Y": [0.0]}),
            "missing.csv": pd.DataFrame({"X": [0.0]}),
        }
        app.file_vars = {
            "complete.csv": FakeVar(True),
            "missing.csv": FakeVar(True),
        }
        app._compute_gate_stats_for(gate)
        self.assertEqual(app.gate_stats[gate["id"]], {})

    def test_single_gate_stats_denominator_uses_finite_transformable_events(self):
        app = make_app()
        gate = rectangle_gate(x0=-10, x1=10, y0=-10, y1=10)
        app.gates = [gate]
        app._bind_gate_context(gate)
        app.loaded_files = {
            "sample.csv": pd.DataFrame({"X": [0.0, 1.0, np.nan],
                                        "Y": [0.0, 1.0, 2.0]})
        }
        app.file_vars = {"sample.csv": FakeVar(True)}
        app._compute_gate_stats_for(gate)
        self.assertEqual(app.gate_stats[gate["id"]]["sample.csv"]["total"], 2)

    def test_multi_shape_stats_rejects_partial_active_file_subset(self):
        class FakeTree:
            def get_children(self):
                return ()
            def delete(self, _item):
                raise AssertionError("nothing should be deleted")
            def insert(self, *args, **kwargs):
                raise AssertionError("partial multi-file stats must not render")

        app = make_app()
        app.gates = [rectangle_gate(1, "A"), rectangle_gate(2, "B")]
        app.stats_tree = FakeTree()
        app.stats_mode_var = FakeVar("merged")
        app.loaded_files = {
            "complete.csv": pd.DataFrame({"X": [0.0], "Y": [0.0]}),
            "missing.csv": pd.DataFrame({"X": [0.0]}),
        }
        app.file_vars = {
            "complete.csv": FakeVar(True),
            "missing.csv": FakeVar(True),
        }
        app._gate_context_matches = lambda gate: True
        app._update_stats_display()

    def test_polar_gate_failure_is_closed(self):
        app = make_app()
        gate = rectangle_gate()
        app.gates = [gate]
        app._bind_gate_context(gate)
        w = vf.PolarAnalysisWindow.__new__(vf.PolarAnalysisWindow)
        w.app = app
        w._gate_var = FakeVar("Gate")
        w._region_var = FakeVar("IN")
        # Missing Y must not become All Cells.
        df = pd.DataFrame({"X": [0.0, 1.0]})
        self.assertIsNone(w._get_population_mask(df, "sample.csv"))

    def test_batch_plot_gate_failure_is_closed(self):
        app = make_app()
        gate = rectangle_gate()
        app.gates = [gate]
        app._bind_gate_context(gate)
        w = vf.BatchPlotWindow.__new__(vf.BatchPlotWindow)
        w.app = app
        w._gate_var = FakeVar("Gate")
        w._region_var = FakeVar("IN")
        df = pd.DataFrame({"X": [0.0, 1.0]})
        self.assertIsNone(w._get_population_mask(df))

    def test_explicit_lineage_context_replays_independently_of_child_context(self):
        app = make_app()
        gate = rectangle_gate(x0=-1, x1=1, y0=-1, y1=1)
        app._bind_gate_context(gate)
        ctx = dict(gate["_analysis_context"])
        snap = app._plain_gate_snapshot(gate)
        # Change the child tab's current context; replay must still use ctx.
        app.x_channel = "Different"
        app.y_scale = "asinh"
        x = np.array([0.0, 2.0], dtype=float)
        y = np.array([0.0, 2.0], dtype=float)
        regions, _ = app._regions_in_explicit_context(snap, x, y, ctx)
        self.assertEqual(int(regions["IN"].sum()), 1)



    def test_serialized_context_validation(self):
        ok, why = vf.FlowApp._validate_gate_context_payload({
            "x_channel": "X", "y_channel": "Y",
            "x_scale": "linear", "y_scale": "linear", "cofactor": None,
        })
        self.assertTrue(ok, why)
        ok, why = vf.FlowApp._validate_gate_context_payload({
            "x_channel": "X", "y_channel": "Y",
            "x_scale": "asinh", "y_scale": "linear", "cofactor": None,
        })
        self.assertFalse(ok)
        ok, why = vf.FlowApp._validate_gate_context_payload({
            "x_channel": "", "y_channel": "Y",
            "x_scale": "linear", "y_scale": "linear", "cofactor": None,
        })
        self.assertFalse(ok)

    def test_region_masks_are_restricted_to_valid_population(self):
        app = make_app()
        regions = {
            "IN": np.array([True, False, False]),
            "OUT": np.array([False, True, True]),
        }
        valid = np.array([True, True, False])
        clean = app._restrict_regions_to_valid(regions, valid)
        self.assertEqual(clean["IN"].tolist(), [True, False, False])
        self.assertEqual(clean["OUT"].tolist(), [False, True, False])

    def test_log_lock_snap_never_crosses_zero(self):
        self.assertGreater(vf.FlowApp._snap_outward(10.0, -1, "log", 100.0), 0.0)
        self.assertGreater(vf.FlowApp._snap_outward(1e-30, -1, "log", 1.0), 0.0)
        self.assertGreater(vf.FlowApp._snap_outward(10.0, +1, "log", 100.0), 10.0)

    def test_nonfinite_cofactor_trace_is_rejected(self):
        app = make_app()
        app.cofactor_str = FakeVar("inf")
        app._analysis_context_changed = lambda: (_ for _ in ()).throw(AssertionError("must not apply inf"))
        app._on_cofactor_change()
        self.assertEqual(app.cofactor, 150.0)

    def test_kde_validator_rejects_unimodal_tail_fallback(self):
        rng = np.random.default_rng(123)
        bimodal = np.r_[rng.normal(-2, 0.35, 3000), rng.normal(2, 0.4, 3000)]
        kde = gaussian_kde(bimodal, bw_method="scott")
        grid = np.linspace(bimodal.min(), bimodal.max(), 2048)
        smooth = savgol_filter(kde(grid), 51, 3)
        dy = np.gradient(smooth, grid)
        valleys = np.where(np.diff(np.sign(dy)) > 0)[0]
        threshold = float(grid[valleys[0]])
        self.assertTrue(vf.FlowApp._kde_valley_supported(
            bimodal, threshold, 1.0, 5.0, 0.01))

        unimodal = rng.normal(0, 1, 6000)
        fallback = float(np.percentile(unimodal, 5))
        self.assertFalse(vf.FlowApp._kde_valley_supported(
            unimodal, fallback, 1.0, 5.0, 0.01))


if __name__ == "__main__":
    unittest.main(verbosity=2)


def test_single_gate_stats_preserves_file_with_zero_transform_valid_events():
    app = make_app()
    app.x_scale = "log"
    gate = rectangle_gate(x0=1.0, x1=10.0, y0=-10.0, y1=10.0)
    app.gates = [gate]
    app._bind_gate_context(gate)
    app.loaded_files = {
        "all_invalid.csv": pd.DataFrame({"X": [-2.0, 0.0], "Y": [1.0, 2.0]})
    }
    app.file_vars = {"all_invalid.csv": FakeVar(True)}
    app._compute_gate_stats_for(gate)
    info = app.gate_stats[gate["id"]]["all_invalid.csv"]
    assert info["total"] == 0
    assert all(cell["count"] == 0 and cell["pct"] == 0.0
               for cell in info["stats"].values())
