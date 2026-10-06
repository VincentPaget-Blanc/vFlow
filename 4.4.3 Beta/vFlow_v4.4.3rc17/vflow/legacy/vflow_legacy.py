"""Compatibility surface for the packaged vFlow application.

Pure helpers are exported from their extracted modules. UI classes are loaded
lazily from the packaged application module so importing this module stays
headless-safe.
"""

from __future__ import annotations


_UI_NAMES = {
    "BatchPlotWindow",
    "FlowApp",
    "FlowTabManager",
    "PolarAnalysisWindow",
}
_EXTRACTED_UI_NAMES = {"BatchStatsDialog", "FolderScanDialog"}
_AUTO_GATE_NAMES = {"derivative_threshold", "gmm_thresholds", "otsu_threshold"}
_FCS_READER_NAMES = {"read_fcs"}


def _legacy_module():
    from vflow.main import _load_legacy_module

    return _load_legacy_module()


def __getattr__(name: str):
    if name in _EXTRACTED_UI_NAMES:
        if name == "BatchStatsDialog":
            from vflow.ui.batch_stats_dialog import BatchStatsDialog

            return BatchStatsDialog
        if name == "FolderScanDialog":
            from vflow.ui.folder_scan_dialog import FolderScanDialog

            return FolderScanDialog
    if name in _UI_NAMES:
        return getattr(_legacy_module(), name)
    if name in _AUTO_GATE_NAMES:
        from vflow.core import auto_gate

        return getattr(auto_gate, name)
    if name in _FCS_READER_NAMES:
        from vflow.core import fcs_reader

        return getattr(fcs_reader, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BatchPlotWindow",
    "BatchStatsDialog",
    "FlowApp",
    "FlowTabManager",
    "FolderScanDialog",
    "PolarAnalysisWindow",
    "read_fcs",
    "gmm_thresholds",
    "derivative_threshold",
    "otsu_threshold",
]
