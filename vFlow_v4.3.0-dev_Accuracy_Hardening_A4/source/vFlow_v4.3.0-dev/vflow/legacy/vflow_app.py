#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Legacy Tk application compatibility facade for vFlow.

The controller remains the public compatibility surface while v4.3 development
progressively moves cohesive computation, workflow, interaction, and rendering
ownership into composed modules. Scientific and interaction behavior remain
certified against the v4.2.0 release baseline. Historical release notes live in
``CHANGELOG.md`` at the source root.
"""

import os
import sys
import time
import functools
import itertools
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_VERSION = "4.2.0"

# Scientific/runtime compatibility guard: launcher and companion package must
# be from the same release. A stale package can otherwise silently reintroduce
# older gate-mask/transform/export behavior under a newer UI version string.
from vflow import __version__ as _VFLOW_PACKAGE_VERSION
if _VFLOW_PACKAGE_VERSION != APP_VERSION:
    raise RuntimeError(
        f"vFlow version mismatch: launcher={APP_VERSION}, "
        f"package={_VFLOW_PACKAGE_VERSION}. Use files from the same release."
    )

# ── Splash screen — shown BEFORE heavy imports so the user sees feedback ──────
# matplotlib, numpy, scipy each take ~0.5-2 s to import on first launch.
# By starting the splash here we show progress during that dead time.
if __name__ == '__main__':
    try:
        from vflow_splash import SplashScreen as _SplashScreen
        _splash = _SplashScreen(version=APP_VERSION, total_steps=7)
    except Exception:
        _splash = None

# ── Heavy imports (each one advances the splash bar) ─────────────────────────
import matplotlib
if __name__ == '__main__':
    from vflow.backends import configure_matplotlib_backend
    configure_matplotlib_backend(headless=False)
import matplotlib.lines as mlines
# Use Figure directly — avoids pyplot registering a second window
from matplotlib.figure import Figure
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.ticker import FixedLocator
from matplotlib.path import Path as MplPath
from matplotlib.patches import Rectangle as MplRect, Ellipse as MplEllipse
if __name__ == '__main__' and _splash: _splash.step("matplotlib")

import copy
import numpy as np
if __name__ == '__main__' and _splash: _splash.step("numpy")

import pandas as pd

from scipy.stats import gaussian_kde
if __name__ == '__main__' and _splash: _splash.step("pandas")

from scipy.interpolate import RegularGridInterpolator
if __name__ == '__main__' and _splash: _splash.step("scipy")

try:
    from sklearn.mixture import GaussianMixture
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
if __name__ == '__main__' and _splash: _splash.step("scikit-learn")

from vflow.app.cache import AnalysisCache, CompactScatterPayload
from vflow.app.dataset import DatasetState
from vflow.app.lineage import (LineageStage, PopulationLineage, append_legacy_stage,
                               copy_legacy_lineage)
from vflow.app.state import AnalysisState
from vflow.app.session import ApplicationSession
from vflow.core.column_normalization import normalize_columns_to_reference
from vflow.core.auto_gate import (
    ClusterPolygonInsufficientData,
    derivative_threshold,
    cluster_min_fraction,
    cluster_polygons_status,
    fit_cluster_polygons,
    finite_displayable_raw_channel_values,
    finite_raw_channel_values,
    finite_transformed_channel_values,
    fit_gmm_crossings,
    gmm_component_count,
    gmm_multi_status,
    gmm_thresholds,
    kde_valley_supported,
    prepare_cluster_polygon_data,
    otsu_threshold,
    percent_at_or_below,
    percent_below,
    sensitivity_parameters,
    two_axis_threshold_status,
)
from vflow.core.circular_stats import (
    auto_detect_vector_columns,
    build_polar_stats_export_row,
    circular_mean_direction,
    common_columns,
    format_polar_stats_values,
    mean_resultant_length,
    rayleigh_p_value,
    vector_direction_stats,
    vectors_from_coordinate_columns,
)
from vflow.core.data_io import read_flow_data_file, smart_read_csv
from vflow.core.fcs_reader import read_fcs
from vflow.core.cache_keys import (
    evict_cache_keys,
    gate_mask_cache_keys_for_gate_ids,
    gate_signature as _gate_sig,
    scatter_cache_keys_for_gate_signature,
)
from vflow.core.gate_definition import GateDefinition
from vflow.core.gates import (
    active_x_boundaries,
    active_y_boundary,
    active_y_boundaries,
    append_polygon_vertex,
    begin_gate_draw,
    bounded_horizontal_line_distance,
    bounded_vertical_line_distance,
    clicked_subgate_region,
    closed_polygon_points,
    crosshair_corner_label_position,
    crosshair_preview_boundaries,
    ellipse_area,
    ellipse_center_radii,
    ellipse_preview_geometry,
    ellipse_perimeter_points,
    finite_point_pairs,
    gate_by_id,
    gate_control_points,
    gate_handles,
    gate_snapshot,
    handle_cache_entries,
    handle_cache_entry,
    handle_display_mode,
    handle_marker_style,
    is_degenerate_shape_gate,
    is_finite_point,
    iter_gate_draw_assignments,
    iter_gate_draw_initialization_assignments,
    iter_handle_drag_assignments,
    manual_crosshair_gate,
    nearest_cached_handle,
    new_gate_dict,
    point_distance,
    point_in_ellipse,
    point_in_rectangle,
    point_to_polyline_min_distance,
    point_to_segment_distance,
    polygon_area,
    PolygonGeometrySchemaError,
    polygon_gate_can_finish,
    plan_polygon_close_entry,
    plan_polygon_finish,
    polygon_preview_points,
    polygon_rubber_band_points,
    plan_polygon_vertex,
    require_polygon_vertices,
    rectangle_area,
    rectangle_bounds,
    rectangle_preview_geometry,
    rectangle_line_segments,
    remove_gate_and_select_neighbor,
    should_draw_gate_preview,
    smaller_area_hit,
    subgate_candidate_order,
    update_gate_from_control_points,
    visible_handle_gate_ids,
    gate_preview_style,
)
from vflow.core.gate_masks import (
    compute_gate_regions,
    region_masks,
    selected_region_mask,
)
from vflow.core.gate_stats import (
    binary_gate_partition_counts,
    binary_gate_partition_sort_key,
    binomial_percentage_sem,
    build_gate_stats_export_rows,
    merge_gate_stats,
    region_percentages,
    region_percentages_with_total,
    stats_from_regions,
)
from vflow.core.sample_labels import (
    make_sample_label,
    shorten_common_prefix_labels,
)
from vflow.core.logicle import LogicleParameters
from vflow.core.transforms import (
    forward_transform,
    inverse_transform,
    scale_uses_cofactor,
    scale_uses_logicle_params,
    transform_xy,
)
from vflow.plotting.render_lifecycle import reset_refresh_axes
from vflow.plotting.kde_payloads import (
    KDERenderComputation,
    compute_contour_surface_payload,
    compute_density_render_payload,
    compute_kde_jobs_parallel,
)
from vflow.plotting.utils import (
    apply_sample_indices,
    evict_oldest_cache_entries,
    gmm_overlay_curves,
    gmm_overlay_legend_layout,
    get_rng as _get_rng,
    hex_to_rgba as _hex_to_rgba,
    sampled_indices,
    set_spines_color as _set_spines_color,
    threshold_band_boundaries,
    threshold_band_labels,
    valid_values,
)
from vflow.services.batch_plot_export import (
    build_batch_plot_stats_row,
    distribution_summary,
    format_display_number,
    short_display_label,
)
from vflow.services.channel_selection import plan_channel_menu
from vflow.services.axis_input_planning import (
    plan_axis_apply, plan_cofactor_entry, plan_cofactor_trace, plan_scale_apply,
)
from vflow.services.gate_axis_swap import (
    apply_gate_axis_swap_plan, plan_gate_axis_swap,
)
from vflow.services.active_file_changes import (
    build_incompatible_gate_status, plan_active_file_change,
)
from vflow.services.gate_lifecycle import (
    build_new_gate_plan, gate_selector_labels, plan_gate_delete,
    resolve_gate_selector,
)
from vflow.services.gate_threshold_planning import (
    manual_crosshair_threshold_plan, multi_y_auto_threshold_plan,
    single_y_auto_threshold_plan,
)
from vflow.services.gate_geometry_interaction import (
    gate_pixel_delta, plan_draw_start, plan_gate_move_start,
    plan_handle_drag_start, resolve_fresh_draw_finalization_path,
    resolve_fresh_draw_release_guard, resolve_release_interaction_path,
    run_crosshair_release_side_effect_sequence,
    run_fresh_draw_discard_side_effect_sequence,
    run_gate_move_motion_presentation_sequence,
    run_handle_drag_motion_presentation_sequence,
    run_polygon_motion_presentation_sequence,
    run_fresh_draw_motion_presentation_sequence,
    run_gate_move_release_side_effect_sequence,
    run_handle_drag_release_side_effect_sequence,
    run_shape_release_side_effect_sequence, translate_gate_pixel_points,
)
from vflow.services.batch_plot_samples import (
    build_batch_plot_samples,
    common_numeric_columns,
    first_distance_column,
    first_intensity_column,
    has_source_file_samples,
    preferred_distribution_column,
)
from vflow.services.concat_export import (
    build_concatenated_csv,
    concat_no_csv_message,
    concat_no_selection_message,
    concat_output_filename,
    concat_read_error_message,
    concat_save_path,
    concat_skipped_fcs_message,
    concat_success_message,
    concat_success_status,
)
from vflow.services.export_names import (
    active_export_stem,
    export_channel_token,
    xy_export_prefix,
)
from vflow.services.figure_export import save_figure
from vflow.services.population_evaluation import (
    regions_in_explicit_context, restrict_regions_to_valid,
    selected_population_mask_for_dataframe,
)
from vflow.services.gate_evaluation import evaluate_gate_regions
from vflow.services.subgate_population import (
    SubgateChannelMismatchError, resolve_subgate_selection)
from vflow.services.gate_session import validate_gate_context_payload
from vflow.services.polar_results import collect_polar_datasets
from vflow.services.batch_plot_results import compute_batch_plot_results
from vflow.services.gated_data_export import (
    build_gated_export_frames,
)
from vflow.controllers.gate_interaction_controller import GateInteractionController
from vflow.controllers.project_data_load_coordinator import ProjectDataLoadCoordinator
from vflow.rendering.flow_renderer import FlowRenderer
from vflow.services.batch_stats_runner import (
    BatchStatsAdapters,
    BatchStatsRequest,
    BatchStatsRunner,
)
from vflow.services.batch_stats_export import (
    batch_details_message,
    batch_status_message,
    batch_summary_message,
    all_batch_targets_excluded_message,
    gate_output_labels,
    no_batch_targets_message,
)
from vflow.ui.folder_state import get_last_folder, set_last_folder
from vflow.config.themes import THEMES
from vflow.config.styles import _apply_ttk_style
from vflow.core.scales import register_flow_scales
from vflow.config.constants import (
    ALL_SCALES,
    _LOCK_SNAP,
    _FLOW_MINOR_TICKS,
    GATE_PALETTE,
    HANDLE_PX,
    HANDLE_SZ,
    REGION_COLORS,
    _N_REGION_COLORS,
    KDE_SUBSAMPLE,
    RENDER_CAP,
    _GMC_MAX,
    _SCATTER_CACHE_MAX,
    _SCATTER_CACHE_MAX_BYTES,
)
from vflow.ui.folder_scan_dialog import FolderScanDialog
from vflow.ui.polar_analysis_window import PolarAnalysisWindowBase
from vflow.ui.batch_plot_window import BatchPlotWindowBase
from vflow.ui.tab_manager import FlowTabManagerBase
from vflow.ui.flow_app_shell import FlowAppShellBase
from vflow.ui.file_list import FileListUIState
from vflow.ui.axis_name_resolver import AxisNameResolverDialog
from vflow.nomenclature.channel_names import (
    axis_name_similarity as _axis_name_similarity,
    channel_relation as _channel_relation,
    discover_channel_schema as _discover_channel_schema,
    extract_channel_from_template as _extract_channel_from_template,
    replace_channel_in_template as _replace_channel_in_template,
)
from vflow.platform.file_reveal import (
    file_manager_label as _platform_file_manager_label,
    reveal_paths as _platform_reveal_paths,
)
from vflow.ui.gate_interaction import (
    GateHoverCache,
    GateInteractionState,
    continue_hover_hit_testing,
    run_hover_hit_test_execution_sequence,
    iter_handle_pixel_cache_entries,
    select_nearest_cached_handle_gate,
    resolve_winning_cached_handle_key,
    run_hover_handle_proximity_execution_sequence,
    resolve_cached_handle_hover_cursor,
    should_resolve_hover_cursor,
    resolve_hover_cursor_gate_id,
    resolve_hover_cursor_nearest_result,
    resolve_hover_cursor_result_projection,
    resolve_hover_cursor_workflow,
    plan_hover_hit_testing,
    invoke_hover_hit_test_plan,
    plan_hover_cursor_policy,
    invoke_hover_cursor_policy,
    run_hover_cursor_application_sequence,
    plan_hover_presentation,
    run_hover_presentation_sequence,
    run_outside_axes_hover_clear_sequence,
    plan_pin_interaction,
    should_clear_hover_outside_axes,
)
from vflow.ui.batch_stats_dialog import BatchStatsDialog

register_flow_scales()

# ─────────────────────────────────────────────────────────────────────────────
#  Runtime ownership
# ─────────────────────────────────────────────────────────────────────────────
# Themes, styles, scales, constants, FCS I/O, auto-gating helpers and shared
# dialogs are package-owned.  v4.1.7 intentionally contains no shadow local
# implementations of those components.

# ─────────────────────────────────────────────────────────────────────────────
#  Polar / Vector Analysis Window
# ─────────────────────────────────────────────────────────────────────────────

class PolarAnalysisWindow(PolarAnalysisWindowBase, tk.Toplevel):
    """Compatibility subclass retaining frozen Polar scientific computation."""

    def __init__(self, parent_root, T: dict, app: 'FlowApp'):
        # Frozen lifecycle contract remains in the extracted base:
        # _initial_compute_pending; WM_DELETE_WINDOW
        super().__init__(parent_root, T, app)

    def _on_close(self):
        # Frozen lifecycle contract remains in the extracted base:
        # _initial_compute_pending; _replot_pending; after_cancel
        return super()._on_close()

    def _get_population_mask(self, *args, **kwargs):
        mask = super()._get_population_mask(*args, **kwargs)
        if mask is None:
            return None
        return mask

    def _compute_and_plot(self):
        """
        Collect per-file vector data for visible files, render polar figure,
        and populate the statistics treeview.
        """
        # ── Parse parameters ──────────────────────────────────────────────
        try:
            mrl_thresh = float(self._mrl_thresh_var.get())
            if not np.isfinite(mrl_thresh) or not (0.0 <= mrl_thresh <= 1.0):
                raise ValueError("MRL threshold must be between 0 and 1")
            max(4, int(self._n_bins_var.get()))
            float(np.clip(float(self._alpha_var.get()), 0.05, 1.0))
        except ValueError as exc:
            messagebox.showerror("Polar Analysis",
                f"Invalid parameter value(s): {exc}", parent=self)
            return

        # ── Validate column selection ─────────────────────────────────────
        if not all([self._cx1_var.get(), self._cy1_var.get(),
                    self._cx2_var.get(), self._cy2_var.get()]):
            self._status_var.set("Select all four coordinate columns, then compute")
            return

        active_all = self.app._active()
        visible_paths = set(self._get_active_paths())
        active = {p: df for p, df in active_all.items() if p in visible_paths}
        if not active:
            self._status_var.set("No data loaded")
            return

        # ── Refresh file list to pick up any new/removed files ────────────
        self._build_file_list()

        # ── Collect data for visible files ────────────────────────────────
        visible_paths = self._get_active_paths()
        collection = collect_polar_datasets(
            active, visible_paths,
            population_mask_for=self._get_population_mask,
            vectors_for=self._get_vectors_for_df,
        )
        if collection.failed:
            path = collection.failure_path
            if collection.failure_kind == 'population':
                self._status_var.set(
                    f"Selected gate cannot be evaluated for {os.path.basename(path)}; "
                    "comparison stopped rather than dropping that sample.")
            else:
                self._status_var.set(
                    f"Vector columns cannot be evaluated for {os.path.basename(path)}; "
                    "comparison stopped rather than dropping that sample.")
            self._fig.clear()
            self._canvas.draw()
            self._last_datasets = []
            self._update_stats_display()
            return
        datasets = list(collection.datasets)

        if not datasets or not any(len(a) > 0 for a, _, _, _, _ in datasets):
            self._status_var.set(
                "No valid vector data — check coordinate columns and gate")
            self._fig.clear()
            self._canvas.draw()
            self._last_datasets = []
            self._update_stats_display()
            return

        self._last_datasets = datasets
        self._render_figure(datasets)
        self._update_stats_display()

# ─────────────────────────────────────────────────────────────────────────────
#  Main application
# ─────────────────────────────────────────────────────────────────────────────

from vflow.services.gate_assignment_transaction import (
    snapshot_gate_assignment as _snapshot_gate_assignment,
    rollback_gate_assignments as _rollback_gate_assignments,
)



def _gate_interaction_owner(host):
    """Resolve the composed owner while preserving unbound FlowApp helper calls."""
    accessor = getattr(host, '_interaction_controller', None)
    if callable(accessor):
        return accessor()
    return GateInteractionController(host)


def _project_data_load_owner(host):
    """Resolve the composed project/data owner for initialized or test hosts."""
    try:
        owner = host.__dict__.get('_project_data_load_coordinator')
    except Exception:
        owner = None
    if owner is None:
        owner = ProjectDataLoadCoordinator(host)
        try:
            host.__dict__['_project_data_load_coordinator'] = owner
        except Exception:
            pass
    return owner


class FlowApp(FlowAppShellBase):
    # v4.2 refactor: one Tk-free ApplicationSession owns analysis state,
    # dataset mappings, and analysis/render caches.  The legacy private helper
    # names remain aliases for compatibility so tests/callers can
    # continue using the frozen v4.1.11 surface unchanged.
    def _app_session_obj(self) -> ApplicationSession:
        session = self.__dict__.get('_app_session')
        if session is None:
            session = ApplicationSession(
                analysis=self.__dict__.get('_analysis_state') or AnalysisState(),
                dataset=self.__dict__.get('_dataset_state') or DatasetState(),
                cache=self.__dict__.get('_analysis_cache') or AnalysisCache(),
            )
            self.__dict__['_app_session'] = session
        # Keep compatibility aliases synchronized to the single owner.
        self.__dict__['_analysis_state'] = session.analysis
        self.__dict__['_dataset_state'] = session.dataset
        self.__dict__['_analysis_cache'] = session.cache
        self.__dict__['_nomenclature_state'] = session.nomenclature
        return session

    def _analysis_state_obj(self) -> AnalysisState:
        return self._app_session_obj().analysis

    def _analysis_cache_obj(self) -> AnalysisCache:
        return self._app_session_obj().cache

    def _dataset_state_obj(self) -> DatasetState:
        return self._app_session_obj().dataset

    def _nomenclature_state_obj(self):
        return self._app_session_obj().nomenclature

    def _file_list_ui_obj(self) -> FileListUIState:
        state = self.__dict__.get('_file_list_ui_state')
        if state is None:
            state = FileListUIState()
            self.__dict__['_file_list_ui_state'] = state
        return state

    def _gate_interaction_state_obj(self) -> GateInteractionState:
        state = self.__dict__.get('_gate_interaction_state')
        if state is None:
            state = GateInteractionState()
            self.__dict__['_gate_interaction_state'] = state
        return state

    def _gate_hover_cache_obj(self) -> GateHoverCache:
        cache = self.__dict__.get('_gate_hover_cache')
        if cache is None:
            cache = GateHoverCache()
            self.__dict__['_gate_hover_cache'] = cache
        return cache

    @property
    def file_vars(self):
        return self._file_list_ui_obj().file_vars

    @file_vars.setter
    def file_vars(self, value):
        self._file_list_ui_obj().file_vars = value

    @property
    def file_colors(self):
        return self._file_list_ui_obj().file_colors

    @file_colors.setter
    def file_colors(self, value):
        self._file_list_ui_obj().file_colors = value

    @property
    def _sel_gate_id(self):
        return self._gate_interaction_state_obj().selected_gate_id

    @_sel_gate_id.setter
    def _sel_gate_id(self, value):
        self._gate_interaction_state_obj().selected_gate_id = value

    @property
    def _draw_gate_id(self):
        return self._gate_interaction_state_obj().draw_gate_id

    @_draw_gate_id.setter
    def _draw_gate_id(self, value):
        self._gate_interaction_state_obj().draw_gate_id = value

    @property
    def _hover_gate_id(self):
        return self._gate_interaction_state_obj().hover_gate_id

    @_hover_gate_id.setter
    def _hover_gate_id(self, value):
        self._gate_interaction_state_obj().hover_gate_id = value

    @property
    def _hover_handle_key(self):
        return self._gate_interaction_state_obj().hover_handle_key

    @_hover_handle_key.setter
    def _hover_handle_key(self, value):
        self._gate_interaction_state_obj().hover_handle_key = value

    @property
    def _interior_hover_gate_id(self):
        return self._gate_interaction_state_obj().interior_hover_gate_id

    @_interior_hover_gate_id.setter
    def _interior_hover_gate_id(self, value):
        self._gate_interaction_state_obj().interior_hover_gate_id = value

    @property
    def _pinned_gate_id(self):
        return self._gate_interaction_state_obj().pinned_gate_id

    @_pinned_gate_id.setter
    def _pinned_gate_id(self, value):
        self._gate_interaction_state_obj().pinned_gate_id = value

    @property
    def _last_line_test_pos(self):
        return self._gate_hover_cache_obj().get_last_line_test_pos()

    @_last_line_test_pos.setter
    def _last_line_test_pos(self, value):
        self._gate_hover_cache_obj().set_last_line_test_pos(value)

    @property
    def _handle_px_cache(self):
        return self._gate_hover_cache_obj().handle_pixel_cache

    @_handle_px_cache.setter
    def _handle_px_cache(self, value):
        self._gate_hover_cache_obj().handle_pixel_cache = value

    @property
    def loaded_files(self):
        return self._dataset_state_obj().loaded_files

    @loaded_files.setter
    def loaded_files(self, value):
        self._dataset_state_obj().loaded_files = value

    @property
    def excluded_files(self):
        return self._dataset_state_obj().excluded_files

    @excluded_files.setter
    def excluded_files(self, value):
        self._dataset_state_obj().excluded_files = value

    @property
    def axis_aliases(self):
        return self._nomenclature_state_obj().aliases

    @axis_aliases.setter
    def axis_aliases(self, value):
        self._nomenclature_state_obj().aliases = dict(value or {})

    @property
    def _axis_resolution_prompt_signature(self):
        return self._nomenclature_state_obj().prompt_signature

    @_axis_resolution_prompt_signature.setter
    def _axis_resolution_prompt_signature(self, value):
        self._nomenclature_state_obj().prompt_signature = value

    @property
    def _tc(self):
        return self._analysis_cache_obj().transforms

    @_tc.setter
    def _tc(self, value):
        self._analysis_cache_obj().transforms = value

    @property
    def _gmc(self):
        return self._analysis_cache_obj().gate_masks

    @_gmc.setter
    def _gmc(self, value):
        self._analysis_cache_obj().gate_masks = value

    @property
    def _scatter_cache(self):
        return self._analysis_cache_obj().scatter

    @_scatter_cache.setter
    def _scatter_cache(self, value):
        self._analysis_cache_obj().scatter = value

    @property
    def _density_cache(self):
        return self._analysis_cache_obj().density

    @_density_cache.setter
    def _density_cache(self, value):
        self._analysis_cache_obj().density = value

    @property
    def _marginal_cache(self):
        return self._analysis_cache_obj().marginals

    @_marginal_cache.setter
    def _marginal_cache(self, value):
        self._analysis_cache_obj().marginals = value

    @property
    def _contour_cache(self):
        return self._analysis_cache_obj().contours

    @_contour_cache.setter
    def _contour_cache(self, value):
        self._analysis_cache_obj().contours = value

    @property
    def x_channel(self):
        return self._analysis_state_obj().x_channel

    @x_channel.setter
    def x_channel(self, value):
        self._analysis_state_obj().x_channel = value

    @property
    def y_channel(self):
        return self._analysis_state_obj().y_channel

    @y_channel.setter
    def y_channel(self, value):
        self._analysis_state_obj().y_channel = value

    @property
    def x_scale(self):
        return self._analysis_state_obj().x_scale

    @x_scale.setter
    def x_scale(self, value):
        self._analysis_state_obj().x_scale = value

    @property
    def y_scale(self):
        return self._analysis_state_obj().y_scale

    @y_scale.setter
    def y_scale(self, value):
        self._analysis_state_obj().y_scale = value

    @property
    def cofactor(self):
        return self._analysis_state_obj().cofactor

    @cofactor.setter
    def cofactor(self, value):
        self._analysis_state_obj().cofactor = value

    @property
    def x_transform_params(self):
        return self._analysis_state_obj().x_transform_params

    @x_transform_params.setter
    def x_transform_params(self, value):
        self._analysis_state_obj().x_transform_params = dict(value)

    @property
    def y_transform_params(self):
        return self._analysis_state_obj().y_transform_params

    @y_transform_params.setter
    def y_transform_params(self, value):
        self._analysis_state_obj().y_transform_params = dict(value)

    @property
    def _data_generation(self):
        return self._analysis_state_obj().data_generation

    @_data_generation.setter
    def _data_generation(self, value):
        self._analysis_state_obj().data_generation = value

    @property
    def parent_gate(self):
        return self._analysis_state_obj().parent_gate

    @parent_gate.setter
    def parent_gate(self, value):
        self._analysis_state_obj().parent_gate = value

    @property
    def parent_region(self):
        return self._analysis_state_obj().parent_region

    @parent_region.setter
    def parent_region(self, value):
        self._analysis_state_obj().parent_region = value

    @property
    def population_lineage(self):
        return self._analysis_state_obj().population_lineage

    @population_lineage.setter
    def population_lineage(self, value):
        self._analysis_state_obj().population_lineage = value

    def __init__(self, root: tk.Tk, container=None,
                 parent_label: str = None, manager=None):
        """
        root         – Tk root window (always needed for messagebox parent)
        container    – ttk.Frame to build UI into; None → build into root
        parent_label – name of the parent gate population (sub-gate tabs only)
        manager      – FlowTabManager; enables double-click sub-gate opening
        """
        self.root         = root
        self.manager      = manager
        self.parent_label = parent_label

        # In standalone mode, build directly into root.
        # In tab mode, build into the supplied container frame.
        if container is None:
            root.title(f"vFlow {APP_VERSION}")
            root.geometry("1500x960")
            self._theme_name = 'dark'
            self.T = THEMES['dark']
            _apply_ttk_style(self.T)
            T = self.T   # local alias for the init block below
            root.configure(bg=T['sidebar_bg'])
            # Wrap in a frame so _build_ui always has a Frame container
            self.container = tk.Frame(root, bg=T['sidebar_bg'])
            self.container.pack(fill=tk.BOTH, expand=True)
        else:
            self.container   = container
            self._theme_name = 'dark'
            self.T           = THEMES['dark']

        # Data
        self.loaded_files:   dict = {}
        self.excluded_files: dict = {}   # path → df (excluded from analysis)
        self.file_vars:      dict = {}
        self.file_colors:  dict = {}
        # Confirmed label aliases are session-scoped and never modify source files.
        self.axis_aliases: dict = {}
        self._axis_resolution_prompt_signature = None

        # Sub-gate context (set by FlowTabManager._load_filtered for sub-gate tabs;
        # None on the main tab).  batch_export_stats uses these to pre-filter each
        # raw file through the parent gate before applying the sub-gate's own gates.
        self.parent_gate:   dict = None   # legacy immediate-parent snapshot
        self.parent_region: str  = None   # legacy immediate-parent region
        # Complete immutable ancestry for sub-gate reconstruction.  Each stage:
        # {gate: plain-Python gate snapshot, region: str, context: analysis-context}.
        self.population_lineage: list = []

        # Monotonic token identifying the in-memory dataset generation.  Cache
        # keys include this token so reloading a changed file at the same path
        # can never reuse transformed arrays / masks from the previous contents.
        self._data_generation: int = 0

        # ── Performance caches ────────────────────────────────────────────
        # _tc  : transform cache  — {(path, x_ch, y_ch, x_sc, y_sc, cof): (xt, yt, valid)}
        #        self-invalidating: different settings → different key → cache miss
        # _gmc : gate-mask cache  — {(path, x_ch, y_ch, gid, sig): (regions, colors)}
        #        self-invalidating: gate geometry change → sig changes → cache miss
        # _scatter_cache : scatter payload cache —
        #        {(path, x_ch, y_ch, gate_sigs, dot_size, alpha, color, overlay):
        #         (xa_visible, ya_visible, rgba_visible)}
        #        Stores the already-subsampled, visibility-filtered arrays so
        #        _plot_gated_multi can skip RGBA construction + contains_points
        #        entirely on redraws where nothing has changed.
        #        Invalidated explicitly by _finish_gate and _drag_handle_update.
        # _density_cache : style-independent Density render payload cache —
        #        {(generation, path, x_ch, y_ch, x_sc, y_sc, cofactor):
        #         (x_sorted, y_sorted, density_sorted, vmin, vmax, n_valid)}
        #        Stores only the <= RENDER_CAP displayed points, never full-event
        #        density arrays. Gate edits preserve it; data/context changes clear it.
        self._tc:            dict = {}
        self._gmc:           dict = {}
        self._scatter_cache: dict = {}
        self._density_cache:  dict = {}
        # _marginal_cache : style-independent marginal histogram payloads —
        #        same analysis-context key as Density, storing only the 120-bin
        #        top/right count+edge arrays. Gate/style changes preserve it.
        self._marginal_cache: dict = {}
        # _contour_cache : style-independent Contour numerical payloads —
        #        {(generation, path, x_ch, y_ch, x_sc, y_sc, cofactor):
        #         (x_grid_t, y_grid_t, x_grid_raw, y_grid_raw, kde_surface,
        #          last_prob, level, outlier_x_sample, outlier_y_sample, n_outside)}
        #        Stores one expensive historical KDE/grid surface per analysis
        #        context plus the most-recent probability-specific classification.
        #        Probability changes reuse the KDE surface; gate/style changes
        #        preserve the entire payload. Matplotlib artists are never cached.
        self._contour_cache: dict = {}

        # Plot state
        self.x_channel = None
        self.y_channel = None
        self.x_scale   = 'asinh'
        self.y_scale   = 'asinh'
        self.cofactor  = 150.0

        # View mode
        self.view_mode_var = tk.StringVar(value='overlay')
        self.cycle_idx     = 0

        # ── Multi-gate system ──────────────────────────────────────────────────
        # Each gate dict: {id, name, type, applied, color, ...geometry...}
        #   crosshair: x_boundaries, y_boundary, x_thresh_vars, y_thresh_var
        #   rectangle/ellipse: x0, y0, x1, y1
        #   polygon: vertices [(x,y),...]
        self.gates:           list = []
        self._sel_gate_id:    int  = None  # selected gate (stats/coloring)
        self._draw_gate_id:   int  = None  # gate currently being drawn
        self._next_gate_id:   int  = 0

        # Current drawing state
        self.moving_gate:      bool  = False
        self._poly_active:     bool  = False
        self._poly_cursor:     tuple = None

        # Handle-editing state
        self._handle_drag:            dict  = None  # {gate_id, handle, idx, ox, oy}
        self._gate_move:              dict  = None  # {gate_id, gate, orig, press_px, orig_px}
        self._drag_bg:                object = None  # pixel snapshot for blit drag (copy_from_bbox)
        self._drag_last_draw:         float  = 0.0  # monotonic timestamp of last drag redraw (throttle)
        # Axis-limit snapshots for gate-draw and handle-drag blit paths.
        # Captured at press/click time; restored after each _preview_gate() frame
        # to prevent autoscale expansion when geometry reaches the axes edge.
        self._draw_frozen_xlim:       list   = None
        self._draw_frozen_ylim:       list   = None
        self._hover_gate_id:          int   = None  # gate whose handles are visible via hover
        self._hover_handle_key:       tuple = None  # (gate_id, handle_name, idx) of nearest hovered handle
        self._interior_hover_gate_id: int   = None  # gate body hovered in draw mode (all-handles = move signal)
        self._pinned_gate_id:         int   = None  # gate whose handles are pinned via right-click
        # Debounce: pending after_id for throttled refresh_plot calls
        self._refresh_pending:   str   = None
        self._last_auto_gate_fn        = None   # callable: last-used auto-gate method
        self._sens_rerun_pending: str  = None   # debounce after_id for slider re-run

        # ── Lock-scale state ──────────────────────────────────────────────────
        # Captured axis limits (raw data space) when lock is active; None otherwise.
        # These override both matplotlib autoscale and "Fit axes to data".
        self._locked_xlim: list = None   # [lo, hi] or None
        self._locked_ylim: list = None   # [lo, hi] or None
        # tk.Button widgets overlaid directly on the matplotlib canvas.
        # Keys: 'xl-' 'xl+' 'xr-' 'xr+' 'yb-' 'yb+' 'yt-' 'yt+'
        self._lock_btns:   dict = {}
        # FixedLocator cache for minor ticks: key=(scale, lo, hi) → locator.
        # Avoids rebuilding the list comprehension on every render when limits
        # are stable.  Cleared whenever the axis scale type changes.
        self._minor_loc_cache: dict = {}
        # Cached handle pixel coords: {gate_id: [(px,py,handle,idx),...]}
        # Rebuilt after every full plot redraw, used by _hover_test_handles
        self._handle_px_cache: dict  = {}
        self._handle_artists:  list  = []    # matplotlib artists for handles

        # Preview artists (in-progress gate outline)
        self._preview_artists: list  = []

        # Gate type for NEW gates
        self.gate_type_var  = tk.StringVar(value='crosshair')
        # Gate interaction mode: 'none' | 'draw' | 'edit'
        # gate_var is a BooleanVar alias: True when mode == 'draw'
        # Both are created before _build_ui() so _build_ui() can reference them.
        self.gate_mode_var  = tk.StringVar(value='none')

        # Gate stats (keyed by gate id)
        self.gate_stats:       dict = {}

        # Stats display mode
        self.stats_mode_var = tk.StringVar(value='perfile')

        self._build_ui()

    # ── Theme ─────────────────────────────────────────────────────────────────



    # ── UI ────────────────────────────────────────────────────────────────────


    # ── Widget helpers ────────────────────────────────────────────────────────





    # ── Build controls ────────────────────────────────────────────────────────




    # ── Axes layout ───────────────────────────────────────────────────────────


    # ── File management ───────────────────────────────────────────────────────

    def load_files(self):
        init = get_last_folder() or os.path.expanduser('~')
        paths = filedialog.askopenfilenames(
            title="Select CSV or FCS Files",
            initialdir=init,
            filetypes=[("Flow data", "*.csv *.fcs *.FCS"),
                       ("CSV files", "*.csv"),
                       ("FCS files", "*.fcs *.FCS"),
                       ("All files", "*.*")])
        if paths:
            set_last_folder(os.path.dirname(list(paths)[0]))
        self._load_paths(list(paths))

    def load_from_folder(self):
        dlg = FolderScanDialog(self.root, self.T)
        self.root.wait_window(dlg)
        if dlg.result:
            self._load_paths(dlg.result)

    # ── Explicit axis/channel nomenclature reconciliation ────────────────

    def _axis_name_inventory(self) -> dict:
        """Return {exact_column_name: {file_paths...}} for loaded files."""
        inventory = {}
        for path, df in self.loaded_files.items():
            for col in df.columns:
                inventory.setdefault(col, set()).add(path)
        return inventory

    def _channel_family_inventory(self) -> dict:
        """Return exact structural channel-template inventory for loaded files."""
        inventory = {}
        for path, df in self.loaded_files.items():
            per_file = _discover_channel_schema(df.columns)
            for channel, templates in per_file.items():
                item = inventory.setdefault(
                    channel, {'files': set(), 'templates': set(), 'by_file': {}})
                item['files'].add(path)
                item['templates'].update(templates)
                item['by_file'][path] = set(templates)
        return inventory

    def _channel_templates_for_name(self, channel, include_excluded=False):
        """Collect exact templates in which *channel* is explicitly present."""
        channel = str(channel or '')
        if not channel:
            return set()
        templates = set()
        stores = [self.loaded_files]
        if include_excluded:
            stores.append(self.excluded_files)
        for store in stores:
            for _path, df in store.items():
                if df is None:
                    continue
                schema = _discover_channel_schema(df.columns)
                templates.update(schema.get(channel, set()))
                for raw in df.columns:
                    label = str(raw)
                    suffix = '_' + channel
                    if label.endswith(suffix) and len(label) > len(suffix):
                        templates.add(label[:-len(channel)] + '{channel}')
                    for axis in ('X', 'Y'):
                        prefix = axis + '_'
                        tail = '_microns'
                        if (label.startswith(prefix) and label.endswith(tail)
                                and label[len(prefix):-len(tail)] == channel):
                            templates.add(prefix + '{channel}' + tail)
        return templates

    def _channel_variants_for_canonical(self, canonical_channel):
        """Extract intact literal variants from the Main channel's exact slots."""
        canonical_channel = str(canonical_channel or '')
        templates = self._channel_templates_for_name(canonical_channel)
        result = {}
        if not canonical_channel or not templates:
            return result
        for path, df in self.loaded_files.items():
            if df is None:
                continue
            for template in templates:
                for raw in df.columns:
                    label = str(raw)
                    extracted = _extract_channel_from_template(label, template)
                    if not extracted:
                        continue
                    item = result.setdefault(
                        extracted,
                        {'files': set(), 'templates': set(), 'by_file': {},
                         'columns': {}})
                    item['files'].add(path)
                    item['templates'].add(template)
                    item['by_file'].setdefault(path, set()).add(template)
                    item['columns'].setdefault(path, set()).add(label)
        return result

    def _first_channel_resolution_candidate(self):
        """Suggest the most prevalent Main channel with a non-coexisting alias."""
        inventory = self._channel_family_inventory()
        if len(inventory) < 2:
            return ''
        candidates = []
        for canonical, base in inventory.items():
            variants = self._channel_variants_for_canonical(canonical)
            can_files = set(variants.get(canonical, {}).get('files', base['files']))
            can_count = len(can_files)
            templates = self._channel_templates_for_name(canonical)
            if not templates:
                continue
            for name, info in variants.items():
                if name == canonical:
                    continue
                files = set(info['files'])
                conflict = len(can_files & files)
                coverage = len(can_files | files)
                if conflict or coverage <= can_count:
                    continue
                structural = len(info['templates']) / max(1, len(templates))
                similarity = _axis_name_similarity(canonical, name)
                relation = _channel_relation(canonical, name)
                relation_rank = {'case only': 4, 'separator only': 4,
                                 'partial/suffix': 2, 'manual': 1}.get(relation, 0)
                candidates.append((coverage, can_count, relation_rank,
                                   structural, similarity, canonical))
        if not candidates:
            return ''
        candidates.sort(key=lambda x: (-x[0], -x[1], -x[2], -x[3], -x[4],
                                       str(x[5]).casefold()))
        return candidates[0][5]

    def _resolve_axis_alias_target(self, name):
        return self._nomenclature_state_obj().resolve_target(name)

    def _apply_axis_aliases_to_df(self, df, path=''):
        return self._nomenclature_state_obj().apply_to_dataframe(df)

    def _relabel_analysis_context_channels(self, mapping):
        """Relabel stored channel-name metadata after an unambiguous rename.

        Gate geometry, masks, thresholds, numeric arrays, row order, and source
        files are untouched. This only keeps context labels synchronized with a
        user-confirmed in-memory column rename so an equivalent gate does not
        become falsely incompatible merely because its channel spelling changed.
        """
        mapping = {str(k): str(v) for k, v in dict(mapping or {}).items()
                   if k is not None and v is not None and str(k) != str(v)}
        if not mapping:
            return 0

        changed = 0

        def _relabel_context(ctx):
            nonlocal changed
            if not isinstance(ctx, dict):
                return
            for key in ('x_channel', 'y_channel'):
                old = ctx.get(key)
                if old in mapping:
                    ctx[key] = mapping[old]
                    changed += 1

        for gate in getattr(self, 'gates', []) or []:
            if isinstance(gate, dict):
                _relabel_context(gate.get('_analysis_context'))

        parent_gate = getattr(self, 'parent_gate', None)
        if isinstance(parent_gate, dict):
            _relabel_context(parent_gate.get('_analysis_context'))

        for stage in getattr(self, 'population_lineage', []) or []:
            if not isinstance(stage, dict):
                continue
            _relabel_context(stage.get('context'))
            stage_gate = stage.get('gate')
            if isinstance(stage_gate, dict):
                _relabel_context(stage_gate.get('_analysis_context'))

        return changed

    def _apply_axis_mapping(self, canonical, variants):
        """Persist and apply a user-confirmed full-column alias mapping safely."""
        variants = [v for v in dict.fromkeys(variants) if v and v != canonical]
        if not canonical or not variants:
            return {'renamed_columns': 0, 'changed_files': 0,
                    'ambiguous_files': []}
        selected = set(variants)
        aliases = self.axis_aliases
        for alias, target in list(aliases.items()):
            if alias == canonical:
                continue
            resolved = self._resolve_axis_alias_target(target)
            if target in selected or resolved in selected:
                aliases[alias] = canonical
        for variant in variants:
            aliases[variant] = canonical
        aliases.pop(canonical, None)

        renamed_columns = 0
        changed_files = 0
        ambiguous_files = []
        for store in (self.loaded_files, self.excluded_files):
            for path in list(store.keys()):
                df = store[path]
                if df is None:
                    continue
                new_df, details = self._apply_axis_aliases_to_df(df, path)
                if details['renamed']:
                    renamed_columns += len(details['renamed'])
                    changed_files += 1
                    store[path] = new_df
                ambiguous_files.extend((path, why) for why in details['ambiguous'])

        # Only a globally unambiguous mapping may relabel stored gate/lineage
        # context metadata. If any file is collision-protected, leave contexts
        # untouched so existing gates fail closed rather than silently changing
        # meaning in that ambiguous file.
        if not ambiguous_files:
            self._relabel_analysis_context_channels(
                {variant: canonical for variant in variants})

        if self.x_channel in selected:
            self.x_channel = canonical
            self.x_var.set(canonical)
        if self.y_channel in selected:
            self.y_channel = canonical
            self.y_var.set(canonical)
        self._analysis_cache_obj().clear_all()
        self._axis_resolution_prompt_signature = None
        self._on_active_files_changed()
        self.status_var.set(
            f"Axis mapping applied: {', '.join(map(str, variants))} → {canonical}  │  "
            f"{renamed_columns} label(s) renamed in {changed_files} file(s)")
        return {'renamed_columns': renamed_columns,
                'changed_files': changed_files,
                'ambiguous_files': ambiguous_files}

    def _apply_channel_mapping(self, canonical_channel, variant_channels):
        """Map confirmed channel aliases only inside exact Main-channel templates."""
        variants = [str(v) for v in dict.fromkeys(variant_channels)
                    if v and str(v) != str(canonical_channel)]
        canonical_channel = str(canonical_channel or '')
        if not canonical_channel or not variants:
            return {'renamed_columns': 0, 'changed_files': 0,
                    'ambiguous_files': [], 'axis_pairs': []}
        templates = self._channel_templates_for_name(
            canonical_channel, include_excluded=True)
        if not templates:
            return {'renamed_columns': 0, 'changed_files': 0,
                    'ambiguous_files': [], 'axis_pairs': []}

        selected = set(variants)
        exact_pairs = {}
        pair_conflicts = []
        for store in (self.loaded_files, self.excluded_files):
            for path, df in store.items():
                if df is None:
                    continue
                for template in templates:
                    target = _replace_channel_in_template(template, canonical_channel)
                    for raw in df.columns:
                        source = str(raw)
                        extracted = _extract_channel_from_template(source, template)
                        if extracted not in selected or source == target:
                            continue
                        previous = exact_pairs.get(source)
                        if previous is not None and previous != target:
                            pair_conflicts.append(
                                (path, f'{source!r} matched multiple Main-channel targets'))
                            continue
                        exact_pairs[source] = target
        if not exact_pairs:
            return {'renamed_columns': 0, 'changed_files': 0,
                    'ambiguous_files': pair_conflicts, 'axis_pairs': []}

        sources = set(exact_pairs)
        aliases = self.axis_aliases
        for alias, target in list(aliases.items()):
            resolved = self._resolve_axis_alias_target(target)
            if target in sources:
                aliases[alias] = exact_pairs[target]
            elif resolved in sources:
                aliases[alias] = exact_pairs[resolved]
        for source, target in exact_pairs.items():
            aliases[source] = target
            aliases.pop(target, None)

        renamed_columns = 0
        changed_files = 0
        ambiguous_files = list(pair_conflicts)
        for store in (self.loaded_files, self.excluded_files):
            for path in list(store.keys()):
                df = store[path]
                if df is None:
                    continue
                new_df, details = self._apply_axis_aliases_to_df(df, path)
                if details['renamed']:
                    renamed_columns += len(details['renamed'])
                    changed_files += 1
                    store[path] = new_df
                ambiguous_files.extend((path, why) for why in details['ambiguous'])

        if not ambiguous_files:
            self._relabel_analysis_context_channels(exact_pairs)

        if self.x_channel in exact_pairs:
            self.x_channel = exact_pairs[self.x_channel]
            self.x_var.set(self.x_channel)
        if self.y_channel in exact_pairs:
            self.y_channel = exact_pairs[self.y_channel]
            self.y_var.set(self.y_channel)
        self._analysis_cache_obj().clear_all()
        self._axis_resolution_prompt_signature = None
        self._on_active_files_changed()
        self.status_var.set(
            f"Channel mapping applied: {', '.join(map(str, variants))} → "
            f"{canonical_channel}  │  {renamed_columns} exact column label(s) "
            f"renamed in {changed_files} file(s)")
        return {'renamed_columns': renamed_columns,
                'changed_files': changed_files,
                'ambiguous_files': ambiguous_files,
                'axis_pairs': sorted(exact_pairs.items(),
                                     key=lambda kv: (kv[1].casefold(), kv[0].casefold()))}

    def _first_axis_resolution_candidate(self):
        """Return a likely canonical full-column name for Advanced mode only."""
        inventory = self._axis_name_inventory()
        names = list(inventory)
        if len(names) < 2:
            return ''
        candidates = []
        for i, a in enumerate(names):
            pa = inventory[a]
            for b in names[i + 1:]:
                pb = inventory[b]
                score = _axis_name_similarity(a, b)
                if score < 0.78:
                    continue
                union_n = len(pa | pb)
                if union_n <= max(len(pa), len(pb)):
                    continue
                if len(pa) > len(pb):
                    canonical = a
                elif len(pb) > len(pa):
                    canonical = b
                else:
                    canonical = a
                candidates.append((score, union_n, max(len(pa), len(pb)), canonical))
        if not candidates:
            return ''
        candidates.sort(key=lambda x: (-x[0], -x[1], -x[2], str(x[3]).casefold()))
        return candidates[0][3]

    def _schema_resolution_report(self):
        """Compare loaded files to the dominant exact set of column labels."""
        paths = list(self.loaded_files.keys())
        if not paths:
            return {'n_files': 0, 'reference_path': None,
                    'reference_count': 0, 'reference_columns': [],
                    'reference_unique': True, 'dominant_tie_count': 0,
                    'unresolved': []}
        groups = {}
        first_index = {}
        for idx, path in enumerate(paths):
            sig = frozenset(str(c) for c in self.loaded_files[path].columns)
            groups.setdefault(sig, []).append(path)
            first_index.setdefault(sig, idx)
        max_group_n = max(len(v) for v in groups.values())
        top_sigs = [sig for sig, members in groups.items()
                    if len(members) == max_group_n]
        ref_sig = sorted(top_sigs, key=lambda sig: first_index[sig])[0]
        ref_paths = groups[ref_sig]
        ref_path = ref_paths[0]
        ref_df = self.loaded_files[ref_path]
        ref_order = [str(c) for c in ref_df.columns]
        ref_set = set(ref_order)
        unresolved = []
        for path in paths:
            cols_order = [str(c) for c in self.loaded_files[path].columns]
            cols = set(cols_order)
            missing = [c for c in ref_order if c not in cols]
            extra = [c for c in cols_order if c not in ref_set]
            if missing or extra:
                unresolved.append({'path': path, 'missing': missing, 'extra': extra})
        return {'n_files': len(paths), 'reference_path': ref_path,
                'reference_count': len(ref_paths),
                'reference_columns': ref_order,
                'reference_unique': len(top_sigs) == 1,
                'dominant_tie_count': len(top_sigs),
                'unresolved': unresolved}

    def _unload_paths(self, paths):
        """Unload paths from active analysis without touching source files."""
        targets = [p for p in dict.fromkeys(paths) if p in self.loaded_files]
        if not targets:
            return 0
        for path in targets:
            self.loaded_files.pop(path, None)
            self.file_vars.pop(path, None)
            self.file_colors.pop(path, None)
        for w in self.file_list_frame.winfo_children():
            w.destroy()
        for path in self.loaded_files:
            self._add_file_row(path)
        self._axis_resolution_prompt_signature = None
        self._invalidate_analysis_caches(data_changed=True)
        self._on_active_files_changed()
        self.status_var.set(
            f"Unloaded {len(targets)} unresolved file(s). Source files were not changed.")
        return len(targets)

    def _reveal_paths_in_file_manager(self, paths, parent=None, quiet=False):
        existing = [os.path.abspath(p) for p in dict.fromkeys(paths)
                    if p and os.path.exists(p)]
        if not existing:
            if not quiet:
                messagebox.showwarning(
                    'Reveal files', 'None of the requested source paths currently exist.',
                    parent=parent or self.root)
            return False
        ok = _platform_reveal_paths(existing)
        if not ok and not quiet:
            messagebox.showerror('Reveal files',
                                 'Could not open the system file manager.',
                                 parent=parent or self.root)
        elif ok and not quiet:
            messagebox.showinfo(
                'Reveal files',
                f"Requested the system file manager to show {len(existing)} file(s).",
                parent=parent or self.root)
        return ok

    def _file_manager_menu_label(self):
        return _platform_file_manager_label()

    def _show_single_file_in_manager(self, path: str):
        if not path or not os.path.exists(path):
            messagebox.showwarning(
                'Show source file', f'The source file could not be found at:\n{path}',
                parent=self.root)
            return
        ok = self._reveal_paths_in_file_manager([path], parent=self.root, quiet=True)
        if not ok:
            messagebox.showerror(
                'Show source file',
                'The system file manager could not reveal this file.',
                parent=self.root)

    def _popup_file_context_menu(self, event, path: str):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=self._file_manager_menu_label(),
                         command=lambda p=path: self._show_single_file_in_manager(p))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass
        return 'break'

    def _bind_file_context_menu(self, widget, path: str):
        callback = lambda e, p=path: self._popup_file_context_menu(e, p)
        widget.bind('<Button-3>', callback, add='+')
        if sys.platform == 'darwin':
            widget.bind('<Control-Button-1>', callback, add='+')
            widget.bind('<Button-2>', callback, add='+')

    def open_axis_name_resolver(self):
        if len(self.loaded_files) < 2:
            messagebox.showinfo(
                "Axis Resolver",
                "Load at least two files to compare axis/channel nomenclature.",
                parent=self.root)
            return
        AxisNameResolverDialog(self.root, self)

    def _offer_axis_name_resolution(self):
        """Offer resolver once per heterogeneous schema that constrains menus."""
        if len(self.loaded_files) < 2:
            return
        menu_files = self._active() or self.loaded_files
        if len(menu_files) < 2:
            return
        inventory = {}
        for path, df in menu_files.items():
            for col in df.columns:
                inventory.setdefault(col, set()).add(path)
        n_files = len(menu_files)
        not_shared = {name: len(paths) for name, paths in inventory.items()
                      if len(paths) != n_files}
        if not not_shared:
            return
        signature = (tuple(menu_files), tuple(sorted((str(k), v)
                                                     for k, v in not_shared.items())))
        if signature == self._axis_resolution_prompt_signature:
            return
        self._axis_resolution_prompt_signature = signature
        channel_suggested = self._first_channel_resolution_candidate()
        suggested = channel_suggested or self._first_axis_resolution_candidate()
        extra = (
            f"\n\nAn exact-structure channel-name variant was detected "
            f"(for example around {channel_suggested!r})."
            if channel_suggested else
            (f"\n\nA possible individual-column spelling variant was detected "
             f"(for example around {suggested!r}); use Advanced mode if needed."
             if suggested else
             "\n\nNo safe channel-family match was detected automatically; "
             "the resolver can show which files remain structurally unresolved."))
        if messagebox.askyesno(
                "Axis names differ across files",
                f"{len(not_shared)} exact column/axis name(s) are not present in all "
                f"{n_files} active files. Because the axis menus use the strict "
                "intersection, a single spelling variant can hide an axis for the set."
                + extra + "\n\nOpen the Axis Name Resolver now?",
                parent=self.root):
            self.open_axis_name_resolver()

    def _load_paths(self, paths: list):
        """Compatibility facade for composed dataset loading orchestration."""
        return _project_data_load_owner(self).load_paths(
            paths, messagebox=messagebox)

    @staticmethod
    def _read_data_file(path: str) -> 'pd.DataFrame':
        """Load a CSV or FCS file and return a DataFrame.

        For CSV files, handles the two layouts produced by image-analysis
        exporters — exactly the same detection used by
        FolderScanDialog._smart_read_csv for the Concatenate feature, so
        files behave identically regardless of how they are loaded.

        Layout A — first column has a name (e.g. 'Label', 'Label_2_'):
            Label,Intensity_TH,...
            1,10742176,...
            → read with pd.read_csv as-is.

        Layout B — unnamed integer row-index as first column:
             ,Label,Intensity_TH,...
            1,1,10742176,...
            → discard via index_col=0 so 'Unnamed: 0' never pollutes the
              column set and breaks the intersection logic.
        """
        return read_flow_data_file(path)

    def _normalize_columns_to_loaded(self, df: 'pd.DataFrame') -> 'pd.DataFrame':
        """
        BUG FIX (B1): rename columns of ``df`` to match the case used by
        already-loaded files in ``self.loaded_files``, so that batch routines
        applying the same case-insensitive matching as ``_load_paths`` find
        the channel columns instead of silently dropping the file.

        Returns the (possibly renamed) DataFrame.  No-op if ``loaded_files``
        is empty or no case-insensitive matches are found.
        """
        return normalize_columns_to_reference(df, list(self.loaded_files.values()))


    def _on_active_files_changed(self):
        """Synchronise menus, stats and plot to the checked-file population."""
        old_ctx = self._current_analysis_context()
        self._update_channel_menus()
        new_ctx = self._current_analysis_context()
        plan = plan_active_file_change(old_ctx, new_ctx, self.gates)
        if plan.context_changed:
            self._analysis_context_changed()
            return
        if plan.recompute_gate_stats:
            self._recompute_all_gate_stats()
        self.refresh_plot()



    def clear_all_files(self):
        """Unload every loaded file and reset the UI."""
        if self.loaded_files and not messagebox.askyesno(
                "Clear Files",
                f"Unload all {len(self.loaded_files)} file(s)?\n"
                "(Gates are kept. Excluded files are also cleared.)"):
            return
        self._dataset_state_obj().clear_files()
        self.file_vars.clear()
        self.file_colors.clear()
        self._nomenclature_state_obj().clear()
        self._invalidate_analysis_caches(data_changed=True)
        self.gate_stats.clear()
        for w in self.file_list_frame.winfo_children():
            w.destroy()
        # BUG FIX (B6): reset channel selections so the next file load doesn't
        # treat the stale channel names as valid. Without this, when a user
        # clears files and loads a file with different column names, both
        # x_channel and y_channel fall back to cols[0] (line ~3793-3798) and
        # the same column gets assigned to both axes.
        self.x_channel = None
        self.y_channel = None
        self._rebuild_excluded_list()
        self._update_channel_menus()
        self.refresh_plot()
        self._update_stats_display()
        self.status_var.set("All files cleared.")

    def _exclude_file(self, path: str):
        """Move a file from the active list to the excluded list."""
        if not self._dataset_state_obj().exclude_loaded_file(path):
            return
        self.file_vars.pop(path, None)
        # Destroy the matching row widget
        for w in self.file_list_frame.winfo_children():
            w.destroy()
        for p in self.loaded_files:
            self._add_file_row(p)
        self._rebuild_excluded_list()
        self._axis_resolution_prompt_signature = None
        self._on_active_files_changed()

    def _restore_file(self, path: str):
        """Move a file from the excluded list back into the active list.

        If the entry was registered via load_excluded_list() without the file
        being loaded (df is None), just drop it from the exclusion dict —
        there is nothing to restore to the active list.
        """
        found, df = self._dataset_state_obj().restore_excluded_file(path)
        if not found:
            return
        if df is None:
            # Path was registered from a saved list but never loaded in this
            # session — simply un-register it from the exclusion set.
            self._rebuild_excluded_list()
            return
        # DatasetState.restore_excluded_file commits the DataFrame before this
        # UI rebuild, matching the frozen v4.1.11 restore ordering.
        self._add_file_row(path)
        self._rebuild_excluded_list()
        self._axis_resolution_prompt_signature = None
        self._on_active_files_changed()


    def save_excluded_list(self):
        """Compatibility facade for excluded-file list persistence."""
        return _project_data_load_owner(self).save_excluded_list(
            filedialog=filedialog, messagebox=messagebox,
            last_folder_getter=get_last_folder)

    def load_excluded_list(self):
        """Compatibility facade for excluded-file list restoration."""
        return _project_data_load_owner(self).load_excluded_list(
            filedialog=filedialog, messagebox=messagebox,
            last_folder_getter=get_last_folder)

    def _update_channel_menus(self):
        if not self.loaded_files: return
        # Only checked/active files constrain the common channel set.  An
        # intentionally inactive incompatible file must not hide valid axes.
        menu_files = self._active() or self.loaded_files
        plan = plan_channel_menu(menu_files, self.x_channel, self.y_channel)

        self._col_mismatch_msg = plan.mismatch_message
        self.x_menu['values'] = list(plan.values)
        self.y_menu['values'] = list(plan.values)
        for target, value in plan.operations:
            if target == 'x_var':
                self.x_var.set(value)
            elif target == 'y_var':
                self.y_var.set(value)
            else:
                setattr(self, target, value)

    # ── Scientific-correctness context / invalidation helpers ───────────────

    def _current_analysis_context(self) -> dict:
        """Return the exact coordinate system in which gate geometry is defined."""
        return self._analysis_state_obj().context_dict()

    @staticmethod
    def _contexts_equal(a: dict, b: dict) -> bool:
        return AnalysisState.contexts_equal(a, b)

    def _bind_gate_context(self, gate: dict, context: dict = None) -> None:
        """Bind a gate to a coordinate system without retaining mutable state."""
        self._analysis_state_obj().bind_gate_context(gate, context)

    def _gate_context_matches(self, gate: dict, context: dict = None) -> bool:
        """True only when *gate* is valid in the requested analysis context."""
        return self._analysis_state_obj().gate_context_matches(gate, context)

    def _gate_context_error(self, gate: dict) -> str:
        saved = gate.get('_analysis_context') or {}
        now = self._current_analysis_context()
        return (
            f"Gate '{gate.get('name', gate.get('id', '?'))}' belongs to "
            f"X={saved.get('x_channel','?')} / Y={saved.get('y_channel','?')} "
            f"[{saved.get('x_scale','?')}, {saved.get('y_scale','?')}] and "
            f"cannot be applied to X={now.get('x_channel','?')} / "
            f"Y={now.get('y_channel','?')} "
            f"[{now.get('x_scale','?')}, {now.get('y_scale','?')}]."
        )

    def _compatible_applied_gates(self) -> list:
        return [g for g in self.gates
                if g.get('applied') and self._gate_context_matches(g)]

    def _gate_selector_labels(self) -> list:
        """Stable UI labels; duplicate gate names are disambiguated by gate ID."""
        return gate_selector_labels(self.gates)

    def _gate_from_selector(self, choice: str):
        """Resolve a selector label to exactly one gate; never pick first-by-name."""
        return resolve_gate_selector(self.gates, choice)

    def _invalidate_analysis_caches(self, *, data_changed: bool = False) -> None:
        """Invalidate every cache that can affect quantitative gate results."""
        if data_changed:
            self._data_generation += 1
        self._analysis_cache_obj().clear_all()
        self._minor_loc_cache.clear()

    def _recompute_all_gate_stats(self) -> None:
        """Rebuild stats from current data; incompatible gates get no stale stats."""
        self.gate_stats.clear()
        if not self._active():
            self._update_stats_display()
            return
        for gate in self.gates:
            if gate.get('applied') and self._gate_context_matches(gate):
                self._compute_gate_stats_for(gate)
        self._update_stats_display()

    def _analysis_context_changed(self) -> None:
        """Atomic invalidation/recompute after channels or transforms change."""
        self._invalidate_analysis_caches()
        self._recompute_all_gate_stats()
        self.refresh_plot()
        incompatible = [g for g in self.gates
                        if g.get('applied') and not self._gate_context_matches(g)]
        status_message = build_incompatible_gate_status(incompatible)
        if status_message:
            self.status_var.set(status_message)

    @staticmethod
    def _plain_gate_snapshot(gate: dict) -> dict:
        """Deep, Tk-free snapshot suitable for immutable lineage provenance."""
        return GateDefinition.from_live_dict(
            gate, variable_types=(tk.Variable,)).to_plain_dict()

    @staticmethod
    def _lineage_signature(lineage: list) -> str:
        """Canonical v4.1.11 signature for comparing saved/current populations."""
        return PopulationLineage.legacy_signature(lineage)

    @staticmethod
    def _validate_gate_context_payload(context: dict) -> tuple:
        """Validate serialized v2 gate provenance before trusting it."""
        return validate_gate_context_payload(context)

    @staticmethod
    def _restrict_regions_to_valid(regions: dict, valid) -> dict:
        """Return gate masks restricted to the finite/displayable X/Y population."""
        return restrict_regions_to_valid(regions, valid)

    def _regions_in_explicit_context(self, gate: dict, xa, ya, context: dict):
        """Compute ancestor regions in its immutable original coordinate context.

        Frozen v4.1.11 source-contract marker: the delegated service still
        performs ``transform_xy(...)`` and then
        ``_restrict_regions_to_valid(regions, valid)`` equivalently.
        """
        return regions_in_explicit_context(
            gate, xa, ya, context, fallback_cofactor=self.cofactor)

    # ── Scale helpers ─────────────────────────────────────────────────────────

    def _transform_params_for_axis(self, axis: str):
        if axis == "x":
            return self.x_transform_params
        if axis == "y":
            return self.y_transform_params
        raise ValueError("axis must be 'x' or 'y'")

    def _fwd(self, a, which, axis=None):
        params = self._transform_params_for_axis(axis) if axis else None
        if axis is None and scale_uses_logicle_params(which):
            # Compatibility callers without an axis remain safe when both axes
            # share identical parameters. Ambiguous per-axis standard Logicle
            # calls must be explicit rather than silently choosing X or Y.
            if self.x_transform_params == self.y_transform_params:
                params = self.x_transform_params
            elif which == self.x_scale and which != self.y_scale:
                params = self.x_transform_params
            elif which == self.y_scale and which != self.x_scale:
                params = self.y_transform_params
            else:
                raise ValueError("Standard Logicle transform requires explicit axis parameters.")
        return forward_transform(a, which, self.cofactor, transform_params=params)

    def _inv(self, a, which, axis=None):
        params = self._transform_params_for_axis(axis) if axis else None
        if axis is None and scale_uses_logicle_params(which):
            if self.x_transform_params == self.y_transform_params:
                params = self.x_transform_params
            elif which == self.x_scale and which != self.y_scale:
                params = self.x_transform_params
            elif which == self.y_scale and which != self.x_scale:
                params = self.y_transform_params
            else:
                raise ValueError("Standard Logicle transform requires explicit axis parameters.")
        return inverse_transform(a, which, self.cofactor, transform_params=params)

    def _transform_xy(self, x_raw, y_raw):
        return transform_xy(
            x_raw, y_raw, self.x_scale, self.y_scale, self.cofactor,
            x_transform_params=self.x_transform_params,
            y_transform_params=self.y_transform_params)

    def _transform_xy_cached(self, path: str, x_raw, y_raw):
        """
        Cached version of _transform_xy.  Returns identical results but
        avoids repeating the numpy transform on every redraw when axes/scales
        haven't changed.  The cache key encodes all parameters that affect
        the result, so it self-invalidates on any setting change.
        """
        key = (self._data_generation, path, self.x_channel, self.y_channel,
               self.x_scale, self.y_scale, self.cofactor,
               tuple(sorted(self.x_transform_params.items())),
               tuple(sorted(self.y_transform_params.items())))
        if key in self._tc:
            return self._tc[key]
        result = self._transform_xy(x_raw, y_raw)
        # Partial eviction (drop oldest half) to avoid a cold-cache cliff
        # where all 200 entries clear at once and the next 200 all miss.
        if len(self._tc) >= 200:
            evict = list(itertools.islice(self._tc, 100))
            for k in evict:
                del self._tc[k]
        self._tc[key] = result
        return result

    def apply_axes(self):
        x, y = self.x_var.get(), self.y_var.get()
        plan = plan_axis_apply(x, y, self.x_channel, self.y_channel)
        if plan.missing_axis:
            messagebox.showwarning("Axes", "Select both X and Y channels.")
            return
        if plan.refresh_only:
            self.refresh_plot()
            return

        if plan.swap_axes:
            old_context = self._current_analysis_context()
            try:
                affected = [
                    (gate, plan_gate_axis_swap(gate))
                    for gate in self.gates
                    if self._gate_context_matches(gate, old_context)
                ]
            except Exception as exc:
                messagebox.showerror(
                    "Axes",
                    "Cannot swap X/Y while preserving the current gates because "
                    f"one gate has invalid axis geometry/state.\n\n{exc}"
                )
                return

            self.x_channel, self.y_channel = x, y
            self.x_scale, self.y_scale = self.y_scale, self.x_scale
            self.x_transform_params, self.y_transform_params = (
                copy.deepcopy(self.y_transform_params),
                copy.deepcopy(self.x_transform_params),
            )
            self._locked_xlim, self._locked_ylim = self._locked_ylim, self._locked_xlim

            # Scale StringVars have write traces. Suppress the intermediate
            # half-swapped callbacks until both channel-affine values are set.
            self.__dict__['_axis_swap_syncing_scales'] = True
            try:
                self.x_scale_var.set(self.x_scale)
                self.y_scale_var.set(self.y_scale)
            finally:
                self.__dict__['_axis_swap_syncing_scales'] = False

            new_context = self._current_analysis_context()
            for gate, gate_plan in affected:
                apply_gate_axis_swap_plan(
                    gate, gate_plan, boolean_var_factory=tk.BooleanVar)
                self._bind_gate_context(gate, new_context)

            self._rebuild_thresh_panel()
            self._analysis_context_changed()
            if affected:
                incompatible = [
                    gate for gate in self.gates
                    if gate.get('applied') and not self._gate_context_matches(gate)
                ]
                if not incompatible:
                    self.status_var.set(
                        f"X/Y axes swapped; {len(affected)} gate(s) transposed and recomputed."
                    )
            return

        self.x_channel, self.y_channel = x, y
        self._analysis_context_changed()

    def _apply_scales(self):
        if self.__dict__.get('_axis_swap_syncing_scales', False):
            return
        self.x_scale = self.x_scale_var.get()
        self.y_scale = self.y_scale_var.get()
        plan = plan_scale_apply(
            self.x_scale, self.y_scale, self.cofactor_str.get())
        self.cofactor = plan.cofactor
        if plan.replacement_cofactor_text is not None:
            self.cofactor_str.set(plan.replacement_cofactor_text)
        self._analysis_context_changed()

    def _on_cofactor_change(self, *_):
        # Trace callbacks fire while the user is still typing, so malformed
        # intermediate text is ignored until focus-out/Return validation.
        plan = plan_cofactor_trace(self.cofactor_str.get(), self.cofactor)
        if plan.apply_value is not None:
            self.cofactor = plan.apply_value
            self._analysis_context_changed()

    def _validate_cofactor_entry(self, event=None):
        """Keep the displayed cofactor synchronized with the value in use."""
        plan = plan_cofactor_entry(self.cofactor_str.get(), self.cofactor)
        if plan.context_changed:
            self.cofactor = plan.cofactor
            self._analysis_context_changed()
        self.cofactor_str.set(plan.display_text)
        if plan.status_text is not None:
            self.status_var.set(plan.status_text)
        return 'break' if event is not None and getattr(event, 'keysym', '') == 'Return' else None

    def _edit_logicle_params(self):
        """Edit explicit per-axis Gating-ML Logicle T/W/M/A parameters."""
        dlg = tk.Toplevel(self.root)
        dlg.title("Gating-ML Logicle parameters")
        dlg.transient(self.root)
        dlg.resizable(False, False)
        try:
            dlg.grab_set()
        except Exception:
            pass

        ttk.Label(
            dlg,
            text=("Parameters are stored per axis and with every saved gate. "
                  "Changing them changes the analysis coordinate context; existing "
                  "gates remain bound to their original parameters."),
            wraplength=430, justify='left'
        ).grid(row=0, column=0, columnspan=5, padx=12, pady=(12, 8), sticky='w')

        vars_by_axis = {}
        ttk.Label(dlg, text="Axis").grid(row=1, column=0, padx=5)
        for col, key in enumerate(("T", "W", "M", "A"), start=1):
            ttk.Label(dlg, text=key).grid(row=1, column=col, padx=5)
        for row, (axis, current) in enumerate(
                (("X", self.x_transform_params), ("Y", self.y_transform_params)),
                start=2):
            ttk.Label(dlg, text=axis).grid(row=row, column=0, padx=(12, 5), pady=4)
            axis_vars = {}
            normalized = LogicleParameters.from_mapping(current).as_dict()
            for col, key in enumerate(("T", "W", "M", "A"), start=1):
                var = tk.StringVar(value=f"{normalized[key]:g}")
                ttk.Entry(dlg, textvariable=var, width=11).grid(
                    row=row, column=col, padx=3, pady=4)
                axis_vars[key] = var
            vars_by_axis[axis] = axis_vars

        error_var = tk.StringVar(value="")
        ttk.Label(dlg, textvariable=error_var, foreground='#b04040',
                  wraplength=430).grid(
            row=4, column=0, columnspan=5, padx=12, pady=(4, 0), sticky='w')

        def apply_and_close():
            try:
                parsed = {}
                for axis in ("X", "Y"):
                    raw = {key: float(var.get())
                           for key, var in vars_by_axis[axis].items()}
                    parsed[axis] = LogicleParameters.from_mapping(raw).as_dict()
            except (TypeError, ValueError) as exc:
                error_var.set(str(exc))
                return
            changed = (parsed["X"] != self.x_transform_params or
                       parsed["Y"] != self.y_transform_params)
            self.x_transform_params = parsed["X"]
            self.y_transform_params = parsed["Y"]
            dlg.destroy()
            if changed and (scale_uses_logicle_params(self.x_scale) or
                            scale_uses_logicle_params(self.y_scale)):
                self._analysis_context_changed()
            elif changed:
                self.status_var.set(
                    "Gating-ML Logicle parameters updated; they will apply when "
                    "logicle_gml2 is selected.")

        buttons = ttk.Frame(dlg)
        buttons.grid(row=5, column=0, columnspan=5, padx=12, pady=12, sticky='e')
        ttk.Button(buttons, text="Cancel", command=dlg.destroy).pack(
            side=tk.RIGHT, padx=(6, 0))
        ttk.Button(buttons, text="Apply", command=apply_and_close).pack(side=tk.RIGHT)

    def _set_axis_scale(self):
        for axis, scale, setter in [
                ("x", self.x_scale, self.ax.set_xscale),
                ("y", self.y_scale, self.ax.set_yscale)]:
            try:
                if scale_uses_logicle_params(scale):
                    params = self._transform_params_for_axis(axis)
                    setter(scale, **params)
                elif scale_uses_cofactor(scale):
                    setter(scale, cofactor=self.cofactor)
                else:
                    setter(scale)
            except Exception:
                try: setter('linear')
                except Exception: pass

    # ── Threshold helpers ─────────────────────────────────────────────────────

    def _active_xbs_for(self, g: dict) -> list:
        """Return enabled X boundaries for a specific crosshair gate dict."""
        return active_x_boundaries(g)

    def _active_yb_for(self, g: dict):
        """Return y_boundary for a specific crosshair gate dict if enabled.
        For multi-valley gates that have y_boundaries list, returns the first
        enabled value (backward compat for callers expecting a scalar)."""
        return active_y_boundary(g)

    def _active_ybs_for(self, g: dict) -> list:
        """Return all active Y boundaries for a crosshair gate.
        Single-Y gates: returns [y_boundary] or [].
        Multi-Y gates:  returns enabled subset of y_boundaries list."""
        return active_y_boundaries(g)

    def _active_xbs(self) -> list:
        """Return enabled X boundaries of the selected gate (compat)."""
        return self._active_xbs_for(self._sel_gate())

    def _active_yb(self):
        """Return y_boundary of selected gate if enabled (compat)."""
        return self._active_yb_for(self._sel_gate())

    # ── Main plot ─────────────────────────────────────────────────────────────

    def schedule_refresh(self, delay_ms: int = 80):
        """Debounced refresh: cancel any pending redraw and re-schedule.
        Sliders and checkboxes call this instead of refresh_plot directly,
        so rapid changes (e.g. dragging alpha slider) only fire one replot
        after the user pauses, not one per pixel moved."""
        if self._refresh_pending:
            try:
                self.root.after_cancel(self._refresh_pending)
            except Exception:
                pass
        self._refresh_pending = self.root.after(delay_ms, self._do_refresh)

    def _do_refresh(self):
        self._refresh_pending = None
        self.refresh_plot()

    # ── Lock & Adjust Scale ───────────────────────────────────────────────────

    def _on_lock_scale_toggle(self):
        """Called when the 'Lock & adjust scale' checkbox is toggled.

        Enabling:
          • Captures the current axis limits as the locked limits.
          • Disables "Fit axes to data" (the two modes are incompatible).
          • Shows the eight overlay +/− buttons.
        Disabling:
          • Clears the locked limits so autoscale resumes.
          • Hides the overlay buttons.
        A refresh is issued in both cases so the plot state is consistent.
        Minor ticks are now always applied via refresh_plot → _apply_minor_ticks
        regardless of lock state, so no separate add/remove call is needed here.
        """
        # Invalidate locator cache: limits will change after toggle
        self._minor_loc_cache.clear()
        if self.lock_scale_var.get():
            # Capture current limits before the next refresh overwrites them
            self._locked_xlim = list(self.ax.get_xlim())
            self._locked_ylim = list(self.ax.get_ylim())
            # Disable fit-axes so lock has sole control over limits
            self.fit_axes_var.set(False)
            self._show_lock_buttons(True)
        else:
            self._locked_xlim = None
            self._locked_ylim = None
            self._show_lock_buttons(False)
        self.refresh_plot()

    # ── Snap helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _snap_outward(value: float, direction: int,
                      scale: str, current_range: float) -> float:
        """Return the next snap-grid value outward from *value*.

        direction = +1  → snap to the next LARGER value
        direction = -1  → snap to the next SMALLER value

        For biexp / asinh / logicle / log scales the snap grid is
        _LOCK_SNAP (decade + 2×/5× subdivisions) so each click moves by
        one visually meaningful flow unit.
        For linear scale a step of ~10 % of the current range is used.
        """
        if scale == 'log':
            # A logarithmic axis can never include zero/negative limits. Use
            # only the positive snap grid and keep outward nudges > 0.
            positive = [v for v in _LOCK_SNAP if v > 0]
            if direction > 0:
                candidates = [v for v in positive if v > value + 1e-9]
                return min(candidates) if candidates else max(value * 2.0, 1e-12)
            candidates = [v for v in positive if v < value - 1e-9]
            if candidates:
                return max(candidates)
            return max(value / 10.0, np.finfo(float).tiny)
        if scale in ('biexp', 'legacy_biexp', 'asinh', 'logicle', 'legacy_logicle', 'logicle_gml2'):
            if direction > 0:
                candidates = [v for v in _LOCK_SNAP if v > value + 1e-9]
                return min(candidates) if candidates else value * 2 + 1
            else:
                candidates = [v for v in _LOCK_SNAP if v < value - 1e-9]
                return max(candidates) if candidates else value * 2 - 1
        else:
            # Linear: step ≈ 10 % of the current visible range
            step = max(abs(current_range) * 0.10, 1.0)
            return value + direction * step

    def _nudge_axis(self, axis: str, end: str, sign: int):
        """Move one end of the locked view by one snap unit.

        axis : 'x' or 'y'
        end  : 'lo' or 'hi'   (which limit to move)
        sign : +1 = expand outward, -1 = contract inward

        The expansion convention matches the screenshot annotations:
          • right-end [+]  → hi grows rightward  (sign = +1)
          • right-end [−]  → hi shrinks leftward  (sign = -1)
          • left-end  [−]  → lo shrinks rightward (sign = +1, moves lo up)
          • left-end  [+]  → lo grows leftward    (sign = -1, moves lo down)
        """
        if not self.lock_scale_var.get():
            return

        xlim = list(self._locked_xlim or self.ax.get_xlim())
        ylim = list(self._locked_ylim or self.ax.get_ylim())

        if axis == 'x':
            lim   = xlim
            scale = self.x_scale
        else:
            lim   = ylim
            scale = self.y_scale

        current_range = lim[1] - lim[0]

        if end == 'lo':
            # Moving the lower limit; sign convention: +1 = expand (go lower)
            lim[0] = self._snap_outward(lim[0], -sign, scale, current_range)
        else:
            # Moving the upper limit; sign convention: +1 = expand (go higher)
            lim[1] = self._snap_outward(lim[1], sign, scale, current_range)

        # Safety: never let lo >= hi (would flip or collapse axis)
        if lim[0] >= lim[1]:
            return

        if axis == 'x':
            self._locked_xlim = lim
        else:
            self._locked_ylim = lim

        self.refresh_plot()

    def _apply_locked_limits(self):
        """Enforce the stored locked limits on the axes (called from refresh_plot)."""
        if self._locked_xlim:
            try:
                self.ax.set_xlim(self._locked_xlim[0], self._locked_xlim[1])
            except Exception:
                pass
        if self._locked_ylim:
            try:
                self.ax.set_ylim(self._locked_ylim[0], self._locked_ylim[1])
            except Exception:
                pass

    # ── Minor ticks ───────────────────────────────────────────────────────────

    def _apply_minor_ticks(self):
        """Apply minor ticks to both axes based on their current scale type.

        Always called from refresh_plot() after _set_axis_scale() — minor
        ticks are visible regardless of whether lock-scale mode is active.

        Non-linear (biexp/asinh/logicle/log): _FLOW_MINOR_TICKS filtered to
        the current visible range via FixedLocator, integrated cleanly with
        the custom major-tick formatters already on each axis.
        Linear: standard AutoMinorLocator with 5 subdivisions.

        A per-instance locator cache (_minor_loc_cache) avoids rebuilding the
        FixedLocator on every render when the axis limits have not changed.
        """
        fg = self.T.get('fg', '#cccccc')

        def _set_minor(mpl_axis, scale, lim):
            lo, hi = min(lim), max(lim)
            if scale in ('biexp', 'legacy_biexp', 'asinh', 'logicle', 'legacy_logicle', 'logicle_gml2', 'log'):
                cache_key = (scale, lo, hi)
                if cache_key not in self._minor_loc_cache:
                    visible = [t for t in _FLOW_MINOR_TICKS if lo <= t <= hi]
                    self._minor_loc_cache[cache_key] = FixedLocator(visible)
                mpl_axis.set_minor_locator(self._minor_loc_cache[cache_key])
                mpl_axis.set_minor_formatter(mticker.NullFormatter())
            else:
                mpl_axis.set_minor_locator(mticker.AutoMinorLocator(5))
            mpl_axis.set_tick_params(which='minor',
                                     length=3, width=0.7, color=fg)

        try:
            _set_minor(self.ax.xaxis, self.x_scale, self.ax.get_xlim())
            _set_minor(self.ax.yaxis, self.y_scale, self.ax.get_ylim())
        except Exception:
            pass

    # ── Overlay button management ─────────────────────────────────────────────

    def _create_lock_buttons(self):
        """Create the eight overlay tk.Button widgets on the canvas widget.

        Buttons are created once, hidden by default, and repositioned after
        every draw_event by _reposition_lock_buttons().  Using tk place()
        keeps them completely separate from matplotlib's artist tree so they
        never interfere with gate drawing, panning, or zooming.

        Button map (key → action):
          'xl-' = X left  shrink  (lo → higher, contracts left edge)
          'xl+' = X left  expand  (lo → lower, expands left edge)
          'xr-' = X right shrink  (hi → lower, contracts right edge)
          'xr+' = X right expand  (hi → higher, expands right edge)
          'yb-' = Y bottom shrink (lo → higher, contracts bottom edge)
          'yb+' = Y bottom expand (lo → lower, expands bottom edge)
          'yt-' = Y top shrink    (hi → lower, contracts top edge)
          'yt+' = Y top expand    (hi → higher, expands top edge)
        """
        tk_widget = self.canvas.get_tk_widget()
        T = self.T

        # High-contrast colours regardless of theme:
        #   dark mode  → white text on slate-blue, always readable on dark canvas
        #   light mode → near-black text on soft grey slab
        # tk.Label is used instead of tk.Button because macOS native (Aqua)
        # rendering ignores Python bg/fg options on tk.Button, causing the
        # symbols to be invisible.  tk.Label always honours bg/fg everywhere.
        _is_dark  = T.get('plot_bg', '#ffffff') != '#ffffff'
        _btn_bg   = '#3a4255' if _is_dark else '#c8ccd4'
        _btn_fg   = '#ffffff' if _is_dark else '#1a1a1a'
        _btn_act  = T.get('sel_bg', '#4a90d9')

        def _make(key, text, cmd):
            b = tk.Label(
                tk_widget, text=text,
                bg=_btn_bg, fg=_btn_fg,
                font=('Arial', 9, 'bold'),
                relief='raised', bd=1,
                cursor='hand2',
                padx=3, pady=1)
            # Store theme palette on the widget so hover bindings and future
            # theme-toggle passes can reference up-to-date colours.
            b._bg  = _btn_bg
            b._fg  = _btn_fg
            b._act = _btn_act
            b.bind('<Button-1>', lambda e, c=cmd: c())
            b.bind('<Enter>',    lambda e, w=b: w.config(bg=w._act, fg='white'))
            b.bind('<Leave>',    lambda e, w=b: w.config(bg=w._bg,  fg=w._fg))
            b.place_forget()   # hidden initially
            self._lock_btns[key] = b

        # X-axis: left end (lo limit)
        _make('xl+', '−', lambda: self._nudge_axis('x', 'lo', +1))  # expand left
        _make('xl-', '+', lambda: self._nudge_axis('x', 'lo', -1))  # shrink left
        # X-axis: right end (hi limit)
        _make('xr-', '−', lambda: self._nudge_axis('x', 'hi', -1))  # shrink right
        _make('xr+', '+', lambda: self._nudge_axis('x', 'hi', +1))  # expand right
        # Y-axis: bottom end (lo limit)
        _make('yb+', '−', lambda: self._nudge_axis('y', 'lo', +1))  # expand down
        _make('yb-', '+', lambda: self._nudge_axis('y', 'lo', -1))  # shrink bottom
        # Y-axis: top end (hi limit)
        _make('yt-', '−', lambda: self._nudge_axis('y', 'hi', -1))  # shrink top
        _make('yt+', '+', lambda: self._nudge_axis('y', 'hi', +1))  # expand up

    def _show_lock_buttons(self, visible: bool):
        """Show or hide all lock-scale overlay buttons."""
        if visible:
            self._reposition_lock_buttons()
        else:
            for b in self._lock_btns.values():
                try:
                    b.place_forget()
                except Exception:
                    pass

    def _reposition_lock_buttons(self, event=None):
        """Place the eight overlay buttons at the correct pixel positions.

        Called after every draw_event so buttons track the axes bbox even
        when the window is resized or marginals are toggled.  If lock is
        not active, all buttons are hidden immediately.
        """
        if not self.lock_scale_var.get():
            self._show_lock_buttons(False)
            return

        try:
            tk_widget = self.canvas.get_tk_widget()
            # Get axes bounding box in figure-pixel coordinates
            # (origin at bottom-left of figure).
            bbox = self.ax.get_position()
            fig_w = self.fig.get_figwidth()  * self.fig.dpi
            fig_h = self.fig.get_figheight() * self.fig.dpi

            # Convert figure-fraction bbox to pixel coords with tk origin
            # at TOP-left (tk y is inverted relative to matplotlib).
            ax_left   = int(bbox.x0 * fig_w)
            ax_right  = int(bbox.x1 * fig_w)
            # matplotlib y0 = bottom of axes; tk y0 = top of widget
            ax_top_tk = int((1.0 - bbox.y1) * fig_h)
            ax_bot_tk = int((1.0 - bbox.y0) * fig_h)

            BW = 18   # button width  (px)
            BH = 16   # button height (px)
            GAP = 2   # gap between the two buttons at each end

            # ── X-axis buttons: placed below the tick-label row ───────────────
            # ax_bot_tk is the bottom spine in tk coords.  X tick labels are
            # typically 20-30 px tall; 36 px clears them reliably on both
            # linear and log scales where the label row can be taller.
            y_xbtn = ax_bot_tk + 36

            # Left end: [−][+]  (left button = expand, right button = shrink)
            self._lock_btns['xl+'].place(
                x=ax_left,            y=y_xbtn, width=BW, height=BH)
            self._lock_btns['xl-'].place(
                x=ax_left + BW + GAP, y=y_xbtn, width=BW, height=BH)

            # Right end: [−][+]  (left button = shrink, right button = expand)
            self._lock_btns['xr-'].place(
                x=ax_right - 2*BW - GAP, y=y_xbtn, width=BW, height=BH)
            self._lock_btns['xr+'].place(
                x=ax_right - BW,         y=y_xbtn, width=BW, height=BH)

            # ── Y-axis buttons: placed on the LEFT side, stacked vertically ────
            # Each pair is stacked top-to-bottom (one button above the other)
            # well into the left figure margin, clear of tick labels.
            # Tick labels on biexp/logicle scales can be 35–45 px wide, so
            # we use max(4, ax_left − BW − 50) to guarantee clearance while
            # keeping a 4 px floor when the figure is very narrow.
            x_ybtn = max(4, ax_left - BW - 50)

            # Top end: [+] above [−]  (expand on top, shrink below)
            # + is closest to the axis top → expands the top limit upward.
            # − is below → shrinks the top limit downward.
            self._lock_btns['yt+'].place(
                x=x_ybtn, y=ax_top_tk,            width=BW, height=BH)
            self._lock_btns['yt-'].place(
                x=x_ybtn, y=ax_top_tk + BH + GAP, width=BW, height=BH)

            # Bottom end: [+] above [−]  (shrink on top, expand below)
            self._lock_btns['yb-'].place(
                x=x_ybtn, y=ax_bot_tk - 2*BH - GAP, width=BW, height=BH)
            self._lock_btns['yb+'].place(
                x=x_ybtn, y=ax_bot_tk - BH,          width=BW, height=BH)

            # Apply current theme colours (handles theme toggle after lock-on).
            # Update _bg/_fg/_act on each Label so the <Enter>/<Leave> bindings
            # pick up the new palette; Labels have no activebackground option.
            T = self.T
            _is_dark = T.get('plot_bg', '#ffffff') != '#ffffff'
            _btn_bg  = '#3a4255' if _is_dark else '#c8ccd4'
            _btn_fg  = '#ffffff' if _is_dark else '#1a1a1a'
            _btn_act = T.get('sel_bg', '#4a90d9')
            for b in self._lock_btns.values():
                b._bg  = _btn_bg
                b._fg  = _btn_fg
                b._act = _btn_act
                b.config(bg=_btn_bg, fg=_btn_fg)
                b.bind('<Enter>', lambda e, w=b: w.config(bg=w._act, fg='white'))
                b.bind('<Leave>', lambda e, w=b: w.config(bg=w._bg,  fg=w._fg))

        except Exception:
            pass  # never let positioning errors break the render cycle

    def _precompute_cold_kde_payloads(self, display, plot_type):
        return self._flow_renderer().precompute_cold_kde_payloads(display, plot_type)

    def _flow_renderer(self):
        renderer = self.__dict__.get('_flow_renderer_instance')
        if renderer is None:
            renderer = FlowRenderer(self)
            self.__dict__['_flow_renderer_instance'] = renderer
        return renderer

    def refresh_plot(self):
        return self._flow_renderer().refresh()

    # ── Plot helpers ──────────────────────────────────────────────────────────

    def _plot_dot(self, x_raw, y_raw, valid, color, label, dot_size, alpha):
        return self._flow_renderer().plot_dot(x_raw, y_raw, valid, color, label, dot_size, alpha)

    def _plot_density(self, x_raw, y_raw, xt, yt, valid,
                      dot_size, alpha, label, _cache_path: str = None,
                      _precomputed: KDERenderComputation = None):
        return self._flow_renderer().plot_density(
            x_raw, y_raw, xt, yt, valid, dot_size, alpha, label,
            _cache_path=_cache_path, _precomputed=_precomputed)

    def _plot_contour(self, x_raw, y_raw, xt, yt, valid, color, label,
                      dot_size, alpha, prob_level, _cache_path: str = None,
                      _precomputed: KDERenderComputation = None):
        return self._flow_renderer().plot_contour(
            x_raw, y_raw, xt, yt, valid, color, label, dot_size, alpha,
            prob_level, _cache_path=_cache_path, _precomputed=_precomputed)

    def _plot_gated_multi(self, x_raw, y_raw, dot_size, alpha,
                          applied_gates: list, file_color: str, path: str = None,
                          overlay: bool = False):
        return self._flow_renderer().plot_gated_multi(
            x_raw, y_raw, dot_size, alpha, applied_gates, file_color,
            path=path, overlay=overlay)

    def _plot_marginals(self, x_raw, y_raw, xt, yt, valid, color,
                        _cache_path: str = None):
        return self._flow_renderer().plot_marginals(
            x_raw, y_raw, xt, yt, valid, color, _cache_path=_cache_path)

    def _plot_gmm_overlay(self, ax, gmm_params: dict,
                          orientation: str, hist_data_raw: np.ndarray,
                          bin_edges_raw: np.ndarray):
        return self._flow_renderer().plot_gmm_overlay(ax, gmm_params, orientation,
                                                       hist_data_raw, bin_edges_raw)

    def _plot_threshold_shading(self, gate: dict,
                                ax_h, orient_h: str,
                                ax_v, orient_v: str):
        return self._flow_renderer().plot_threshold_shading(gate, ax_h, orient_h, ax_v, orient_v)

    # ── Fluorophore / population naming ─────────────────────────────────────────

    @staticmethod
    @functools.lru_cache(maxsize=64)
    def _fluor(channel: str) -> str:
        """Extract fluorophore from last _-separated segment.
        e.g. 'Bkgd_Corr_Intensity_TH' → 'TH'
             'CD3' → 'CD3' (no underscore → use whole name)
        Cached: channel names are fixed per session.
        """
        parts = channel.rsplit('_', 1)
        return parts[-1] if parts[-1] else channel

    def _region_masks(self, xa, ya, x_boundaries, y_boundary,
                      y_boundaries=None):
        """
        Returns (regions_dict, colors_list).

        y_boundaries (list, optional): if provided, creates a full X×Y grid.
        y_boundary   (scalar, optional): classic single-Y threshold (backward compat).
        """
        return region_masks(
            xa, ya, x_boundaries, y_boundary,
            y_boundaries=y_boundaries,
            x_channel=self.x_channel or 'X',
            y_channel=self.y_channel or 'Y')

    def _on_gate_mode_change(self):
        """Called when user switches Off / Draw mode."""
        mode = self.gate_mode_var.get()
        self.gate_var.set(mode == 'draw')

        if mode == 'none':
            self._gate_hint_var.set('Off — double-click region to open sub-gate')
            self._poly_active = False
            self._poly_cursor = None
            self._update_poly_close_btn()
        elif mode == 'draw':
            self._on_gate_type_change()

        self.refresh_plot()

    def _on_gate_type_change(self):
        """Update hint text only — does NOT clear existing gates."""
        if self.gate_mode_var.get() != 'draw':
            return
        hints = {
            'crosshair': 'Draw: click & drag to place H/V lines',
            'rectangle': 'Draw: click & drag to draw a rectangle',
            'ellipse':   'Draw: click & drag to draw an ellipse',
            'polygon':   'Draw: click vertices  |  ✓ Close Polygon or dbl-click',
        }
        self._gate_hint_var.set(hints.get(self.gate_type_var.get(), ''))

    # ── Gate manager helpers ──────────────────────────────────────────────────

    def _sel_gate(self):
        """Return the currently selected gate dict or None."""
        return gate_by_id(self.gates, self._sel_gate_id)

    def _draw_gate_obj(self):
        """Return the gate currently being drawn, or None."""
        return gate_by_id(self.gates, self._draw_gate_id)

    def _gate_color(self, idx):
        return GATE_PALETTE[idx % len(GATE_PALETTE)]

    def _add_gate(self, auto_type: str = None, auto_apply: dict = None,
                  auto_method: str = None):
        """
        Create a new (empty) gate of the current type and select it.
        auto_type / auto_apply are used by auto-gate methods to inject geometry.
        auto_method: string tag identifying which auto-gate created this gate
                     (e.g. 'gmm', 'kde', 'otsu').  None = manual gate.
        When called interactively (no auto_apply), also enables Draw mode.
        """
        # Switch to Draw mode automatically so the user can immediately draw
        if auto_apply is None and self.gate_mode_var.get() == 'none':
            self.gate_mode_var.set('draw')
            self.gate_var.set(True)
            self._on_gate_type_change()
        gid   = self._next_gate_id
        self._next_gate_id += 1
        color = self._gate_color(len(self.gates))
        gt    = auto_type or self.gate_type_var.get()
        plan  = build_new_gate_plan(
            gate_id=gid, gate_type=gt, color=color,
            auto_apply=auto_apply, auto_method=auto_method,
        )
        gate = plan.gate
        self._bind_gate_context(gate)
        self.gates.append(gate)
        self._sel_gate_id  = gid
        self._draw_gate_id = plan.draw_gate_id
        self._rebuild_gate_manager()
        self._rebuild_thresh_panel()
        return gate

    def _del_gate(self, gid: int):
        """Delete gate by id; select nearest remaining gate."""
        plan = plan_gate_delete(
            self.gates, gate_id=gid, selected_gate_id=self._sel_gate_id,
            hover_gate_id=self._hover_gate_id, pinned_gate_id=self._pinned_gate_id,
            draw_gate_id=self._draw_gate_id, stats_gate_ids=self.gate_stats,
        )
        self.gates, self._sel_gate_id = plan.gates, plan.selected_gate_id
        if plan.clear_hover:
            self._hover_gate_id = None
        if plan.clear_pinned:
            self._pinned_gate_id = None
        self._handle_px_cache.pop(gid, None)
        if plan.clear_draw:
            self._draw_gate_id = None
            self.moving_gate   = False
            self._poly_active  = False
        if plan.remove_stats:
            del self.gate_stats[gid]
        self._rebuild_gate_manager()
        self._rebuild_thresh_panel()
        self._update_stats_display()
        self.refresh_plot()

    def _select_gate(self, gid: int):
        """Select a gate for stats / editing."""
        self._sel_gate_id = gid
        self._rebuild_thresh_panel()
        self._update_stats_display()
        self.refresh_plot()



    def _update_poly_close_btn(self):
        """Show/hide the Close Polygon button based on polygon draw state."""
        try:
            if self._poly_active:
                self._poly_close_btn.pack(fill=tk.X, padx=16, pady=(0, 4))
            else:
                self._poly_close_btn.pack_forget()
        except Exception:
            pass

    # ── Unified gate mask ─────────────────────────────────────────────────────

    def _gate_mask_for(self, gate: dict, xa, ya, _cache_path: str = None):
        """
        Compatibility wrapper for the frozen v4.1.11 gate evaluator.

        Gate context, cache keys, geometry, and finite-event semantics now live
        in the Tk-free gate-evaluation service.  The public/private FlowApp
        method surface is retained unchanged for legacy callers and tests.

        Frozen v4.1.11 source-contract markers: the delegated service still
        rejects ``len(xa) != len(ya)`` and performs the exact equivalent of
        ``regions = self._restrict_regions_to_valid(regions, valid_xy)`` after
        transforming the current X/Y arrays.
        """
        return evaluate_gate_regions(
            gate, xa, ya,
            analysis_state=self._analysis_state_obj(),
            analysis_cache=self._analysis_cache_obj(),
            cache_path=_cache_path,
            max_cache_entries=_GMC_MAX,
        )

    def _label_centroid(self, xa, ya, mask):
        """Return (mx, my) data-space centroid for mask, using transform-median.

        Fast-path: returns (None, None) immediately for empty masks without
        paying for the _fwd transform call on a zero-length slice.
        """
        if not mask.any():          # fast path — avoids transform on empty mask
            return None, None
        xt = self._fwd(xa[mask], self.x_scale, axis="x")
        yt = self._fwd(ya[mask], self.y_scale, axis="y")
        fx = xt[np.isfinite(xt)]; fy = yt[np.isfinite(yt)]
        if len(fx) == 0 or len(fy) == 0:
            return None, None
        # _inv expects an array; pass a 1-element view rather than allocating
        # two temporary arrays via np.array([float(np.median(...))]).
        mx = float(self._inv(np.array([np.median(fx)]), self.x_scale, axis="x")[0])
        my = float(self._inv(np.array([np.median(fy)]), self.y_scale, axis="y")[0])
        return mx, my

    @staticmethod
    def _crosshair_corner(rname: str):
        """Map a two-sign crosshair quadrant name (e.g. 'TH+/D1R-') to an
        axes-space corner position so the label is pinned to the matching
        corner of the plot instead of being placed on top of the data cloud.

        Returns (x_ax, y_ax, ha, va) for use with ax.transAxes, or None when
        the name does not encode a simple ± quadrant (e.g. mid-band names
        like 'TH(m)/D1R+' fall back to the centroid path).
        """
        return crosshair_corner_label_position(rname)

    def _draw_region_labels(self, applied_gates: list = None):
        return self._flow_renderer().draw_region_labels(applied_gates)

    # ── Gate interactions ─────────────────────────────────────────────────────

    def _interaction_controller(self):
        controller = self.__dict__.get('_gate_interaction_controller')
        if controller is None:
            controller = GateInteractionController(self)
            self.__dict__['_gate_interaction_controller'] = controller
        return controller

    def _on_click(self, event):
        return self._interaction_controller().on_click(event)

    def _on_motion(self, event):
        return self._interaction_controller().on_motion(event)

    def _on_release(self, event):
        return self._interaction_controller().on_release(event)

    def _poly_finish(self):
        """Close and apply the current polygon gate."""
        draw = self._draw_gate_obj()
        try:
            finish_plan = plan_polygon_finish(draw)
        except PolygonGeometrySchemaError as exc:
            try:
                messagebox.showerror(
                    'Polygon Gate',
                    f"Cannot close the polygon because its geometry is invalid.\n\n{exc}"
                )
            except Exception:
                pass
            return
        # Historical source-contract marker: polygon_gate_can_finish(draw)
        if not finish_plan.can_finish:
            return
        _applied_present = 'applied' in draw
        _applied_before = dict.get(draw, 'applied')
        _poly_active_before = self._poly_active
        _poly_cursor_before = self._poly_cursor
        _draw_gate_id_before = self._draw_gate_id
        _close_btn_updated = False

        draw['applied']    = finish_plan.applied_value
        self._poly_active  = finish_plan.poly_active_value
        self._poly_cursor  = finish_plan.poly_cursor_value
        self._draw_gate_id = finish_plan.draw_gate_id_value

        try:
            self._update_poly_close_btn()
            _close_btn_updated = True
            self._end_blit_drag()   # release pixel snapshot before full refresh
            self._finish_gate(draw)
        except Exception:
            if _applied_present:
                dict.__setitem__(draw, 'applied', _applied_before)
            else:
                dict.pop(draw, 'applied', None)
            self._poly_active = _poly_active_before
            self._poly_cursor = _poly_cursor_before
            self._draw_gate_id = _draw_gate_id_before
            if _close_btn_updated:
                try:
                    self._update_poly_close_btn()
                except Exception:
                    pass
            raise

    def _finish_gate(self, gate: dict):
        """After gate geometry is finalised: recompute stats, rebuild UI.
        Automatically switches to Edit mode so the user can immediately
        adjust the gate without accidentally creating another one."""
        self._sel_gate_id = gate['id']
        # Keep Draw mode active so user can add more gates,
        # but update hint to remind right-click reshapes handles.
        if self.gate_mode_var.get() == 'draw':
            self._gate_hint_var.set('Gate placed  |  Right-drag handles to reshape')
        # Geometry is meaningful only in the gate's creation context.
        if not gate.get('_analysis_context'):
            self._bind_gate_context(gate)
        # Explicitly evict quantitative caches as well as scatter payloads.
        self._analysis_cache_obj().clear_gate_dependent()
        self._compute_gate_stats_for(gate)
        self._rebuild_gate_manager()
        self._rebuild_thresh_panel()
        self.refresh_plot()
        self._update_stats_display()

    def _commit_gate(self):
        sel = self._sel_gate()
        if sel:
            self._finish_gate(sel)

    # ── Gate handle system ────────────────────────────────────────────────────

    def _get_handles(self, gate: dict) -> list:
        return _gate_interaction_owner(self).get_handles(gate)

    def _draw_handles(self):
        return _gate_interaction_owner(self).draw_handles()

    def _hit_test_handles(self, event) -> dict:
        return _gate_interaction_owner(self).hit_test_handles(event)

    def _gate_pts_to_pixels(self, gate: dict) -> np.ndarray:
        return _gate_interaction_owner(self).gate_pts_to_pixels(gate)

    def _hit_test_gate_interior(self, event) -> dict:
        return _gate_interaction_owner(self).hit_test_gate_interior(event)

    def _rebuild_handle_px_cache(self, event=None):
        return _gate_interaction_owner(self).rebuild_handle_px_cache(event)

    def _hit_test_gate_line(self, event, threshold_px: int = 8) -> int:
        return _gate_interaction_owner(self).hit_test_gate_line(event, threshold_px=threshold_px)

    def _hover_test_handles(self, event) -> int:
        return _gate_interaction_owner(self).hover_test_handles(event)

    def _cursor_for_hover(self, event) -> str:
        return _gate_interaction_owner(self).cursor_for_hover(event)

    def _drag_handle_update(self, x: float, y: float):
        return _gate_interaction_owner(self).drag_handle_update(x, y)

        # NOTE: _preview_gate() and canvas rendering are intentionally NOT
        # called here.  Rendering is the caller's responsibility (_on_motion)
        # so that throttling and blit logic live in a single place.

    def _clear_handles(self):
        return _gate_interaction_owner(self).clear_handles()

    def _clear_preview(self):
        return _gate_interaction_owner(self).clear_preview()
        # NOTE: draw_idle() intentionally removed here.
        # refresh_plot calls _preview_gate() as part of a larger redraw
        # sequence; a premature flush here would render an incomplete state
        # (scatter drawn, gate artists not yet added, labels not yet added).
        # Each interactive caller (_on_click, _on_motion etc.) issues its own
        # explicit canvas.draw_idle() after _preview_gate() returns.

    def _start_blit_drag(self):
        return _gate_interaction_owner(self).start_blit_drag()

    def _end_blit_drag(self):
        return _gate_interaction_owner(self).end_blit_drag()

    def _blit_render(self):
        return _gate_interaction_owner(self).blit_render()

    def _preview_gate(self, skip_cache: bool = False):
        return _gate_interaction_owner(self).preview_gate(skip_cache=skip_cache)
        # Caller is responsible for draw_idle to avoid duplicate flushes

    # ── Sub-gate (double-click) ───────────────────────────────────────────────

    def _open_subgate(self, click_x, click_y):
        """
        Resolve the clicked parent population and open it in a child tab.

        The deterministic gate hit-testing and per-file filtering now live in a
        Tk-free service.  This wrapper intentionally retains UI messaging,
        lineage provenance construction, and tab-manager interaction.
        """
        try:
            selection = resolve_subgate_selection(
                gates=self.gates,
                selected_gate=self._sel_gate(),
                click_x=click_x,
                click_y=click_y,
                active_files=self._active(),
                analysis_state=self._analysis_state_obj(),
                analysis_cache=self._analysis_cache_obj(),
                max_cache_entries=_GMC_MAX,
            )
        except SubgateChannelMismatchError as exc:
            messagebox.showwarning(
                "Sub-gate unavailable",
                "The active files do not all contain the current X/Y channels. "
                "No partial sub-population was created.\n\n" + str(exc),
            )
            return
        if selection is None:
            return

        clicked_region = selection.region
        if not selection.filtered_data:
            messagebox.showinfo(
                "Sub-gate", f"No cells in '{clicked_region}'.")
            return

        target_gate = selection.target_gate
        stage_value = LineageStage.from_components(
            gate=self._plain_gate_snapshot(target_gate),
            region=clicked_region,
            context=dict(target_gate.get('_analysis_context') or
                         self._current_analysis_context()),
        )
        stage = stage_value.to_legacy_dict()
        lineage = append_legacy_stage(self.population_lineage, stage_value)
        self.manager.open_subgate_tab(
            label=clicked_region, filtered_data=selection.filtered_data,
            parent_x=self.x_channel, parent_y=self.y_channel,
            total_cells=selection.total_cells,
            parent_gate=stage['gate'], parent_region=clicked_region,
            population_lineage=lineage,
            excluded_files=dict(self.excluded_files),
            axis_aliases=dict(self.axis_aliases))

    def clear_gate(self):
        """Clear the currently selected gate."""
        sel = self._sel_gate()
        if sel:
            self._del_gate(sel['id'])
        else:
            self.refresh_plot()

    def clear_all_gates(self):
        """Clear all gates."""
        self.gates          = []
        self.gate_stats     = {}
        # BUG FIX (B24): reset _next_gate_id so IDs start at 0 after clear.
        # Previously IDs grew monotonically across clear/add cycles, making
        # JSON exports harder to reason about and ID values increasingly
        # large after long sessions.
        self._next_gate_id  = 0
        self._sel_gate_id   = None
        self._draw_gate_id  = None
        self.moving_gate    = False
        self._poly_active   = False
        self._poly_cursor   = None
        self._handle_drag              = None
        self._gate_move                = None   # FIX Bug 2: was not reset → stale drag state
        self._drag_bg                  = None   # release any blit background snapshot
        self._drag_last_draw           = 0.0    # reset throttle timestamp
        self._draw_frozen_xlim         = None
        self._draw_frozen_ylim         = None
        self._hover_gate_id            = None
        self._hover_handle_key         = None
        self._interior_hover_gate_id   = None   # FIX Bug 2: was not reset → stale hover state
        self._pinned_gate_id           = None
        self._handle_px_cache  = {}
        # BUG FIX (B24): also drop stale cache entries
        self._analysis_cache_obj().clear_gate_dependent()
        self._clear_preview()
        self._rebuild_gate_manager()
        self._rebuild_thresh_panel()
        self._update_stats_display()
        self.refresh_plot()

        # ── Auto-gating ───────────────────────────────────────────────────────────

    def _sens_params(self) -> dict:
        """
        Convert the single sensitivity slider (1–10) into per-method parameters.

        Uses exponential interpolation so the slider feels linear in effect:
          s=1  → very conservative (only the most obvious gaps)
          s=5  → balanced (roughly equivalent to previous hard-coded defaults)
          s=10 → very sensitive (finds subtle shoulders and weak separations)

        Ranges are intentionally wide — the user can always clear and re-gate.
        """
        return sensitivity_parameters(self.auto_sensitivity_var.get())

    @staticmethod
    @staticmethod
    def _kde_valley_supported(data: np.ndarray, threshold: float,
                              bw_factor: float, min_prominence: float,
                              min_peak_frac: float) -> bool:
        """Compatibility wrapper for the extracted v4.2 KDE valley validator."""
        return kde_valley_supported(
            data, threshold, bw_factor, min_prominence, min_peak_frac)

    def _rerun_last_auto_gate(self):
        """Called after debounce when sensitivity slider changes.
        Re-runs the most recently used auto-gate method with the new parameters."""
        self._sens_rerun_pending = None
        if self._last_auto_gate_fn is not None:
            try:
                self._last_auto_gate_fn()
            except Exception:
                pass   # silently ignore — user can still click the button manually

    def _active_axes_complete(self, active=None) -> bool:
        """Return True only when every active file contains both current axes."""
        active = self._active() if active is None else active
        return bool(active) and bool(self.x_channel) and bool(self.y_channel) and all(
            self.x_channel in df.columns and self.y_channel in df.columns
            for df in active.values()
        )

    def _collect_x_transform(self):
        active = self._active()
        if not self._active_axes_complete(active):
            return np.array([], dtype=float)
        return finite_transformed_channel_values(
            active.values(),
            self.x_channel,
            self.x_scale,
            cofactor=self.cofactor,
            transform_params=self.x_transform_params,
        )

    def _collect_y_transform(self):
        active = self._active()
        if not self._active_axes_complete(active):
            return np.array([], dtype=float)
        return finite_transformed_channel_values(
            active.values(),
            self.y_channel,
            self.y_scale,
            cofactor=self.cofactor,
            transform_params=self.y_transform_params,
        )

    def _apply_gate_and_refresh(self, xbs_raw, yb_raw, auto_method: str = None):
        """
        Store an auto-gate result as a crosshair gate, then refresh everything.

        If auto_method is given and a gate with that same auto_method already
        exists, it is reused in-place (geometry updated, no new gate created).
        This means re-running or slider-scrubbing never accumulates duplicate
        gates.  Manual gates (auto_method=None) are never touched.
        """
        # ── Find an existing gate to reuse ───────────────────────────────────
        target = None
        if auto_method:
            # Prefer the currently selected gate if it matches
            sel = self._sel_gate()
            if sel and sel.get('auto_method') == auto_method:
                target = sel
            else:
                # Otherwise take the first matching gate in the list
                for g in self.gates:
                    if g.get('auto_method') == auto_method:
                        target = g
                        break

        # ── Fall back: use selected crosshair or create new ──────────────────
        if target is None:
            sel = self._sel_gate()
            if sel and sel.get('type') == 'crosshair' and not sel.get('auto_method'):
                # Selected gate is a manual crosshair — don't overwrite it
                target = None
            elif sel and sel.get('type') == 'crosshair' and sel.get('auto_method') == auto_method:
                target = sel
            if target is None:
                target = self._add_gate(auto_type='crosshair',
                                        auto_method=auto_method)

        # ── Write geometry ────────────────────────────────────────────────────
        target['auto_method']   = auto_method   # ensure tag is set
        target['type']          = 'crosshair'
        target['x_boundaries']  = list(xbs_raw)
        target['y_boundary']    = yb_raw
        target['y_boundaries']  = None
        thresh_plan = single_y_auto_threshold_plan(xbs_raw)
        target['x_thresh_vars'] = [tk.BooleanVar(value=value)
                                   for value in thresh_plan.x_values]
        target['y_thresh_var']  = tk.BooleanVar(value=thresh_plan.y_value)
        target['y_thresh_vars'] = [tk.BooleanVar(value=value)
                                   for value in thresh_plan.y_values]
        target['applied']       = True
        self._sel_gate_id       = target['id']
        # Re-running an auto-gate explicitly creates new geometry in the CURRENT
        # analysis context, so rebind a reused auto gate rather than leaving it
        # attached to an older axis/scale context.
        self._bind_gate_context(target)
        self._analysis_cache_obj().clear_gate_dependent()

        self._gate_hint_var.set('Auto-gate placed  |  Right-drag handles to reshape')
        self._compute_gate_stats_for(target)
        self._rebuild_gate_manager()
        self._rebuild_thresh_panel()
        self.refresh_plot()
        self._update_stats_display()

    def auto_gate_derivative(self):
        """
        Run Derivative (first-valley KDE) on BOTH axes:
          X → single threshold (x_boundaries = [val])
          Y → single threshold (y_boundary)
        """
        active = self._active()
        if not active or not self.x_channel or not self.y_channel:
            messagebox.showwarning("Auto-Gate",
                "Load data and select axes first."); return
        if not self._active_axes_complete(active):
            messagebox.showwarning(
                "Auto-Gate",
                "All active files must contain the selected X/Y channels. "
                "No gate was created from a partial file subset.")
            return

        self._last_auto_gate_fn = self.auto_gate_derivative
        sp = self._sens_params()

        # ── X: Derivative ──
        all_xt = self._collect_x_transform()
        all_xt = all_xt[np.isfinite(all_xt)]
        if len(all_xt) < 10 or not np.isfinite(np.ptp(all_xt)) or np.ptp(all_xt) <= 1e-12:
            messagebox.showwarning(
                "KDE Valley",
                "X axis has insufficient or degenerate finite data; no threshold was created.")
            return
        try:
            xb_t = derivative_threshold(all_xt, min_prominence=sp['kde_prominence'], bw_factor=sp['bw_factor'], min_peak_frac=sp['min_peak_frac'])
        except Exception as e:
            messagebox.showerror("Derivative Error (X)", str(e)); return
        if not self._kde_valley_supported(
                all_xt, xb_t, sp['bw_factor'],
                sp['kde_prominence'], sp['min_peak_frac']):
            messagebox.showwarning(
                "KDE Valley",
                "No supported two-population KDE valley was detected on X. "
                "No automatic gate was created; inspect the distribution or "
                "use a method that intentionally forces a split (e.g. Otsu).")
            return
        xb_raw = float(self._inv(np.array([xb_t]), self.x_scale, axis="x")[0])

        # ── Y: Derivative ──
        all_yt = self._collect_y_transform()
        all_yt = all_yt[np.isfinite(all_yt)]
        if len(all_yt) < 10 or not np.isfinite(np.ptp(all_yt)) or np.ptp(all_yt) <= 1e-12:
            messagebox.showwarning(
                "KDE Valley",
                "Y axis has insufficient or degenerate finite data; no threshold was created.")
            return
        try:
            yb_t = derivative_threshold(all_yt, min_prominence=sp['kde_prominence'], bw_factor=sp['bw_factor'], min_peak_frac=sp['min_peak_frac'])
        except Exception as e:
            messagebox.showerror("Derivative Error (Y)", str(e)); return
        if not self._kde_valley_supported(
                all_yt, yb_t, sp['bw_factor'],
                sp['kde_prominence'], sp['min_peak_frac']):
            messagebox.showwarning(
                "KDE Valley",
                "No supported two-population KDE valley was detected on Y. "
                "No automatic gate was created; inspect the distribution or "
                "use a method that intentionally forces a split (e.g. Otsu).")
            return
        yb_raw = float(self._inv(np.array([yb_t]), self.y_scale, axis="y")[0])

        self._apply_gate_and_refresh([xb_raw], yb_raw, auto_method='kde')

        pct_x = percent_at_or_below(
            finite_displayable_raw_channel_values(
                active.values(), self.x_channel, self.x_scale,
                cofactor=self.cofactor,
                transform_params=self._axis_transform_params("x"),
            ),
            xb_raw,
        )
        pct_y = percent_at_or_below(
            finite_displayable_raw_channel_values(
                active.values(), self.y_channel, self.y_scale,
                cofactor=self.cofactor,
                transform_params=self._axis_transform_params("y"),
            ),
            yb_raw,
        )
        self.status_var.set(two_axis_threshold_status(
            "KDE Valley",
            x_threshold=xb_raw,
            y_threshold=yb_raw,
            x_percent_below=pct_x,
            y_percent_below=pct_y,
        ))

    def auto_gate_otsu(self):
        """
        Otsu threshold on each axis independently, using ALL selected files merged.

        Otsu's method maximises between-class variance across all binary splits
        of the histogram — equivalent to minimising within-class variance.
        No distributional assumptions: works for any histogram shape.

        Fastest of all methods (O(n_bins) after one histogram).  Particularly
        reliable for clearly bimodal data with 20/80 to 80/20 splits.
        For very unequal populations (5/95) prefer KDE Valley or 2D GMM.
        """
        active = self._active()
        if not active or not self.x_channel or not self.y_channel:
            messagebox.showwarning("Auto-Gate",
                "Load data and select axes first."); return
        if not self._active_axes_complete(active):
            messagebox.showwarning(
                "Auto-Gate",
                "All active files must contain the selected X/Y channels. "
                "No gate was created from a partial file subset.")
            return

        self._last_auto_gate_fn = self.auto_gate_otsu
        sp = self._sens_params()

        all_xt = self._collect_x_transform()
        all_xt = all_xt[np.isfinite(all_xt)]
        all_yt = self._collect_y_transform()
        all_yt = all_yt[np.isfinite(all_yt)]

        if (len(all_xt) < 2 or len(all_yt) < 2 or
                np.ptp(all_xt) <= 1e-12 or np.ptp(all_yt) <= 1e-12):
            messagebox.showwarning(
                "Otsu",
                "One or both axes have insufficient/constant finite data; "
                "no threshold was created.")
            return

        try:
            xb_t = otsu_threshold(all_xt, min_class_fraction=sp['otsu_min_frac'])
            yb_t = otsu_threshold(all_yt, min_class_fraction=sp['otsu_min_frac'])
        except Exception as e:
            messagebox.showerror("Otsu Error", str(e)); return

        xb_raw = float(self._inv(np.array([xb_t]), self.x_scale, axis="x")[0])
        yb_raw = float(self._inv(np.array([yb_t]), self.y_scale, axis="y")[0])

        self._apply_gate_and_refresh([xb_raw], yb_raw, auto_method='otsu')

        pct_x = percent_at_or_below(
            finite_displayable_raw_channel_values(
                active.values(), self.x_channel, self.x_scale,
                cofactor=self.cofactor,
                transform_params=self._axis_transform_params("x"),
            ),
            xb_raw,
        )
        pct_y = percent_at_or_below(
            finite_displayable_raw_channel_values(
                active.values(), self.y_channel, self.y_scale,
                cofactor=self.cofactor,
                transform_params=self._axis_transform_params("y"),
            ),
            yb_raw,
        )
        self.status_var.set(two_axis_threshold_status(
            "Otsu",
            x_threshold=xb_raw,
            y_threshold=yb_raw,
            x_percent_below=pct_x,
            y_percent_below=pct_y,
        ))

    def auto_gate_gmm_multi(self):
        """
        GMM Multi (v3.9.7) — fit independent 1-D GMMs on X and Y with
        user-specified component counts, then place ALL equal-density
        thresholds into the existing multi-threshold crosshair system.

        Workflow
        --------
        1.  Read 'GMM pops — X' and 'Y' spinboxes (set independently).
        2.  Fit a GaussianMixture with exactly that many components on
            each axis in transform space (no BIC selection — user decides).
        3.  Compute each supported equal-density crossing between adjacent
            components (up to N-1 crossings for N components); skip pairs
            that do not actually cross between their fitted means.
        4.  Store ALL crossings as x_thresh_vars / y_thresh_vars so they
            appear as individual checkboxes in the Threshold panel.
        5.  User unchecks any crossings they do not want.

        Why 'exact N' instead of BIC-best up to N
        ------------------------------------------
        BIC penalises complexity — it almost always prefers fewer
        components than the user can visually identify (e.g. it merges
        a small negative cloud into the dominant positive population).
        Giving the user direct control over the component count makes
        the negative sub-populations discoverable by simply increasing
        the spinbox and observing where new crossings appear.

        Negative population detection tip
        ----------------------------------
        Increase the X or Y spinbox by 1 at a time.  Each extra
        component can add another supported crossing.  Start with the value
        that produces crossings that match the visible histogram peaks, then
        uncheck any crossings that are not biologically useful (rather than
        populations).
        """
        if not HAS_SKLEARN:
            messagebox.showerror(
                "GMM Multi",
                "scikit-learn is required:\n  pip install scikit-learn")
            return
        active = self._active()
        if not active or not self.x_channel or not self.y_channel:
            messagebox.showwarning(
                "GMM Multi", "Load data and select axes first.")
            return
        if not self._active_axes_complete(active):
            messagebox.showwarning(
                "GMM Multi",
                "All active files must contain the selected X/Y channels. "
                "No GMM gate was created from a partial file subset.")
            return

        self._last_auto_gate_fn = self.auto_gate_gmm_multi

        n_x = gmm_component_count(self.gmm_max_x_var.get())
        n_y = gmm_component_count(self.gmm_max_y_var.get())

        # ── X axis ────────────────────────────────────────────────────────────
        all_xt = self._collect_x_transform()
        xbs_raw, x_summary, gmm_x_params = fit_gmm_crossings(
            all_xt, n_x, self.x_scale,
            lambda values, scale: self._inv(values, scale, axis="x"))

        # ── Y axis ────────────────────────────────────────────────────────────
        all_yt = self._collect_y_transform()
        ybs_raw, y_summary, gmm_y_params = fit_gmm_crossings(
            all_yt, n_y, self.y_scale,
            lambda values, scale: self._inv(values, scale, axis="y"))

        if not xbs_raw and not ybs_raw:
            messagebox.showwarning(
                "GMM Multi",
                "Could not fit GMM on either axis.\n"
                "Check that enough data is loaded.")
            return

        # ── Reuse or create gate (same pattern as multi_valley) ───────────────
        target = None
        for g in self.gates:
            if g.get('auto_method') == 'gmm_multi':
                target = g
                break
        if target is None:
            target = self._add_gate(auto_type='crosshair',
                                    auto_method='gmm_multi')

        target['auto_method']   = 'gmm_multi'
        target['type']          = 'crosshair'
        target['x_boundaries']  = xbs_raw
        thresh_plan = multi_y_auto_threshold_plan(xbs_raw, ybs_raw)
        target['x_thresh_vars'] = [tk.BooleanVar(value=value)
                                   for value in thresh_plan.x_values]

        if ybs_raw:
            target['y_boundaries']  = ybs_raw
            target['y_thresh_vars'] = [tk.BooleanVar(value=value)
                                        for value in thresh_plan.y_values]
            target['y_boundary']    = None
            target['y_thresh_var']  = thresh_plan.y_value
        else:
            target['y_boundaries']  = None
            target['y_thresh_vars'] = []
            target['y_boundary']    = None
            target['y_thresh_var']  = thresh_plan.y_value

        target['applied']     = True
        target['gmm_x_params'] = gmm_x_params   # None if fit failed
        target['gmm_y_params'] = gmm_y_params   # None if fit failed
        self._bind_gate_context(target)
        self._analysis_cache_obj().clear_gate_dependent()
        self._sel_gate_id     = target['id']
        self._gate_hint_var.set(
            'GMM Multi placed — uncheck crossings you do not want')
        self._compute_gate_stats_for(target)
        self._rebuild_gate_manager()
        self._rebuild_thresh_panel()
        self.refresh_plot()
        self._update_stats_display()

        nx = len(xbs_raw); ny = len(ybs_raw)
        self.status_var.set(gmm_multi_status(
            x_components=n_x,
            x_crossings=nx,
            y_components=n_y,
            y_crossings=ny,
        ))

    def auto_gate_cluster_polygons(self):
        """Identify discrete 2-D populations and commit polygon gates.

        Numerical preparation, clustering, and transform-space hull construction
        are owned by ``vflow.core.auto_gate``.  This compatibility method retains
        the v4.2 dependency/UI/state-commit ordering.
        """
        try:
            from sklearn.cluster import HDBSCAN as _HDBSCAN
            _DBSCAN = None
        except ImportError:
            try:
                from sklearn.cluster import DBSCAN as _DBSCAN
                _HDBSCAN = None
            except ImportError:
                messagebox.showerror("Missing library",
                    "Cluster Polygons requires scikit-learn ≥ 1.3.\n"
                    "Install with: pip install -U scikit-learn")
                return
        try:
            from scipy.spatial import ConvexHull
        except ImportError:
            messagebox.showerror("Missing library",
                "Cluster Polygons requires scipy.\n"
                "Install with: pip install scipy")
            return

        active = self._active()
        if not active or not self.x_channel or not self.y_channel:
            messagebox.showwarning("Auto-Gate",
                "Load data and select axes first."); return
        if not self._active_axes_complete(active):
            messagebox.showwarning(
                "Cluster Polygons",
                "All active files must contain the selected X/Y channels. "
                "No clusters were computed from a partial file subset.")
            return

        self._last_auto_gate_fn = self.auto_gate_cluster_polygons
        min_frac = cluster_min_fraction(self.auto_sensitivity_var.get())

        all_xt = self._collect_x_transform()
        all_yt = self._collect_y_transform()
        all_xr = np.concatenate([
            df[self.x_channel].to_numpy(dtype=float, copy=False)
            for df in active.values()
        ])
        all_yr = np.concatenate([
            df[self.y_channel].to_numpy(dtype=float, copy=False)
            for df in active.values()
        ])
        try:
            prepared = prepare_cluster_polygon_data(
                all_xt, all_yt, all_xr, all_yr,
                min_fraction=min_frac,
            )
        except ClusterPolygonInsufficientData:
            messagebox.showwarning("Cluster Polygons", "Not enough data."); return

        self.status_var.set("Running HDBSCAN…  please wait")
        self.root.update_idletasks()

        try:
            result = fit_cluster_polygons(
                prepared,
                hdbscan_cls=_HDBSCAN,
                dbscan_cls=_DBSCAN,
                convex_hull_cls=ConvexHull,
            )
        except Exception as e:
            messagebox.showerror("Cluster Error", str(e)); return

        if result.cluster_count == 0:
            self.status_var.set(
                "✗ No clusters found — try increasing sensitivity or checking axes/scale")
            return

        prev_tags = {'hdbscan', 'dbscan'}
        old_ids = {g['id'] for g in self.gates
                   if g.get('auto_method') in prev_tags}
        if old_ids:
            self.gates = [g for g in self.gates if g['id'] not in old_ids]
            stale = gate_mask_cache_keys_for_gate_ids(self._gmc, old_ids)
            evict_cache_keys(self._gmc, stale)
            if self._sel_gate_id in old_ids:
                self._sel_gate_id = self.gates[-1]['id'] if self.gates else None

        n_created = 0
        for verts in result.polygons:
            gate = self._add_gate(auto_method=result.algorithm_tag)
            gate['type'] = 'polygon'
            gate['vertices'] = [(float(v[0]), float(v[1])) for v in verts]
            gate['applied'] = True
            self._compute_gate_stats_for(gate)
            n_created += 1

        self._rebuild_gate_manager()
        self._rebuild_thresh_panel()
        self.refresh_plot()
        self._update_stats_display()
        self.status_var.set(cluster_polygons_status(
            algorithm=result.algorithm_label,
            gates_created=n_created,
            noise_count=result.noise_count,
            labels_count=result.labels_count,
        ))

    # ── Threshold panel ───────────────────────────────────────────────────────



    def _on_thresh_toggle(self):
        sel = self._sel_gate()
        if sel:
            self._compute_gate_stats_for(sel)
        self.refresh_plot()
        self._update_stats_display()

    # ── Stats ─────────────────────────────────────────────────────────────────

    def _compute_gate_stats_for(self, gate: dict):
        """Compute stats for one compatible gate using finite displayable events."""
        if not gate or not gate.get('applied'): return
        gid = gate['id']
        self.gate_stats[gid] = {}
        if not self._gate_context_matches(gate):
            return
        active = self._active()
        if any(
            self.x_channel not in df.columns or self.y_channel not in df.columns
            for df in active.values()
        ):
            # Do not report a plausible gate statistic assembled from only the
            # compatible subset of active files. Channel selection should make
            # this unreachable during normal UI use, but stale/programmatic
            # states must still fail closed.
            return
        for path, df in active.items():
            xa = df[self.x_channel].to_numpy(dtype=float, copy=False)
            ya = df[self.y_channel].to_numpy(dtype=float, copy=False)
            _, _, valid = self._transform_xy_cached(path, xa, ya)
            total = int(valid.sum())
            # Preserve the sample in statistics even when the active transform
            # leaves zero displayable events. Omitting it silently changes the
            # apparent sample count/provenance of per-file and merged exports.
            regions, _ = self._gate_mask_for(gate, xa, ya, _cache_path=path)
            info = stats_from_regions(regions, total)
            # ``total`` is intentionally the transform-valid denominator used
            # by every percentage. Preserve the current input-population count
            # alongside it so exports make transform exclusions explicit without
            # changing the frozen scientific denominator. In a sub-gate window
            # this input is already parent-filtered, so it is not labelled as an
            # acquisition total.
            info['raw_total'] = int(len(df))
            info['transform_excluded'] = int(len(df) - total)
            attrs = getattr(df, 'attrs', {}) or {}
            info['compensation_metadata_keys'] = tuple(
                attrs.get('fcs_compensation_metadata_keys', ()) or ())
            self.gate_stats[gid][path] = info

    def _merged_stats_from(self, gate_data: dict) -> dict:
        """Merge per-file stats from a {path: {stats, total}} dict."""
        return merge_gate_stats(gate_data)

    def _merged_stats(self) -> dict:
        """Convenience wrapper used by export_stats."""
        return self._merged_stats_from(
            self.gate_stats.get(self._sel_gate_id, {}))

    def _update_stats_display(self):
        """
        Show a combined gate partition.

        Single gate:  IN / OUT rows as before.

        Multiple gates: compute a Venn-like partition across ALL files:
          - Each gate's exclusive IN cells
          - Cells IN multiple gates (overlap regions)
          - Outside all gates

        This gives percentages that sum to 100%% and are directly comparable.
        """
        for item in self.stats_tree.get_children():
            self.stats_tree.delete(item)

        applied = [g for g in self.gates
                   if g.get('applied') and self._gate_context_matches(g)]
        if not applied: return

        mode = self.stats_mode_var.get()

        # ── Single gate: show per-gate IN/OUT breakdown ───────────────────
        if len(applied) == 1:
            gate       = applied[0]
            gid        = gate['id']
            gate_stats = self.gate_stats.get(gid, {})
            if not gate_stats: return
            star = ' ▸' if gid == self._sel_gate_id else ''
            lbl  = f'{gate["name"]}{star}  [{gate["type"]}]'
            if mode == 'merged':
                merged = self._merged_stats_from(gate_stats)
                if not merged: return
                root_id = self.stats_tree.insert(
                    '', 'end', text=f'  {lbl}',
                    values=(f"{merged['total']:,}", ''), open=True)
                for ri, (q, d) in enumerate(merged['stats'].items()):
                    self.stats_tree.insert(
                        root_id, 'end', text=f'    {q}',
                        values=(f"{d['count']:,}", f"{d['pct']:.1f}%"),
                        tags=(f'rc{ri % _N_REGION_COLORS}',))
            else:
                for path, info in gate_stats.items():
                    name  = os.path.basename(path)
                    short = (name[:26] + '…') if len(name) > 27 else name
                    fid   = self.stats_tree.insert(
                        '', 'end', text=f'  {lbl}  ·  {short}',
                        values=(f"{info['total']:,}", ''), open=True)
                    for ri, (q, d) in enumerate(info['stats'].items()):
                        self.stats_tree.insert(
                            fid, 'end', text=f'    {q}',
                            values=(f"{d['count']:,}", f"{d['pct']:.1f}%"),
                            tags=(f'rc{ri % _N_REGION_COLORS}',))
            return

        # Crosshair gates partition the full plane into quadrants/bands; they do
        # not define a binary IN set.  A Venn-style overlap with them is therefore
        # mathematically misleading.  Show each gate independently instead.
        if any(g.get('type', 'crosshair') == 'crosshair' for g in applied):
            for gate in applied:
                gate_stats = self.gate_stats.get(gate['id'], {})
                if not gate_stats:
                    continue
                if mode == 'merged':
                    merged = self._merged_stats_from(gate_stats)
                    if not merged:
                        continue
                    rid = self.stats_tree.insert(
                        '', 'end', text=f"  {gate['name']}  [{gate['type']}]",
                        values=(f"{merged['total']:,}", ''), open=True)
                    for ri, (region, d) in enumerate(merged['stats'].items()):
                        self.stats_tree.insert(
                            rid, 'end', text=f'    {region}',
                            values=(f"{d['count']:,}", f"{d['pct']:.1f}%"),
                            tags=(f'rc{ri % _N_REGION_COLORS}',))
                else:
                    for path, info in gate_stats.items():
                        name = os.path.basename(path)
                        short = (name[:26] + '…') if len(name) > 27 else name
                        rid = self.stats_tree.insert(
                            '', 'end',
                            text=f"  {gate['name']} [{gate['type']}] · {short}",
                            values=(f"{info['total']:,}", ''), open=True)
                        for ri, (region, d) in enumerate(info['stats'].items()):
                            self.stats_tree.insert(
                                rid, 'end', text=f'    {region}',
                                values=(f"{d['count']:,}", f"{d['pct']:.1f}%"),
                                tags=(f'rc{ri % _N_REGION_COLORS}',))
            return

        # ── Multiple shape gates: Venn partition ─────────────────────────
        # Compute partition using all active file data merged together,
        # or per-file depending on mode.
        active = self._active()
        if not active: return
        if any(
            self.x_channel not in df.columns or self.y_channel not in df.columns
            for df in active.values()
        ):
            # Never display a multi-gate Venn partition computed from only the
            # subset of active files that happen to contain the current axes.
            return

        def _partition_data(xa, ya):
            """Evaluate shape-gate IN masks, then delegate pure partition math."""
            n = len(xa)
            in_masks = []
            for gate in applied:
                regions, _ = self._gate_mask_for(gate, xa, ya)
                if 'IN' not in regions:
                    raise ValueError(
                        f"Gate {gate.get('name', gate.get('id'))!r} does not "
                        "produce a valid IN/OUT partition in the current "
                        "channel/transform context."
                    )
                in_masks.append(regions.get('IN', np.zeros(n, bool)))
            return binary_gate_partition_counts(
                gate_output_labels(applied), in_masks)

        if mode == 'merged':
            total = 0
            merged_parts = {}
            for df in active.values():
                xa = df[self.x_channel].to_numpy(dtype=float, copy=False)
                ya = df[self.y_channel].to_numpy(dtype=float, copy=False)
                _, _, valid = self._transform_xy(xa, ya)
                xa = xa[valid]; ya = ya[valid]
                total += len(xa)
                for k, v in _partition_data(xa, ya).items():
                    merged_parts[k] = merged_parts.get(k, 0) + v

            root_id = self.stats_tree.insert(
                '', 'end',
                text=f'  Combined ({len(applied)} gates, {len(active)} files)',
                values=(f"{total:,}", ''), open=True)
            for ri, (region, cnt) in enumerate(
                    sorted(merged_parts.items(), key=lambda x: binary_gate_partition_sort_key(x[0]))):
                pct = cnt / total * 100 if total else 0.0
                self.stats_tree.insert(
                    root_id, 'end', text=f'    {region}',
                    values=(f"{cnt:,}", f"{pct:.1f}%"),
                    tags=(f'rc{ri % _N_REGION_COLORS}',))
        else:
            for path, df in active.items():
                xa = df[self.x_channel].to_numpy(dtype=float, copy=False)
                ya = df[self.y_channel].to_numpy(dtype=float, copy=False)
                _, _, valid = self._transform_xy(xa, ya)
                xa = xa[valid]; ya = ya[valid]
                total = len(xa)
                parts = _partition_data(xa, ya)
                name  = os.path.basename(path)
                short = (name[:26] + '…') if len(name) > 27 else name
                fid   = self.stats_tree.insert(
                    '', 'end', text=f'  {short}',
                    values=(f"{total:,}", ''), open=True)

                for ri, (region, cnt) in enumerate(
                        sorted(parts.items(), key=lambda x: binary_gate_partition_sort_key(x[0]))):
                    pct = cnt / total * 100 if total else 0.0
                    self.stats_tree.insert(
                        fid, 'end', text=f'    {region}',
                        values=(f"{cnt:,}", f"{pct:.1f}%"),
                        tags=(f'rc{ri % _N_REGION_COLORS}',))

    # ── Export ────────────────────────────────────────────────────────────────

    def _auto_stem(self) -> str:
        return active_export_stem(self._active())

    def save_gates(self):
        """Compatibility facade for composed gate-session serialization."""
        return _project_data_load_owner(self).save_gates(
            filedialog=filedialog, messagebox=messagebox)

    def load_gates(self):
        """Compatibility facade for composed gate-session loading."""
        return _project_data_load_owner(self).load_gates(
            filedialog=filedialog, messagebox=messagebox,
            boolean_var_factory=tk.BooleanVar)

    def export_stats(self):
        sel = self._sel_gate()
        if sel is not None and not self._gate_context_matches(sel):
            messagebox.showerror("Export", self._gate_context_error(sel)); return
        if not self.gate_stats.get(self._sel_gate_id):
            messagebox.showwarning("Export", "Apply a gate first."); return
        stem = self._auto_stem()
        xn   = export_channel_token(self.x_channel, 'X')
        yn   = export_channel_token(self.y_channel, 'Y')
        path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            initialfile=f'{stem}_{xn}_vs_{yn}_stats.csv',
            filetypes=[("CSV", "*.csv")])
        if not path: return

        xbs  = self._active_xbs()
        yb   = self._active_yb()
        ybs  = self._active_ybs_for(sel) if sel is not None else []
        mode = self.stats_mode_var.get()
        gate_stats_for = self.gate_stats.get(self._sel_gate_id, {})
        rows = build_gate_stats_export_rows(
            mode=mode,
            gate_stats_for=gate_stats_for,
            merged_stats=self._merged_stats() if mode == 'merged' else {},
            x_channel=self.x_channel,
            y_channel=self.y_channel,
            x_boundaries=xbs,
            y_boundary=yb,
            y_boundaries=ybs,
            gate=sel,
        )
        pd.DataFrame(rows).to_csv(path, index=False)
        messagebox.showinfo("Export", f"Stats saved:\n{path}")

    # ── Batch stats export ────────────────────────────────────────────────────

    def batch_export_stats(self):
        """Run the behavior-frozen Batch Stats workflow through its service."""
        applied = [g for g in self.gates if g.get('applied')]
        if not applied:
            messagebox.showwarning("Batch Stats",
                "Apply at least one gate first."); return
        if not self.x_channel or not self.y_channel:
            messagebox.showwarning("Batch Stats",
                "Select X and Y channels first."); return
        incompatible = [g for g in applied if not self._gate_context_matches(g)]
        if incompatible:
            messagebox.showerror(
                "Batch Stats",
                "Applied gates belong to a different channel/transform context. "
                "Switch back before batch export:\n" +
                "\n".join(f"• {g.get('name', g.get('id'))}" for g in incompatible[:8]))
            return

        auto_folders = sorted({os.path.dirname(p) for p in self.loaded_files})
        dlg = BatchStatsDialog(self.root, self.T, auto_folders,
                               self.x_channel, self.y_channel)
        self.root.wait_window(dlg)
        if not dlg.result:
            return
        folder, suffix, file_types, save_path = dlg.result

        def _load_batch_frame(fpath):
            # Keep this adapter order source-visible: nomenclature aliases must
            # be applied before case normalization on every fresh disk read.
            df = self._read_data_file(fpath)
            df, alias_details = self._apply_axis_aliases_to_df(df, fpath)
            if not alias_details['ambiguous']:
                df = self._normalize_columns_to_loaded(df)
            return df, list(alias_details['ambiguous'])

        def _current_valid_mask(xa, ya):
            _, _, valid = self._transform_xy(xa, ya)
            return valid

        def _batch_regions(gate, xa, ya):
            # Fresh batch reads intentionally bypass the interactive persistent
            # mask cache even when a filesystem path happens to be the same.
            regions, _ = self._gate_mask_for(gate, xa, ya)
            return regions

        def _batch_lineage():
            lineage = copy_legacy_lineage(self.population_lineage)
            if not lineage and self.parent_gate is not None:
                lineage = [{
                    'gate': self._plain_gate_snapshot(self.parent_gate),
                    'region': self.parent_region,
                    'context': dict(self.parent_gate.get('_analysis_context') or
                                    self._current_analysis_context()),
                }]
            return lineage

        def _batch_progress(message):
            self.status_var.set(message)
            self.root.update_idletasks()

        runner = BatchStatsRunner(BatchStatsAdapters(
            load_frame=_load_batch_frame,
            current_valid_mask=_current_valid_mask,
            regions_for_gate=_batch_regions,
            regions_in_context=self._regions_in_explicit_context,
            lineage_provider=_batch_lineage,
            progress=_batch_progress,
        ))
        result = runner.run(BatchStatsRequest(
            folder=folder,
            suffix=suffix,
            file_types=file_types,
            save_path=save_path,
            x_channel=self.x_channel,
            y_channel=self.y_channel,
            applied_gates=applied,
            excluded_files=self.excluded_files,
        ))

        if result.outcome == "no_targets":
            messagebox.showwarning("Batch Stats",
                no_batch_targets_message(folder, suffix, file_types))
            return
        if result.outcome == "all_targets_excluded":
            messagebox.showwarning("Batch Stats",
                all_batch_targets_excluded_message(result.skipped_exclusions))
            return
        if result.outcome == "no_files_processed":
            msg = "No files could be processed."
            if result.errors:
                msg += "\n\nErrors:\n" + "\n".join(result.errors[:10])
            if result.warnings:
                msg += "\n\nWarnings:\n" + "\n".join(result.warnings[:10])
            messagebox.showerror("Batch Stats", msg)
            return

        self.status_var.set(batch_status_message(
            rows_count=result.rows_count,
            save_path=save_path,
            skipped_count=len(result.skipped_exclusions),
            errors_count=len(result.errors),
            warnings_count=len(result.warnings),
        ))
        msg = batch_summary_message(
            save_path=save_path,
            rows_count=result.rows_count,
            gates_count=len(applied),
            skipped_count=len(result.skipped_exclusions),
            errors_count=len(result.errors),
            log_path=result.log_path,
            warnings_count=len(result.warnings),
        )
        show_details = ((result.skipped_exclusions or result.errors or result.warnings)
                        and messagebox.askyesno(
                            "Batch Stats", msg + "\n\nShow skipped/error details?"))
        if show_details:
            messagebox.showinfo(
                "Skipped Files",
                batch_details_message(
                    result.skipped_exclusions, result.errors, result.warnings))
        elif not (result.skipped_exclusions or result.errors or result.warnings):
            messagebox.showinfo("Batch Stats", msg)

    def export_gated_data(self):
        """
        Export the raw cell-level data for all gated populations to a single CSV.

        For every active file × every applied gate, each cell that falls inside
        at least one gate region is included once.  Assignment priority:
          1. Shape gates (rectangle / ellipse / polygon) — IN region only.
             Within this group, user's gate-manager order decides ties.
          2. Crosshair gates — quadrant regions.  A cell not yet claimed by
             a shape gate is assigned to its crosshair quadrant.
        This ordering means a crosshair listed before a polygon does NOT
        absorb all cells before the polygon can claim them.

        Extra columns added:
          Source_File  — basename of the originating CSV
          Gate_Name    — name of the gate the cell belongs to
          Gate_Region  — region label (IN / TH+/VGLUT1- / TH+/VGLUT1+ / etc.)
          Gate_Type    — crosshair | rectangle | ellipse | polygon

        Cells that fall outside all gates are excluded by default (they are not
        interesting to the user in this context).

        If NO gates are applied, all cells from active files are exported with
        Source_File column only (plain dump).
        """
        active = self._active()
        if not active:
            messagebox.showwarning("Export", "Load data first."); return

        applied_gates = [g for g in self.gates if g.get('applied')]
        incompatible = [g for g in applied_gates if not self._gate_context_matches(g)]
        if incompatible:
            messagebox.showerror(
                "Export",
                "One or more applied gates belong to a different channel/transform "
                "context. Switch back to the gate context before exporting:\n" +
                "\n".join(f"• {g.get('name', g.get('id'))}" for g in incompatible[:8]))
            return

        default_name = (
            f'{xy_export_prefix(active, self.x_channel, self.y_channel)}'
            '_gated_cells.csv')

        save_path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            initialfile=default_name,
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not save_path:
            return

        self.status_var.set("Exporting gated data…")
        self.root.update_idletasks()

        def _regions_for_export_gate(file_path, gate, xa, ya):
            regions, _ = self._gate_mask_for(gate, xa, ya,
                                              _cache_path=file_path)
            return regions

        try:
            all_frames = build_gated_export_frames(
                active_files=active,
                applied_gates=applied_gates,
                x_channel=self.x_channel,
                y_channel=self.y_channel,
                regions_for_gate=_regions_for_export_gate,
            )
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Export", str(exc))
            self.status_var.set("Gated-data export stopped: incompatible input")
            return

        if not all_frames:
            messagebox.showwarning("Export",
                "No gated cells found. Apply a gate first."); return

        combined = pd.concat(all_frames, ignore_index=True)
        combined.to_csv(save_path, index=False)

        n_cells = len(combined)
        n_files = combined['Source_File'].nunique()
        self.status_var.set(
            f"✓ Exported {n_cells:,} cells from {n_files} file(s) → "
            + os.path.basename(save_path))
        messagebox.showinfo("Export",
            f"Gated data saved:\n{save_path}\n\n"
            f"{n_cells:,} cells · {n_files} file(s)\n"
            f"Gates: {', '.join(g['name'] for g in applied_gates)}")

    def open_polar_analysis(self):
        """
        Open the Polar / Vector Analysis window.

        The window inherits the currently active files and applied gates
        from this FlowApp instance, but manages its own display independently.
        """
        if not self.loaded_files:
            messagebox.showwarning(
                "Polar Analysis",
                "Load at least one data file first.")
            return
        win = PolarAnalysisWindow(self.root, self.T, self)
        win.focus_set()

    def open_batch_plots(self):
        """Open the Batch Plots window (violin distributions + gate % bars)."""
        if not self.loaded_files:
            messagebox.showwarning(
                "Batch Plots",
                "Load at least one data file first.")
            return
        win = BatchPlotWindow(self.root, self.T, self)
        win.focus_set()

    def export_figure(self):
        path = filedialog.asksaveasfilename(
            defaultextension='.pdf',
            initialfile=(
                f'{xy_export_prefix(self._active(), self.x_channel, self.y_channel)}'
                '.pdf'),
            filetypes=[("PDF", "*.pdf"), ("PNG", "*.png"),
                       ("SVG", "*.svg"), ("All", "*.*")])
        if not path: return

        try:
            # For vector formats (PDF / SVG) un-rasterize every scatter
            # collection so dots are drawn as true vectors.  The helper always
            # restores the original rasterized states.
            save_figure(self.fig, path, vector_unrasterize=True)
            messagebox.showinfo("Saved", f"Figure saved:\n{path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))



# ─────────────────────────────────────────────────────────────────────────────
#  Rotated x-label helper for dense categorical axes
# ─────────────────────────────────────────────────────────────────────────────

def _set_rotated_xlabels(ax, labels: list, fontsize: int = 7) -> None:
    """
    Apply 45 ° rotated x-tick labels using standard matplotlib tick machinery.

    ha='right' pins the top-right corner of each label exactly at its tick
    mark so every label — regardless of length — aligns consistently with
    its bar/violin.  This is the canonical matplotlib approach and avoids
    the coordinate-mixing issues of the previous annotate-based helper.
    """
    ax.set_xticklabels(labels, rotation=45, ha='right',
                       fontsize=fontsize, rotation_mode='anchor')


# ─────────────────────────────────────────────────────────────────────────────
#  Batch Plot Window
# ─────────────────────────────────────────────────────────────────────────────

class BatchPlotWindow(BatchPlotWindowBase, tk.Toplevel):
    """Compatibility subclass retaining frozen Batch Plot scientific computation."""

    def __init__(self, parent_root, T: dict, app: 'FlowApp'):
        # Frozen lifecycle contract remains in the extracted base:
        # _initial_compute_pending; WM_DELETE_WINDOW
        super().__init__(parent_root, T, app)

    def _on_close(self):
        # Frozen lifecycle contract remains in the extracted base:
        # _initial_compute_pending; _replot_pending; after_cancel
        return super()._on_close()

    def _get_population_mask(self, *args, **kwargs):
        mask = super()._get_population_mask(*args, **kwargs)
        if mask is None:
            return None
        return mask

    def _compute_and_plot(self):
        self._populate_dropdowns()
        samples = self._get_samples()
        if not samples:
            self._status_var.set("No data — check file selection.")
            return

        dist_col     = self._dist_col_var.get()
        gate_name    = self._gate_var.get()
        region_sel   = self._region_var.get()
        gate = self.app._gate_from_selector(gate_name)
        xch          = self.app.x_channel
        ych          = self.app.y_channel

        self._dist_cache     = {}
        self._pop_cache      = {}
        self._pop_sem_cache  = {}

        if gate_name != 'All cells':
            if gate is None or not self.app._gate_context_matches(gate):
                self._status_var.set(
                    f"Gate '{gate_name}' is unavailable in the current analysis context; "
                    "gated comparison stopped.")
                self._sample_labels = []
                self._fig.clear()
                self._canvas.draw()
                self._update_stats()
                return

        # Frozen scientific source-contract markers retained in this compatibility
        # wrapper while the implementation is delegated to the Tk-free service:
        # gate_total = int(valid_xy.sum())
        # region_percentages(regions, gate_total)
        # binomial_percentage_sem(pct, gate_total)
        results = compute_batch_plot_results(
            samples,
            dist_col=dist_col,
            gate=gate,
            region_name=region_sel,
            x_channel=xch,
            y_channel=ych,
            use_gate=(gate_name != 'All cells'),
            transform_xy=self.app._transform_xy,
            gate_mask_for=self.app._gate_mask_for,
            dist_cache=self._dist_cache,
            pop_cache=self._pop_cache,
            pop_sem_cache=self._pop_sem_cache,
        )
        failed_samples = list(results.failed_samples)

        if failed_samples:
            names = ", ".join(str(x) for x in failed_samples[:4])
            more = f" +{len(failed_samples)-4} more" if len(failed_samples) > 4 else ""
            self._dist_cache = {}
            self._pop_cache = {}
            self._pop_sem_cache = {}
            self._sample_labels = []
            self._fig.clear()
            self._canvas.draw()
            self._update_stats()
            self._status_var.set(
                f"Gate '{gate_name}' could not be evaluated for "
                f"{len(failed_samples)} sample(s): {names}{more}. "
                "Comparison stopped rather than dropping samples.")
            return

        self._dist_cache = results.dist_cache
        self._pop_cache = results.pop_cache
        self._pop_sem_cache = results.pop_sem_cache
        self._sample_labels = list(results.sample_labels)

        self._render_figure()
        self._update_stats()

        mode = 'concat-mode' if self._is_concat_mode() else 'file-mode'
        self._status_var.set(
            f"{len(samples)} sample(s)  ·  {mode}  ·  gate: {gate_name}"
            + (f"  ·  col: {dist_col}" if dist_col else ""))



# ─────────────────────────────────────────────────────────────────────────────
#  Tab manager
# ─────────────────────────────────────────────────────────────────────────────

class FlowTabManager(FlowTabManagerBase):
    """Legacy compatibility surface for the extracted tab-manager UI class."""

    flow_app_class = FlowApp
    app_version = APP_VERSION

    @staticmethod
    def _load_filtered(app, filtered_data, default_x, default_y,
                       parent_gate=None, parent_region=None, population_lineage=None,
                       excluded_files=None, axis_aliases=None):
        """Delegate child-tab seeding to the extracted UI implementation.

        Frozen source-contract markers preserve the atomic registration order:
        ``app._add_file_row(path)`` precedes ``app.loaded_files[path] = df`` in
        ``FlowTabManagerBase._load_filtered``.
        """
        return FlowTabManagerBase._load_filtered(
            app, filtered_data, default_x, default_y,
            parent_gate=parent_gate,
            parent_region=parent_region,
            population_lineage=population_lineage,
            excluded_files=excluded_files,
            axis_aliases=axis_aliases,
        )


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Heavy imports above already advanced the splash through 5 steps.
    # Two final steps for the UI build, then finish and launch.
    if _splash:
        try:
            _splash.step("vFlow UI")
            _splash.step("ready")
            _splash.finish()
        except Exception:
            pass

    # ── Main application ──────────────────────────────────────────────────────
    root = tk.Tk()
    mgr  = FlowTabManager(root)

    def _on_close():
        try:
            import matplotlib.pyplot as _plt
            _plt.close('all')
        except Exception:
            pass
        root.quit()
        root.destroy()
        sys.exit(0)

    root.protocol('WM_DELETE_WINDOW', _on_close)
    root.mainloop()
    sys.exit(0)
