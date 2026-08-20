import pandas as pd

from vflow.app.state import AnalysisState
from vflow.ui.batch_plot_window import BatchPlotWindowBase
from vflow.ui.polar_analysis_window import PolarAnalysisWindowBase


class FakeVar:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value


class FakeApp:
    def __init__(self):
        self.state = AnalysisState(
            x_channel='X', y_channel='Y',
            x_scale='linear', y_scale='linear', cofactor=150.0)
        self.gate = {
            'id': 1, 'name': 'Gate', 'type': 'rectangle', 'applied': True,
            'x0': -1.0, 'y0': -1.0, 'x1': 1.0, 'y1': 1.0,
        }
        self.state.bind_gate_context(self.gate)

    def _gate_from_selector(self, name):
        return self.gate if name == 'Gate' else None

    def _analysis_state_obj(self):
        return self.state


def test_extracted_bases_do_not_own_sensitive_compute_method():
    assert '_compute_and_plot' not in PolarAnalysisWindowBase.__dict__
    assert '_compute_and_plot' not in BatchPlotWindowBase.__dict__


def test_legacy_secondary_windows_use_extracted_bases_but_retain_compute_method():
    from vflow.legacy.vflow_legacy import PolarAnalysisWindow, BatchPlotWindow
    assert issubclass(PolarAnalysisWindow, PolarAnalysisWindowBase)
    assert issubclass(BatchPlotWindow, BatchPlotWindowBase)
    assert '_compute_and_plot' in PolarAnalysisWindow.__dict__
    assert '_compute_and_plot' in BatchPlotWindow.__dict__


def test_polar_extracted_population_helper_still_fails_closed_for_missing_channel():
    w = PolarAnalysisWindowBase.__new__(PolarAnalysisWindowBase)
    w.app = FakeApp()
    w._gate_var = FakeVar('Gate')
    w._region_var = FakeVar('IN')
    df = pd.DataFrame({'X': [0.0, 1.0]})
    assert w._get_population_mask(df, 'sample.csv') is None


def test_batch_extracted_population_helper_still_fails_closed_for_missing_channel():
    w = BatchPlotWindowBase.__new__(BatchPlotWindowBase)
    w.app = FakeApp()
    w._gate_var = FakeVar('Gate')
    w._region_var = FakeVar('IN')
    df = pd.DataFrame({'X': [0.0, 1.0]})
    assert w._get_population_mask(df) is None


