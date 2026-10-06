from vflow.legacy.vflow_app import FlowApp
from vflow.ui.flow_app_shell import FlowAppShellBase


EXTRACTED_UI_METHODS = {
    'toggle_theme',
    '_apply_theme_to_tk_widgets',
    '_build_ui',
    '_section',
    '_lbl',
    '_btn',
    '_scale_w',
    '_build_controls',
    '_build_plot',
    '_build_status_bar',
    '_setup_axes',
}

SCIENTIFIC_AND_APPLICATION_METHODS = {
    '_load_paths',
    '_gate_mask_for',
    '_analysis_context_changed',
    '_transform_xy',
    'refresh_plot',
    '_finish_gate',
    '_compute_gate_stats_for',
    'save_gates',
    'load_gates',
    'batch_export_stats',
    'export_gated_data',
}


def test_flow_app_inherits_extracted_ui_shell():
    assert FlowApp.__mro__[1] is FlowAppShellBase


def test_extracted_ui_methods_are_owned_only_by_shell_base():
    for name in EXTRACTED_UI_METHODS:
        assert name in FlowAppShellBase.__dict__, name
        assert name not in FlowApp.__dict__, name
        assert getattr(FlowApp, name) is getattr(FlowAppShellBase, name)


def test_scientific_and_application_methods_remain_on_flow_app():
    for name in SCIENTIFIC_AND_APPLICATION_METHODS:
        assert name in FlowApp.__dict__, name


def test_flow_app_shell_has_no_scientific_gate_or_export_methods():
    forbidden = {
        '_gate_mask_for', '_transform_xy', '_finish_gate',
        '_compute_gate_stats_for', 'save_gates', 'load_gates',
        'batch_export_stats', 'export_gated_data',
    }
    assert forbidden.isdisjoint(FlowAppShellBase.__dict__)
