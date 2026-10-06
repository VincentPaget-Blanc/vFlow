import pandas as pd

from vflow.app.dataset import DatasetState
from vflow.legacy import vflow_app as legacy
from vflow.legacy.vflow_app import FlowApp


class FakeVar:
    def __init__(self, value=True):
        self.value = value

    def get(self):
        return self.value


class FakeCache:
    def __init__(self, trace):
        self.trace = trace

    def clear_all(self):
        self.trace.append("cache.clear_all")


class Harness:
    def __init__(self):
        self.trace = []
        self.loaded_files = {}
        self.excluded_files = {}
        self.file_vars = {}
        self.file_colors = {}
        self._dataset = DatasetState(self.loaded_files, self.excluded_files)
        self._data_generation = 0
        self._col_mismatch_msg = ""

    def _dataset_state_obj(self):
        return self._dataset

    def _analysis_cache_obj(self):
        return FakeCache(self.trace)

    def _read_data_file(self, path):
        self.trace.append(f"read:{path}")
        return pd.DataFrame({"X": [1.0], "Y": [2.0]})

    def _add_file_row(self, path):
        self.trace.append(f"addrow:{path}")
        self.file_vars[path] = FakeVar(True)

    def _update_channel_menus(self):
        self.trace.append("update_channels")

    def _on_active_files_changed(self):
        self.trace.append("active_changed")


def _silence_dialogs(monkeypatch):
    errors = []
    warnings = []
    monkeypatch.setattr(
        legacy.messagebox, "showerror",
        lambda *args, **kwargs: errors.append((args, kwargs)),
    )
    monkeypatch.setattr(
        legacy.messagebox, "showwarning",
        lambda *args, **kwargs: warnings.append((args, kwargs)),
    )
    return errors, warnings


def test_br_file_002_failed_row_after_checkbox_creation_rolls_back_ui_state(monkeypatch):
    app = Harness()
    errors, _ = _silence_dialogs(monkeypatch)

    def fail_after_var(path):
        app.trace.append(f"addrow:{path}")
        app.file_vars[path] = FakeVar(True)
        raise RuntimeError("row boom")

    app._add_file_row = fail_after_var
    FlowApp._load_paths(app, ["a.csv"])

    assert app.loaded_files == {}
    assert app.file_colors == {}
    assert app.file_vars == {}
    assert app._data_generation == 0
    assert "cache.clear_all" not in app.trace
    assert app.trace == ["read:a.csv", "addrow:a.csv", "update_channels", "active_changed"]
    assert len(errors) == 1
    assert errors[0][0][0] == "Load Error"
    assert "UI registration failed for a.csv" in errors[0][0][1]
    assert "row boom" in errors[0][0][1]


def test_br_file_002_failed_row_before_checkbox_creation_remains_clean(monkeypatch):
    app = Harness()
    _silence_dialogs(monkeypatch)

    def fail_before_var(path):
        app.trace.append(f"addrow:{path}")
        raise RuntimeError("frame boom")

    app._add_file_row = fail_before_var
    FlowApp._load_paths(app, ["a.csv"])

    assert app.loaded_files == {}
    assert app.file_colors == {}
    assert app.file_vars == {}
    assert app._data_generation == 0
    assert "cache.clear_all" not in app.trace


def test_br_file_002_successful_registration_order_and_state_are_unchanged(monkeypatch):
    app = Harness()
    _silence_dialogs(monkeypatch)

    FlowApp._load_paths(app, ["a.csv"])

    assert list(app.loaded_files) == ["a.csv"]
    assert list(app.file_colors) == ["a.csv"]
    assert list(app.file_vars) == ["a.csv"]
    assert app.file_vars["a.csv"].get() is True
    assert app._data_generation == 1
    assert app.trace == [
        "read:a.csv",
        "addrow:a.csv",
        "cache.clear_all",
        "update_channels",
        "active_changed",
    ]
