from vflow.app.dataset import DatasetState
from vflow.legacy.vflow_app import FlowApp


def test_dataset_state_defaults_are_independent_mutable_mappings():
    a = DatasetState()
    b = DatasetState()
    a.loaded_files['a.csv'] = object()
    a.excluded_files['x.csv'] = None
    assert b.loaded_files == {}
    assert b.excluded_files == {}


def test_flowapp_loaded_files_property_preserves_mapping_identity():
    app = FlowApp.__new__(FlowApp)
    mapping = {'a.csv': object()}
    app.loaded_files = mapping
    assert app.loaded_files is mapping
    assert app.__dict__['_dataset_state'].loaded_files is mapping


def test_flowapp_excluded_files_property_preserves_mapping_identity():
    app = FlowApp.__new__(FlowApp)
    mapping = {'excluded.csv': None}
    app.excluded_files = mapping
    assert app.excluded_files is mapping
    assert app.__dict__['_dataset_state'].excluded_files is mapping


def test_flowapp_dataset_properties_lazy_initialize_for_headless_harnesses():
    app = FlowApp.__new__(FlowApp)
    assert app.loaded_files == {}
    assert app.excluded_files == {}
    app.loaded_files['a.csv'] = 'df-a'
    app.excluded_files['b.csv'] = None
    assert app._dataset_state_obj().loaded_files == {'a.csv': 'df-a'}
    assert app._dataset_state_obj().excluded_files == {'b.csv': None}


def test_dataset_state_inherits_exclusions_by_shallow_mapping_copy():
    from vflow.app.dataset import DatasetState

    df_marker = object()
    source = {'a.csv': df_marker}
    state = DatasetState()
    state.inherit_excluded_files(source)
    assert state.excluded_files == source
    assert state.excluded_files is not source
    assert state.excluded_files['a.csv'] is df_marker
    source['b.csv'] = object()
    assert 'b.csv' not in state.excluded_files


def test_dataset_state_commit_loaded_file_preserves_value_identity():
    state = DatasetState()
    marker = object()
    state.commit_loaded_file('a.csv', marker)
    assert state.loaded_files['a.csv'] is marker


def test_dataset_state_exclude_loaded_file_moves_value_and_fails_closed():
    marker = object()
    state = DatasetState(loaded_files={'a.csv': marker})
    assert state.exclude_loaded_file('missing.csv') is False
    assert state.exclude_loaded_file('a.csv') is True
    assert state.loaded_files == {}
    assert state.excluded_files['a.csv'] is marker


def test_dataset_state_restore_excluded_file_preserves_none_placeholder_semantics():
    marker = object()
    state = DatasetState(excluded_files={'a.csv': marker, 'placeholder.csv': None})
    found, restored = state.restore_excluded_file('a.csv')
    assert found is True and restored is marker
    assert state.loaded_files['a.csv'] is marker

    found, restored = state.restore_excluded_file('placeholder.csv')
    assert found is True and restored is None
    assert 'placeholder.csv' not in state.loaded_files
    assert 'placeholder.csv' not in state.excluded_files

    assert state.restore_excluded_file('missing.csv') == (False, None)


def test_dataset_state_register_unloaded_exclusion_is_non_destructive():
    marker = object()
    state = DatasetState(excluded_files={'a.csv': marker})
    assert state.register_unloaded_exclusion('a.csv') is False
    assert state.excluded_files['a.csv'] is marker
    assert state.register_unloaded_exclusion('b.csv') is True
    assert state.excluded_files['b.csv'] is None


def test_dataset_state_clear_files_clears_mappings_in_place():
    loaded = {'a.csv': object()}
    excluded = {'b.csv': None}
    state = DatasetState(loaded_files=loaded, excluded_files=excluded)
    state.clear_files()
    assert state.loaded_files is loaded
    assert state.excluded_files is excluded
    assert loaded == {}
    assert excluded == {}
