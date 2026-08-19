# vFlow Historical Changelog

This file contains the historical release/change notes previously embedded in `vflow/legacy/vflow_app.py`. Moving these notes is documentation-only; it does not alter runtime or scientific behavior.

Changelog v4.3.0-dev A5 -> B6
-------------------------------
POST-REFACTOR INTEGRITY / EDGE-STATE HARDENING

  B6-01 Clear All now clears stale plot artists/title, channel selector UI state,
        and dataset-owned locked limits before a subsequent load.

  B6-02 Sub-gate tab closure now destroys forgotten notebook children after
        cancelling pending callbacks, eliminating repeated-tab widget/canvas leaks.

  B6-03 Hardened the sub-gate provenance boundary so a live Tk-backed gate is
        converted to a plain GateDefinition before AnalysisState deep-copy.

  B6-04 Layout rebuilds normalize old axes before Figure.clear(), preventing
        log/shared-axis teardown warnings and incompatible retained state.

  B6-05 Gate-session saves now handle filesystem OSError failures in the UI
        instead of propagating out of the refactored coordinator callback.

  B6-06 Constant/degenerate Density and Contour inputs now fall back to Dot
        instead of constructing a non-monotonic RegularGridInterpolator grid.
        The old test that intentionally preserved this crash was corrected.

  B6-07 Added permanent refactor-wiring, edge-dataset, Clear/reload, repeated-tab,
        and 80-operation real-GUI fuzz validators. Cumulative suite: 1115 tests.

Changelog v4.3.0-dev A4 -> A5
-------------------------------
POST-REFACTOR RUNTIME REGRESSION HARDENING

  A5-01 Restored gate preview rendering after controller decomposition by moving
        the missing `handle_cache_entries` dependency into
        GateInteractionController. Real GUI gate preview now builds the handle
        pixel cache without NameError.

  A5-02 Hardened render lifecycle across display-scale transitions. Full resets
        linearize the live Matplotlib axes before clearing, and retained-axis
        rendering is allowed only when live and target scale identities are
        compatible. This prevents stale log limits from reversing an axis after
        transitions such as log -> asinh.

  A5-03 Separated strict transform provenance from runtime gate applicability.
        Gates remain bound to their ordered X/Y measurement channels and are
        re-bound/recomputed when display scale, cofactor, or Logicle parameters
        change on those same channels. Selecting a genuinely different channel
        keeps the gate inactive; returning restores/recomputes it.

  A5-04 Repaired KDE/Derivative and Otsu auto-gating after refactor by replacing
        stale `_axis_transform_params()` calls with the current
        `_transform_params_for_axis()` API.

  A5-05 Added generated-data headless-GUI regression validation covering all 36
        combinations of linear/log/asinh/GML2 Logicle/legacy biexp/legacy
        logicle axes, manual creation/editing of all gate shapes, marginals,
        multi-file overlay/cycle, session round trips, and all four auto-gate
        families. The cumulative suite is now 1109 tests.

Changelog v4.1.11 -> v4.2.0
-------------------------------
REFACTOR, BEHAVIOR HARDENING, AND PERFORMANCE RELEASE

  V1   Completed the behavior-preserving v4.2 structural refactor and made the
       packaged ``vflow`` entry point the single release source authority.

  V2   Added deliberate robustness fixes from the post-refactor behavior review,
       including transactional geometry/state handling and cache-key correctness,
       while preserving the certified scientific/FCS baseline.

  V3   Added session-scoped channel nomenclature resolution, file reveal actions,
       and a resizable sidebar without weakening active-file axis compatibility.

  V4   Accelerated Density/Contour rendering, marginal rendering, hover geometry,
       gate evaluation, and cold multi-file KDE computation with deterministic
       caches and bounded worker concurrency.

  V5   Reworked gate/scatter caches to use packed masks, compact scatter payloads,
       and byte budgets so large many-file sessions avoid fixed-entry cache churn
       without unbounded memory growth.

  V6   Release metadata now reports v4.2.0 and the duplicate standalone
       ``vflow 1.4.11.py`` source copy has been retired.

Changelog v4.1.10 -> v4.1.11
-------------------------------
FCS EXPORTER COMPATIBILITY — FlowJo TextToFCS v1.3

  F1   Accept whitespace padding after the final TEXT delimiter. The padding
       is ignored only when it is whitespace-only; non-whitespace trailing
       tokens remain a hard error.

  F2   Accept the TextToFCS one-past-EOF DATA-end convention only when the
       declared end equals the exact file length. Strict payload-length checks
       still prove that the decoded DATA block contains exactly $TOT events.

  F3   If $PnE is absent, infer linear 0,0 only when the same parameter
       explicitly declares $PnD=Linear. Ambiguous missing amplification
       metadata remains rejected.

  F4   Record all compatibility normalizations in DataFrame attrs and surface a
       non-modal status notice. The decoded DATA values themselves are unchanged.

Changelog v4.1.9 -> v4.1.10
-------------------------------
PRE-TEST RELIABILITY HARDENING

  R1   Installable package now carries the legacy UI implementation inside
       vflow/legacy/vflow_app.py. Source-tree and installed-wheel launches use
       the same packaged file, eliminating the source-tree-only startup trap.

  R2   Polar and Batch Plot windows own and cancel their delayed after()
       callbacks on close, preventing callbacks from firing against destroyed
       Tk widgets/canvases.

  R3   Case-insensitive duplicate channel names are rejected for CSV input and
       disambiguated for FCS input, preventing case normalization from creating
       duplicate pandas columns and silently selecting multiple channels.

  R4   Exact-path batch exclusions use normalized real filesystem paths rather
       than lower-cased strings, avoiding false exclusions on case-sensitive
       filesystems and improving symlink/path-form consistency.

  R5   Concatenated-file detection prefers Source_Path provenance when present,
       so concatenates containing distinct origins with the same basename are
       still recognized and cannot be double-counted alongside originals.

Changelog v4.1.8 -> v4.1.9
------------------------------
PACKAGE SCIENTIFIC-CORRECTNESS HARDENING

  P1   Core gate masks now enforce the finite/displayable X/Y event universe.
  P2   Unknown region names fail closed instead of silently selecting all rows.
  P3   Transform names and asinh/logicle cofactors are validated centrally.
  P4   Fixed-seed auto-gate/render subsampling is actually deterministic per call.
  P5   Polar vectors discard non-finite coordinate pairs before circular stats.
  P6   Concatenated sample labels retain semantic names instead of bare numbers.
  P7   Loaded gates reject malformed applied geometry and duplicate IDs are repaired.
  P8   Gated-data export fails closed on missing axes and records Gate_ID provenance.
  P9   Batch wide exports disambiguate duplicate gate names by gate ID.
  P10  FCS reader now handles escaped TEXT delimiters, strict byte order, tight integer
       bit packing, duplicate channel labels, required metadata and truncation checks.
  P11  Launcher/package release versions are checked at import time.
  P12  CSV import only removes an unnamed first column when its values prove it
       is a generated row-number index; legitimate unnamed measurements are kept.
  P13  Concatenation and gated exports preserve collision-safe Source_File labels
       plus full Source_Path provenance; nested concatenation is rejected.
  P14  Batch Plot sample construction no longer drops ordinary files when concat
       inputs are selected and no longer merges same-named sources across containers.
  P15  Core auto-gating now fails closed for empty/degenerate data and unsupported
       KDE/Otsu splits instead of returning plausible tail/zero thresholds.
  P16  Core gate statistics validate non-overlapping complete region partitions and
       identical region schemas/event universes before percentages or merges.
  P17  FCS files carrying $SPILLOVER are explicitly flagged as uncompensated at load
       time; vFlow does not silently imply that compensation has been applied.
  P18  Package metadata now requires Python >=3.10, matching the PEP 604 union type
       syntax already used throughout the package.
  P19  The UI now explicitly identifies the legacy `biexp` and `logicle` choices as
       vFlow signed-log approximations, not Gating-ML-compatible transforms. Their
       numeric behavior is intentionally unchanged in this correctness baseline.
  P20  Polar/vector analysis excludes zero-length displacement vectors because their
       direction is undefined; atan2(0,0)=0 must not create a false 0-degree signal.
  P21  Polar MRL thresholds must be finite and in [0,1]; invalid values no longer
       silently fall back to 0.3 in the stats tree or export. Polar CSV rows also
       include Source_Path provenance.

Changelog v4.1.7 -> v4.1.8
------------------------------
MASK INTEGRITY / SECONDARY-ANALYSIS CORRECTNESS HARDENING

  C15  Gate-region masks are now centrally intersected with the finite,
       displayable X/Y population for the active transform. Shape-gate OUT
       masks can therefore never absorb NaN/Inf/log-invalid events while
       statistics use a smaller finite denominator.

  C16  Explicit-context ancestor replay uses the same finite-mask rule. Nested
       sub-gate batch reconstruction therefore cannot re-introduce transform-
       invalid events through an ancestor OUT population.

  C17  Polar Analysis is all-or-nothing for the requested file set. If a
       selected gate or vector mapping cannot be evaluated for any visible
       sample, the comparison is stopped instead of silently dropping that
       sample and rendering a plausible-looking partial analysis.

  C18  Batch Plots are likewise all-or-nothing for gated comparisons. A sample
       whose requested gate cannot be evaluated aborts the gated comparison
       instead of appearing as an empty/omitted sample while the status line
       later reports a normal successful render.

  C19  Batch Plot population percentages and binomial counting SEM now use the
       finite/displayable X/Y event count as denominator, matching interactive
       gate statistics and the actual gate-mask population.

  C20  Folder Batch Stats no longer reuses the interactive persistent gate-mask
       cache for freshly re-read files. This prevents an externally modified
       file at the same path and row count from inheriting a stale in-session
       mask during batch export.

  C21  Sub-gate tab preloading now uses atomic file/UI registration, preserving
       the v4.1.5 B27 invariant in child tabs as well as the main tab.

  C22  Gate files with unknown schema versions are now rejected instead of
       being loaded on a best-effort basis. Scientific provenance must not be
       guessed for a schema the application does not understand.

  C23  Legacy v1 gate files can no longer be rebound across different X/Y
       channels. When channels match, loading requires an explicit warning that
       v1 did not record scale/cofactor provenance and will bind geometry to the
       currently selected transform. v2 files must contain a valid context for
       every gate; missing/malformed v2 provenance is rejected.

Changelog v4.1.6 -> v4.1.7
------------------------------
LAUNCHER ARCHITECTURE CLEANUP — no intended analytical behavior changes

  R1   Removed shadow/dead implementations that were defined locally and then
       overwritten before first use by the companion `vflow` package.  The
       package is now visibly the single runtime source of truth for themes,
       scales, constants, FCS reading, cache signatures, auto-gating helpers,
       plotting helpers, and the folder/batch-stats dialogs.

  R2   Effective imports now bind directly to the names used by the launcher
       instead of importing `core_*` names and reassigning them later.  This
       eliminates a class of audit errors where comments/changelog described a
       local implementation that could never execute.

  R3   Removed matplotlib scale-construction imports used only by the dead local
       scale classes.  Heavy scientific imports still used by the launcher
       (KDE, Savitzky-Golay, interpolation, sklearn GMM) are retained.

  R4   Consolidated package configuration/UI imports into the main dependency
       section and retained a single explicit `register_flow_scales()` call.

  R5   Added static regression coverage (companion test file) that fails if
       critical package-owned symbols are redefined/shadowed again or if the
       launcher loses the v4.1.6 scientific-hardening hooks.

Changelog v4.1.5 -> v4.1.6
------------------------------
SCIENTIFIC CORRECTNESS HARDENING

  C1   Gates are now bound to the analysis context in which they were created
       (X/Y channels, X/Y scales, and relevant cofactor). A gate is never
       silently reinterpreted on different axes or a different nonlinear
       transform. Switching back to the original context re-enables it.

  C2   Axis / scale / cofactor changes centrally invalidate transform, gate-mask
       and scatter caches and recompute statistics for every compatible applied
       gate. This prevents stale plot/stat/export state after context changes.

  C3   Gate-mask and scatter cache keys now include the data-generation token,
       scales and cofactor. Reloading changed data from the same path can no
       longer reuse a mask/transform created for an older dataset generation.

  C4   Polar and Batch Plot population selection now FAILS CLOSED. If a chosen
       gate cannot be resolved, is incompatible with the current analysis
       context, or required channels are missing, the analysis does not silently
       substitute All Cells. The affected computation is stopped / omitted and
       the UI reports the reason.

  C5   Polar stats export now respects the Polar window's own per-file visibility
       checkboxes, matching the files actually plotted.

  C6   Sub-gate provenance is snapshotted immutably and propagated as a complete
       ancestor lineage. Batch stats reapply every ancestor stage using the
       exact channel/transform context that created that stage, rather than a
       mutable reference to only the immediate parent gate.

  C7   Gate JSON schema upgraded to v2 at the launcher boundary. Per-gate
       analysis contexts and sub-gate population lineage are persisted. A gate
       file created in a different sub-population is refused rather than being
       silently applied to a different denominator. Legacy v1 files remain
       loadable and are explicitly bound to the current context on import.

  C8   Finite transformed-event counts are used as the denominator for interactive
       single-gate statistics, matching the population that can actually be
       classified/displayed on the selected transforms.

  C9   Multiple-gate Venn-like overlap is disabled when any applied gate is a
       crosshair partition. Crosshairs divide the whole plane into regions and
       do not define a meaningful binary IN/OUT set; each gate is shown
       independently instead of fabricating an overlap interpretation.

  C10  Density plotting checks for fewer than two valid transformed observations
       before percentile/KDE work, preventing all-invalid channels from failing
       before the existing KDE fallback can run.

  C11  Gate selectors disambiguate duplicate gate names by immutable gate ID.
       Secondary analyses no longer resolve duplicate names by silently taking
       the first gate in list order.

  C12  Axis menus are constrained by checked/active files rather than every
       loaded file. Intentionally inactive files can no longer hide otherwise
       valid analysis channels.

  C13  Concatenation refuses duplicate basenames from different folders because
       basename-only Source_File provenance would make those samples
       indistinguishable downstream.

  C14  KDE Valley auto-gating validates that the returned threshold is backed by
       a genuine two-sided KDE valley. Unimodal tail-percentile fallbacks are no
       longer presented as detected population separations.

Changelog v4.1.4 -> v4.1.5
------------------------------
SCIENTIFIC CORRECTNESS — fixes for issues that produce silently wrong stats
or crash the UI on common data shapes.

  B1   batch_export_stats: re-apply column-case normalization
          The interactive view rewrites a file's column casing to match
          previously loaded files (Intensity_vgat → Intensity_VGAT) so the
          axis menus see a consistent set.  batch_export_stats called
          _read_data_file directly and skipped the rename, silently
          dropping files whose case differed from the leader.  Fixed by
          factoring the rename into a new _normalize_columns_to_loaded()
          helper called from both paths.

  B2   _dict_to_gate: assign unique IDs to gates missing one
          Original used d.get('id', self._next_gate_id) which produced the
          same fallback id for every gate missing one — and then
          _del_gate(0) filtered on id != 0 and removed ALL of them at
          once.  Now the loader tracks the next-free id (max+1 of any
          present, plus current _next_gate_id) and bumps it for each
          missing-id gate.

  B3   derivative_threshold: handle empty-after-filter data
          On a fully-saturated channel (all NaN/Inf), the function dropped
          straight through to np.percentile([], 5) → IndexError. Now
          returns 0.0 when the filter empties the input, and wraps
          gaussian_kde construction in a try/except for constant data.

  B4   _plot_density / _plot_contour: catch gaussian_kde LinAlgError
          Collinear data, saturated channels, or duplicate points yield a
          singular covariance matrix; the exception propagated out of
          refresh_plot and made the UI unable to draw any plot until the
          user manually switched modes.  Both density and contour paths
          now fall back to dot mode on (np.linalg.LinAlgError, ValueError).

  B5   _dict_to_gate: validate vertex / threshold types
          A malformed JSON gate (non-numeric vertex like [['a','b'],[1,2]])
          loaded "successfully" but then cascaded crashes through every
          subsequent file load — _gate_sig calls float('a') from the
          active-files-changed callback.  All numeric fields are now
          coerced through _safe_float / _safe_float_list / _safe_vertices
          helpers that drop bad entries silently.  Top-level structure is
          also validated (non-list 'gates' field is rejected with a clear
          message).

  B6   clear_all_files: reset x_channel / y_channel
          When the user cleared files and loaded a file with different
          column names, the stale channel names triggered the cols[0]
          fallback in _update_channel_menus for both axes — assigning the
          SAME column to both X and Y.  Reset happens on clear; the
          y-fallback also now picks a different column from x.

  B7   _hit_test_gate_interior: polygon test in transform space
          _gate_mask_for forward-transforms polygon vertices to match
          the rendered (straight-pixel-segment) boundary.  The hit-test
          used raw space, so on log/asinh/biexp axes a double-click just
          inside the drawn polygon could miss it (or land on the wrong
          gate when nested).  Hit-test, rectangle area, and ellipse area
          are all now computed in transform space for consistent
          tie-breaking against polygons.

  B8   export_stats: y_boundary == 0 no longer blanked
          Original wrote 'Y Gate': round(yb, 4) if yb else '' — `if yb`
          is False for 0.0, a perfectly valid threshold (especially on
          biexp/asinh axes that pass through zero).  Changed to
          'if yb is not None'.

  B9   _rebuild_thresh_panel: persist new BooleanVars into the gate
          When x_thresh_vars was shorter than x_boundaries, the panel
          created a fresh BooleanVar(True) for the checkbox but never
          appended it back to the gate dict.  Toggling fired the orphan
          var; _active_xbs_for then saw a length mismatch and returned
          ALL boundaries, so the checkbox had no effect.  Y multi-valley
          path had the same bug.  All paths now append the new var.

  B10  Family-exclusion docstring lies — fixed implementation
          The documented use case (excluding '..._Pooled_CytoFile'
          should also exclude '..._1___CytoFile') never actually fired
          under the prior 70%-of-shorter-stem rule.

  B11  Family-exclusion: stop false positives on substring filenames
          'alpha' (excluded) wrongly excluded 'alphabet' (common prefix
          'alpha' = 100% of 5-char short stem).  New rule:
            • common prefix must end at an '_' boundary;
            • prefix must contain ≥ 2 '_' segments (so 'TH_' alone
              doesn't cascade);
            • both stems must extend strictly past the prefix.
          Verified against 11 test cases including the docstring example
          (now matches) and the alpha/alphabet false-positive (now
          rejected).

  B12  export_gated_data: shape gates take priority over crosshair
          The "first matching gate" rule (per docstring) was literally
          true but practically useless: a crosshair listed first has
          four quadrants covering 100% of cells, absorbing them all
          before any polygon/rectangle/ellipse could claim them.
          Verified: a 1000-cell file with order [XHair, PolyA, PolyB]
          previously assigned 1000 to XHair, 0 to PolyA, 0 to PolyB.
          Now: shape gates win first (43 to PolyA, 31 to PolyB), then
          crosshair gets the rest (926).  Docstring updated to reflect
          this priority.

  B13  auto_gate_cluster_polygons: hull in transform space
          Clustering ran in transform space (asinh/biexp/etc.) but the
          convex hull was computed on the RAW data points of each
          cluster.  On non-linear axes the raw-space hull corresponds to
          a non-convex shape in display space — the visible polygon then
          excluded visually-clustered cells.  Hull is now computed on
          the transform-space coordinates; vertices are mapped back to
          raw via the cluster's index mapping for storage.  Falls back
          to a raw-space bounding box for degenerate (collinear) clusters.

  B14  Tk variable leaks via `.get(key, tk.SomeVar(default)).get()`
          Tk variables are registered with the Tcl interpreter and never
          garbage-collected, so the `dict.get(key, tk.BooleanVar(default))`
          pattern leaks one variable per call when the key is missing.
          Fixed at five hot-path locations:
            – PolarAnalysisWindow._get_active_paths
            – _rebuild_thresh_panel (Y-multi, Y-single, X-multi)
            – BatchPlotWindow._build_file_list
            – BatchPlotWindow._render_figure (zoom_x / zoom_y)

  B15  auto_gate_cluster_polygons: tag 'hdbscan' when HDBSCAN is used
          Gates created by the HDBSCAN path stored auto_method='dbscan'.
          The tag is now 'hdbscan' when HDBSCAN was selected;
          'dbscan' is kept for the DBSCAN fallback.  Both legacy values
          are recognised when wiping previous results.

  B16  _flow_fmt: fix fallback formatting
          For |x| >= 1e4 not in _TICK_MAP the previous f-string produced
          ambiguous output like '-107' for x = -1e7.  Now uses Unicode
          superscripts ('-10⁷') consistent with _TICK_MAP entries.

  B17  _drag_handle_update: targeted scatter cache eviction
          The previous full `self._scatter_cache.clear()` on every
          motion frame wiped all loaded files' caches at ~60 Hz during
          a drag.  Only entries whose gate-sig tuple references the
          dragged gate are now evicted; entries for other gate
          configurations remain valid.

  B18  auto_sensitivity_var: fix initial label
          IntVar initialised to 7 but label hardcoded to '5'; the trace
          handler that syncs them was attached after the var was set, so
          the initial label was wrong until the user moved the slider.
          Label now reads from the var directly.

  B19  otsu_threshold: suppress RuntimeWarning: divide by zero
          The `(total_mean - w0 * mu0) / w1` expression evaluated for
          ALL elements before np.where masked the result, producing a
          stream of warnings on every call.  Replaced with np.divide
          using `where=(w1 > 1e-9)` and a pre-allocated out array.

  B21  load_gates: validate JSON structure
          Top-level shape (gates field must be a list) is now checked
          before iteration.  Each gate dict is type-checked, with
          malformed gates rejected and reported as skipped in the
          success message.

  B22  _open_subgate: pass _cache_path
          The sub-gate population mask was recomputed from scratch even
          though refresh_plot had just placed an identical entry in
          _gmc.  Now passes _cache_path so the cache is consulted.

  B23  _preview_gate: skip empty rect/ellipse gates
          Previous skip condition only caught polygons.  An empty 0×0
          rectangle from an aborted draw would otherwise render as a
          single dot at the axes corner on every refresh.

  B24  clear_all_gates: reset _next_gate_id and caches
          IDs grew monotonically across clear/add cycles, making JSON
          exports harder to reason about and ID values increasingly
          large over long sessions.  Reset to 0; _gmc and _scatter_cache
          are cleared too to drop stale entries.

  B25  _on_release: reset _draw_frozen_xlim / _draw_frozen_ylim
          The frozen-axis snapshots captured at click-time were never
          released, so a later autoscale could be surprised by stale
          data.  Reset in all three release paths (handle drag, gate
          move, gate draw).

  B26  _close_tab: cancel pending after callbacks
          _refresh_pending, _replot_pending, _sens_rerun_pending could
          fire on a destroyed canvas after a sub-gate tab was closed.
          The catch-all except blocks swallowed the resulting Tcl error
          but kept the FlowApp instance alive (closure reference) until
          the timer fired.  All three are now cancelled on close.

  B27  _load_paths: atomic file-row registration
          loaded_files[path] was set before _add_file_row(path) was
          called.  If _add_file_row raised (Tk widget failure), file_vars
          was missing the key and _active() would KeyError later.  Now
          file_colors and _add_file_row are committed first; loaded_files
          is set only after the row succeeds.

  B28  _rebuild_gate_manager: hoist _LS_MAP / _LS_INV out of hot loop
          These dicts never change at runtime; building them on every
          gate-row render was pure overhead.  Moved to module scope as
          _LINESTYLE_MAP / _LINESTYLE_INV.

  B29  batch_export_stats: detect concat files and previous batch output
          A folder containing the Concatenate output AND its source
          files would have every cell counted twice (once via each
          source, once via the concat).  Files with a `Source_File`
          column referencing more than one origin are now skipped with
          an explicit log entry.  Previous batch CSVs (which have
          Sample/Total_Cells but no channel data) are also skipped
          explicitly instead of being silently logged as "missing
          channel" errors.  Percentage rounding unified to 3 decimals
          between export_stats and batch_export_stats so the two
          export paths produce identical values for the same data.

  B30  batch_export_stats: disambiguate duplicate basenames
          os.walk recurses into all subfolders, so a tree like
              /data/file_0.csv
              /data/old_runs/file_0.csv
          previously produced TWO batch-output rows both labelled
          'file_0' — silently mismatching interactive analysis that
          loaded only the top-level files.  Rows whose basename
          collides are now relabelled with their relative subfolder
          path ('sub/file_0' instead of 'file_0').  A `Relative_Path`
          column is always included so users can audit the origin of
          every row regardless of whether disambiguation triggered.

Changelog v4.1.3 -> v4.1.4
------------------------------
PERFORMANCE

  Perf 1  Blit acceleration extended to handle-corner drag and gate drawing
             v4.1.2 introduced blit for gate-body move only.  The same
             three-part pattern (background capture → per-frame restore+blit
             → release on drop) is now applied to the two remaining
             interactive paths that previously used draw_idle() on every
             motion event:

             (a) Handle-corner / vertex resize drag (_handle_drag)
                 At right-click press on a handle, _start_blit_drag()
                 captures the scatter-only pixel buffer once.  Each motion
                 event throttles at 60 fps, calls _preview_gate(skip_cache)
                 to rebuild only the gate outline artists, restores the
                 saved buffer, composites those artists with draw_artist(),
                 and flushes with canvas.blit().  The scatter layer is never
                 re-rendered during the drag.  Frozen axis limits are
                 snapshotted into _handle_drag at press time and restored
                 after each preview, preventing autoscale expansion when a
                 corner is dragged to the axes edge.  _end_blit_drag() is
                 called in _on_release before _finish_gate().

             (b) Gate drawing (rectangle, ellipse, crosshair, polygon)
                 When the user clicks to begin drawing a new gate,
                 _start_blit_drag() captures the scatter background once.
                 Rectangle/ellipse/crosshair: each motion event throttles at
                 60 fps, updates the corner coordinate, calls
                 _preview_gate(skip_cache), restores frozen axis limits, and
                 blits.  Polygon: the background is captured at the first
                 vertex click; each rubber-band motion event throttles and
                 blits the partial polygon + tentative segment without a full
                 redraw; subsequent vertex clicks reuse the captured
                 background (the scatter hasn't changed) and blit immediately.
                 _end_blit_drag() is called in _poly_finish() (polygon close
                 or double-click) and in _on_release for other gate types.

             In both cases the draw_idle() fallback is retained: if
             _drag_bg is None (canvas not yet fully rendered at press time)
             the motion handler falls back to the previous draw_idle() path.

  Perf 2  _drag_handle_update no longer calls _preview_gate / draw_idle
             These calls have been moved to _on_motion so the throttle and
             blit logic live in one place.  _drag_handle_update now only
             updates gate geometry and evicts stale caches; rendering is
             always the caller's responsibility.

  Perf 3  New _blit_render() helper
             The restore_region → draw_artist loop → canvas.blit / draw_idle
             fallback sequence was previously duplicated in the _gate_move
             block and is now needed in five further locations.  Extracted
             into a single _blit_render() method called by all three drag
             paths and the polygon vertex-click path.

Changelog v4.1.2 -> v4.1.3
------------------------------
BUG FIXES

  Bug 1  Loaded gates: corner resize broken (deepcopy crash on Tkinter objects)
             _hit_test_handles() built the 'orig' snapshot of a gate with
             copy.deepcopy(gate).  Loaded gates can store tk.BooleanVar /
             tk.Variable objects as gate-dict values (e.g. applied flags).
             copy.deepcopy raises a TypeError on Tkinter objects.  Because
             this deepcopy happened after the try/except block that only
             wraps transData.transform(), the exception propagated out of
             _hit_test_handles uncaught, making the function return None
             for every right-click on a loaded-gate handle.  The click then
             fell through to the body-move or line-pin path instead — making
             all corner and vertex resizing appear completely broken for any
             gate that was loaded from a JSON file.

             Fix: replaced copy.deepcopy(gate) with the same Tkinter-safe
             shallow dict comprehension introduced for _gate_move in v4.1.0:
               {k: v for k, v in gate.items()
                if not isinstance(v, (tk.BooleanVar, tk.Variable))}
             The only values actually read from 'orig' inside
             _drag_handle_update are plain floats (x0, x1, y0, y1), so a
             shallow copy is fully correct.  This fix applies to all
             resizable gate types (rectangle, ellipse, polygon) identically.

Changelog v4.1.1 -> v4.1.2
------------------------------
PERFORMANCE
  Perf 1  Gate body-drag now uses matplotlib blitting — scatter is never
          re-rendered during a drag
             Previously every motion event called canvas.draw_idle(), which
             re-rendered the full scene: scatter points, axes, ticks, legend.
             With 10 k points and a typical renderer this costs 30–150 ms per
             frame, making drag feel sluggish even with the 60 fps throttle.

             New approach — three cooperating parts:
             (a) _start_blit_drag() — called once at right-click press.
                 Clears gate outline artists, does one synchronous canvas.draw()
                 to commit the scatter-only state, then captures the pixel buffer
                 with canvas.copy_from_bbox(fig.bbox).  The full render happens
                 exactly once per drag; the momentary press latency is far less
                 perceptible than per-frame lag during the motion.
             (b) Motion frames — restore_region() restores the captured buffer,
                 draw_artist() composites only the updated gate outline artists
                 on top, canvas.blit() flushes just those changed pixels to the
                 screen.  The scatter layer is never touched mid-drag.
             (c) _end_blit_drag() — called in _on_release before _finish_gate().
                 Releases the background snapshot; the next refresh_plot() does a
                 normal full render to reconcile the final gate position.
             Fallback: if copy_from_bbox fails (canvas not yet fully initialised),
             _drag_bg is set to None and the motion handler falls back to the
             previous draw_idle() path — no crash, just the old behaviour.

  Perf 2  Motion-event throttle — redraws capped at ~60 fps
             A 16 ms minimum interval between frames (time.monotonic()) prevents
             event pile-up when the mouse moves faster than the renderer.
             _drag_last_draw is reset to 0.0 at every drag-start so the very
             first frame is never dropped.

  Perf 3  _rebuild_handle_px_cache() skipped during body drag
             This call transforms every gate handle vertex to display pixels
             after each preview rebuild.  During a body-drag, hover hit-testing
             is never reached (motion handler returns at the _gate_move block),
             making the rebuild pure overhead.  A skip_cache kwarg on
             _preview_gate() suppresses it without affecting any other caller.
             The cache is rebuilt correctly on mouse-release via the normal
             refresh_plot() → _preview_gate() path.

Changelog v4.1.0 -> v4.1.1
------------------------------
BUG FIXES (superseding all previous v4.1.0 attempts)

  Bug 1  Hover detection broken for ALL gates after 4.1.0 changes
             v4.1.0 replaced _hover_test_handles / _cursor_for_hover /
             new_hover_handle_key with live transData.transform calls,
             intending to eliminate stale-cache issues.  This BROKE hover:
             after ax.clear() + set_xscale(), viewLim is at its default
             (0,1) and autoscale has not yet committed.  Live-transform
             calls before draw_idle() actually renders return pixel coords
             based on the (0,1) viewport — far from where handles appear.
             Fix: reverted all three to _handle_px_cache-based lookup
             (original 4.0.21 approach).  The draw_event callback
             (added in 4.1.0) ensures the cache is rebuilt with the
             fully-committed transform after every render, making it
             reliable for all scales (linear, log, biexp, asinh, logicle).

  Bug 2  Loaded gates: corner resize dead zone (original 4.0.21 bug)
             _hover_test_handles used a 30 px threshold (HANDLE_PX * 2.5)
             but _hit_test_handles (click path) used only 12 px (HANDLE_PX).
             The user could see a highlighted handle (hover fired at 20 px),
             right-click exactly on it, and have the click fall through to
             _hit_test_gate_line (pin) instead of grabbing the handle —
             because the click was outside the 12 px radius.
             Fix: _hit_test_handles now uses HANDLE_PX * 2.5 = 30 px,
             matching hover exactly.  If hover shows a handle, a click
             there is guaranteed to grab it.

  Bug 3  axis_lock broke gate body move (introduced and removed in 4.1.0)
             Fully removed — gate body moves are free 2-D.

  Bug 4  Axis limits expand during gate body drag
             _preview_gate() calls ax.plot() which participates in
             matplotlib autoscale.  Axis limits are now snapshotted into
             _gate_move['frozen_xlim'/'frozen_ylim'] at drag-start and
             restored after each _preview_gate() during the drag.

Changelog v4.0.21 -> v4.1.0
------------------------------
NEW FEATURE
  Feat 1  Axis-limits frozen during gate-body right-drag
             When right-dragging a gate body to reposition it, the plot
             axis limits are now locked for the duration of the drag.
             Previously, _preview_gate() calling ax.plot() / add_patch()
             participated in matplotlib's autoscale, causing the view to
             zoom out unexpectedly when gate vertices moved close to or
             beyond the current axis edges.
             Implementation: frozen_xlim / frozen_ylim are snapshotted into
             the _gate_move state dict at the moment of the right-click press
             and restored after every _preview_gate() call during the drag.
             The limits are re-evaluated normally by the next refresh_plot()
             on mouse release.

BUG FIXES
  Bug 1  Loaded gates: corner resize appeared broken (click dead-zone)
             _hover_test_handles used a 30 px radius (HANDLE_PX * 2.5) to
             decide whether to highlight a handle, but _hit_test_handles (the
             click path) used only 12 px (HANDLE_PX).  This created a dead
             zone of 13-29 px: the user saw a handle highlighted and right-
             clicked exactly on it, but the click fell through to the
             interior-move path instead of starting a resize drag — making
             corner reshaping appear completely broken for loaded gates.
             Fix: _hit_test_handles now uses the same HANDLE_PX * 2.5 = 30 px
             threshold, eliminating the dead zone.  The hover and click radii
             are now always in sync: if hover shows a handle, a click there
             is guaranteed to grab it.

  Bug 2  Loaded gates / all gates: gate move appeared broken (axis_lock)
             The axis_lock feature committed the drag to H or V after just
             5 px of travel.  For any diagonal movement the perpendicular
             component was permanently zeroed, making the gate appear to slide
             only in one direction — or appear stationary if the user dragged
             roughly orthogonal to the committed axis.  This misfeature was
             also the cause of the user-reported "nothing happens" when trying
             to move a loaded gate.  The H/V direction lock was never
             requested; the user asked for axis-LIMITS to stay frozen during
             the move (Feat 1 above), not for movement direction to be
             constrained.
             Fix: the axis_lock key and its entire logic block have been
             removed from _gate_move and _on_motion.  Gate body moves are
             now fully free 2-D translations.

  Bug 3  Loaded gates: handle pixel cache stale on non-linear axes
             _hover_test_handles, _cursor_for_hover, and the hover_handle_key
             block in _on_motion all used _handle_px_cache, which was built
             by _rebuild_handle_px_cache() immediately after _set_axis_scale()
             in refresh_plot().  Because matplotlib's transform tree is lazy,
             the cache was still stale at that point.  All three now use the
             live transData.transform on every event.  _rebuild_handle_px_cache
             is retained as a draw_event callback (belt-and-suspenders) but no
             longer drives interactive hit-testing.

  Bug 4  clear_all_gates() left _gate_move and _interior_hover_gate_id
             stale — added explicit None resets matching the existing pattern
             for _handle_drag and _hover_gate_id.

Changelog v4.0.19 -> v4.0.20
------------------------------
BUG FIXES
  Bug 1  Top-Y lock buttons: + and − were swapped
             yt+ (+, expand up) was placed BELOW yt- (−, shrink), the
             opposite of the intuitive direction.  Swapped so + sits at
             the top of the pair (closest to the axis top, expands
             upward) and − sits below it (shrinks the top limit).
             Bottom-Y pair was already correct (+ below −).

  Bug 2  X-axis lock buttons: vertical offset increased
             y_xbtn = ax_bot_tk + 26 left the buttons clipping into the
             tick-label row on linear scales where labels render taller.
             Increased to ax_bot_tk + 36 for reliable clearance.

Changelog v4.0.18 -> v4.0.19
------------------------------
BUG FIXES
  Bug 1  Lock-scale buttons now truly visible in dark mode on all platforms
             tk.Button ignores bg/fg on macOS because native Aqua rendering
             overrides Python colour options — buttons rendered as plain grey
             squares with invisible text.  Replaced all eight lock-scale
             tk.Button widgets with tk.Label widgets bound to <Button-1>.
             tk.Label always respects bg/fg on every platform (macOS, Linux,
             Windows).  Hover effect is implemented via <Enter>/<Leave>
             bindings that swap bg ↔ accent colour.  Stored _bg/_fg/_act
             attributes on each label allow _reposition_lock_buttons and
             toggle_theme to update hover colours after a theme switch.

  Bug 2  toggle_theme now uses the high-contrast lock-button palette
             The theme-switch path in toggle_theme still called b.configure()
             with header_bg/fg (old dim palette) and passed activebackground
             which is not a tk.Label attribute.  Updated to use the same
             #3a4255/#ffffff (dark) and #c8ccd4/#1a1a1a (light) palette and
             to rebind <Enter>/<Leave> so hover colours also update on switch.

UI
  UI 1  Y lock buttons shifted further left — clear of tick labels
             Previous offset ax_left − BW − 6 px left the buttons inside the
             tick-label band (labels can be 35–45 px wide on biexp/logicle
             scales).  New offset: max(4, ax_left − BW − 50), placing buttons
             well into the left figure margin with a guaranteed 4 px floor.

Changelog v4.0.17 -> v4.0.18
------------------------------
UI
  UI 1  Lock-scale Y buttons moved to LEFT spine, stacked vertically
             Y buttons now sit just to the left of the scatter axes left
             spine (x = ax_left − BW − 6 px) rather than in the right
             figure margin.  Each pair is stacked vertically (one button
             above the other) at the top and bottom of the Y axis, matching
             the layout shown in the reference screenshot.

  UI 2  Lock-scale +/− buttons: high-contrast colours in dark mode
             Replaced the theme-fg / header_bg palette (which gave
             insufficient contrast against the dark plot background) with a
             dedicated high-contrast palette:
               dark mode  → #ffffff text on #3a4255 slate-blue background
               light mode → #1a1a1a text on #c8ccd4 grey background
             The same palette is applied both at button creation time and on
             every repositioning pass (theme-toggle safe).  Font size raised
             from 8 → 9 pt bold for extra legibility.

Changelog v4.0.16 -> v4.0.17
------------------------------
BUG FIXES
  Bug 1  Minor ticks now always visible on non-linear axes
             Previously _apply_lock_minor_ticks() / _remove_lock_minor_ticks()
             were called inside the lock-scale if/else block, so decade-
             subdivision ticks only appeared while "Lock & Adjust Scale" was
             enabled.  The two methods have been merged into a single
             _apply_minor_ticks() that is called unconditionally from
             refresh_plot() after _set_axis_scale(), regardless of lock state.
             The dead for…pass loop that was inside _apply_lock_minor_ticks
             has also been removed.

  Bug 2  Lock-scale +/− buttons no longer overlap axis labels
             X buttons: y-offset raised from +4 px → +26 px, clearing the
             ~20 px x-tick label row.
             Y buttons: moved from the LEFT side of the axes (where they sat
             directly on top of labels like "−10⁵") to the RIGHT figure margin
             at ax_right + 30 px, which is always free of tick labels regardless
             of whether the marginal histogram is visible.

  Bug 3  Spurious f-prefix removed from 10 static strings
             f'…' literals with no {} placeholder emit SyntaxWarning on
             Python ≥ 3.12 and mislead readers into thinking interpolation
             occurs.  All 10 instances removed:
             lines 1555–56 (concatenation warning), 2464 (suptitle),
             2476 (status bar), 2510 (stats tree), 6724 (hint var),
             6735 (status bar), 7291 (save dialog), 7321 (load dialog),
             9111 (tab menu).

PERFORMANCE
  Perf 1  _hex_to_rgba — collapsed redundant wrapper + alias chain.
             _hex_to_rgba_cached and _HEX_RGBA_CACHE alias removed; the
             single @lru_cache(256) function is now called directly.
             Saves one extra Python function-call frame per RGBA lookup.

  Perf 2  _flow_fmt — added @functools.lru_cache(128).
             Tick formatter is called on a small fixed set of values
             (the _FLOW_TICKS grid); after warm-up every label is a
             dict hit with no log10 / string-format work.

  Perf 3  _apply_minor_ticks — FixedLocator result cached in
             self._minor_loc_cache keyed on (scale, lo, hi).
             On stable renders the ~120-item list comprehension over
             _FLOW_MINOR_TICKS is skipped entirely.  Cache cleared
             in _apply_scales() and _on_lock_scale_toggle().

  Perf 4  _N_FILE_COLORS / _N_REGION_COLORS — module-level constants
             replace 16 repeated len() calls inside file and region
             colour-index loops.

  Perf 5  _plot_gated_multi RGBA loop — three micro-optimisations:
             • Short-circuit continue on empty regions dict.
             • Shared _empty_bool sentinel replaces per-iteration
               np.zeros(n, bool) allocation for shape-gate fallback.
             • in_any |= mask (vectorised OR) replaces in_any[mask]=True
               (indexed boolean write).

  Perf 6  _plot_dot / _plot_contour — eliminated redundant array
             reductions in scatter legend labels.
             _plot_dot:    n = len(xv) already equals valid.sum(); label
                           now uses n directly.
             _plot_contour: n_outside = len(xo) pre-computed; also
                            reused as argument to rng.choice(), removing
                            a second len() call.

  Perf 7  Fit-axes transform — batched 8 single-element _fwd/_inv
             calls into 2 two-element array calls, halving the number
             of Python→NumPy dispatch round-trips on every refresh when
             "Fit axes to data" is active.

  Perf 8  Cache eviction — all three caches (_tc, _gmc, _scatter_cache)
             now use itertools.islice instead of list(cache)[:n] to build
             the eviction list.  islice stops after n steps; the old pattern
             built a full copy of all keys then sliced it.  itertools is
             now imported at module level (was inline in three hot paths).

  Perf 9  self.T attribute caching — local T = self.T alias added in
             FlowApp.__init__, FlowTabManager.__init__, and _new_tab so
             the dict-theme is not re-fetched from the instance __dict__
             on every widget creation during startup.

  Perf 10 _label_centroid — removed double float() boxing around
             np.median() before passing it to np.array(); np.array
             accepts a scalar directly.
