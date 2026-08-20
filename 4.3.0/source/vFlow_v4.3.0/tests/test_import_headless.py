import importlib
import sys

import pytest

from vflow.backends import configure_matplotlib_backend


def test_package_import_does_not_require_matplotlib():
    import vflow

    assert vflow.__version__ == "4.3.0"


def test_package_imports_headlessly():
    pytest.importorskip("matplotlib")
    configure_matplotlib_backend(headless=True)

    import vflow

    assert vflow.__version__ == "4.3.0"


def test_core_modules_import_without_tk_root():
    pytest.importorskip("matplotlib")
    configure_matplotlib_backend(headless=True)

    assert importlib.import_module("vflow.core.auto_gate")
    assert importlib.import_module("vflow.core.fcs_reader")


def test_legacy_compat_module_imports_headlessly():
    sys.modules.pop("vflow.legacy.vflow_app", None)
    sys.modules.pop("vflow.core.fcs_reader", None)

    legacy = importlib.import_module("vflow.legacy.vflow_legacy")

    assert "read_fcs" in legacy.__all__
    assert "gmm_thresholds" in legacy.__all__
    assert "derivative_threshold" in legacy.__all__
    assert "otsu_threshold" in legacy.__all__
    assert "vflow.legacy.vflow_app" not in sys.modules
    assert "vflow.core.fcs_reader" not in sys.modules


def test_legacy_package_imports_headlessly_without_loading_legacy_app():
    sys.modules.pop("vflow.legacy.vflow_app", None)

    legacy = importlib.import_module("vflow.legacy")

    assert "read_fcs" in legacy.__all__
    assert "gmm_thresholds" in legacy.__all__
    assert "derivative_threshold" in legacy.__all__
    assert "otsu_threshold" in legacy.__all__
    assert "FlowApp" in legacy.__all__
    assert "vflow.legacy.vflow_app" not in sys.modules


def test_legacy_folder_scan_dialog_uses_extracted_class_without_legacy_app():
    sys.modules.pop("vflow.legacy.vflow_app", None)

    legacy = importlib.import_module("vflow.legacy.vflow_legacy")
    from vflow.ui.folder_scan_dialog import FolderScanDialog

    assert legacy.FolderScanDialog is FolderScanDialog
    assert "vflow.legacy.vflow_app" not in sys.modules


def test_legacy_batch_stats_dialog_uses_extracted_class_without_legacy_app():
    sys.modules.pop("vflow.legacy.vflow_app", None)

    legacy = importlib.import_module("vflow.legacy.vflow_legacy")
    from vflow.ui.batch_stats_dialog import BatchStatsDialog

    assert legacy.BatchStatsDialog is BatchStatsDialog
    assert "vflow.legacy.vflow_app" not in sys.modules


def test_ui_proxy_modules_import_without_loading_legacy_app():
    sys.modules.pop("vflow.legacy.vflow_app", None)
    had_pandas = "pandas" in sys.modules

    assert importlib.import_module("vflow.ui")
    assert importlib.import_module("vflow.ui.app")
    assert importlib.import_module("vflow.ui.batch_plot_window")
    batch_stats_module = importlib.import_module("vflow.ui.batch_stats_dialog")
    folder_module = importlib.import_module("vflow.ui.folder_scan_dialog")
    assert importlib.import_module("vflow.ui.polar_analysis_window")
    assert importlib.import_module("vflow.ui.tab_manager")
    assert batch_stats_module.BatchStatsDialog.__name__ == "BatchStatsDialog"
    assert folder_module.FolderScanDialog.__name__ == "FolderScanDialog"
    assert "vflow.legacy.vflow_app" not in sys.modules
    if not had_pandas:
        assert "pandas" not in sys.modules


def test_legacy_loader_reuses_standard_packaged_module():
    from vflow import main

    sys.modules.pop(main.LEGACY_MODULE_NAME, None)
    first = main._load_legacy_module()
    second = main._load_legacy_module()

    assert first is second
    assert first.__name__ == "vflow.legacy.vflow_app"


def test_ui_proxy_symbols_resolve_through_packaged_legacy_module():
    from vflow import main

    sys.modules.pop(main.LEGACY_MODULE_NAME, None)

    from vflow.ui.app import FlowApp
    from vflow.ui.batch_plot_window import BatchPlotWindow
    from vflow.ui.tab_manager import FlowTabManager

    module = sys.modules[main.LEGACY_MODULE_NAME]
    assert FlowApp is module.FlowApp
    assert BatchPlotWindow is module.BatchPlotWindow
    assert FlowTabManager is module.FlowTabManager

