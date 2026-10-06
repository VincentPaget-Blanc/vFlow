from vflow.app.cache import AnalysisCache
from vflow.app.dataset import DatasetState
from vflow.app.session import ApplicationSession
from vflow.app.state import AnalysisState
from vflow.legacy.vflow_app import FlowApp


def test_application_session_components_are_independent_between_instances():
    a = ApplicationSession()
    b = ApplicationSession()
    a.analysis.x_channel = 'X'
    a.dataset.loaded_files['a.csv'] = object()
    a.cache.transforms['k'] = object()
    assert b.analysis.x_channel is None
    assert b.dataset.loaded_files == {}
    assert b.cache.transforms == {}


def test_flowapp_legacy_helpers_share_one_application_session_owner():
    app = FlowApp.__new__(FlowApp)
    analysis = app._analysis_state_obj()
    dataset = app._dataset_state_obj()
    cache = app._analysis_cache_obj()
    session = app.__dict__['_app_session']
    assert analysis is session.analysis
    assert dataset is session.dataset
    assert cache is session.cache
    # Compatibility aliases remain available for regression harnesses and
    # staged callers that inspect the old private holders directly.
    assert app.__dict__['_analysis_state'] is analysis
    assert app.__dict__['_dataset_state'] is dataset
    assert app.__dict__['_analysis_cache'] is cache


def test_application_session_adopts_preexisting_legacy_component_objects():
    app = FlowApp.__new__(FlowApp)
    analysis = AnalysisState(x_channel='LegacyX')
    dataset = DatasetState(loaded_files={'a.csv': 'df'})
    cache = AnalysisCache(transforms={'k': 'v'})
    app.__dict__['_analysis_state'] = analysis
    app.__dict__['_dataset_state'] = dataset
    app.__dict__['_analysis_cache'] = cache
    session = app._app_session_obj()
    assert session.analysis is analysis
    assert session.dataset is dataset
    assert session.cache is cache
    assert app.x_channel == 'LegacyX'
    assert app.loaded_files == {'a.csv': 'df'}
    assert app._tc == {'k': 'v'}
