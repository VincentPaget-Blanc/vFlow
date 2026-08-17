import inspect

import numpy as np
import pandas as pd

from vflow.app.session import ApplicationSession
from vflow.legacy.vflow_app import FlowApp
from vflow.nomenclature.channel_names import (
    channel_relation,
    discover_channel_schema,
    extract_channel_from_template,
)
from vflow.nomenclature.session import ChannelAliasSession
from vflow.ui.axis_name_resolver import AxisNameResolverDialog
from vflow.ui.file_list import FileListPresentationMixin
from vflow.ui.flow_app_shell import FlowAppShellBase
from vflow.ui.tab_manager import FlowTabManagerBase


class FakeVar:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _channel_app():
    app = FlowApp.__new__(FlowApp)
    app.loaded_files = {
        'canonical.csv': pd.DataFrame({
            'Intensity_VGLUT1-Venus': [1.0, 2.0],
            'Bkgd_Corr_Intensity_VGLUT1-Venus': [3.0, 4.0],
            'X_VGLUT1-Venus_microns': [5.0, 6.0],
            'Y_VGLUT1-Venus_microns': [7.0, 8.0],
            'Intensity_D1R': [9.0, 10.0],
        }),
        'variant.csv': pd.DataFrame({
            'Intensity_VGLUT1_Venus': [11.0, 12.0],
            'Bkgd_Corr_Intensity_VGLUT1_Venus': [13.0, 14.0],
            'X_VGLUT1_Venus_microns': [15.0, 16.0],
            'Y_VGLUT1_Venus_microns': [17.0, 18.0],
            'Intensity_D1R': [19.0, 20.0],
        }),
    }
    app.excluded_files = {}
    return app


def test_multitoken_channel_is_preserved_by_exact_template_extraction():
    schema = discover_channel_schema([
        'Intensity_VGLUT1_Venus',
        'X_VGLUT1_Venus_microns',
        'Y_VGLUT1_Venus_microns',
    ])
    assert 'VGLUT1_Venus' in schema
    assert extract_channel_from_template(
        'Intensity_VGLUT1_Venus', 'Intensity_{channel}') == 'VGLUT1_Venus'
    assert channel_relation('VGLUT1-Venus', 'VGLUT1_Venus') == 'separator only'


def test_selected_main_channel_finds_full_variant_but_not_coexisting_d1r():
    app = _channel_app()
    variants = app._channel_variants_for_canonical('VGLUT1-Venus')
    assert 'VGLUT1_Venus' in variants
    assert variants['VGLUT1_Venus']['templates'] == {
        'Intensity_{channel}',
        'Bkgd_Corr_Intensity_{channel}',
        'X_{channel}_microns',
        'Y_{channel}_microns',
    }

    dlg = AxisNameResolverDialog.__new__(AxisNameResolverDialog)
    dlg.app = app
    dlg.main_var = FakeVar('VGLUT1-Venus')
    dlg.show_conflicts_var = FakeVar(False)
    names = [row[0] for row in dlg._variant_rows()]
    assert 'VGLUT1_Venus' in names
    assert 'D1R' not in names


def test_alias_session_renames_labels_only_and_protects_collisions():
    source = pd.DataFrame({'Intensity_vGAT': [1.25, 2.5], 'Other': [3, 4]})
    before = source.to_numpy(copy=True)
    session = ChannelAliasSession({'Intensity_vGAT': 'Intensity_VGAT'})
    renamed, details = session.apply_to_dataframe(source)
    assert list(renamed.columns) == ['Intensity_VGAT', 'Other']
    np.testing.assert_array_equal(renamed.to_numpy(), before)
    assert details['renamed'] == {'Intensity_vGAT': 'Intensity_VGAT'}

    collision = pd.DataFrame({
        'Intensity_vGAT': [1],
        'Intensity_VGAT': [2],
    })
    protected, details = session.apply_to_dataframe(collision)
    assert list(protected.columns) == list(collision.columns)
    assert details['renamed'] == {}
    assert details['ambiguous']


def test_confirmed_channel_mapping_updates_exact_family_only():
    app = FlowApp.__new__(FlowApp)
    variant = pd.DataFrame({
        'Intensity_vGAT': [1.0, 2.0],
        'Bkgd_Corr_Intensity_vGAT': [3.0, 4.0],
        'X_vGAT_microns': [5.0, 6.0],
        'Y_vGAT_microns': [7.0, 8.0],
        'Unrelated_vGAT_suffix': [9.0, 10.0],
    })
    app.loaded_files = {
        'canonical.csv': pd.DataFrame({
            'Intensity_VGAT': [10.0],
            'Bkgd_Corr_Intensity_VGAT': [11.0],
            'X_VGAT_microns': [12.0],
            'Y_VGAT_microns': [13.0],
        }),
        'variant.csv': variant.copy(),
    }
    app.excluded_files = {}
    app.x_channel = 'Intensity_vGAT'
    app.y_channel = 'X_vGAT_microns'
    app.x_var = FakeVar(app.x_channel)
    app.y_var = FakeVar(app.y_channel)
    app.status_var = FakeVar('')
    app._on_active_files_changed = lambda: None

    result = app._apply_channel_mapping('VGAT', ['vGAT'])
    got = app.loaded_files['variant.csv']
    assert result['renamed_columns'] == 4
    assert 'Intensity_VGAT' in got
    assert 'Bkgd_Corr_Intensity_VGAT' in got
    assert 'X_VGAT_microns' in got
    assert 'Y_VGAT_microns' in got
    assert 'Unrelated_vGAT_suffix' in got
    np.testing.assert_array_equal(got.to_numpy(), variant.to_numpy())
    assert app.x_channel == 'Intensity_VGAT'
    assert app.y_channel == 'X_VGAT_microns'


def test_subgate_seed_inherits_axis_aliases_even_before_data_registration():
    class FakeAnalysis:
        def set_population_context(self, **kwargs):
            self.kwargs = kwargs

    class FakeApp:
        def __init__(self):
            self.analysis = FakeAnalysis()
            self.axis_aliases = {}
            self.loaded_files = {}

        def _analysis_state_obj(self):
            return self.analysis

    app = FakeApp()
    FlowTabManagerBase._load_filtered(
        app, {}, None, None,
        axis_aliases={'Intensity_vGAT': 'Intensity_VGAT'})
    assert app.axis_aliases == {'Intensity_vGAT': 'Intensity_VGAT'}


def test_port_source_contracts_are_wired_into_refactored_ui_seams():
    shell = inspect.getsource(FlowAppShellBase._build_ui)
    assert 'tk.PanedWindow' in shell
    assert "sashcursor='sb_h_double_arrow'" in shell
    assert '_resize_sidebar_window' in shell
    assert 'Resolve Channel / Axis Names…' not in shell  # control lives in _build_controls
    controls = inspect.getsource(FlowAppShellBase._build_controls)
    assert 'Resolve Channel / Axis Names…' in controls

    file_row = inspect.getsource(FileListPresentationMixin._add_file_row)
    excluded = inspect.getsource(FileListPresentationMixin._rebuild_excluded_list)
    assert '_bind_file_context_menu(widget, path)' in file_row
    assert '_bind_file_context_menu(widget, path)' in excluded


def test_load_and_batch_raw_rereads_apply_aliases_before_schema_use():
    from vflow.controllers.project_data_load_coordinator import ProjectDataLoadCoordinator

    load_src = inspect.getsource(ProjectDataLoadCoordinator.load_paths)
    assert load_src.index('_read_data_file(path)') < load_src.index('apply_aliases(df, path)')
    assert load_src.index('apply_aliases(df, path)') < load_src.index('plan_loaded_frame(')
    assert 'h.axis_aliases.update(frame_plan.rename_map)' in load_src

    batch_src = inspect.getsource(FlowApp.batch_export_stats)
    assert batch_src.index('_read_data_file(fpath)') < batch_src.index(
        '_apply_axis_aliases_to_df(df, fpath)')
    assert batch_src.index('_apply_axis_aliases_to_df(df, fpath)') < batch_src.index(
        '_normalize_columns_to_loaded(df)')


def test_schema_report_refuses_to_claim_unique_reference_on_tie():
    app = FlowApp.__new__(FlowApp)
    app.loaded_files = {
        'a.csv': pd.DataFrame({'A': [1], 'B': [2]}),
        'b.csv': pd.DataFrame({'A': [3], 'C': [4]}),
    }
    app.excluded_files = {}
    report = app._schema_resolution_report()
    assert report['reference_unique'] is False
    assert report['dominant_tie_count'] == 2
    assert report['reference_count'] == 1
    assert len(report['unresolved']) == 1


def test_file_manager_labels_are_platform_specific():
    from vflow.platform.file_reveal import file_manager_label

    assert file_manager_label(platform='darwin', os_name='posix') == 'Show in Finder'
    assert file_manager_label(platform='win32', os_name='nt') == 'Show in Explorer'
    assert file_manager_label(platform='linux', os_name='posix') == 'Show in File Manager'


def test_reveal_service_builds_native_commands_without_modifying_file(tmp_path, monkeypatch):
    import vflow.platform.file_reveal as reveal

    source = tmp_path / 'sample.csv'
    source.write_text('x\n1\n')
    popen_calls = []
    run_calls = []

    class DummyProc:
        returncode = 0

    monkeypatch.setattr(reveal.subprocess, 'Popen',
                        lambda args, **kwargs: popen_calls.append(args) or DummyProc())
    monkeypatch.setattr(reveal.subprocess, 'run',
                        lambda args, **kwargs: run_calls.append(args) or DummyProc())

    assert reveal.reveal_paths([str(source)], platform='darwin', os_name='posix')
    assert popen_calls[-1][:2] == ['open', '-R']
    assert popen_calls[-1][2] == str(source.resolve())
    assert source.exists()

    popen_calls.clear()
    assert reveal.reveal_paths([str(source)], platform='win32', os_name='nt')
    assert popen_calls[-1] == ['explorer', f'/select,{source.resolve()}']
    assert source.exists()

    popen_calls.clear(); run_calls.clear()
    assert reveal.reveal_paths([str(source)], platform='linux', os_name='posix')
    assert run_calls and 'org.freedesktop.FileManager1.ShowItems' in run_calls[-1]
    assert popen_calls == []  # successful DBus reveal needs no fallback opener
    assert source.exists()


def test_unload_removes_analysis_entry_but_never_source_file(tmp_path):
    source = tmp_path / 'unresolved.csv'
    source.write_text('A,B\n1,2\n')

    class EmptyFrame:
        def winfo_children(self):
            return []

    app = FlowApp.__new__(FlowApp)
    path = str(source)
    app.loaded_files = {path: pd.DataFrame({'A': [1], 'B': [2]})}
    app.excluded_files = {}
    app.file_vars = {path: FakeVar(True)}
    app.file_colors = {path: '#fff'}
    app.file_list_frame = EmptyFrame()
    app.status_var = FakeVar('')
    app._add_file_row = lambda _p: None
    app._invalidate_analysis_caches = lambda **_kw: None
    app._on_active_files_changed = lambda: None

    assert app._unload_paths([path]) == 1
    assert path not in app.loaded_files
    assert path not in app.file_vars
    assert path not in app.file_colors
    assert source.exists()
    assert source.read_text() == 'A,B\n1,2\n'


def test_case_only_load_normalization_is_persisted_for_raw_rereads(tmp_path):
    first = tmp_path / 'first.csv'
    second = tmp_path / 'second.csv'
    first.write_text('Intensity_VGAT,Other\n1,2\n')
    second.write_text('Intensity_vgat,Other\n3,4\n')

    app = FlowApp.__new__(FlowApp)
    app.loaded_files = {}
    app.excluded_files = {}
    app.file_vars = {}
    app.file_colors = {}
    app._data_generation = 0
    app.status_var = FakeVar('')
    app.root = object()
    app._add_file_row = lambda p: app.file_vars.setdefault(p, FakeVar(True))
    app._update_channel_menus = lambda: setattr(app, '_col_mismatch_msg', '')
    app._on_active_files_changed = lambda: None
    app._offer_axis_name_resolution = lambda: None

    FlowApp._load_paths(app, [str(first), str(second)])
    assert 'Intensity_VGAT' in app.loaded_files[str(second)].columns
    assert app.axis_aliases['Intensity_vgat'] == 'Intensity_VGAT'

    reread = FlowApp._read_data_file(str(second))
    reread, details = app._apply_axis_aliases_to_df(reread, str(second))
    assert details['renamed'] == {'Intensity_vgat': 'Intensity_VGAT'}
    assert reread['Intensity_VGAT'].tolist() == [3]


def test_unambiguous_relabel_preserves_gate_context_and_membership():
    app = FlowApp.__new__(FlowApp)
    app.loaded_files = {
        'canonical.csv': pd.DataFrame({'Intensity_VGAT': [0.5, 2.0], 'Y': [0.5, 2.0]}),
        'variant.csv': pd.DataFrame({'Intensity_vGAT': [0.5, 2.0], 'Y': [0.5, 2.0]}),
    }
    app.excluded_files = {}
    app.x_channel = 'Intensity_vGAT'
    app.y_channel = 'Y'
    app.x_scale = 'linear'
    app.y_scale = 'linear'
    app.cofactor = 150.0
    app.x_var = FakeVar(app.x_channel)
    app.y_var = FakeVar(app.y_channel)
    app.status_var = FakeVar('')
    app.parent_gate = None
    app.population_lineage = []
    gate = {
        'id': 1, 'name': 'R', 'type': 'rectangle', 'applied': True,
        'color': '#fff', 'x0': 0.0, 'x1': 1.0, 'y0': 0.0, 'y1': 1.0,
    }
    app.gates = [gate]
    app._bind_gate_context(gate)
    before_ctx = dict(gate['_analysis_context'])
    x = app.loaded_files['variant.csv']['Intensity_vGAT'].to_numpy()
    y = app.loaded_files['variant.csv']['Y'].to_numpy()
    before_regions, _ = app._gate_mask_for(gate, x, y)
    before_masks = {k: v.copy() for k, v in before_regions.items()}

    app._on_active_files_changed = lambda: None
    result = app._apply_axis_mapping('Intensity_VGAT', ['Intensity_vGAT'])

    assert result['ambiguous_files'] == []
    assert before_ctx['x_channel'] == 'Intensity_vGAT'
    assert gate['_analysis_context']['x_channel'] == 'Intensity_VGAT'
    assert app.x_channel == 'Intensity_VGAT'
    assert app._gate_context_matches(gate)
    x2 = app.loaded_files['variant.csv']['Intensity_VGAT'].to_numpy()
    after_regions, _ = app._gate_mask_for(gate, x2, y)
    for name in before_masks:
        np.testing.assert_array_equal(before_masks[name], after_regions[name])


def test_sixty_file_strict_intersection_and_explicit_resolution(monkeypatch):
    from vflow.legacy import vflow_app as legacy

    app = FlowApp.__new__(FlowApp)
    app.loaded_files = {
        f'canonical_{i:02d}.csv': pd.DataFrame({
            'Intensity_VGAT': [float(i)], 'Shared': [float(i + 1)]})
        for i in range(59)
    }
    app.loaded_files['variant.csv'] = pd.DataFrame(
        {'Intensity_vGAT': [99.0], 'Shared': [100.0]})
    app.excluded_files = {}
    app.file_vars = {p: FakeVar(True) for p in app.loaded_files}
    app.x_menu = {}; app.y_menu = {}
    app.x_var = FakeVar(); app.y_var = FakeVar()
    app.x_channel = None; app.y_channel = None
    app.status_var = FakeVar('')
    app._on_active_files_changed = lambda: None

    app._update_channel_menus()
    assert 'Shared' in app.x_menu['values']
    assert 'Intensity_VGAT' not in app.x_menu['values']
    assert app._first_channel_resolution_candidate() == 'VGAT'

    result = app._apply_channel_mapping('VGAT', ['vGAT'])
    assert result['ambiguous_files'] == []
    app._update_channel_menus()
    assert 'Intensity_VGAT' in app.x_menu['values']
    assert app._schema_resolution_report()['unresolved'] == []

    # High file count alone must never trigger the resolver prompt.
    monkeypatch.setattr(legacy.messagebox, 'askyesno',
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError('resolver prompt should not appear')))
    app._axis_resolution_prompt_signature = None
    app._offer_axis_name_resolution()


def test_multitoken_space_and_short_suffix_candidates_keep_literal_channel_slot():
    app = FlowApp.__new__(FlowApp)
    app.loaded_files = {
        'canonical.csv': pd.DataFrame({
            'Intensity_VGLUT1-Venus': [1],
            'X_VGLUT1-Venus_microns': [2],
            'Y_VGLUT1-Venus_microns': [3],
        }),
        'underscore.csv': pd.DataFrame({
            'Intensity_VGLUT1_Venus': [4],
            'X_VGLUT1_Venus_microns': [5],
            'Y_VGLUT1_Venus_microns': [6],
        }),
        'space.csv': pd.DataFrame({
            'Intensity_VGLUT1 Venus': [7],
            'X_VGLUT1 Venus_microns': [8],
            'Y_VGLUT1 Venus_microns': [9],
        }),
        'short.csv': pd.DataFrame({
            'Intensity_Venus': [10],
            'X_Venus_microns': [11],
            'Y_Venus_microns': [12],
        }),
    }
    app.excluded_files = {}
    variants = app._channel_variants_for_canonical('VGLUT1-Venus')
    assert 'VGLUT1_Venus' in variants
    assert 'VGLUT1 Venus' in variants
    assert 'Venus' in variants
    assert channel_relation('VGLUT1-Venus', 'VGLUT1 Venus') == 'separator only'
    assert channel_relation('VGLUT1-Venus', 'Venus') == 'partial/suffix'


def test_two_aliases_to_one_absent_target_are_protected_as_ambiguous():
    session = ChannelAliasSession({'A_alias': 'A', 'A-other': 'A'})
    df = pd.DataFrame({'A_alias': [1], 'A-other': [2], 'B': [3]})
    out, details = session.apply_to_dataframe(df)
    assert list(out.columns) == list(df.columns)
    assert details['renamed'] == {}
    assert details['ambiguous']


def test_unresolved_workflow_converges_from_five_to_two_structural_outliers():
    app = FlowApp.__new__(FlowApp)
    app.loaded_files = {}
    for i in range(55):
        app.loaded_files[f'canonical_{i}.csv'] = pd.DataFrame({
            'Intensity_VGAT': [i], 'Bkgd_Corr_Intensity_VGAT': [i + 1],
            'Shared': [i + 2]})
    for i in range(3):
        app.loaded_files[f'variant_{i}.csv'] = pd.DataFrame({
            'Intensity_vGAT': [i], 'Bkgd_Corr_Intensity_vGAT': [i + 1],
            'Shared': [i + 2]})
    app.loaded_files['structural_missing.csv'] = pd.DataFrame({
        'Intensity_VGAT': [1], 'Shared': [2]})
    app.loaded_files['structural_extra.csv'] = pd.DataFrame({
        'Intensity_VGAT': [1], 'Bkgd_Corr_Intensity_VGAT': [2],
        'Shared': [3], 'Genuine_Extra': [4]})
    app.excluded_files = {}
    app.x_channel = None; app.y_channel = None
    app.x_var = FakeVar(); app.y_var = FakeVar(); app.status_var = FakeVar('')
    app._on_active_files_changed = lambda: None

    before = app._schema_resolution_report()
    assert before['reference_unique'] is True
    assert before['reference_count'] == 55
    assert len(before['unresolved']) == 5

    app._apply_channel_mapping('VGAT', ['vGAT'])
    after = app._schema_resolution_report()
    assert after['reference_count'] == 58
    assert len(after['unresolved']) == 2
    by_name = {item['path']: item for item in after['unresolved']}
    assert by_name['structural_missing.csv']['missing'] == [
        'Bkgd_Corr_Intensity_VGAT']
    assert by_name['structural_extra.csv']['extra'] == ['Genuine_Extra']


def test_alias_session_clear_resets_mappings_and_prompt_signature():
    session = ChannelAliasSession({'old': 'new'}, prompt_signature=('schema', 1))
    session.clear()
    assert session.aliases == {}
    assert session.prompt_signature is None


def test_resolver_prompt_respects_checked_active_files(monkeypatch):
    from vflow.legacy import vflow_app as legacy

    app = FlowApp.__new__(FlowApp)
    app.loaded_files = {
        'a.csv': pd.DataFrame({'Intensity_VGAT': [1], 'Shared': [2]}),
        'b.csv': pd.DataFrame({'Intensity_VGAT': [3], 'Shared': [4]}),
        'inactive_variant.csv': pd.DataFrame({'Intensity_vGAT': [5], 'Shared': [6]}),
    }
    app.excluded_files = {}
    app.file_vars = {
        'a.csv': FakeVar(True), 'b.csv': FakeVar(True),
        'inactive_variant.csv': FakeVar(False),
    }
    app._axis_resolution_prompt_signature = None
    monkeypatch.setattr(legacy.messagebox, 'askyesno',
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError('inactive file must not trigger resolver')))
    app._offer_axis_name_resolution()


def test_linux_reveal_falls_back_to_containing_folder_when_dbus_unavailable(
        tmp_path, monkeypatch):
    import vflow.platform.file_reveal as reveal

    source = tmp_path / 'sample.csv'
    source.write_text('x\n1\n')
    calls = []

    class FailedRun:
        returncode = 1

    monkeypatch.setattr(reveal.subprocess, 'run', lambda *a, **k: FailedRun())
    monkeypatch.setattr(reveal.subprocess, 'Popen',
                        lambda args, **kwargs: calls.append(args) or object())
    assert reveal.reveal_paths([str(source)], platform='linux', os_name='posix')
    assert calls == [['xdg-open', str(tmp_path.resolve())]]
    assert source.exists()
