# vFlow v4.3.0 — Cumulative Changelog, Bug Fixes, Refactor and Validation Notes

> **Comparison baseline:** vFlow v4.1.4  
> **Target release:** vFlow v4.3.0 (Refactor Integrity B6 release baseline)  
> **Intended use:** GitHub `CHANGELOG.md` / release notes and Zenodo software-version update documentation  
> **Release status:** **release-ready source baseline** — internal version metadata is synchronized to `4.3.0`; final GitHub/Zenodo publication will assign the release DOI.

---

## Release comparison

| Item | v4.1.4 baseline | v4.3.0 B6 release baseline |
|---|---|---|
| Distribution | Single Python script | Installable/package-based application |
| Baseline source | `vFlow_v4.1.4(1).py` | `vflow` package + launcher + tests |
| Baseline script size | 9,726 lines | Refactored across 89 production Python files, including compatibility/legacy modules |
| Test structure | Not used as the certification boundary for this comparison | 132 Python test files; **1,118 automated tests passing** in the release-ready tree (1,115 B6 baseline + 3 release-metadata checks) |
| Gate-session schema | Historical pre-context format | Schema v3 with analysis/transform provenance and Gating-ML Logicle parameters |
| Standard Logicle | No standards-reproducible Logicle mode | Added Gating-ML Logicle (`logicle_gml2`) with explicit `T/W/M/A` parameters |
| Validation checkpoint | v4.1.4 behavior | Scientific fingerprint, FCS reference, render hashes, gate-membership validators, generated real-GUI tests and state fuzzing |

### Reproducibility hashes used for this comparison

- Attached v4.1.4 source SHA-256: `95719165eb793c84833c1bd3edddff235a05355626cda92f506de94f86d9e053`
- Internal pre-release B6 checkpoint SHA-256: `7118a5e8ed8243a46367cf478d2f95c95cdb40fda643a6aaa95d1371dccff4b2` (retained as provenance; the final release-ready archive has a different hash because release metadata/documentation were added)

---

# What changed since v4.1.4

## 1. Scientific correctness and result integrity

A major part of the work after v4.1.4 was not feature expansion, but preventing **plausible-looking yet scientifically incorrect output**.

### Gate populations and denominators

- Gate masks now consistently operate on the **finite, transform-displayable event universe** for the active X/Y transforms.
- Shape-gate OUT populations can no longer absorb NaN, Inf, or transform-invalid events while statistics use a smaller denominator.
- Interactive statistics, Batch Stats, Batch Plot gated percentages, ancestor/sub-gate replay, and exported provenance now use the same validated analysis universe.
- Batch region partitions must be both **non-overlapping and exhaustive** over the transform-valid population; overlapping or incomplete partitions fail closed instead of changing the denominator silently.
- Zero-transform-valid-event samples are retained in results with explicit `Total=0` and transform-exclusion provenance rather than disappearing from the analysis.
- Main statistics, sub-gating, auto-gating, Batch Plot and Batch Stats no longer proceed on only the compatible subset of active files when the current X/Y context is invalid for another active file.

### Gate context and provenance

- Gates are stored with explicit analysis provenance rather than being treated as context-free geometry.
- Gate-session schema progressed to **v3** and now records the relevant analysis context, lineage and transform parameters.
- Malformed saved gates are rejected instead of being partially sanitized into different future geometry.
- Textual JSON booleans such as `"false"` can no longer become truthy Python values and silently invert gate/threshold state.
- Duplicate gate names are disambiguated by immutable gate ID in downstream statistics and exports.
- Gated-data exports now include stronger gate identity and source provenance.

### Axis swapping and gate preservation

- A true X/Y swap (`A/B -> B/A`) is now distinguished from a genuine channel replacement.
- Rectangle, ellipse, polygon and crosshair gate geometry is transposed transactionally during a true axis swap.
- Scale/transform parameters and locked limits move with their biological channel.
- Gate population membership is preserved across the swap, including nonlinear contexts.
- Loading a saved A/B session while viewing B/A now uses the same axis-transposition semantics.
- A genuine channel replacement remains incompatible and does not silently reinterpret the gate.

### Current scale-change gate behavior

After the post-refactor regression audit, gate applicability is based on the **ordered measurement channels** rather than the exact current display-scale identity. On the same X/Y channels, changing scale/cofactor/Logicle parameters causes the gate to be rebound/recomputed in the current transform rather than disappearing. Selecting genuinely different channels makes the gate inactive; returning to the original channels restores/recomputes it.

This behavior was added specifically to prevent valid gates from vanishing merely because the display transform was changed during analysis.

---

## 2. Standards-compatible Logicle and transform provenance

### Added Gating-ML Logicle

vFlow now provides an equation-based, standards-reproducible Gating-ML Logicle transform under the canonical identity:

- `logicle_gml2`

with explicit per-axis parameters:

- `T` — top of scale
- `W` — width of the approximately linear region
- `M` — positive logarithmic decades
- `A` — additional negative range

The transform is threaded through:

- numerical forward/inverse transforms;
- Matplotlib axis transforms;
- gate evaluation;
- rendering and KDE payloads;
- auto-gating;
- lineage replay;
- cache identities;
- gate-session persistence.

Independent numerical validation performed **480/480** randomized root comparisons against a separate bracketed solution path.

### Historical transform behavior preserved explicitly

The historical vFlow transforms were **not** silently redefined:

- historical `logicle` is represented as `legacy_logicle`;
- historical `biexp` is represented as `legacy_biexp`.

Their formulas remain the legacy vFlow signed-log approximations for backward compatibility. They are not presented as exact FlowJo Biex or standards Gating-ML Logicle.

### Gate-session migration

- v1 compatibility remains available with conservative binding/warnings.
- v2 historical `logicle` / `biexp` identities migrate to explicit `legacy_*` names without numerically moving gate coordinates.
- v3 sessions can persist `logicle_gml2` with explicit per-axis `T/W/M/A` parameters.
- A standard-Logicle context missing required parameters is rejected rather than assigned hidden defaults.

---

## 3. Polar/vector analysis corrections

- Rayleigh p-values were corrected to the stated Zar/CircStat approximation.
- X/Y centroid auto-detection now pairs coordinates by shared channel identity rather than list position, preventing cross-wired vectors.
- If X/Y identities cannot be matched safely, auto-detection now refuses to guess and requires explicit mapping.
- Non-finite coordinate pairs are removed before circular statistics.
- Zero-length displacement vectors are excluded because their direction is undefined.
- Numerically antipodal/symmetric vectors now return an undefined/blank mean direction instead of a floating-point artifact such as 90°.
- Mean-resultant-length thresholds must be finite and within `[0,1]`.
- Polar statistics export now preserves source-path provenance.
- A visible Y-coordinate orientation choice was added:
  - `cartesian_y_up`
  - `image_y_down`
- The exported angle convention is explicit: **0° = +X; positive direction = counter-clockwise after Y-orientation normalization**.
- Switching Y orientation reflects direction as expected without changing displacement magnitude, MRL, or Rayleigh significance strength.

---

## 4. FCS reader and import hardening

The FCS path was substantially hardened relative to v4.1.4.

### Parsing and numeric integrity

- Escaped TEXT delimiters are supported and validated.
- Required metadata, byte order, offsets and truncation are checked explicitly.
- Mixed integer widths and tightly packed non-byte-aligned integer fields are supported under strict validation.
- Integer measurements are decoded using the significant bit range and validated against `$PnR` without silently converting malformed values into other measurements.
- Float precision/range cases that cannot be represented safely fail rather than silently losing integer meaning.
- Supplemental FCS TEXT metadata is parsed and validated instead of being ignored.
- Duplicate keywords within or across TEXT segments are rejected rather than allowing silent overwrite.
- TIME metadata and gain/log-scale metadata receive stricter interpretation checks.
- Duplicate/case-colliding FCS channel labels are disambiguated safely within a file.
- Automatically disambiguated duplicate stain labels are not assumed to represent the same detector across files without explicit nomenclature mapping.

### FlowJo TextToFCS v1.3 compatibility

Compatibility was added for documented exporter quirks while keeping payload-length checks strict:

- whitespace padding after the final TEXT delimiter;
- the one-past-EOF DATA-end convention when it exactly equals file length;
- missing `$PnE` inferred as linear `0,0` only when `$PnD` explicitly declares `Linear`.

These compatibility normalizations are recorded as metadata/status information; DATA values are not altered by the repair logic.

### Compensation metadata

- vFlow detects modern and historical compensation/spillover-related FCS metadata.
- Current behavior is intentionally neutral: **compensation state requires verification**.
- vFlow does **not** automatically apply, reverse, or infer a compensation matrix/state from that metadata.

---

## 5. CSV, channel identity and multi-file safety

- Raw CSV headers are checked before pandas normalization so exact/case-only duplicate measurement names cannot be silently renamed into different channel identities.
- An unnamed first column is removed only when its values prove it is a generated row-number index; legitimate unnamed measurements are retained.
- Preserved unnamed measurement columns are not automatically assumed to represent the same biological channel across files.
- Multi-file axis menus are built only from safe/common channel identities for the active files.
- If no safe common channel exists, the axes are cleared instead of falling back to the first file and analyzing only a subset.
- Automatic fallback avoids collapsing X and Y onto the same channel when two safe channels exist.
- An explicitly user-selected same-channel X/Y plot remains allowed.
- Session-scoped channel nomenclature resolution was added to resolve cross-file naming differences safely.
- Nomenclature inheritance is propagated into sub-gating and Batch Stats workflows.

---

## 6. Concatenation, sample identity and provenance

- Concatenated exports now preserve collision-safe `Source_File` plus full `Source_Path` provenance.
- Nested concatenation is rejected where provenance would become ambiguous.
- Duplicate physical input aliases are rejected so the same acquisition cannot be silently counted twice through symlink/path aliases.
- Concatenated-file detection prefers `Source_Path` provenance when available.
- Batch analysis distinguishes same-named source files from different containers/directories.
- Duplicate basenames in recursive batch output are disambiguated using relative paths.
- Previous batch-output CSVs and concatenated files are identified explicitly so they are not re-counted as ordinary raw samples.
- Heterogeneous concatenation remains supported, but channels that are structurally absent from one or more constituent source files are hidden from pooled axis selection rather than silently analyzing only the rows that contain them.

---

## 7. Gating and gate-interaction fixes

### Manual gates

- Polygon interior hit-testing is performed consistently with nonlinear display geometry.
- Exact polygon edge/vertex membership is deterministic and independent of winding direction.
- Transform-invalid polygon vertices now invalidate the applied gate instead of being dropped and reconnecting the surviving vertices into a different polygon.
- Nonlinear ellipse previews now trace the same raw-data ellipse equation used for membership/statistics, preventing visible-boundary/statistics disagreement.
- Empty/aborted rectangle and ellipse gates are not rendered as stray single-point artifacts.
- Loaded gate corner/vertex resizing remains Tk-safe.
- Gate IDs and relevant caches reset cleanly after clearing all gates.
- Frozen draw/move axis snapshots are released after interaction completion.
- Targeted cache invalidation replaces unnecessarily broad scatter-cache clearing during geometry manipulation.

### Gate export/assignment behavior

- Shape gates take priority over crosshair partitions during gated-data assignment so a crosshair cannot absorb every cell before specific polygon/rectangle/ellipse populations are considered.
- Y thresholds exactly equal to `0.0` are exported correctly rather than being treated as empty/false.
- Threshold checkbox state is persisted correctly into the gate model.
- Duplicate gate names are disambiguated by gate ID in downstream selectors/exports.

### Auto-gating

- KDE/Derivative auto-gating rejects unsupported/unimodal valley cases rather than presenting a tail percentile as a detected separator.
- Otsu calculations avoid divide-by-zero warning paths.
- GMM Multi emits a threshold only when adjacent weighted Gaussian components have a genuine supported equal-density crossing between their means.
- HDBSCAN/cluster polygon gates compute hulls in the transformed clustering space rather than mixing transform-space clustering with raw-space hull geometry.
- Degenerate/unrepresentable fitted clusters are skipped instead of being replaced by fabricated bounding rectangles.
- HDBSCAN-created gates are labelled with the correct method identity.
- All auto-gate families now fail closed on empty/degenerate data or invalid multi-file analysis context rather than constructing plausible fallback gates from partial/invalid input.

---

## 8. Rendering, scale and display fixes

- Density/Contour rendering now falls back deterministically to Dot mode for constant/degenerate data instead of crashing inside `RegularGridInterpolator`.
- KDE failures from singular/collinear data are handled rather than leaving the UI unusable.
- Scale transitions were hardened so stale Matplotlib log state cannot leak into asinh/Logicle/etc. and reverse axis limits.
- Retained-axis rendering is used only when live and target scale identities are compatible.
- Existing axes are normalized before destructive layout rebuilds to avoid log/shared-axis teardown problems.
- Invalid/no-common-channel contexts actively clear the previous biological plot instead of leaving stale data visible.
- `Clear All` now removes stale scatter/title content and displays an explicit no-data state.
- Channel selector values are cleared with the data model.
- Locked X/Y limits are cleared when all files are cleared, preventing old limits from making a newly loaded, numerically distant dataset appear blank.
- Marginals, log→asinh transitions and mixed nonlinear scales were regression-tested for ordered limits.

---

## 9. Batch statistics, exports and secondary analysis

- Batch column-case normalization now follows the same normalization as interactive analysis.
- Batch Stats family exclusion is limited to explicit SynaptosomesMacro CytoFile naming families rather than generic underscore-prefix similarity that could remove biologically different samples.
- Batch and secondary analyses fail closed if the requested gate or required channel context cannot be evaluated for the full requested active file set.
- Batch region masks must form one complete, non-overlapping partition of the transform-valid population.
- Batch output now distinguishes:
  - `Source_Total_Cells`
  - `Input_Total_Cells`
  - `Total_Cells` (transform-valid analysis denominator)
  - `Transform_Excluded_Cells`
- Single-gate export includes stronger analysis provenance: gate identity/type, geometry/threshold information, scale/cofactor/transform parameters, input/valid/excluded counts and compensation-verification metadata.
- Batch wide exports disambiguate duplicate gate names by gate ID.
- Output naming collisions are detected instead of silently overwriting distinct populations.
- Batch Plot counting error bars are explicitly treated as within-sample binomial counting SE, not biological replicate SEM.
- Gated Batch Plot/Polar comparisons stop rather than silently omitting a file and presenting an apparently complete comparison.

---

## 10. Reliability and lifecycle fixes

- Installed/source launch paths now use the same packaged application implementation.
- Polar and Batch Plot windows own and cancel delayed Tk callbacks on close.
- Sub-gate tabs cancel pending callbacks and now **destroy** forgotten notebook child widgets rather than merely hiding them, eliminating repeated-tab Tk/Matplotlib resource leaks.
- Live Tk variables are converted to plain gate/provenance data before crossing into `AnalysisState`, preventing `deepcopy()`/pickle failures.
- File-row registration is atomic: the data model is committed only after the corresponding UI row succeeds.
- Gate-session save filesystem errors are reported cleanly instead of escaping the UI callback.
- Tk-variable default-construction patterns that leaked Tcl variables on repeated calls were removed from hot paths.
- Clear/reload state is reset consistently across model, selectors, render state and locked limits.

---

## 11. Performance and memory improvements

v4.1.4 already included blitting for gate drawing/dragging. Subsequent releases extend performance work into rendering, gating, caching and multi-file analysis:

- Density/Contour rendering and cold KDE computation are cached and optimized.
- Cold multi-file KDE work can be precomputed with bounded worker concurrency while Tk/Matplotlib commits remain deterministic on the main thread.
- Marginal rendering and hover geometry were profiled and reduced.
- Gate-mask evaluation and repeated transform calculations use stronger cache keys and targeted invalidation.
- Gate masks use compact/packed storage where appropriate.
- Scatter/render payloads are stored more compactly.
- Cache retention moved from simple fixed-entry behavior to bounded byte-budget policies, reducing churn in large many-file sessions without allowing unbounded memory growth.
- Handle-pixel caches and gate-preview work are rebuilt only when needed.
- Dragging invalidates only cache entries that depend on the changed gate rather than clearing all file scatter caches at every motion frame.

---

# Architectural refactor

## From monolithic script to package architecture

The v4.1.4 baseline is a single 9,726-line Python application script. The target B6 codebase is an installable package organized into explicit responsibility boundaries.

### Core scientific/data layer — `vflow/core`

Contains package-owned implementations for:

- FCS reading and data I/O;
- transformations/scales and Gating-ML Logicle;
- gate definitions, masks and serialization;
- gate statistics;
- auto-gating;
- circular statistics;
- threshold state;
- path/sample/column identity helpers;
- cache-key construction.

### Application state — `vflow/app`

Separates:

- analysis/session state;
- dataset state;
- lineage/provenance;
- cache ownership.

### Scientific/workflow services — `vflow/services`

Extracted services cover:

- active-file and axis planning;
- channel selection;
- population/gate evaluation;
- gate lifecycle and threshold planning;
- transactional gate assignment;
- axis-swap planning;
- sub-gate population reconstruction;
- gated-data export;
- Batch Stats and Batch Plot result/export construction;
- concatenation and source-path planning;
- gate-session handling;
- polar result generation;
- file-load planning and figure export.

### Controllers — `vflow/controllers`

- `GateInteractionController` owns concrete gate interaction, preview, hit-testing, drag and handle behavior.
- `ProjectDataLoadCoordinator` owns data admission/loading, gate-session load/save orchestration and excluded-file persistence.

### Rendering — `vflow/rendering` and `vflow/plotting`

- `RenderPlan` provides a stable structural render snapshot.
- `FlowRenderer` owns deterministic full-render lifecycle and Dot/Density/Contour/Gated drawing.
- Plotting helpers isolate KDE payloads, render lifecycle and shared utilities.

### UI — `vflow/ui`

UI responsibilities are split into dedicated modules for:

- application shell;
- gate manager;
- file list;
- tab manager;
- Batch Plot/Batch Stats windows;
- Polar Analysis;
- folder scanning;
- axis nomenclature/resolution;
- interaction presentation.

### Nomenclature and platform helpers

Dedicated modules now own:

- session/channel nomenclature mapping;
- platform file-reveal behavior.

### Compatibility surface

The historical `FlowApp`/legacy facade remains as a compatibility surface where needed, but major scientific, rendering, controller and workflow implementations have moved to package-owned modules. The refactor deliberately preserved observable callback ordering and monkeypatch/failure boundaries used by the characterization tests.

---

# v4.3 scientific/accuracy hardening ledger

The v4.3 development cycle added a second layer of adversarial accuracy review on top of the v4.2 refactor.

## Accuracy A1

1. Restrict Batch Stats family exclusion to explicit CytoFile families.
2. Require genuine weighted-Gaussian crossings for GMM Multi thresholds.
3. Skip degenerate cluster hulls instead of fabricating bounding rectangles.
4. Correct Rayleigh p-value calculation to the stated Zar/CircStat method.
5. Pair polar X/Y centroid columns by channel identity.
6. Make polygon boundary membership deterministic and orientation-independent.
7. Reject transform-invalid polygon vertices rather than reconnecting survivors.
8. Make nonlinear ellipse preview agree with membership geometry.
9. Reject ambiguous duplicate raw CSV headers before pandas renaming.
10. Protect integer FCS measurement values from silent bit-mask corruption.
11. Parse/validate supplemental FCS TEXT and reject duplicate metadata keys.
12. Parse serialized booleans strictly.
13. Reject malformed applied saved-gate geometry instead of sanitizing it.
14. Disambiguate duplicate shape-gate names and reject invalid shape partitions.
15. Reject overlapping Batch Stats region masks.
16. Prevent export-column normalization from overwriting distinct populations.

## Science Method A2

- Added standards Gating-ML Logicle with explicit `T/W/M/A` provenance.
- Preserved historical transforms as explicit `legacy_logicle` / `legacy_biexp`.
- Upgraded gate-session schema to v3.
- Added explicit polar Y-coordinate orientation.

## Gate Axis Preservation A3

- Added transactional gate/context transposition for true X↔Y channel swaps.
- Preserved gate membership across rectangle, ellipse, polygon and crosshair swaps.
- Moved scale parameters and locked limits with the associated biological channel.

## Accuracy A4

1. Broadened compensation metadata detection while avoiding unsupported claims about compensation state.
2. Corrected FCS integer handling for unused high bits.
3. Rejected malformed inactive saved gates rather than creating different future gates.
4. Applied A3 axis-swap semantics when loading reversed-axis gate sessions.
5. Removed plausible circular mean angles when mean direction is mathematically undefined.
6. Retained zero-valid-event samples with explicit provenance.
7. Expanded single-gate export provenance.
8. Aligned KDE/Otsu status percentages with the actual transform-valid gate universe and boundary rule.
9. Removed first-file fallback when active files have no safe common channel.
10. Prevented duplicate FCS stain-label suffixes from being treated as cross-file biological identity.
11. Prevented synthetic unnamed CSV labels from being treated as cross-file biological identity.
12. Hid structurally partial concatenated channels from pooled axis selection.
13. Prevented forced fallback from collapsing X and Y onto one channel.
14. Required Batch Stats partitions to be exhaustive as well as disjoint.
15. Added explicit source/input/transform-valid/excluded denominator provenance.
16. Prevented sub-gating from constructing a child population from only a compatible active-file subset.
17. Prevented main statistics from aggregating only a compatible subset.
18. Cleared stale rendered biology when the active analysis context becomes invalid.
19. Prevented auto-gating on only a compatible subset under stale state.
20. Removed remaining unsafe polar centroid pairing guesses.

---

# Post-refactor regression hardening

## A5 — runtime regression repair

- Restored gate preview rendering after the decomposed controller missed the `handle_cache_entries` dependency.
- Fixed axis reversal during display-scale transitions caused by stale Matplotlib log state.
- Reworked runtime gate applicability so same-channel scale/cofactor changes recompute/rebind gates instead of hiding them.
- Repaired Derivative/KDE and Otsu auto-gates that still called the removed `_axis_transform_params()` API.
- Added real-GUI generated-data regression tests across all 36 X/Y scale combinations and manual/auto gate interactions.

## B6 — broader refactor integrity audit

- `Clear All` now clears stale plot artists/title.
- `Clear All` now clears visible channel selectors.
- `Clear All` now resets locked axis state/limits before a new dataset.
- Closed sub-gate tabs destroy their child widgets and canvases.
- Tk-backed live gates are converted to plain provenance at the analysis-state boundary.
- Layout teardown is protected against stale log/shared-axis state.
- Gate-session filesystem write failures are handled by the UI.
- Constant/degenerate Density and Contour data use deterministic Dot fallback instead of crashing.
- Refactor debris such as a duplicate decorator was removed.
- Added permanent edge-dataset, refactor-wiring, Clear/reload, repeated-tab and randomized GUI-state validators.

---

# Validation and certification evidence for the B6 checkpoint

The B6 checkpoint passed the following cumulative validation:

- **1,115 / 1,115 automated tests passed**.
- Python `compileall`: PASS.
- Live refactor-wiring audit:
  - UI shell/file list/gate manager: **134 references, 0 missing**
  - `GateInteractionController` host boundary: **56 references, 0 missing**
  - `FlowRenderer` host boundary: **50 references, 0 missing**
- All **36 X/Y scale combinations** passed generated real-GUI validation across:
  - linear
  - log
  - asinh
  - Gating-ML Logicle
  - legacy biexp
  - legacy logicle
- Manual rectangle, ellipse, crosshair and polygon creation: PASS.
- Gate handle resizing and whole-gate movement: PASS.
- Scale-change gate rebinding: PASS.
- Different-channel hide + return restore: PASS.
- Marginal log→asinh ordered-limit behavior: PASS.
- Two-file overlay/cycle: PASS.
- Gate-session reload on the current scale: PASS.
- Derivative/KDE, Otsu, GMM Multi and HDBSCAN auto-gates: PASS.
- Constant Density inputs across all six scale families: PASS.
- NaN / +Inf / -Inf data across all six scale families: PASS.
- Zero-row and single-column files fail closed safely.
- Mismatched multi-file channel sets fail closed safely.
- Eight repeated sub-gate open/close cycles verified child-widget destruction.
- Deterministic real-GUI state fuzz: **80 operations, 0 failures, 0 asynchronous callback errors, 0 messagebox errors**.
- Gating-ML Logicle independent root comparisons: **480**.
- Gate X/Y swap membership-preservation comparisons: **480**.
- A4 valid batch partition checks: **300**.
- A4 deliberately invalid partition rejections: **600**.
- A4 multi-file/channel-integrity scenarios: **303**.
- FlowJo/TextToFCS reference:
  - shape: **1473 × 8**
  - all finite: true
  - maximum direct DATA difference: **0.0**
- Frozen scientific fingerprint: byte-identical to the certified reference.
- Frozen Dot/Density/Contour/Gate-preview render hashes: unchanged on the reference rendering dataset.

These checks provide strong regression evidence for the audited paths. They should not be interpreted as a mathematical guarantee that no defect can exist for every possible file, operating system, Tk version, Matplotlib version or experimental workflow.

---

# Compatibility and migration notes

## Saved gates

- Historical gate files remain supported only where their provenance can be interpreted safely.
- Unknown gate-schema versions fail closed.
- Legacy v1 files do not contain complete transform provenance and therefore require conservative handling/warnings.
- v2 legacy transform identities are normalized to explicit `legacy_*` identities without changing numeric gate geometry.
- v3 stores full standard-Logicle parameters where required.
- Malformed applied/inactive gate geometry is rejected instead of silently repaired into a different gate.

## Transform compatibility

- `legacy_logicle` and `legacy_biexp` preserve historical vFlow behavior.
- `logicle_gml2` is the standards-reproducible Logicle path.
- vFlow does not claim exact FlowJo Biex equivalence.
- Historical gates are not automatically numerically converted to standard Logicle coordinates.

## Compensation

- Compensation-related FCS metadata is detected and reported.
- vFlow does not currently apply or infer compensation automatically.
- Compensation state should therefore be verified upstream/in the acquisition/export workflow before quantitative interpretation.

## Python/runtime

- Package metadata requires Python **>= 3.10**.
- `scikit-learn >= 1.3` remains an optional advanced dependency for GMM Multi / clustering functionality.

---

# Known limitations / deliberately unchanged behavior

The following are explicit boundaries rather than hidden fixes:

1. vFlow does not automatically compensate FCS fluorescence data.
2. `legacy_biexp` and `legacy_logicle` remain historical signed-log approximations.
3. `logicle_gml2` is standards Logicle, not a claim of exact FlowJo Biex display parity.
4. Logicle `T/W/M/A` parameters are explicit; they are not silently inferred from FCS metadata.
5. Ambiguous multi-file channel identity is resolved conservatively: vFlow refuses automatic matching rather than guessing.
6. Transform-valid events remain the intended analysis denominator; the newer exports make source/input/excluded counts explicit rather than changing that denominator definition.

---

# Suggested concise GitHub / Zenodo release description

**vFlow v4.3.0** is a major scientific-correctness, architecture and robustness update relative to v4.1.4. The application has been refactored from a single monolithic script into an installable package with explicit scientific, state, rendering, controller and workflow boundaries. The release hardens FCS/CSV parsing, gate provenance, transform-valid denominators, multi-file channel identity, Batch Stats/Batch Plot behavior, sub-gating, polar statistics and gated-data export. It adds standards-reproducible Gating-ML Logicle with explicit `T/W/M/A` parameters while preserving historical vFlow transforms as legacy compatibility modes. True X/Y axis swaps now transpose gates while preserving population membership. Post-refactor audits also repaired gate-preview wiring, scale-transition axis reversal, auto-gate API regressions, stale Clear/reload state, sub-tab resource leaks and degenerate Density/Contour crashes. The release-ready tree passes **1,118 automated tests** (the 1,115-test B6 application baseline plus three release-metadata checks), with the B6 scientific/GUI validation evidence retained and key validators rerun after the version finalization.

---

# Suggested Zenodo metadata

The repository metadata in this release-ready source is aligned with the existing vFlow Zenodo/GitHub record. A version-specific DOI will be assigned only when the v4.3.0 version is published.

| Zenodo field | Suggested value |
|---|---|
| Upload/resource type | Software |
| Title | `vFlow: Visual Flow Cytometry & Immunofluorescence Analysis Tool` |
| Creator | Vincent Paget-Blanc |
| Version | `4.3.0` |
| Publication date | Release date |
| Language | English (`eng`) |
| License | `GPL-3.0-only` (matching the included GNU GPL v3 license text as packaged) |
| Keywords | flow cytometry; immunofluorescence; gating; FCS; single-particle analysis; synaptosomes; quantitative microscopy; Logicle; Gating-ML; batch statistics; Python |
| Repository | `https://github.com/VincentPaget-Blanc/vFlow` |
| Description | Use the concise release description above followed by a link/reference to this changelog |
| Version DOI | `TBD after v4.3.0 publication` |
| Version chain | Existing vFlow Zenodo record; publish v4.3.0 using **New version** so Zenodo links it to prior releases |

## Zenodo DOI usage

For reproducibility, cite the **version-specific DOI** when referring to analyses performed with this exact release. Use the **concept DOI** when referring to vFlow as a software project across all versions.

---

# Zenodo + GitHub release checklist

Before publishing the release:

- [x] Final release number set to `4.3.0`.
- [x] `pyproject.toml` version set to `4.3.0`.
- [x] `vflow.__version__` set to `4.3.0`.
- [x] Launcher/application `APP_VERSION` set to `4.3.0`.
- [x] Release-version tests updated to assert `4.3.0`.
- [ ] Run the complete automated suite and B6 GUI/scientific validators after the version-only change.
- [ ] Ensure the Git tag exactly matches the intended release version (for example `v4.3.0`).
- [ ] Ensure the GitHub Release title and Zenodo version use the same version.
- [x] Cumulative release history added as repository `CHANGELOG.md`.
- [x] Added both `CITATION.cff` and `.zenodo.json`; GitHub can use the former and Zenodo will prefer the latter.
- [x] `.zenodo.json` is present and intentionally authoritative for Zenodo GitHub archiving.
- [x] Creator name aligned to the existing Zenodo record: Vincent Paget-Blanc. No ORCID/affiliation was invented where none was verified.
- [x] Release metadata uses `GPL-3.0-only`, matching the packaged GNU GPL v3 license text.
- [x] GitHub repository is recorded in `CITATION.cff` and `pyproject.toml`; Zenodo GitHub integration will also retain repository context.
- [ ] Add funding/grant/community metadata if applicable.
- [ ] Create the GitHub release only after metadata files are valid.
- [ ] Confirm the new Zenodo record is a **new version of the existing vFlow record**, not an unrelated new software record, if v4.1.4 already belongs to an existing Zenodo version chain.
- [ ] After Zenodo publishes the release, record both the version DOI and concept DOI in the repository documentation/CITATION metadata where appropriate.
- [ ] Prefer the version DOI in papers/protocols that depend on this exact software behavior.

---

# Repository metadata recommendation

Zenodo's current GitHub integration supports both `CITATION.cff` and `.zenodo.json` for software metadata.

- Use **`CITATION.cff`** if standard citation metadata is sufficient.
- Use **`.zenodo.json`** when Zenodo-specific fields are needed, such as grants, communities, access settings, related identifiers or Zenodo contributor roles.
- If both files exist, Zenodo uses **`.zenodo.json`** for the GitHub release and ignores `CITATION.cff` during that archive operation.

This v4.3.0 release-ready package contains **both** files. GitHub uses `CITATION.cff` for its citation UI; Zenodo uses `.zenodo.json` when both are present.

Official Zenodo documentation consulted for this release note:

- Zenodo — Describe software: https://help.zenodo.org/docs/github/describe-software/
- Zenodo — `.zenodo.json`: https://help.zenodo.org/docs/github/describe-software/zenodo-json/
- Zenodo — Archive a GitHub software release: https://help.zenodo.org/docs/github/archive-software/github-upload/
- Zenodo — Manage versions: https://help.zenodo.org/docs/deposit/manage-versions/
- Zenodo — DOI versioning FAQ: https://support.zenodo.org/help/en-gb/1-upload-deposit/97-what-is-doi-versioning

---

# Maintainer provenance for this cumulative changelog

This document was assembled by comparing:

1. vFlow v4.1.4;
2. the historical changelog embedded in the current package for v4.1.4 → v4.2.0;
3. the v4.3 controller-decomposition audit;
4. v4.3 Accuracy A1;
5. v4.3 Science Method A2;
6. v4.3 Gate Axis Preservation A3;
7. v4.3 Accuracy A4;
8. v4.3 Regression Hardening A5; and
9. v4.3 Refactor Integrity B6.

The purpose is to provide a cumulative public-facing account of **what changed relative to v4.1.4**, while retaining enough technical detail for reproducibility, GitHub history and Zenodo software-release documentation.
