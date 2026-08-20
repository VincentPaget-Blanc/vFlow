import os

import pandas as pd
import pytest

from vflow.services.file_load_planning import (
    build_load_warning_plan,
    plan_loaded_frame,
    plan_path_admission,
)


def test_exact_loaded_path_is_silent_skip(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("x\n1\n", encoding="utf-8")
    plan = plan_path_admission(str(p), [str(p)], [])
    assert plan.should_load is False
    assert plan.duplicate_notice is None


def test_physical_alias_of_loaded_path_reports_loaded_alias(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("x\n1\n", encoding="utf-8")
    alias = tmp_path / "alias.csv"
    try:
        os.link(p, alias)
    except OSError:
        pytest.skip("hard links unavailable")
    plan = plan_path_admission(str(alias), [str(p)], [])
    assert plan.should_load is False
    assert plan.duplicate_notice == "alias.csv = already loaded as a.csv"


def test_physical_alias_of_excluded_path_reports_excluded_alias(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("x\n1\n", encoding="utf-8")
    alias = tmp_path / "alias.csv"
    try:
        os.link(p, alias)
    except OSError:
        pytest.skip("hard links unavailable")
    plan = plan_path_admission(str(alias), [], [str(p)])
    assert plan.should_load is False
    assert plan.duplicate_notice == "alias.csv = same physical file as excluded a.csv"


def test_loaded_frame_plan_preserves_first_loaded_case_and_notice_order():
    ref = pd.DataFrame({"Intensity_VGAT": [1], "Other": [2]})
    df = pd.DataFrame({"Intensity_vgat": [3], "Other": [4]})
    df.attrs["fcs_compensation_unapplied"] = True
    df.attrs["fcs_compatibility_fixes"] = ("a", "b")
    plan = plan_loaded_frame("/tmp/sample.fcs", df, [ref])
    assert plan.rename_map == {"Intensity_vgat": "Intensity_VGAT"}
    assert plan.rename_notice == "sample.fcs: 'Intensity_vgat'→'Intensity_VGAT'"
    assert plan.uncompensated_fcs_name == "sample.fcs"
    assert plan.fcs_compatibility_notice == "sample.fcs (2 metadata normalizations)"



def test_loaded_frame_plan_retains_legacy_spillover_marker_fallback():
    df = pd.DataFrame({"X": [1]})
    df.attrs["fcs_spillover_unapplied"] = True
    plan = plan_loaded_frame("legacy.fcs", df, [])
    assert plan.uncompensated_fcs_name == "legacy.fcs"

def test_loaded_frame_plan_keeps_ambiguous_column_rejection():
    ref = pd.DataFrame({"A": [1]})
    df = pd.DataFrame([[1, 2]], columns=["a", "A"])
    with pytest.raises(ValueError, match="Ambiguous channel columns differ only by case"):
        plan_loaded_frame("x.csv", df, [ref])


def test_warning_plan_preserves_legacy_order_and_truncation():
    plan = build_load_warning_plan(
        duplicate_file_notices=["d1", "d2"],
        rename_notices=["r1"],
        mismatch="mismatch",
        fcs_compat_notices=["c1", "c2", "c3", "c4", "c5"],
        uncompensated_fcs=["u1", "u2", "u3", "u4", "u5"],
    )
    assert plan.suffix_parts == (
        "⚠ Duplicate physical file skipped: d1  |  d2",
        "⚠ Column case corrected: r1",
        "mismatch",
        "ℹ FCS exporter compatibility metadata normalized (DATA values unchanged): c1, c2, c3, c4 +1 more",
        "⚠ FCS compensation metadata present; compensation state requires verification: u1, u2, u3, u4 +1 more",
    )
    assert plan.spillover_files_summary == "u1, u2, u3, u4 +1 more"


def test_project_data_coordinator_owns_load_planning_and_side_effect_order():
    import inspect
    from vflow.controllers.project_data_load_coordinator import ProjectDataLoadCoordinator
    from vflow.legacy.vflow_app import FlowApp

    facade = inspect.getsource(FlowApp._load_paths)
    assert "_project_data_load_owner(self).load_paths" in facade
    assert "plan_path_admission" not in facade

    src = inspect.getsource(ProjectDataLoadCoordinator.load_paths)
    assert "plan_path_admission" in src
    assert "plan_loaded_frame" in src
    assert "build_load_warning_plan" in src
    assert "h._read_data_file(path)" in src
    assert "h._add_file_row(path)" in src
    assert "commit_loaded_file(path, df)" in src
    assert "h._data_generation += 1" in src
    assert "clear_all()" in src
    assert "messagebox.showwarning" in src


def test_file_load_planner_has_no_tk_or_file_reader_dependency():
    import inspect
    import vflow.services.file_load_planning as planning

    src = inspect.getsource(planning)
    assert "tkinter" not in src
    assert "messagebox" not in src
    assert "read_flow_data_file" not in src
