import inspect

from vflow.controllers.project_data_load_coordinator import ProjectDataLoadCoordinator
from vflow.legacy.vflow_app import FlowApp


def test_flow_app_project_data_methods_are_compatibility_facades():
    load_paths = inspect.getsource(FlowApp._load_paths)
    save_gates = inspect.getsource(FlowApp.save_gates)
    load_gates = inspect.getsource(FlowApp.load_gates)

    assert "_project_data_load_owner(self).load_paths" in load_paths
    assert "_project_data_load_owner(self).save_gates" in save_gates
    assert "_project_data_load_owner(self).load_gates" in load_gates
    assert len([ln for ln in load_paths.splitlines() if ln.strip()]) <= 4
    assert len([ln for ln in save_gates.splitlines() if ln.strip()]) <= 4
    assert len([ln for ln in load_gates.splitlines() if ln.strip()]) <= 5


def test_project_data_coordinator_owns_all_three_workflows():
    load_src = inspect.getsource(ProjectDataLoadCoordinator.load_paths)
    save_src = inspect.getsource(ProjectDataLoadCoordinator.save_gates)
    gate_load_src = inspect.getsource(ProjectDataLoadCoordinator.load_gates)

    assert "plan_path_admission" in load_src
    assert "commit_loaded_file(path, df)" in load_src
    assert load_src.index("h._add_file_row(path)") < load_src.index(
        "commit_loaded_file(path, df)")

    assert "build_gate_session_payload(" in save_src
    assert "except (ThresholdSchemaError, ValueError) as exc:" in save_src
    assert save_src.index("build_gate_session_payload(") < save_src.index(
        "with open(path, 'w') as fh:")

    assert "prepare_gate_session_load(" in gate_load_src
    assert gate_load_src.index("h.clear_all_gates()") < gate_load_src.index(
        "h.gates = new_gates")
    assert gate_load_src.index("h._update_stats_display()") < gate_load_src.index(
        "h.refresh_plot()")


def test_project_data_controller_is_composed_not_inherited():
    assert ProjectDataLoadCoordinator.__bases__ == (object,)
    assert not issubclass(FlowApp, ProjectDataLoadCoordinator)

class _Status:
    def __init__(self):
        self.value = ""
    def set(self, value):
        self.value = value


class _Dialogs:
    def __init__(self, path):
        self.path = str(path)
        self.infos = []
        self.errors = []
    def asksaveasfilename(self, **kwargs):
        return self.path
    def askopenfilename(self, **kwargs):
        return self.path
    def showinfo(self, *args, **kwargs):
        self.infos.append((args, kwargs))
    def showerror(self, *args, **kwargs):
        self.errors.append((args, kwargs))


def test_excluded_list_facades_delegate_to_project_data_owner():
    save_src = inspect.getsource(FlowApp.save_excluded_list)
    load_src = inspect.getsource(FlowApp.load_excluded_list)
    assert "_project_data_load_owner(self).save_excluded_list" in save_src
    assert "_project_data_load_owner(self).load_excluded_list" in load_src


def test_project_data_coordinator_round_trips_excluded_list_contract(tmp_path):
    from types import SimpleNamespace
    from vflow.app.dataset import DatasetState

    csv_path = tmp_path / "excluded_files.csv"
    status = _Status()
    host = SimpleNamespace(
        root=object(),
        excluded_files={"already.csv": None, "save_me.csv": None},
        loaded_files={},
        status_var=status,
    )
    dialogs = _Dialogs(csv_path)
    owner = ProjectDataLoadCoordinator(host)
    owner.save_excluded_list(
        filedialog=dialogs, messagebox=dialogs, last_folder_getter=lambda: None)
    assert csv_path.read_text().splitlines() == ["Path", "already.csv", "save_me.csv"]
    assert status.value == "Excluded list saved: 2 file(s) → excluded_files.csv"

    csv_path.write_text("Path\nalready.csv\nloaded.csv\nnew.csv\n", encoding="utf-8")
    loaded = {"loaded.csv": object()}
    excluded = {"already.csv": None}
    dataset = DatasetState(loaded, excluded)
    trace = []
    host = SimpleNamespace(
        root=object(),
        excluded_files=excluded,
        loaded_files=loaded,
        status_var=status,
        _dataset_state_obj=lambda: dataset,
        _rebuild_excluded_list=lambda: trace.append("rebuild"),
        _on_active_files_changed=lambda: trace.append("active_changed"),
    )
    def exclude(path):
        trace.append(f"exclude:{path}")
        dataset.exclude_loaded_file(path)
    host._exclude_file = exclude

    owner = ProjectDataLoadCoordinator(host)
    owner.load_excluded_list(
        filedialog=dialogs, messagebox=dialogs, last_folder_getter=lambda: None)
    assert trace == ["exclude:loaded.csv", "rebuild", "active_changed"]
    assert set(excluded) == {"already.csv", "loaded.csv", "new.csv"}
    assert status.value == (
        "Excluded list loaded: 1 moved to excluded, 1 registered (not loaded), "
        "1 already excluded")


def test_gate_session_load_uses_a3_axis_transposition_for_pure_saved_axis_swap():
    import inspect
    from vflow.controllers.project_data_load_coordinator import ProjectDataLoadCoordinator
    src = inspect.getsource(ProjectDataLoadCoordinator.load_gates)
    assert "is_pure_axis_swap" in src
    assert "transpose_loaded_gate_for_current_axes" in src
    assert "channel_mismatch and not pure_axis_swap" in src
