from vflow.ui.batch_plot_window import BatchPlotWindowBase
from vflow.ui.polar_analysis_window import PolarAnalysisWindowBase


class _FakeWindow:
    def __init__(self):
        self._initial_compute_pending = "initial"
        self._replot_pending = "replot"
        self.cancelled = []
        self.destroyed = False

    def after_cancel(self, token):
        self.cancelled.append(token)

    def destroy(self):
        self.destroyed = True


def test_secondary_windows_cancel_owned_callbacks_before_destroy():
    for cls in (PolarAnalysisWindowBase, BatchPlotWindowBase):
        fake = _FakeWindow()
        cls._on_close(fake)
        assert fake.cancelled == ["initial", "replot"]
        assert fake._initial_compute_pending is None
        assert fake._replot_pending is None
        assert fake.destroyed is True
