"""Tk-free composed owner for FlowApp's full render lifecycle."""

from __future__ import annotations

import os

import matplotlib.lines as mlines
import numpy as np
from scipy.interpolate import RegularGridInterpolator

from vflow.app.cache import CompactScatterPayload
from vflow.core.cache_keys import gate_signature as _gate_sig
from vflow.plotting.kde_payloads import (
    KDERenderComputation,
    compute_contour_surface_payload,
    compute_density_render_payload,
    compute_kde_jobs_parallel,
)
from vflow.plotting.render_lifecycle import can_preserve_axis_state, reset_refresh_axes
from vflow.plotting.utils import (
    apply_sample_indices,
    gmm_overlay_curves,
    gmm_overlay_legend_layout,
    hex_to_rgba as _hex_to_rgba,
    sampled_indices,
    set_spines_color as _set_spines_color,
    threshold_band_boundaries,
    threshold_band_labels,
    valid_values,
)
from vflow.config.constants import (
    GATE_PALETTE,
    REGION_COLORS,
    RENDER_CAP,
    _N_REGION_COLORS,
    _SCATTER_CACHE_MAX,
    _SCATTER_CACHE_MAX_BYTES,
)
from vflow.rendering.render_plan import RenderPlan


def _host_fwd_axis(host, values, scale, axis):
    """Use explicit per-axis parameters only for standards Logicle.

    Historical host test doubles and compatibility callers expose the original
    two-argument ``_fwd`` surface; keep that surface for every legacy scale.
    """
    if scale == "logicle_gml2":
        return host._fwd(values, scale, axis=axis)
    return host._fwd(values, scale)


def _host_inv_axis(host, values, scale, axis):
    if scale == "logicle_gml2":
        return host._inv(values, scale, axis=axis)
    return host._inv(values, scale)


class FlowRenderer:
    """Own one complete deterministic render pass for a FlowApp host.

    The host remains the compatibility/UI surface and provides scientific/cache
    services.  This controller owns render orchestration plus plot-specific
    artist construction; it deliberately does not own interaction blitting.
    """

    def __init__(self, host):
        self._host = host

    def _clear_invalid_analysis_view(self, message: str):
        """Clear stale artists when the active dataset has no valid X/Y context."""
        host = self._host
        host._setup_axes()
        T = host.T
        host.ax.set_facecolor(T['ax_bg'])
        host.ax.text(
            0.5, 0.5, message,
            transform=host.ax.transAxes, ha='center', va='center',
            color=T.get('fg_dim', T.get('fg', 'black')), fontsize=9,
            wrap=True,
        )
        host.ax.set_xticks([])
        host.ax.set_yticks([])
        if hasattr(host, 'status_var'):
            host.status_var.set(message)
        host.canvas.draw_idle()

    def refresh(self):
        host = self._host
        # Compute active-file dict before validating the axes so a newly-invalid
        # multi-file selection can actively clear the previous plot instead of
        # returning early and leaving stale biological data on screen.
        active = host._active()
        # A full data clear must also clear the last rendered biological data.
        # ``x_channel``/``y_channel`` are intentionally reset by Clear All;
        # returning early here used to leave the previous scatter/title on
        # screen indefinitely.  Guard with hasattr so lightweight renderer
        # hosts used by services/tests keep their historical contract.
        if hasattr(host, 'loaded_files') and not host.loaded_files:
            self._clear_invalid_analysis_view("No data loaded.")
            return
        if active and (not host.x_channel or not host.y_channel):
            self._clear_invalid_analysis_view(
                "No safe shared X/Y channels are available for all active files.")
            return
        if not host.x_channel or not host.y_channel:
            return
        if any(
            host.x_channel not in df.columns or host.y_channel not in df.columns
            for df in active.values()
        ):
            self._clear_invalid_analysis_view(
                "Active files do not all contain the current X/Y channels; "
                "analysis is paused to prevent partial-file results.")
            return
        T = host.T
        # ``active`` is reused by _update_cycle_label, _display_files, and the
        # status bar at the bottom of this method.

        need_marg = host.show_marginals_var.get()
        if (host.ax_top is not None) != need_marg:
            host._setup_axes()
        else:
            host.fig.patch.set_facecolor(T['fig_bg'])
            host.ax.set_facecolor(T['ax_bg'])
            _set_spines_color(host.ax, T['spine'])
            if host.ax_top:
                host.ax_top.set_facecolor(T['ax_bg'])
                _set_spines_color(host.ax_top, T['spine'])
            if host.ax_right:
                host.ax_right.set_facecolor(T['ax_bg'])
                _set_spines_color(host.ax_right, T['spine'])

        host._update_cycle_label(active)
        display = host._display_files(active)

        # Collect all *effective* applied gates (filter out disabled crosshairs)
        applied_gates = []
        for g in host.gates:
            if not g.get('applied'): continue
            if not host._gate_context_matches(g): continue
            if g.get('type', 'crosshair') == 'crosshair':
                xbs = host._active_xbs_for(g)
                yb  = host._active_yb_for(g)
                if xbs or yb is not None:
                    applied_gates.append(g)
            else:
                applied_gates.append(g)

        eff_gate = bool(applied_gates)

        plot_type = host.plot_type_var.get()
        dot_size  = host.dot_size_var.get()
        alpha     = host.alpha_var.get()
        prob      = float(host.prob_var.get().strip('%')) / 100

        plan = RenderPlan(
            theme=T,
            active=active,
            display=display,
            applied_gates=tuple(applied_gates),
            effective_gate=eff_gate,
            need_marginals=need_marg,
            plot_type=plot_type,
            dot_size=dot_size,
            alpha=alpha,
            probability=prob,
            x_channel=host.x_channel,
            y_channel=host.y_channel,
            x_scale=host.x_scale,
            y_scale=host.y_scale,
        )
        return self.render(plan)

    def render(self, plan: RenderPlan):
        host = self._host
        T = plan.theme
        active = plan.active
        display = plan.display
        applied_gates = plan.applied_gates
        eff_gate = plan.effective_gate
        plot_type = plan.plot_type
        dot_size = plan.dot_size
        alpha = plan.alpha
        prob = plan.probability

        # AP04: Density/Dot artists are transform-dynamic, so retain the
        # Axis/Tick objects across refreshes instead of paying Axes.clear()'s
        # tick-allocation cost every time.  Contour Plot deliberately keeps the
        # historical full clear because clabel() chooses positions using the
        # transform live at contour-construction time; preserving a prior
        # nonlinear scale would change those label positions.  Plain log axes
        # also keep full clear because a retained log transform cannot accept
        # the historical temporary 0..1 fresh-axes limits.
        # Reusing Axis/Tick objects is safe only when the live Matplotlib
        # transform already matches the requested transform.  A scale change
        # (especially log -> signed nonlinear) must take the full-reset path;
        # otherwise the reset helper operates through the previous transform
        # and stale limits can leak into the new scale, including an inverted
        # axis.
        reset_refresh_axes(
            (host.ax, host.ax_top, host.ax_right),
            preserve_axis_state=can_preserve_axis_state(
                host.ax,
                plot_type=plot_type,
                target_x_scale=plan.x_scale,
                target_y_scale=plan.y_scale,
            ),
        )
        host.ax.set_facecolor(T['ax_bg'])
        if host.ax_top:
            host.ax_top.set_facecolor(T['ax_bg'])
            host.ax_top.set_ylabel('Count', color=T['fg'], fontsize=7)
            for lbl in host.ax_top.get_xticklabels(): lbl.set_visible(False)
        if host.ax_right:
            host.ax_right.set_facecolor(T['ax_bg'])
            host.ax_right.set_xlabel('Count', color=T['fg'], fontsize=7)
            for lbl in host.ax_right.get_yticklabels(): lbl.set_visible(False)

        total_cells = 0
        # In gated mode we build a legend entry per file (not per region)
        gated_legend_handles = []
        # Accumulators for "Fit axes to data", GMM overlay, and marginal histograms.
        # _raw_x_parts / _raw_y_parts collect finite raw values from all display
        # files.  They are reused for BOTH the fit-axes percentile calc AND the
        # GMM marginal overlay — one accumulation serves both consumers.
        _raw_x_parts: list = []
        _raw_y_parts: list = []

        # Full valid raw arrays are needed only by Fit-axes percentiles and the
        # optional GMM marginal overlay.  Avoid retaining duplicate full-file
        # arrays during ordinary redraws; with many million-event files the old
        # unconditional accumulation could transiently consume hundreds of MB.
        _need_fit_raw = (host.fit_axes_var.get()
                         and not host.lock_scale_var.get())
        _gmm_overlay_gate = None
        if (host.ax_top and host.ax_right and host.show_legend_var.get()):
            _gmm_overlay_gate = next(
                (g for g in host.gates
                 if g.get('applied')
                 and host._gate_context_matches(g)
                 and g.get('auto_method') == 'gmm_multi'),
                None)
        _need_raw_parts = _need_fit_raw or (_gmm_overlay_gate is not None)

        # AP07: cold Density/Contour KDE payloads are independent per file.
        # Compute misses concurrently, but keep all cache commits and drawing
        # in the original deterministic main-thread file order below.
        _kde_precomputed = self.precompute_cold_kde_payloads(display, plot_type)

        for path, df in display.items():
            if plan.x_channel not in df.columns or \
               plan.y_channel not in df.columns: continue
            color  = host.file_colors[path]
            lbl    = os.path.basename(path)
            lbl_s  = (lbl[:28] + '…') if len(lbl) > 30 else lbl
            x_raw  = df[plan.x_channel].to_numpy(dtype=float, copy=False)
            y_raw  = df[plan.y_channel].to_numpy(dtype=float, copy=False)
            xt, yt, valid = host._transform_xy_cached(path, x_raw, y_raw)
            n_cells = int(valid.sum())
            total_cells += n_cells
            if valid.any() and _need_raw_parts:
                _raw_x_parts.append(x_raw[valid])
                _raw_y_parts.append(y_raw[valid])

            if eff_gate:
                # Render base visualization as chosen (density/contour/dot)
                # then overlay gate membership coloring on top
                if plot_type == 'Density':
                    self.plot_density(x_raw, y_raw, xt, yt, valid,
                                       dot_size, alpha * 0.5, lbl_s,
                                       _cache_path=path,
                                       _precomputed=_kde_precomputed.get(path))
                elif plot_type == 'Contour Plot':
                    self.plot_contour(x_raw, y_raw, xt, yt, valid,
                                       color, lbl_s, dot_size, alpha * 0.4, prob,
                                       _cache_path=path,
                                       _precomputed=_kde_precomputed.get(path))
                else:
                    # Dot mode: use full gated coloring (outside faded, IN colored)
                    pass  # handled by _plot_gated_multi below

                # Gated overlay: color IN cells by their gate membership
                self.plot_gated_multi(x_raw, y_raw, dot_size,
                                       alpha if plot_type == 'Dot Plot' else alpha * 0.85,
                                       applied_gates, color, path=path,
                                       overlay=(plot_type != 'Dot Plot'))
                h = mlines.Line2D([], [], color=color, marker='o',
                                  linestyle='None', markersize=4,
                                  label=f'{lbl_s}  (n={n_cells:,})')
                gated_legend_handles.append(h)
            elif plot_type == 'Density':
                self.plot_density(x_raw, y_raw, xt, yt, valid,
                                   dot_size, alpha, lbl_s,
                                   _cache_path=path,
                                   _precomputed=_kde_precomputed.get(path))
            elif plot_type == 'Contour Plot':
                self.plot_contour(x_raw, y_raw, xt, yt, valid,
                                   color, lbl_s, dot_size, alpha, prob,
                                   _cache_path=path,
                                   _precomputed=_kde_precomputed.get(path))
            else:
                self.plot_dot(x_raw, y_raw, valid, color, lbl_s,
                               dot_size, alpha)

            if host.ax_top and host.ax_right:
                xr_full, yr_full, x_edges, y_edges = self.plot_marginals(
                    x_raw, y_raw, xt, yt, valid, color, _cache_path=path)

        # ── GMM overlay on marginal histograms ───────────────────────────────
        # Drawn once, after all files' histograms, using the first applied GMM
        # gate (gmm_multi).  Controlled by show_legend_var so the user can
        # toggle it off together with the rest of the plot legend.
        if (host.ax_top and host.ax_right
                and host.show_legend_var.get()):
            gmm_gate = _gmm_overlay_gate
            if gmm_gate is not None and _raw_x_parts:
                # Reuse the raw parts already gathered in the main render loop
                # — no second pass through display files needed.
                x_all_raw = np.concatenate(_raw_x_parts)
                y_all_raw = np.concatenate(_raw_y_parts)
                x_t_all = _host_fwd_axis(host, x_all_raw, plan.x_scale, "x")
                y_t_all = _host_fwd_axis(host, y_all_raw, plan.y_scale, "y")
                xv_all  = x_t_all[np.isfinite(x_t_all)]
                yv_all  = y_t_all[np.isfinite(y_t_all)]
                if len(xv_all) > 1:
                    _bt_x = np.linspace(xv_all.min(), xv_all.max(), 121)
                    _be_x = _host_inv_axis(host, _bt_x, plan.x_scale, "x")
                else:
                    _be_x = None
                if len(yv_all) > 1:
                    _bt_y = np.linspace(yv_all.min(), yv_all.max(), 121)
                    _be_y = _host_inv_axis(host, _bt_y, plan.y_scale, "y")
                else:
                    _be_y = None
                gxp = gmm_gate.get('gmm_x_params')
                gyp = gmm_gate.get('gmm_y_params')
                try:
                    if gxp is not None and _be_x is not None:
                        self.plot_gmm_overlay(
                            host.ax_top, gxp,
                            'horizontal', x_all_raw, _be_x)
                except Exception:
                    pass
                try:
                    if gyp is not None and _be_y is not None:
                        self.plot_gmm_overlay(
                            host.ax_right, gyp,
                            'vertical', y_all_raw, _be_y)
                except Exception:
                    pass

        # ── Population shading on marginals for KDE / Otsu gates ──────────────
        # If a KDE Valley or Otsu crosshair gate is applied and marginals are
        # visible, shade each population band between threshold lines so the
        # user can see which region is positive / negative — the same visual
        # cue that GMM Multi provides via its Gaussian component curves.
        if host.ax_top and host.ax_right:
            _shading_gate = next(
                (g for g in host.gates
                 if g.get('applied')
                 and host._gate_context_matches(g)
                 and g.get('type', 'crosshair') == 'crosshair'
                 and g.get('auto_method') in ('kde', 'otsu')),
                None)
            if _shading_gate is not None:
                self.plot_threshold_shading(
                    _shading_gate,
                    host.ax_top, 'horizontal',
                    host.ax_right, 'vertical')

        # NOTE: _preview_gate() is intentionally NOT called here.
        # It is moved to AFTER _set_axis_scale() below (FIX Bug 1).
        # Calling it here (before the scale is applied) would build the
        # handle pixel cache with a stale linear transform — causing hover
        # detection to fail on loaded gates on non-linear axes.

        fg = T['fg']
        host.fig.suptitle(f'{plan.x_channel}  ×  {plan.y_channel}',
                          color=fg, fontsize=10, y=0.97)
        host.ax.set_xlabel(plan.x_channel, color=fg, fontsize=9)
        host.ax.set_ylabel(plan.y_channel, color=fg, fontsize=9)
        # Full Axes.clear() used to make an unchecked grid implicitly
        # disappear.  The retained-axis path must make that reset explicit.
        # Matplotlib treats grid(False, **line_props) as an enable request, so
        # keep the disabled branch property-free.
        if host.show_grid_var.get():
            host.ax.grid(True, alpha=0.25, color=T['grid'])
        else:
            host.ax.grid(False)
        host.ax.tick_params(colors=fg, labelsize=8)
        if host.ax_top:
            host.ax_top.tick_params(colors=fg, labelsize=6)
        if host.ax_right:
            host.ax_right.tick_params(colors=fg, labelsize=6)

        # Apply the custom axis scale BEFORE drawing region labels so that
        # the full axis transform (asinh / biexp / logicle) is in place when
        # _label_centroid() resolves text positions.  Labels placed before
        # set_xscale() can be clipped or repositioned when the axis
        # autoscale range is recalculated for the new scale type.
        host._set_axis_scale()

        # ── Fit axes to data (FlowJo-style "zoom to data") ────────────────────
        # After _set_axis_scale so the scale type is already applied.
        # Uses p0.5 / p99.5 of all valid raw values with a 5 % margin so the
        # population is centred with a small breathing room on each side.
        # Skipped when lock-scale is active (lock takes priority).
        # _raw_x_parts already contains exactly the finite raw values needed —
        # no separate _fit_x_all accumulator required.
        if (host.fit_axes_var.get()
                and not host.lock_scale_var.get()
                and _raw_x_parts):
            all_x = np.concatenate(_raw_x_parts)
            all_y = np.concatenate(_raw_y_parts)
            xlo_r, xhi_r = np.nanpercentile(all_x, [0.5, 99.5])
            ylo_r, yhi_r = np.nanpercentile(all_y, [0.5, 99.5])
            # Add 5 % breathing room in transform space to avoid edge clipping.
            # Batch the scalar transforms: 2 _fwd calls (one per axis, each on a
            # 2-element array) instead of 4 single-element calls — halves the
            # number of Python→numpy dispatch round-trips.
            xt_lo, xt_hi = _host_fwd_axis(host, np.array([xlo_r, xhi_r]), plan.x_scale, "x")
            yt_lo, yt_hi = _host_fwd_axis(host, np.array([ylo_r, yhi_r]), plan.y_scale, "y")
            x_pad = (xt_hi - xt_lo) * 0.05
            y_pad = (yt_hi - yt_lo) * 0.05
            x_margin_lo, x_margin_hi = _host_inv_axis(
                host, np.array([xt_lo - x_pad, xt_hi + x_pad]), plan.x_scale, "x")
            y_margin_lo, y_margin_hi = _host_inv_axis(
                host, np.array([yt_lo - y_pad, yt_hi + y_pad]), plan.y_scale, "y")
            try:
                host.ax.set_xlim(x_margin_lo, x_margin_hi)
                host.ax.set_ylim(y_margin_lo, y_margin_hi)
            except Exception:
                pass   # non-finite limits (e.g. log of negative) → keep auto

        # ── Region % labels ───────────────────────────────────────────────────
        # Drawn AFTER _set_axis_scale() + fit-axes so that:
        #   • _label_centroid uses the correct axis transform space
        #   • axis limits are finalised before text positions are resolved
        if eff_gate and host.show_labels_var.get():
            try:
                self.draw_region_labels(applied_gates)
            except Exception:
                pass   # never let a label error crash the full refresh

        if host.show_legend_var.get():
            if eff_gate and gated_legend_handles:
                host.ax.legend(handles=gated_legend_handles,
                               fontsize=7, loc='lower left',
                               framealpha=0.6, facecolor=T['legend_bg'],
                               labelcolor=fg)
            else:
                handles, _ = host.ax.get_legend_handles_labels()
                if handles:
                    host.ax.legend(fontsize=7, markerscale=3, loc='lower left',
                                   framealpha=0.6, facecolor=T['legend_bg'],
                                   labelcolor=fg)

        host.status_var.set(
            f"Shown: {len(display)}/{len(active)} files  │  "
            f"Cells: {total_cells:,}  │  "
            f"{plan.x_channel} vs {plan.y_channel}  │  "
            f"Scale: {plan.x_scale}/{plan.y_scale}"
            + (f"  │  {len(applied_gates)} gate(s) ON" if eff_gate else ""))

        # ── Lock-scale: enforce captured limits ───────────────────────────────
        # Must run after _set_axis_scale() and after the fit-axes block so the
        # lock wins over both.  Minor ticks are applied unconditionally below
        # (they do not depend on lock state).
        if host.lock_scale_var.get():
            host._apply_locked_limits()

        # ── Minor ticks — always on for non-linear scales ─────────────────────
        # _set_axis_scale() resets the minor locator to NullLocator each time
        # the scale is applied; _apply_minor_ticks() reinstates decade-
        # subdivision ticks for biexp/asinh/logicle/log and AutoMinorLocator
        # for linear.  Called unconditionally so ticks are visible even when
        # lock-scale is off.
        host._apply_minor_ticks()

        # ── FIX Bug 1: Draw gate outlines + handles AFTER all transforms are
        # finalised.  _preview_gate() calls _rebuild_handle_px_cache() which
        # records handle positions in display pixels.  Those pixels must be
        # computed with the FINAL transform (scale + fit-axes + lock applied)
        # or hover hit-testing will misplace handles on non-linear axes,
        # making loaded gates impossible to interact with.
        # Previously this call lived before _set_axis_scale() — the cache was
        # always built with a stale linear transform after ax.clear().
        host._preview_gate()

        # Single unconditional flush — renders scatter + gate outlines +
        # labels + axis styling all at once, avoiding partial repaints.
        host.canvas.draw_idle()
    def plot_dot(self, x_raw, y_raw, valid, color, label, dot_size, alpha):
        host = self._host
        xv = valid_values(x_raw, valid)
        yv = valid_values(y_raw, valid)
        n  = len(xv)   # == valid.sum(); already computed by boolean indexing
        xv, yv = apply_sample_indices(
            xv, yv, indices=sampled_indices(n, RENDER_CAP, seed=2))
        host.ax.scatter(xv, yv, s=dot_size, alpha=alpha, color=color,
                        label=f'{label} (n={n:,})',
                        rasterized=True, linewidths=0)

    def plot_density(self, x_raw, y_raw, xt, yt, valid,
                      dot_size, alpha, label, _cache_path: str = None,
                      _precomputed: KDERenderComputation = None):
        host = self._host
        # The expensive KDE/grid/interpolation result is style-independent.
        # Cache only the final <= RENDER_CAP display payload, keyed by complete
        # data-generation + axis/transform context.  Alpha, dot size, and label
        # are intentionally excluded so UI styling changes reuse the same data.
        density_key = None
        payload = None
        if _cache_path is not None:
            density_key = (
                host._data_generation, _cache_path,
                host.x_channel, host.y_channel,
                host.x_scale, host.y_scale, host.cofactor,
                tuple(sorted(host.x_transform_params.items())),
                tuple(sorted(host.y_transform_params.items())),
            )
            payload = host._analysis_cache_obj().get_density_render(density_key)

        if payload is None:
            result = (_precomputed if _precomputed is not None
                      else compute_density_render_payload(
                          x_raw, y_raw, xt, yt, valid))
            if result.action == "error":
                raise result.error
            if result.action == "dot":
                return self.plot_dot(x_raw, y_raw, valid,
                                      GATE_PALETTE[0], label, dot_size, alpha)
            if result.action == "skip":
                return
            payload = result.payload
            if density_key is not None:
                host._analysis_cache_obj().put_density_render(
                    density_key, payload, max_entries=128, evict_count=64)

        xr_plot, yr_plot, dens_plot, vlo, vhi, n_valid = payload
        host.ax.scatter(xr_plot, yr_plot,
                        c=dens_plot, cmap='jet',
                        s=dot_size, alpha=alpha, rasterized=True, linewidths=0,
                        vmin=vlo, vmax=vhi,
                        label=f'{label} (n={n_valid:,})')

    def plot_contour(self, x_raw, y_raw, xt, yt, valid,
                      color, label, dot_size, alpha, prob_level,
                      _cache_path: str = None,
                      _precomputed: KDERenderComputation = None):
        host = self._host
        contour_key = None
        payload = None
        if _cache_path is not None:
            contour_key = (
                host._data_generation, _cache_path,
                host.x_channel, host.y_channel,
                host.x_scale, host.y_scale, host.cofactor,
                tuple(sorted(host.x_transform_params.items())),
                tuple(sorted(host.y_transform_params.items())),
            )
            payload = host._analysis_cache_obj().get_contour_render(contour_key)

        if payload is None:
            result = (_precomputed if _precomputed is not None
                      else compute_contour_surface_payload(
                          xt, yt, valid,
                          x_scale=host.x_scale, y_scale=host.y_scale,
                          cofactor=host.cofactor,
                          x_transform_params=host.x_transform_params,
                          y_transform_params=host.y_transform_params))
            if result.action == "error":
                raise result.error
            if result.action == "dot":
                return self.plot_dot(x_raw, y_raw, valid, color, label,
                                      dot_size, alpha)
            payload = result.payload

        (xg_t, yg_t, xg_raw, yg_raw, Z,
         cached_prob, lv, xo, yo, n_outside) = payload

        # Probability affects only the boundary threshold and outlier sample,
        # not the fitted KDE/grid surface. Cache the most-recent probability
        # result without duplicating the large grid for each combobox option.
        if cached_prob != float(prob_level):
            xv = valid_values(xt, valid)
            yv = valid_values(yt, valid)
            s_z = np.sort(Z.ravel())
            cum = np.cumsum(s_z) / s_z.sum()
            lv = float(np.interp(prob_level, cum, s_z))
            interp = RegularGridInterpolator(
                (xg_t, yg_t), Z, method='linear',
                bounds_error=False, fill_value=float(Z.min()))
            pt_dens = interp(np.column_stack([xv, yv]))
            outside = pt_dens < lv

            xo = valid_values(x_raw, valid)[outside]
            yo = valid_values(y_raw, valid)[outside]
            n_outside = len(xo)
            xo, yo = apply_sample_indices(
                xo, yo, indices=sampled_indices(n_outside, RENDER_CAP, seed=4))
            payload = (
                xg_t, yg_t, xg_raw, yg_raw, Z,
                float(prob_level), lv, xo, yo, n_outside,
            )
            if contour_key is not None:
                host._analysis_cache_obj().put_contour_render(
                    contour_key, payload, max_entries=128, evict_count=64)

        host.ax.contourf(xg_raw, yg_raw, Z, levels=12,
                         cmap='viridis', alpha=0.35)
        c = host.ax.contour(xg_raw, yg_raw, Z, levels=[lv],
                             colors=[color], linewidths=0.5)
        host.ax.clabel(c, fmt={lv: f'{prob_level*100:.0f}%'},
                        fontsize=8, colors=[color])

        host.ax.scatter(xo, yo,
                        s=dot_size, color=color, alpha=alpha, linewidths=0,
                        label=f'{label} outliers ({n_outside:,})',
                        rasterized=True)

    def plot_gated_multi(self, x_raw, y_raw, dot_size, alpha,
                          applied_gates: list, file_color: str, path: str = None,
                          overlay: bool = False):
        """
        Color cells by gate membership — single scatter() call via RGBA array.

        One scatter call regardless of gate/region count eliminates the N×scatter
        overhead that dominated render time for large files.  Outside cells are
        faded (or invisible when overlay=True); IN cells use their gate color.

        When n > RENDER_CAP the display is subsampled:
          • ALL IN-region cells are always kept (gate boundaries stay sharp).
          • Outside/faded cells are randomly thinned to fill the remaining budget.
        Gate stats are NOT affected — they run on the full array elsewhere.

        Performance: a scatter-payload cache (_scatter_cache) stores the
        already-subsampled, visibility-filtered (xa, ya, rgba) arrays keyed on
        everything that can affect visual output.  On unchanged redraws (e.g.
        marginal histogram update, label refresh) the RGBA build and
        contains_points calls are skipped entirely.  The cache is invalidated
        explicitly in _finish_gate and _drag_handle_update whenever gate geometry
        or selection changes.
        """
        host = self._host
        xa = np.asarray(x_raw, float)
        ya = np.asarray(y_raw, float)
        n  = len(xa)

        out_alpha = 0.0 if overlay else max(alpha * 0.25, 0.05)

        # ── Scatter-payload cache lookup ──────────────────────────────────
        # Key encodes every parameter that affects the visual output.
        # _gate_sig() covers gate geometry; the rest covers display style.
        gate_sigs = tuple(_gate_sig(g) for g in applied_gates)
        sc_key    = (host._data_generation, path,
                     host.x_channel, host.y_channel,
                     host.x_scale, host.y_scale, host.cofactor,
                     gate_sigs, dot_size, alpha, file_color, overlay,
                     tuple(sorted(host.x_transform_params.items())),
                     tuple(sorted(host.y_transform_params.items())))
        cached_scatter = host._analysis_cache_obj().get_scatter_render(sc_key)
        if cached_scatter is not None:
            if isinstance(cached_scatter, CompactScatterPayload):
                xa_v, ya_v, rgba_v = cached_scatter.materialize(xa, ya)
            else:
                xa_v, ya_v, rgba_v = cached_scatter
            if len(xa_v):
                host.ax.scatter(xa_v, ya_v, c=rgba_v, s=dot_size,
                                rasterized=True, linewidths=0)
            return

        # ── Build per-cell RGBA array ─────────────────────────────────────
        outside_rgba = _hex_to_rgba(file_color, out_alpha)
        in_any  = np.zeros(n, bool)

        # AP06 compact scatter cache: track the exact final RGBA row as a small
        # integer code.  The float32 RGBA matrix is materialized only for final
        # visible/subsampled points, avoiding a duplicate full-event colour array
        # while retaining byte-identical scatter arguments.
        color_codes = np.zeros(n, dtype=np.uint32)
        palette_rows = [outside_rgba]
        palette_codes = {outside_rgba.tobytes(): 0}

        def _scatter_color_code(rgba_row):
            key = rgba_row.tobytes()
            code = palette_codes.get(key)
            if code is None:
                code = len(palette_rows)
                palette_codes[key] = code
                palette_rows.append(rgba_row)
            return code

        _empty_bool = np.zeros(n, bool)   # shared empty mask; never mutated
        for gate in applied_gates:
            regions, colors = host._gate_mask_for(gate, xa, ya,
                                                   _cache_path=path)
            if not regions:
                continue
            gt = gate.get('type', 'crosshair')
            if gt == 'crosshair':
                for (rname, mask), c in zip(regions.items(), colors):
                    region_rgba = _hex_to_rgba(c, alpha)
                    color_codes[mask] = _scatter_color_code(region_rgba)
                    in_any |= mask
            else:
                in_mask = regions.get('IN', _empty_bool)
                c = gate.get('color', colors[0] if colors else file_color)
                region_rgba = _hex_to_rgba(c, alpha)
                color_codes[in_mask] = _scatter_color_code(region_rgba)
                in_any |= in_mask

        # ── Render-cap subsampling ────────────────────────────────────────
        # Always keep all IN cells; thin outside cells to stay under cap.
        # FIX BUG 4: use a LOCAL rng (not the cached _get_rng) so the
        # subsample is identical on every render and the scatter does not
        # visually "shift" between redraws.  Matches the v4.0.8 strip-plot fix.
        keep = None
        if n > RENDER_CAP:
            in_idx  = np.where(in_any)[0]
            out_idx = np.where(~in_any)[0]
            budget  = max(0, RENDER_CAP - len(in_idx))
            if budget < len(out_idx):
                _local_rng = np.random.default_rng(1)   # local, not cached
                out_idx    = _local_rng.choice(out_idx, budget, replace=False)
            keep    = np.concatenate([in_idx, out_idx])
            color_codes = color_codes[keep]

        # ── Single scatter call ───────────────────────────────────────────
        palette = np.asarray(palette_rows, dtype=np.float32)
        visible = palette[color_codes, 3] > 0
        if keep is None:
            visible_idx = np.flatnonzero(visible)
        else:
            visible_idx = keep[visible]
        xa_v    = xa[visible_idx]
        ya_v    = ya[visible_idx]
        visible_codes = color_codes[visible]
        rgba_v  = palette[visible_codes]
        index_dtype = np.uint32 if n <= np.iinfo(np.uint32).max else np.uint64
        visible_idx = visible_idx.astype(index_dtype, copy=False)
        max_code = int(visible_codes.max()) if len(visible_codes) else 0
        if max_code <= np.iinfo(np.uint8).max:
            code_dtype = np.uint8
        elif max_code <= np.iinfo(np.uint16).max:
            code_dtype = np.uint16
        else:
            code_dtype = np.uint32
        visible_codes = visible_codes.astype(code_dtype, copy=False)
        if visible.any():
            host.ax.scatter(xa_v, ya_v, c=rgba_v, s=dot_size,
                            rasterized=True, linewidths=0)

        # ── Store in scatter-payload cache ────────────────────────────────
        # AP06 bounds retained numeric payload bytes rather than using the old
        # 40-entry cliff.  A generous entry safeguard remains secondary.
        host._analysis_cache_obj().put_scatter_render(
            sc_key,
            CompactScatterPayload(visible_idx, visible_codes, palette),
            max_entries=_SCATTER_CACHE_MAX,
            max_bytes=_SCATTER_CACHE_MAX_BYTES,
        )

    def plot_marginals(self, x_raw, y_raw, xt, yt, valid, color,
                        _cache_path: str = None):
        host = self._host
        # Preserve the historical direct-call path exactly when no cache identity
        # is supplied.  refresh_plot always supplies a path and therefore uses
        # the AP03 bounded histogram-payload cache below.
        if _cache_path is None:
            xv = valid_values(xt, valid)
            yv = valid_values(yt, valid)
            xr = valid_values(x_raw, valid)
            yr = valid_values(y_raw, valid)
            MARG_MAX = 30_000
            idx = sampled_indices(len(xr), MARG_MAX, seed=5)
            if idx is not None:
                xr_h = xr[idx]; yr_h = yr[idx]
                xv_h = xv[idx]; yv_h = yv[idx]
            else:
                xr_h = xr; yr_h = yr; xv_h = xv; yv_h = yv
            x_edges = y_edges = None
            if len(xv_h) > 1 and host.ax_top:
                bt = np.linspace(xv.min(), xv.max(), 121)
                br = _host_inv_axis(host, bt, host.x_scale, "x")
                _, x_edges, _ = host.ax_top.hist(
                    xr_h, bins=br, color=color, alpha=0.55,
                    histtype='stepfilled', linewidth=0.5)
            if len(yv_h) > 1 and host.ax_right:
                bt = np.linspace(yv.min(), yv.max(), 121)
                br = _host_inv_axis(host, bt, host.y_scale, "y")
                _, y_edges, _ = host.ax_right.hist(
                    yr_h, bins=br, color=color, alpha=0.55,
                    histtype='stepfilled',
                    orientation='horizontal', linewidth=0.5)
            return xr, yr, x_edges, y_edges

        marginal_key = (
            host._data_generation, _cache_path,
            host.x_channel, host.y_channel,
            host.x_scale, host.y_scale, host.cofactor,
            tuple(sorted(host.x_transform_params.items())),
            tuple(sorted(host.y_transform_params.items())))
        payload = host._analysis_cache_obj().get_marginal_render(marginal_key)

        if payload is None:
            n_valid = int(np.count_nonzero(valid))
            x_counts = x_edges = y_counts = y_edges = None
            if n_valid > 1:
                MARG_MAX = 30_000
                if n_valid > MARG_MAX:
                    # Match the legacy sample exactly while avoiding four full
                    # valid-array copies for large files.  sampled_indices() is
                    # defined in compact-valid-index space, so map those compact
                    # positions back to source rows before gathering raw values.
                    valid_rows = np.flatnonzero(valid)
                    sample_compact = sampled_indices(n_valid, MARG_MAX, seed=5)
                    sample_rows = valid_rows[sample_compact]
                    xr_h = x_raw[sample_rows]
                    yr_h = y_raw[sample_rows]
                else:
                    xr_h = x_raw[valid]
                    yr_h = y_raw[valid]

                # The historical bins span the full transformed valid range,
                # not the sampled range.  where= avoids materialising full xv/yv
                # copies while producing the same finite extrema.
                x_lo = np.min(xt, where=valid, initial=np.inf)
                x_hi = np.max(xt, where=valid, initial=-np.inf)
                y_lo = np.min(yt, where=valid, initial=np.inf)
                y_hi = np.max(yt, where=valid, initial=-np.inf)

                x_bt = np.linspace(x_lo, x_hi, 121)
                y_bt = np.linspace(y_lo, y_hi, 121)
                x_edges = _host_inv_axis(host, x_bt, host.x_scale, "x")
                y_edges = _host_inv_axis(host, y_bt, host.y_scale, "y")
                x_counts, _ = np.histogram(xr_h, bins=x_edges)
                y_counts, _ = np.histogram(yr_h, bins=y_edges)

            payload = (x_counts, x_edges, y_counts, y_edges, n_valid)
            host._analysis_cache_obj().put_marginal_render(
                marginal_key, payload, max_entries=128, evict_count=64)
        else:
            x_counts, x_edges, y_counts, y_edges, n_valid = payload

        # Axes.stairs(counts, edges, fill=True) is raster-equivalent to the
        # historical hist(..., histtype='stepfilled') output, but skips both
        # histogram recomputation and Matplotlib's histogram wrapper overhead.
        if x_counts is not None and host.ax_top:
            host.ax_top.stairs(
                x_counts, x_edges, fill=True, color=color, alpha=0.55,
                linewidth=0.5)
        if y_counts is not None and host.ax_right:
            host.ax_right.stairs(
                y_counts, y_edges, fill=True, color=color, alpha=0.55,
                orientation='horizontal', linewidth=0.5)

        # refresh_plot historically assigned these return values but never used
        # them.  Keep the four-item shape for internal sequencing compatibility
        # without recreating full valid raw arrays on cache hits.
        return None, None, x_edges, y_edges

    def plot_gmm_overlay(self, ax, gmm_params: dict,
                          orientation: str, hist_data_raw: np.ndarray,
                          bin_edges_raw: np.ndarray):
        """
        Draw per-component Gaussian curves on a marginal histogram axis,
        scaled to match the histogram counts.

        Strategy: the GMM was fitted in transform space where bins are
        *uniform* (linspace).  The scale factor is therefore simple:
            counts = pdf_transform(x_t) × n_total × bin_width_transform
        The curve is evaluated on a dense transform-space grid, then
        back-transformed to raw space for plotting (matching the x-axis
        already used by the histogram).  No Jacobian needed.

        The legend is placed outside the histogram bars — anchored to the
        top-right corner of the axes bounding box via bbox_to_anchor so it
        never overlaps the data.
        """
        host = self._host
        legend_handles = []

        curves = gmm_overlay_curves(
            gmm_params,
            inverse_transform=(
                lambda values, scale: _host_inv_axis(
                    host, values, scale,
                    "x" if orientation == "horizontal" else "y")
            ),
            n_total=len(hist_data_raw),
        )
        for curve in curves:
            if orientation == 'horizontal':
                ax.plot(curve['x_raw'], curve['pdf_count'],
                        color=curve['color'], lw=1.0, ls='--', zorder=5)
            else:
                ax.plot(curve['pdf_count'], curve['x_raw'],
                        color=curve['color'], lw=1.0, ls='--', zorder=5)
            legend_handles.append(
                mlines.Line2D([], [], color=curve['color'], lw=1.0,
                              ls='--', label=curve['label']))

        T   = host.T

        # Anchor legend to the top-left corner of the axes (outside the tallest
        # histogram bars which tend to be on the right for flow data).
        # bbox_to_anchor=(0, 1) = top-left corner of axes in axes coordinates;
        # loc='upper left' makes the legend box grow downward from that corner.
        # For the vertical (right) histogram, bars grow leftward from the y-axis,
        # so the empty space is at the bottom — anchor there instead.
        bbox, loc, ncol = gmm_overlay_legend_layout(
            orientation, len(curves))

        ax.legend(
            handles=legend_handles,
            fontsize=5.5,
            loc=loc,
            bbox_to_anchor=bbox,
            bbox_transform=ax.transAxes,
            framealpha=0.75,
            facecolor=T['legend_bg'],
            labelcolor=T['fg'],
            handlelength=1.6,
            borderpad=0.5,
            labelspacing=0.25,
            ncol=ncol,
        )

    def plot_threshold_shading(self, gate: dict,
                                ax_h, orient_h: str,
                                ax_v, orient_v: str):
        """
        Shade population bands on marginal histograms for KDE/Otsu gates.

        For the horizontal (top) histogram (X axis) and the vertical (right)
        histogram (Y axis), each band between consecutive threshold lines is
        filled with a semi-transparent colour matching the REGION_COLORS palette
        and labelled with the population name (e.g. TH+, VGLUT1-).

        This gives the same visual population feedback that GMM Multi provides
        via Gaussian curve overlays, but for the simpler single-threshold methods.
        """
        host = self._host
        T = host.T

        xbs = host._active_xbs_for(gate)   # list of active X threshold raw values
        ybs = host._active_ybs_for(gate)   # list of active Y threshold raw values

        def _shade_axis(ax, thresholds_raw, scale_name, channel, orientation):
            """Draw region bands on one marginal histogram axis."""
            if not thresholds_raw:
                return
            # Axis limits from the histogram bars already drawn
            try:
                if orientation == 'horizontal':
                    axis_limits = ax.get_xlim()
                else:
                    axis_limits = ax.get_ylim()
            except Exception:
                return

            # Build band boundaries: [lo, t1, t2, ..., hi]
            thresholds_raw = sorted(thresholds_raw)
            boundaries = threshold_band_boundaries(axis_limits, thresholds_raw)
            n_bands    = len(boundaries) - 1

            # Band label suffixes: first band is "-", last is "+", middle "m"
            fluor = host._fluor(channel or '')
            labels = threshold_band_labels(fluor, n_bands)

            for i in range(n_bands):
                b0 = boundaries[i]
                b1 = boundaries[i + 1]
                col = REGION_COLORS[i % _N_REGION_COLORS]
                try:
                    if orientation == 'horizontal':
                        ax.axvspan(b0, b1, alpha=0.13, color=col,
                                   linewidth=0, zorder=1)
                        mid = (b0 + b1) / 2.0
                        y_top = ax.get_ylim()[1]
                        ax.text(mid, y_top * 0.88, labels[i],
                                ha='center', va='top', fontsize=6,
                                color=col, fontweight='bold',
                                clip_on=True, zorder=6)
                    else:
                        ax.axhspan(b0, b1, alpha=0.13, color=col,
                                   linewidth=0, zorder=1)
                        mid = (b0 + b1) / 2.0
                        x_right = ax.get_xlim()[1]
                        ax.text(x_right * 0.96, mid, labels[i],
                                ha='right', va='center', fontsize=6,
                                color=col, fontweight='bold',
                                rotation=90, clip_on=True, zorder=6)
                except Exception:
                    pass

            # Draw threshold lines on the marginal axis
            for thresh in thresholds_raw:
                try:
                    if orientation == 'horizontal':
                        ax.axvline(thresh, color=T['gate_line'],
                                   lw=0.8, ls='--', alpha=0.7, zorder=4)
                    else:
                        ax.axhline(thresh, color=T['gate_line'],
                                   lw=0.8, ls='--', alpha=0.7, zorder=4)
                except Exception:
                    pass

        _shade_axis(ax_h, xbs, host.x_scale, host.x_channel, 'horizontal')
        _shade_axis(ax_v, ybs, host.y_scale, host.y_channel, 'vertical')

    def precompute_cold_kde_payloads(self, display, plot_type):
        """Compute independent cold Density/Contour payloads concurrently.

        Workers receive NumPy arrays plus immutable scale/context values only;
        they never touch Tk, Matplotlib, or persistent caches.  Results remain
        transient until the historical per-file render loop consumes them in
        display order, preserving cache-commit and exception ordering.
        """
        host = self._host
        if plot_type not in ("Density", "Contour Plot"):
            return {}

        cache = host._analysis_cache_obj()
        jobs = []
        for path, df in display.items():
            if host.x_channel not in df.columns or host.y_channel not in df.columns:
                continue
            if plot_type == "Density":
                key = (
                    host._data_generation, path,
                    host.x_channel, host.y_channel,
                    host.x_scale, host.y_scale, host.cofactor,
                    tuple(sorted(host.x_transform_params.items())),
                    tuple(sorted(host.y_transform_params.items())),
                )
                if cache.get_density_render(key) is not None:
                    continue
            else:
                key = (
                    host._data_generation, path,
                    host.x_channel, host.y_channel,
                    host.x_scale, host.y_scale, host.cofactor,
                    tuple(sorted(host.x_transform_params.items())),
                    tuple(sorted(host.y_transform_params.items())),
                )
                if cache.get_contour_render(key) is not None:
                    continue

            # Keep data/transform exceptions on the historical main-thread path.
            # Stop preparing later files at the first such error so no later
            # transform-cache state can appear when sequential rendering would
            # have aborted before reaching it.
            try:
                x_raw = df[host.x_channel].to_numpy(dtype=float, copy=False)
                y_raw = df[host.y_channel].to_numpy(dtype=float, copy=False)
                xt, yt, valid = host._transform_xy_cached(path, x_raw, y_raw)
            except Exception:
                break

            if plot_type == "Density":
                jobs.append((
                    path, compute_density_render_payload,
                    (x_raw, y_raw, xt, yt, valid), {},
                ))
            else:
                jobs.append((
                    path, compute_contour_surface_payload,
                    (xt, yt, valid),
                    {
                        "x_scale": host.x_scale,
                        "y_scale": host.y_scale,
                        "cofactor": host.cofactor,
                        "x_transform_params": host.x_transform_params,
                        "y_transform_params": host.y_transform_params,
                    },
                ))

        # A single miss has no concurrency benefit; leave it on the exact
        # historical direct path.
        if len(jobs) < 2:
            return {}
        return compute_kde_jobs_parallel(jobs)

    def draw_region_labels(self, applied_gates: list = None):
        """
        Draw population labels on the scatter plot.

        Single gate  → IN label + OUT label (classic view).
        Multi-gate   → Venn partition: one label per non-empty zone
                       (exclusive regions, overlaps, and "Outside all").
                       Percentages match what is shown in the stats panel.
                       No generic OUT label that would flood the canvas.
        """
        host = self._host
        if applied_gates is None:
            applied_gates = [g for g in host.gates if g.get('applied')]
        if not applied_gates: return
        display = host._display_files()
        if not display: return
        T = host.T

        x_parts, y_parts = [], []
        for path, df in display.items():
            if host.x_channel not in df.columns or \
               host.y_channel not in df.columns: continue
            x_parts.append(df[host.x_channel].to_numpy(dtype=float, copy=False))
            y_parts.append(df[host.y_channel].to_numpy(dtype=float, copy=False))
        if not x_parts: return
        xa = np.concatenate(x_parts)
        ya = np.concatenate(y_parts)
        _, _, valid_xy = host._transform_xy(xa, ya)
        xa = xa[valid_xy]
        ya = ya[valid_xy]
        total = len(xa)
        if total == 0: return

        # ── Single gate: classic IN / OUT labels ─────────────────────────
        if len(applied_gates) == 1:
            gate         = applied_gates[0]
            c            = gate.get('color', GATE_PALETTE[0])
            is_crosshair = gate['type'] == 'crosshair'

            # BUG FIX (performance): pass a synthetic cache key so _gmc is
            # consulted here just as it is in _plot_gated_multi.  Without a
            # _cache_path the original code bypassed the cache entirely, forcing
            # a second full contains_points call on the concatenated cell array
            # every render — easily 50 ms+ for 100 k-event files.
            # The key encodes all active file paths; the length-check inside
            # _gate_mask_for catches any stale entry whose mask length differs.
            _label_ck = '__lbl__' + '|'.join(sorted(display.keys()))
            regions, _ = host._gate_mask_for(gate, xa, ya,
                                             _cache_path=_label_ck)

            for rname, mask in regions.items():
                cnt = int(mask.sum())
                if cnt == 0 or (rname == 'OUT' and cnt == total): continue
                pct       = cnt / total * 100
                hint      = ' ⤵' if host.manager and rname != 'OUT' else ''
                label_txt = f'{rname}{hint}\n{pct:.1f}%\n({cnt:,})'

                # Crosshair quadrants: pin label to the matching plot corner so
                # it never obscures the data cloud.  Non-simple quadrant names
                # (mid-bands with '(m)') fall back to the centroid path.
                corner = host._crosshair_corner(rname) if is_crosshair else None
                if corner is not None:
                    cx, cy, ha, va = corner
                    host.ax.text(cx, cy, label_txt,
                                 ha=ha, va=va, fontsize=7.5,
                                 fontweight='bold', color=T['label_txt'],
                                 linespacing=1.4,
                                 transform=host.ax.transAxes,
                                 bbox=dict(boxstyle='round,pad=0.3',
                                           facecolor=T['label_box'],
                                           alpha=0.65, linewidth=0))

                # BUG FIX (visual): shape-gate OUT label was placed at the
                # centroid of the OUT population.  When a gate captures ~90 %
                # of events the remaining ~10 % (e.g. doublets at top-right)
                # have a centroid that visually lands inside the gate boundary,
                # making the plot unreadable.  Pin the OUT label to the
                # top-right axes corner instead — the same strategy used by
                # the crosshair corner labels — so it is always unambiguous.
                elif rname == 'OUT' and not is_crosshair:
                    host.ax.text(0.98, 0.97, label_txt,
                                 ha='right', va='top', fontsize=7.5,
                                 fontweight='bold', color=T['label_txt'],
                                 linespacing=1.4,
                                 transform=host.ax.transAxes,
                                 bbox=dict(boxstyle='round,pad=0.3',
                                           facecolor=T['label_box'],
                                           alpha=0.65, linewidth=0))

                else:
                    # IN label (and crosshair non-corner fallback): centroid
                    mx, my = host._label_centroid(xa, ya, mask)
                    if mx is None: continue
                    host.ax.text(mx, my, label_txt,
                                 ha='center', va='center', fontsize=7.5,
                                 fontweight='bold', color=T['label_txt'],
                                 linespacing=1.4,
                                 bbox=dict(boxstyle='round,pad=0.35',
                                           facecolor=c if not is_crosshair
                                                      else T['label_box'],
                                           alpha=0.82, linewidth=0))
            return

        # ── Multiple gates: Venn partition labels ────────────────────────
        # Build one boolean "in" mask per gate
        n = len(xa)
        in_masks = []
        for gate in applied_gates:
            regions, _ = host._gate_mask_for(gate, xa, ya)
            gt = gate.get('type', 'crosshair')
            if gt == 'crosshair':
                in_m = np.zeros(n, bool)
                for rname, m in regions.items():
                    if rname != 'OUT':
                        in_m |= m
            else:
                in_m = regions.get('IN', np.zeros(n, bool))
            in_masks.append(in_m)

        # Iterate over all 2^N combinations
        for combo in range(2 ** len(applied_gates)):
            flags      = [bool((combo >> i) & 1) for i in range(len(applied_gates))]
            combo_mask = np.ones(n, bool)
            for i, flag in enumerate(flags):
                combo_mask &= (in_masks[i] if flag else ~in_masks[i])
            cnt = int(combo_mask.sum())
            if cnt == 0:
                continue
            pct  = cnt / total * 100
            mx, my = host._label_centroid(xa, ya, combo_mask)
            if mx is None:
                continue

            in_gates = [applied_gates[i] for i, f in enumerate(flags) if f]
            if not in_gates:
                # Outside all gates
                label_text = f'Outside all\n{pct:.1f}%\n({cnt:,})'
                fc = T['label_box']
            elif len(in_gates) == 1:
                g    = in_gates[0]
                hint = ' ⤵' if host.manager else ''
                label_text = f'{g["name"]}{hint}\n{pct:.1f}%\n({cnt:,})'
                fc   = g.get('color', GATE_PALETTE[0])
            else:
                names      = ' ∩ '.join(g['name'] for g in in_gates)
                hint       = ' ⤵' if host.manager else ''
                label_text = f'{names}{hint}\n{pct:.1f}%\n({cnt:,})'
                # Blend: use first gate's color at reduced alpha
                fc = in_gates[0].get('color', GATE_PALETTE[0])

            host.ax.text(mx, my, label_text,
                         ha='center', va='center', fontsize=7.5,
                         fontweight='bold', color=T['label_txt'],
                         linespacing=1.4,
                         bbox=dict(boxstyle='round,pad=0.35',
                                   facecolor=fc,
                                   alpha=0.82, linewidth=0))
