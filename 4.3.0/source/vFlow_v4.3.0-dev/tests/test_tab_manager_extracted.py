import pandas as pd
import pytest

from vflow.app.session import ApplicationSession
from vflow.ui.tab_manager import FlowTabManagerBase


class FakeVar:
    def __init__(self, value=None):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class FakeApp:
    def __init__(self):
        self._app_session = ApplicationSession()
        self.file_colors = {}
        self.file_vars = {}
        self.x_menu = {}
        self.y_menu = {}
        self.x_var = FakeVar()
        self.y_var = FakeVar()
        self.lock_scale_var = FakeVar(False)
        self.fit_axes_var = FakeVar(False)
        self.refresh_count = 0
        self.added_rows = []
        self.excluded_rebuilds = 0

    def _analysis_state_obj(self):
        return self._app_session.analysis
    def _dataset_state_obj(self):
        return self._app_session.dataset
    @property
    def loaded_files(self):
        return self._app_session.dataset.loaded_files
    @property
    def excluded_files(self):
        return self._app_session.dataset.excluded_files
    @property
    def _data_generation(self):
        return self._app_session.analysis.data_generation
    @_data_generation.setter
    def _data_generation(self, value):
        self._app_session.analysis.data_generation = value
    @property
    def x_channel(self):
        return self._app_session.analysis.x_channel
    @x_channel.setter
    def x_channel(self, value):
        self._app_session.analysis.x_channel = value
    @property
    def y_channel(self):
        return self._app_session.analysis.y_channel
    @y_channel.setter
    def y_channel(self, value):
        self._app_session.analysis.y_channel = value

    def _add_file_row(self, path):
        self.added_rows.append(path)
        self.file_vars[path] = FakeVar(True)

    def _rebuild_excluded_list(self):
        self.excluded_rebuilds += 1

    def refresh_plot(self):
        self.refresh_count += 1


def test_extracted_tab_manager_load_filtered_preserves_child_state_axes_and_generation():
    app = FakeApp()
    df = pd.DataFrame({'A': [1.0], 'B': [2.0], 'C': [3.0]})
    parent_gate = {'id': 1, 'vertices': [(1.0, 2.0)]}
    lineage = [{'gate': {'id': 1}, 'region': 'IN', 'context': {'x_channel': 'A'}}]
    FlowTabManagerBase._load_filtered(
        app, {'sample.csv': df}, 'B', 'C',
        parent_gate=parent_gate, parent_region='IN',
        population_lineage=lineage,
        excluded_files={'excluded.csv': None},
    )
    assert app.loaded_files['sample.csv'] is df
    assert app.added_rows == ['sample.csv']
    assert app._data_generation == 1
    assert app.x_channel == 'B' and app.x_var.get() == 'B'
    assert app.y_channel == 'C' and app.y_var.get() == 'C'
    assert app.fit_axes_var.get() is True
    assert app.refresh_count == 1
    assert app.excluded_files == {'excluded.csv': None}
    assert app.excluded_rebuilds == 1
    assert app._analysis_state_obj().parent_gate == parent_gate
    assert app._analysis_state_obj().population_lineage == lineage
    parent_gate['vertices'][0] = (99.0, 99.0)
    lineage[0]['gate']['id'] = 999
    assert app._analysis_state_obj().parent_gate['vertices'][0] == (1.0, 2.0)
    assert app._analysis_state_obj().population_lineage[0]['gate']['id'] == 1


def test_extracted_tab_manager_keeps_file_registration_atomic_on_ui_failure():
    app = FakeApp()
    df = pd.DataFrame({'A': [1.0], 'B': [2.0]})

    def fail_row(path):
        app.file_vars[path] = FakeVar(True)
        raise RuntimeError('row failed')

    app._add_file_row = fail_row
    with pytest.raises(RuntimeError, match='row failed'):
        FlowTabManagerBase._load_filtered(
            app, {'sample.csv': df}, 'A', 'B')
    assert 'sample.csv' not in app.loaded_files
    assert 'sample.csv' not in app.file_colors
    assert 'sample.csv' not in app.file_vars
    assert app._data_generation == 0


def test_extracted_tab_manager_does_not_force_fit_axes_when_scale_lock_is_active():
    app = FakeApp()
    app.lock_scale_var.set(True)
    FlowTabManagerBase._load_filtered(
        app,
        {'sample.csv': pd.DataFrame({'A': [1.0], 'B': [2.0]})},
        'A', 'B')
    assert app.fit_axes_var.get() is False
