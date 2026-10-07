from pathlib import Path

import numpy as np
import pandas as pd

from vflow.services.batch_stats_runner import (
    BatchStatsAdapters,
    BatchStatsRequest,
    BatchStatsRunner,
)


def _base_adapters(*, progress=None, lineage_provider=lambda: []):
    def load_frame(path):
        return pd.read_csv(path), []

    def valid_mask(xa, ya):
        return np.isfinite(xa) & np.isfinite(ya)

    def regions_for_gate(gate, xa, ya):
        threshold = gate.get("threshold", 0.0)
        inside = xa >= threshold
        valid = np.isfinite(xa) & np.isfinite(ya)
        return {"IN": inside & valid, "OUT": (~inside) & valid}

    def regions_in_context(gate, xa, ya, _context):
        return regions_for_gate(gate, xa, ya), None

    return BatchStatsAdapters(
        load_frame=load_frame,
        current_valid_mask=valid_mask,
        regions_for_gate=regions_for_gate,
        regions_in_context=regions_in_context,
        lineage_provider=lineage_provider,
        progress=progress,
    )


def _request(tmp_path, **overrides):
    data = dict(
        folder=str(tmp_path), suffix="___CytoFile", file_types="csv",
        save_path=str(tmp_path / "batch.csv"), x_channel="X", y_channel="Y",
        applied_gates=[{"id": 1, "name": "G", "threshold": 2.0}],
        excluded_files=set(),
    )
    data.update(overrides)
    return BatchStatsRequest(**data)


def test_runner_writes_exact_wide_csv_log_and_progress(tmp_path):
    (tmp_path / "a___CytoFile.csv").write_text("X,Y\n1,1\n2,2\n3,3\n")
    (tmp_path / "b___CytoFile.csv").write_text("X,Y\n4,4\n5,5\n")
    progress = []
    result = BatchStatsRunner(_base_adapters(progress=progress.append)).run(
        _request(tmp_path)
    )

    assert result.outcome == "success"
    assert result.rows_count == 2
    assert result.errors == []
    assert result.skipped_exclusions == []
    assert progress == [
        "Batch stats: processing 0 / 2 files…",
        "Batch stats: 1 / 2 — a___CytoFile.csv",
        "Batch stats: 2 / 2 — b___CytoFile.csv",
    ]
    out = pd.read_csv(result.save_path)
    assert list(out.columns) == [
        "Sample", "Source_Total_Cells", "Input_Total_Cells", "Total_Cells",
        "Transform_Excluded_Cells", "FCS_Compensation_Metadata",
        "Compensation_State",
        "G__IN__N", "G__IN__pct", "G__OUT__N", "G__OUT__pct",
        "Relative_Path", "Source_File",
    ]
    assert out["Total_Cells"].tolist() == [3, 2]
    assert out["Source_Total_Cells"].tolist() == [3, 2]
    assert out["Input_Total_Cells"].tolist() == [3, 2]
    assert out["Transform_Excluded_Cells"].tolist() == [0, 0]
    assert out["G__IN__N"].tolist() == [2, 2]
    assert Path(result.log_path).read_text().splitlines() == [
        "Filename,Full_Path,Reason"
    ]


def test_runner_preserves_dummy_gate_evaluation_before_lineage_and_files(tmp_path):
    path = tmp_path / "a___CytoFile.csv"
    path.write_text("X,Y\n1,1\n")
    events = []

    def load_frame(file_path):
        events.append(("load", Path(file_path).name))
        return pd.read_csv(file_path), []

    def regions(gate, xa, ya):
        events.append(("regions", len(xa)))
        valid = np.ones(len(xa), dtype=bool)
        return {"IN": valid}

    def lineage():
        events.append(("lineage", None))
        return []

    adapters = BatchStatsAdapters(
        load_frame=load_frame,
        current_valid_mask=lambda xa, ya: np.ones(len(xa), dtype=bool),
        regions_for_gate=regions,
        regions_in_context=lambda gate, xa, ya, ctx: (regions(gate, xa, ya), None),
        lineage_provider=lineage,
    )
    result = BatchStatsRunner(adapters).run(_request(tmp_path))

    assert result.outcome == "success"
    assert events[:3] == [
        ("regions", 1),
        ("lineage", None),
        ("load", "a___CytoFile.csv"),
    ]


def test_runner_alias_ambiguity_is_not_reclassified_as_load_error(tmp_path):
    path = tmp_path / "a___CytoFile.csv"
    path.write_text("X,Y\n1,1\n")
    adapters = _base_adapters()
    adapters = BatchStatsAdapters(
        load_frame=lambda p: (pd.read_csv(p), ["X -> X1/X2"]),
        current_valid_mask=adapters.current_valid_mask,
        regions_for_gate=adapters.regions_for_gate,
        regions_in_context=adapters.regions_in_context,
        lineage_provider=adapters.lineage_provider,
    )
    result = BatchStatsRunner(adapters).run(_request(tmp_path))

    assert result.outcome == "no_files_processed"
    assert result.errors == [
        "a___CytoFile.csv: ambiguous axis alias — X -> X1/X2"
    ]


def test_runner_replays_lineage_then_uses_filtered_denominator(tmp_path):
    path = tmp_path / "a___CytoFile.csv"
    path.write_text("X,Y,PX,PY\n1,1,0,0\n2,2,1,1\n3,3,2,2\n")
    parent = {"id": 9, "name": "Parent", "type": "polygon"}
    lineage = [{
        "gate": parent,
        "region": "IN",
        "context": {"x_channel": "PX", "y_channel": "PY"},
    }]
    base = _base_adapters(lineage_provider=lambda: lineage)

    def ancestor_regions(_gate, xa, ya, _ctx):
        return {"IN": xa >= 1.0, "OUT": xa < 1.0}, None

    adapters = BatchStatsAdapters(
        load_frame=base.load_frame,
        current_valid_mask=base.current_valid_mask,
        regions_for_gate=base.regions_for_gate,
        regions_in_context=ancestor_regions,
        lineage_provider=base.lineage_provider,
    )
    result = BatchStatsRunner(adapters).run(_request(tmp_path))
    out = pd.read_csv(result.save_path)

    assert result.outcome == "success"
    assert out.loc[0, "Source_Total_Cells"] == 3
    assert out.loc[0, "Input_Total_Cells"] == 2
    assert out.loc[0, "Total_Cells"] == 2
    assert out.loc[0, "Transform_Excluded_Cells"] == 0
    assert out.loc[0, "G__IN__N"] == 2
    assert out.loc[0, "G__IN__pct"] == 100.0


def test_runner_distinguishes_no_targets_all_excluded_and_no_processed(tmp_path):
    runner = BatchStatsRunner(_base_adapters())
    no_targets = runner.run(_request(tmp_path))
    assert no_targets.outcome == "no_targets"

    path = tmp_path / "a___CytoFile.csv"
    path.write_text("X,Y\n1,1\n")
    excluded = runner.run(_request(tmp_path, excluded_files={str(path)}))
    assert excluded.outcome == "all_targets_excluded"
    assert excluded.skipped_exclusions == [
        ("a___CytoFile.csv", "directly excluded from analysis")
    ]

    adapters = _base_adapters()
    broken = BatchStatsAdapters(
        load_frame=lambda _p: (_ for _ in ()).throw(RuntimeError("boom")),
        current_valid_mask=adapters.current_valid_mask,
        regions_for_gate=adapters.regions_for_gate,
        regions_in_context=adapters.regions_in_context,
        lineage_provider=adapters.lineage_provider,
    )
    failed = BatchStatsRunner(broken).run(_request(tmp_path))
    assert failed.outcome == "no_files_processed"
    assert failed.errors == ["a___CytoFile.csv: load error — boom"]


def test_runner_denominator_provenance_survives_transform_prefilter(tmp_path):
    path = tmp_path / "a___CytoFile.csv"
    path.write_text("X,Y\n-1,1\n0,2\n2,3\n3,4\n")
    base = _base_adapters()
    adapters = BatchStatsAdapters(
        load_frame=base.load_frame,
        current_valid_mask=lambda xa, ya: np.isfinite(xa) & np.isfinite(ya) & (xa > 0),
        regions_for_gate=base.regions_for_gate,
        regions_in_context=base.regions_in_context,
        lineage_provider=base.lineage_provider,
    )
    result = BatchStatsRunner(adapters).run(_request(tmp_path))
    assert result.outcome == "success"
    out = pd.read_csv(result.save_path)
    assert out.loc[0, "Source_Total_Cells"] == 4
    assert out.loc[0, "Input_Total_Cells"] == 4
    assert out.loc[0, "Total_Cells"] == 2
    assert out.loc[0, "Transform_Excluded_Cells"] == 2


def test_runner_surfaces_fcs_compensation_metadata_without_dropping_file(tmp_path):
    path = tmp_path / "a___CytoFile.fcs"
    path.write_bytes(b"placeholder")
    df = pd.DataFrame({"X": [1.0, 2.0], "Y": [1.0, 2.0]})
    df.attrs["fcs_compensation_metadata_present"] = True
    df.attrs["fcs_compensation_metadata_keys"] = ("$SPILLOVER",)
    base = _base_adapters()
    adapters = BatchStatsAdapters(
        load_frame=lambda _p: (df.copy(), []),
        current_valid_mask=base.current_valid_mask,
        regions_for_gate=base.regions_for_gate,
        regions_in_context=base.regions_in_context,
        lineage_provider=base.lineage_provider,
    )
    result = BatchStatsRunner(adapters).run(
        _request(tmp_path, file_types="fcs")
    )
    assert result.outcome == "success"
    assert result.rows_count == 1
    assert result.errors == []
    assert len(result.warnings) == 1
    assert "$SPILLOVER" in result.warnings[0]
    out = pd.read_csv(result.save_path)
    assert out.loc[0, "FCS_Compensation_Metadata"] == "$SPILLOVER"
    assert out.loc[0, "Compensation_State"] == "VERIFY"
    log = pd.read_csv(result.log_path)
    assert len(log) == 1
    assert log.loc[0, "Filename"] == path.name
    assert log.loc[0, "Reason"].startswith("WARNING — FCS compensation metadata present")
