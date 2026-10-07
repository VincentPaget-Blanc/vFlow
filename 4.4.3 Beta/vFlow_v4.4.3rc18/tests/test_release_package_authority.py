from vflow.config.styles import _apply_ttk_style
from vflow.config.themes import THEMES
from vflow.core.auto_gate import derivative_threshold, gmm_thresholds, otsu_threshold
from vflow.core.cache_keys import gate_signature
from vflow.core.fcs_reader import read_fcs
from vflow.plotting.utils import get_rng, hex_to_rgba, set_spines_color
from vflow.ui.batch_stats_dialog import BatchStatsDialog
from vflow.ui.folder_scan_dialog import FolderScanDialog
from vflow.legacy import vflow_app as app


def test_packaged_application_uses_extracted_runtime_authorities():
    assert app.THEMES is THEMES
    assert app._apply_ttk_style is _apply_ttk_style
    assert app.read_fcs is read_fcs
    assert app.gmm_thresholds is gmm_thresholds
    assert app.derivative_threshold is derivative_threshold
    assert app.otsu_threshold is otsu_threshold
    assert app._gate_sig is gate_signature
    assert app._hex_to_rgba is hex_to_rgba
    assert app._get_rng is get_rng
    assert app._set_spines_color is set_spines_color
    assert app.FolderScanDialog is FolderScanDialog
    assert app.BatchStatsDialog is BatchStatsDialog


def test_release_hardening_api_surface_is_present():
    required = {
        "_bind_gate_context",
        "_gate_context_matches",
        "_plain_gate_snapshot",
        "_regions_in_explicit_context",
        "_restrict_regions_to_valid",
        "_validate_gate_context_payload",
        "_invalidate_analysis_caches",
        "_analysis_context_changed",
        "_kde_valley_supported",
        "_gate_selector_labels",
        "_gate_from_selector",
    }
    missing = sorted(name for name in required if not callable(getattr(app.FlowApp, name, None)))
    assert missing == []
