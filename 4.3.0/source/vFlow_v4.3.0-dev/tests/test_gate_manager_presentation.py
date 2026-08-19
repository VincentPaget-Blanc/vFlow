import inspect

from vflow.legacy.vflow_app import FlowApp
from vflow.ui.flow_app_shell import FlowAppShellBase
from vflow.ui.gate_manager import GateManagerPresentationMixin


EXTRACTED_GATE_PRESENTATION_METHODS = {
    '_rename_gate',
    '_rebuild_gate_manager',
    '_rebuild_thresh_panel',
}

SENSITIVE_GATE_METHODS = {
    '_on_thresh_toggle',
    '_finish_gate',
    '_commit_gate',
    '_gate_mask_for',
    '_compute_gate_stats_for',
    '_preview_gate',
    '_hit_test_gate_line',
    '_hit_test_gate_interior',
    'save_gates',
    'load_gates',
}


def test_flow_app_shell_composes_gate_manager_presentation_without_changing_direct_base():
    assert FlowApp.__mro__[1] is FlowAppShellBase
    assert GateManagerPresentationMixin in FlowAppShellBase.__mro__


def test_gate_presentation_methods_are_owned_by_mixin_not_flow_app():
    for name in EXTRACTED_GATE_PRESENTATION_METHODS:
        assert name in GateManagerPresentationMixin.__dict__, name
        assert name not in FlowApp.__dict__, name
        assert getattr(FlowApp, name) is getattr(GateManagerPresentationMixin, name)


def test_sensitive_gate_behavior_remains_on_flow_app():
    for name in SENSITIVE_GATE_METHODS:
        assert name in FlowApp.__dict__, name


def test_gate_manager_mixin_does_not_own_scientific_gate_behavior():
    assert SENSITIVE_GATE_METHODS.isdisjoint(GateManagerPresentationMixin.__dict__)


def test_threshold_panel_keeps_frozen_persistent_threshold_variable_semantics():
    src = inspect.getsource(GateManagerPresentationMixin._rebuild_thresh_panel)
    assert "gate['y_thresh_vars'] = y_tvs" in src
    assert "gate['y_thresh_var'] = ytv" in src
    assert "gate['x_thresh_vars'] = tvs" in src
    assert "command=self._on_thresh_toggle" in src


def test_gate_style_ui_keeps_frozen_preview_draw_and_debounce_callbacks():
    src = inspect.getsource(GateManagerPresentationMixin._rebuild_gate_manager)
    assert "g['linestyle'] = _LINESTYLE_MAP.get(v.get(), '-')" in src
    assert "g['linewidth'] = float(v.get())" in src
    assert 'self._preview_gate()' in src
    assert 'self.canvas.draw_idle()' in src
    assert 'self.schedule_refresh(120)' in src
    assert 'self.schedule_refresh(200)' in src

class _FakeBoolVar:
    def __init__(self, value=False):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _FakeWidget:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.pack_calls = []
        self.destroyed = False

    def pack(self, *args, **kwargs):
        self.pack_calls.append((args, kwargs))
        return self

    def destroy(self):
        self.destroyed = True


class _FakePanel:
    def __init__(self):
        self.children = []

    def winfo_children(self):
        return list(self.children)


def _patch_threshold_widgets(monkeypatch):
    import types
    import vflow.ui.gate_manager as gm

    monkeypatch.setattr(gm.tk, 'BooleanVar', _FakeBoolVar)
    fake_ttk = types.SimpleNamespace(
        Label=_FakeWidget,
        Frame=_FakeWidget,
        Checkbutton=_FakeWidget,
    )
    monkeypatch.setattr(gm, 'ttk', fake_ttk)


def test_threshold_panel_persists_missing_multi_y_boolean_vars(monkeypatch):
    _patch_threshold_widgets(monkeypatch)
    gate = {
        'name': 'G', 'type': 'crosshair', 'x_boundaries': [],
        'y_boundary': None, 'y_boundaries': [1.0, 2.0],
        'y_thresh_vars': [_FakeBoolVar(False)],
    }
    app = FlowApp.__new__(FlowApp)
    app.thresh_panel = _FakePanel()
    app._sel_gate = lambda: gate
    app._on_thresh_toggle = lambda: None

    app._rebuild_thresh_panel()

    assert len(gate['y_thresh_vars']) == 2
    assert gate['y_thresh_vars'][0].get() is False
    assert gate['y_thresh_vars'][1].get() is True


def test_threshold_panel_persists_missing_single_y_boolean_var(monkeypatch):
    _patch_threshold_widgets(monkeypatch)
    gate = {
        'name': 'G', 'type': 'crosshair', 'x_boundaries': [],
        'y_boundary': 3.0, 'y_boundaries': None,
    }
    app = FlowApp.__new__(FlowApp)
    app.thresh_panel = _FakePanel()
    app._sel_gate = lambda: gate
    app._on_thresh_toggle = lambda: None

    app._rebuild_thresh_panel()

    assert isinstance(gate['y_thresh_var'], _FakeBoolVar)
    assert gate['y_thresh_var'].get() is True


def test_threshold_panel_persists_missing_multi_x_boolean_vars(monkeypatch):
    _patch_threshold_widgets(monkeypatch)
    gate = {
        'name': 'G', 'type': 'crosshair', 'x_boundaries': [4.0, 5.0],
        'y_boundary': None, 'y_boundaries': None,
        'x_thresh_vars': [],
    }
    app = FlowApp.__new__(FlowApp)
    app.thresh_panel = _FakePanel()
    app._sel_gate = lambda: gate
    app._on_thresh_toggle = lambda: None

    app._rebuild_thresh_panel()

    assert len(gate['x_thresh_vars']) == 2
    assert [v.get() for v in gate['x_thresh_vars']] == [True, True]
