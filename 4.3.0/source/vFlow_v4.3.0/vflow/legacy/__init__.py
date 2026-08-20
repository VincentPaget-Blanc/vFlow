"""Compatibility imports for code that still expects legacy vFlow symbols."""

from __future__ import annotations


_LAZY_NAMES = {
    "BatchPlotWindow",
    "BatchStatsDialog",
    "derivative_threshold",
    "FlowApp",
    "FlowTabManager",
    "FolderScanDialog",
    "gmm_thresholds",
    "otsu_threshold",
    "PolarAnalysisWindow",
    "read_fcs",
}


def __getattr__(name: str):
    if name in _LAZY_NAMES:
        from . import vflow_legacy

        return getattr(vflow_legacy, name)
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
