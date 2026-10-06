from vflow.app.dataset import DatasetState
from vflow.legacy.vflow_app import FlowApp
from vflow.ui.file_list import FileListPresentationMixin, FileListUIState
from vflow.ui.flow_app_shell import FlowAppShellBase


class FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeTextVar(FakeVar):
    pass


def test_flow_app_keeps_shell_as_direct_base_and_shell_composes_file_list_presentation():
    assert FlowApp.__mro__[1] is FlowAppShellBase
    assert FileListPresentationMixin in FlowAppShellBase.__mro__


def test_file_list_ui_state_is_separate_from_dataset_state():
    app = FlowApp.__new__(FlowApp)
    app.loaded_files = {"a.csv": object()}
    app.excluded_files = {"b.csv": None}
    app.file_vars = {"a.csv": FakeVar(True)}
    app.file_colors = {"a.csv": "red"}

    assert isinstance(app._dataset_state_obj(), DatasetState)
    assert isinstance(app._file_list_ui_obj(), FileListUIState)
    assert app._dataset_state_obj().__dict__ == {
        "loaded_files": app.loaded_files,
        "excluded_files": app.excluded_files,
    }
    assert app._file_list_ui_obj().__dict__ == {
        "file_vars": app.file_vars,
        "file_colors": app.file_colors,
    }


def test_file_list_compatibility_properties_preserve_mapping_identity():
    app = FlowApp.__new__(FlowApp)
    file_vars = {"a.csv": FakeVar(False)}
    file_colors = {"a.csv": "blue"}
    app.file_vars = file_vars
    app.file_colors = file_colors

    assert app.file_vars is file_vars
    assert app.file_colors is file_colors


def test_active_files_uses_loaded_order_and_checkbox_state():
    app = FlowApp.__new__(FlowApp)
    a, b, c = object(), object(), object()
    app.loaded_files = {"a.csv": a, "b.csv": b, "c.csv": c}
    app.file_vars = {
        "a.csv": FakeVar(True),
        "b.csv": FakeVar(False),
        "c.csv": FakeVar(True),
    }

    assert list(app._active().items()) == [("a.csv", a), ("c.csv", c)]


def test_display_files_cycle_mode_preserves_active_order_and_cycle_modulo():
    app = FlowApp.__new__(FlowApp)
    app.view_mode_var = FakeTextVar("cycle")
    app.cycle_idx = 3
    active = {"a.csv": 1, "b.csv": 2, "c.csv": 3}

    assert app._display_files(active) == {"a.csv": 1}


def test_select_and_unselect_all_keep_single_active_change_callback():
    app = FlowApp.__new__(FlowApp)
    app.file_vars = {"a": FakeVar(False), "b": FakeVar(True)}
    calls = []
    app._on_active_files_changed = lambda: calls.append("changed")

    app._select_all()
    assert [v.get() for v in app.file_vars.values()] == [True, True]
    assert calls == ["changed"]

    app._unselect_all()
    assert [v.get() for v in app.file_vars.values()] == [False, False]
    assert calls == ["changed", "changed"]
