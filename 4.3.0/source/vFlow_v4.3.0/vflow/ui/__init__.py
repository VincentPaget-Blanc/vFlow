"""Lazy UI compatibility package for vFlow.

The main Tk classes remain in the packaged compatibility module. These proxies
provide stable public import paths without importing the heavy UI during
headless package imports.
"""

from __future__ import annotations


def __getattr__(name: str):
    if name == "BatchPlotWindow":
        from .batch_plot_window import BatchPlotWindow

        return BatchPlotWindow
    if name == "BatchStatsDialog":
        from .batch_stats_dialog import BatchStatsDialog

        return BatchStatsDialog
    if name == "FlowApp":
        from .app import FlowApp

        return FlowApp
    if name == "FlowTabManager":
        from .tab_manager import FlowTabManager

        return FlowTabManager
    if name == "FolderScanDialog":
        from .folder_scan_dialog import FolderScanDialog

        return FolderScanDialog
    if name == "PolarAnalysisWindow":
        from .polar_analysis_window import PolarAnalysisWindow

        return PolarAnalysisWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BatchPlotWindow",
    "BatchStatsDialog",
    "FlowApp",
    "FlowTabManager",
    "FolderScanDialog",
    "PolarAnalysisWindow",
]
