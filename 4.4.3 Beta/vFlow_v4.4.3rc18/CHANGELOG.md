# vFlow 4.4.3rc18

- Compact gate list with one selected-gate editor for Rename, Delete, line style, width and thresholds. Keep transfer/application and editor navigation in gate Actions and right-click menus. Put Delete all gates in a list menu.
- Consolidate workspace commands into Open/Save plus a Workspace actions menu. Keep File menu and keyboard shortcuts. Consolidate interface preferences in Settings.
- Use one visible sample list, state-dependent Exclude/Restore and Cycle-only navigation buttons. Reject ambiguous multi-row sample actions. Preserve exclusion-list import/export and every source action.
- Remove repeated sample-action and gate-tool headers, reduce secondary button colours, and initially collapse advanced transform, gate-session and exclusion-list controls. Restore saved preferences.
- Preserve scientific algorithms, benchmark acquisitions, all RC17 interaction fixes and RC16 integrity/recovery.

# vFlow 4.4.3rc17

- Make sample-row selection additive: click again to deselect, with Space/Enter toggling the focused row. Keep Active checkboxes independent of row highlights. Rapid double/triple clicks no longer invoke Show sample or change Overlay/Cycle mode; use the explicit button/menu or mode selector.
- Preserve the displayed Cycle sample when other samples are activated, excluded or restored, and keep saved Overlay axes through an empty Cycle population.
- Give Matplotlib Pan/Zoom exclusive pointer ownership, reject middle-button gate drawing, and restrict population-opening double-clicks to the left button.
- Keep workspace shortcuts out of descendant dialogs and leave editable-field undo to text controls. Consume sample context-menu gestures, ignore headings/empty areas, disable unavailable actions, and clean up population-tab context menus (including macOS Control-click).
- Dismiss tooltips before custom click/key handlers, prevent mouse-focus help from reopening over action buttons, and release tooltip binding callbacks when widgets are destroyed.
- Reject nonfinite/out-of-range gate widths during typing and restore the previous valid value on Return/focus loss. Preserve independent Batch Plot sample choices across file-list rebuilds.
- Retain workspace-integrity/recovery behavior and all supplied benchmark bytes. See UI_INTERACTION_REVIEW_v4.4.3rc17.md for validation, coverage and platform limits.

# vFlow 4.4.3rc16

- Guard workspace commits with a saved byte revision, nonblocking concurrent-writer locking and a second revision check immediately before replacement. Refuse external edits, deletion and retargeted aliases while retaining live edits for Save As. Keep stable lock files and let the operating system release ownership on exit.
- Save per-instance recovery checkpoints with unsaved gate geometry, per-sample overrides, exclusions, activation and audit decisions. Preserve the last complete checkpoint and its gate revision through failed checkpoint writes; restore recovered work as dirty. Search older valid recovery files when a newer file is corrupt, and retain the original saved revision guard after recovery.
- Use full SHA-256 source, gate and audit identities for new references, preserve historical sampled fingerprints, and pin full bytes when accepting legacy references. Preserve relative-only missing locators through Save As and verify physical paths when relocating or saving through aliases.
- Keep acquisition identities captured at ingestion. Check source bytes before and after decoding. When an owned derivative CSV redirects to an original LMD, apply the outer integrity check and identity attributes only to samples sourced from that CSV; the recursively loaded original is checked independently and may legitimately regenerate the CSV. Add the derivative-refresh regression, including a mutation during recursive original decoding.
- Explain that statistical scores and exports retain the saved data/gate snapshot while Current state follows present inclusion. Preserve true numeric zeros, show unavailable comparisons explicitly, refresh inclusion while the results dialog stays open, and scale the results dialog to font metrics and screen bounds.
- Retain all earlier functionality, source launch behavior, scientific settings and benchmark bytes. Preserve all RC15 changelog history below. Final acceptance details and limits are recorded in RELEASE_VALIDATION_v4.4.3rc16.md.
- Validate 1,663 ordinary full-suite tests, 34 focused regressions, 61 ingestion tests, 13 integrity checks, four compound scenarios, 88 scientific benchmark checks, 36 app workflows, 15 native phases, four persistence phases and two actual cached-RC5 Spyder launches. Complete 1206.004 seconds of final-source endurance and matched RC15/RC16 timings with identical numerical outputs. Preserve all 57 original benchmark extension files and exact wheel/source/README identity. See RELEASE_VALIDATION_v4.4.3rc16.md for timing and platform limits.

# vFlow 4.4.3rc15

- Refresh the wheel's embedded README to match the RC15 source documentation, and gate packaging on exact README as well as Python-source identity. Complete the interrupted delivery without changing the tested application code or prior changelog history.
- Finalize unreachable retired Tk interpreters on the GUI thread before parallel KDE, Statistical Audit and missing-file scan workers. Preserve queue-only GUI publication, cancellation, numerical payloads and worker ordering; do not disable garbage collection globally or modify Tk internals.
- Keep independent unloaded exclusions for multiple members of the same acquisition container, mapped to their recorded sample IDs. Preserve original container/member references through repeated capture/save/reopen, removal of either unavailable member, successful locate/retry and restore. Cover both missing-source and decoder-failure states without changing raw acquisitions.
- Recheck document identity/disposal after the Save As destination chooser. Ignore stale chooser responses after Clear or same-UUID reopen, and recapture name, activation and gate edits made while the chooser is open before staging the saved document.
- Add 12 regression cases; verify 7 workspace failures against all 122 byte-identical delivered RC14 package sources. Run 33 isolated crash/control comparisons: RC13/RC14 fail all 18 forced worker-collection cases with Tcl wrong-thread cleanup; RC15 passes all 9 corresponding cases, with main-thread finalizers. The observed fatal signal is SIGILL/-4; the earlier SIGSEGV/139 remains unproved.
- Validate 1,629 ordinary full-suite tests with faulthandler and no NativeCleanup plugin, 46 focused cases, all 88 scientific benchmark checks, 39 frozen hashes, 36 real app workflows/48,000 events, four fresh-process persistence phases and two RC5-cached Spyder launches. Exercise 40 workspace switches, 20 actual benchmark audit preparations/cancellations, moved workspace trees, Save As revision preservation and before/after final-replace process interruption. Include a safe native/Spyder diagnostic runner that excludes intentionally fatal controls.
- Preserve every original module and legacy class method, the source launcher, all scientific settings, 19 core modules and 11 statistics modules apart from release metadata. Density/contour numerical bodies and KDE scheduling remain unchanged apart from collection preflight; analysis stays audit-4 / review-3. Current acceptance is Linux/Python 3.12.14/Tk 9.0.4/Xvfb with the actual Spyder runner. Fresh Tk 8.6 and native Windows/macOS checks remain outstanding. See BUG_HUNT_REPORT_v4.4.3rc15.md for controlled-crash evidence, stress duration and limits.

# vFlow 4.4.3rc14

- Retain visible excluded-file placeholders when a recorded source exists but decoding fails. Retry unloaded exclusions during relocation/reload, including when a formerly missing file is found at its original path. Preserve sample IDs and successfully decoded events across restore/save/reopen; acquisition identity checks remain unchanged.
- Keep failed multi-member container exclusions anchored to their authoritative source, rather than registering a temporary CSV derivative as another acquisition. Repeated workspace capture preserves recorded sample/member identities; a later successful decode restores the recorded member.
- Remove Tk dialog references from statistical prepare/run worker closures. Deliver prepared populations through the queue and publish dialog state on the main thread. Direct parent destruction now cancels the audit and scheduled callbacks, with idempotent close/destroy behavior.
- Recheck audit identity after modal Rename responses, and ignore biological-replicate edit responses after dialog closure or workspace change. Stale dialogs no longer rename detached audit references or dirty the newly opened workspace.
- Add 14 native edge-case regressions; verify 11 failures against the delivered RC13 package. Validate 1,617 full-suite tests, 64 focused native tests, all 88 scientific benchmark checks, 39 unchanged corpus files, 36 benchmark app workflows, four fresh-process persistence phases and two RC5-cached Spyder launches. The current full suite runs through ordinary pytest with faulthandler, without the earlier custom garbage-collection plugin.
- Preserve all settings/functionality, the source launcher, all legacy class methods, 19 core modules and 11 statistics modules (apart from release metadata). Analysis stays audit-4 / review-3. Linux/Python 3.12/Tk 9.0.4 native testing passed; fresh Tk 8.6 and native Windows/macOS checks remain outstanding. Earlier native crashes were not conclusively isolated. See BUG_HUNT_REPORT_v4.4.3rc14.md.

# vFlow 4.4.3rc13

- Preserve sample identities, gate assignments and child-population membership when manually relinking an already loaded acquisition. Capture edits before rebasing references, retire obsolete loaded keys, and ignore Locate dialogs from a replaced/disposed workspace.
- Refresh all child populations before capturing their sample paths, retain inactive choices after relocation, and discard construction-only tab records during restoration. Repeated save/reopen no longer accumulates phantom population tabs or records null active-sample identities.
- Persist imported exclusions whose files are unavailable without blocking capture/save. Retain missing excluded placeholders after reopen; restoring an unloaded placeholder unregisters its workspace reference. Resolve relative and symlink exclusion keys consistently so repeated capture does not duplicate/drop sample identities.
- Restrict population-tab Statistical Audit lists and input capture to that tab's recorded sample membership; prevent applying its gate lineage to unrelated workspace samples. Main-tab audits and explicitly selected excluded members retain their existing behavior.
- Validate nested saved UI identities/selections, section booleans, channel aliases, lineage fields, legacy transform parameters and bounded geometry before changing the live session. Preserve defaults and unknown optional metadata.
- Protect family-excluded acquisition files and skipped filesystem aliases from batch-output overwrites as well as the files actually processed. Keep existing batch filters, counts and repeated output behavior.
- Add 47 regression cases and verify 44 failures against all 122 original delivered RC12 package sources. Validate 1,603 full-suite tests, all 88 scientific benchmark checks, 39 corpus hashes, 31 benchmark-loaded app workflows, fresh-process save/edit/reopen and two RC5-cached Spyder launches. The full native suite uses explicit collection of retired test objects on the GUI thread after exploratory runs encountered native interpreter crashes; see the report for the unresolved runtime limit.
- Keep the working launcher, 19 core modules and ten statistical calculation/export modules unchanged apart from release metadata. Population capture is unchanged after its new membership guard; analysis stays audit-4 / review-3. Current testing uses Linux/Python 3.12/Tk 9.0.4; native Windows/macOS and a fresh Tk 8.6 check remain outstanding. See BUG_HUNT_REPORT_v4.4.3rc13.md.

# vFlow 4.4.3rc12

- Protect acquisition files, workspace files, referenced gates and audit artifacts from accidental export/Save As overwrites, including symlink and hardlink aliases. Publish CSVs and gate JSON through staged atomic writes; report failures without truncating the previous destination. Batch main/log CSVs are individually atomic, not a two-file transaction.
- Reject malformed workspace structures, unsafe IDs and nonfinite/invalid view settings before replacing the live workspace. Reset View now resets the currently displayed sample immediately as well as its saved preference.
- Cancel stale Find Missing Files work after workspace replacement/disposal and retain gate edits made while the scan runs. Reject stale Batch Plot/Polar calculations and exports after switching workspaces or closing their population tab, including reopening the same workspace UUID.
- Ignore malformed derivative metadata/cache members and regenerate from the original acquisition rather than crashing or trusting unusable cached data.
- Escape formula-like text in human-readable audit CSV tables. Numeric values and exact canonical/review JSON remain unchanged; raw event CSVs are not modified.
- Add 58 regression cases; reproduce 33 failures against the delivered RC11 package. Validate 1,556 full-suite tests, 88 scientific benchmark checks, 39 corpus hashes, 23 benchmark-loaded app workflows, fresh-process workspace save/edit/reopen and two RC5-cached Spyder launches. Test Linux/Python 3.12/Tk 9.0.4; fresh Tk 8.6 and native macOS/Windows acceptance remain outstanding.
- Retain all prior settings, the working launcher, 19 byte-identical core modules and unchanged numerical audit algorithms (audit-4 / review-3). See BUG_HUNT_REPORT_v4.4.3rc12.md for evidence and limits.

# vFlow 4.4.3rc11

- Make Statistical Audit sample rows independently toggle on plain clicks. Clicking another row preserves earlier highlights; clicking a selected row deselects it. Arrow-key navigation preserves selection, with Space/Enter toggling the focused sample. Add None beside Select all samples and keep active samples selected by default.
- Use persistent multiple selection for audit variables, without Ctrl/Command. Keep highlights when focus moves; ignore empty-list/blank-space clicks. Add horizontal/vertical scrolling, consistent theme/font/selection colors and a selected-variable count that also updates with All/None. Preserve the initial all-eligible default and the user's chosen variables, including None, when re-preparing a changed sample set.
- Keep biological replicate ID editing on a double-click in its own column; preserve sample membership while editing. Ordinary clicks/double-clicks in other columns do not open the replicate editor.
- Remove the redundant empty-sample Open Workspace shortcut from the pinned sidebar. Data → Workspace retains New, Open, Save, Save As, Close and Open Recent, plus the File menu and keyboard shortcuts.
- During audit workers, freeze input edits and keep the dialog busy until both the worker and its queue finish. Fix a queue-exit race that could lose completed results. Reject old audit dialogs/results after replacing the workspace, including reopening the same file/UUID or closing the population tab. Show commit failures in the dialog status; cancellation does not register results.
- Fix a reproduced Large/200%-scaling case where the sample table and Prepare button disappeared. Size the audit dialog from measured font metrics within the screen bounds, adapt variable-list height to reserve sample rows, wrap hints, remeasure after status/footer wrapping, keep compact control spacing and cancel pending resize work on close. No nested event-loop pumping is added.
- Test real mouse/keyboard/drag/focus behavior, empty selections, all/none, long lists/names, changing populations, workspace replacement, cancellation, queue races, dark/light themes and 100/150/200% scaling. Run a click-driven audit on supplied benchmark CSVs, export Excel/CSV, save/reopen it, and check unchanged raw hashes. Validate 1,498 full-suite tests, 39 native audit/selection cases on Tk 9, 75 audit/workspace/adaptive cases on Tk 8.6 and all 88 scientific benchmark checks. Also verify fresh-process workspace editing/reopening and two RC5-cached Spyder launches on each Tk version. See IMPLEMENTATION_REPORT_v4.4.3rc11.md for evidence.
- Preserve statistical algorithms, sample-inclusion decisions, all other settings and the working launcher. The 19 core and 41 statistics/ingestion/service modules are unchanged apart from release metadata; audit-4 / review-3 remains in use.

# vFlow 4.4.3rc10

- Put a Workspace section first in the Data task: New, Open, Save, Save As, Close and Open Recent. Keep these controls available with loaded samples. Open switches workspaces without quitting; New/Close leave the app running, and unsaved changes retain the existing Save/Discard/Cancel prompt. Preserve the File menu, keyboard shortcuts and empty-workspace shortcut.
- Replace the static workspace title with an editable name field above the samples. Enter or leaving the field applies the name; Escape cancels; empty names are ignored. Save pending text when Save is clicked, persist names across reopen/recovery, and synchronize names across population tabs. Older unnamed workspaces use their filename. Renaming leaves the file path unchanged; Save As selects another file.
- Show Saved, Unsaved changes or Not saved yet in Data, with the file path on hover. Match Open Recent menu-button fonts/padding to the other controls at all interface sizes. Suggest a filesystem-safe filename from the display name. Refresh Open Recent in the File menu and all Data panels.
- Fix a pre-existing false dirty state when restoring expanded/collapsed sections: reopening a saved workspace no longer marks it changed merely because its controls were restored. Real section edits still mark it dirty.
- Retain the working RC9 launcher unchanged. The user confirmed the reported launch failure came from an incorrect Spyder environment; this release adds no further startup workaround.
- Exercise visible workspace controls, switching two loaded workspaces, save/reopen/edit/save/reopen, cancelled/failed dialogs, names in population tabs, old workspace compatibility and scaled displays. Validate 1,474 full-suite tests, 11 focused workspace cases on each of Tk 8.6/Tk 9, all 88 scientific benchmark checks and four native benchmark-loaded UI views. See IMPLEMENTATION_REPORT_v4.4.3rc10.md for final counts and evidence.
- Preserve all prior settings and scientific behavior. All 19 core and 41 statistics/ingestion/service modules are unchanged apart from release metadata; analysis stays audit-4 / review-3.

# vFlow 4.4.3rc9

- Remove nested `update_idletasks()` processing from adaptive sample allocation and initial UI construction. Guard recursive layout requests, coalesce follow-up measurements, and avoid rewriting unchanged pane/window/scroll geometry. Retain automatic/manual sizing, task navigation, saved divider preferences and all existing controls.
- Harden `run_vflow.py` for Spyder: open the selected checkout in a fresh app process using the same Python executable, preserve the user's environment, prevent recursive child launches, and print the startup-log location. This isolates the app from cached older RC modules and the IDE's GUI lifetime. Ordinary command-line/module/installed launches retain their entry points. Set `VFLOW_IN_PROCESS=1` only for deliberate in-kernel debugging.
- Add seven startup/layout/launcher regression cases plus a child-launch guard case. Verify repeated actual Spyder-runner launches with RC5 cached in the parent, visible app windows and four benchmark CSVs (48,000 events) on Linux Tk 8.6.14 and Tk 9.0.4.
- Validate 1,463 tests; 29 targeted native layout checks on Tk 8.6; 53 frozen and 35 expanded scientific checks; 39 unchanged corpus hashes; ten current adaptive screenshots; and separate-process save → reopen → edit → save → reopen. See IMPLEMENTATION_REPORT_v4.4.3rc9.md for evidence and limits.
- Preserve all 120 Python package modules except two presentation fixes and five release-version fields; also update the source launcher. All 19 core and 41 statistics/ingestion/service modules remain unchanged apart from release metadata. Analysis stays audit-4 / review-3.
- The reported no-window condition was not reproduced in clean Linux sessions; the fixes address demonstrated reentrancy hazards and shared-kernel launch failures. Native macOS/Windows Spyder desktop acceptance remains outstanding. Format acceptance limits are unchanged.

# vFlow 4.4.3rc8

- Automatically size the sample list from the current window height, sample count, styled row height and measured header/action/tab geometry. Long lists fill the initial sidebar while keeping sample actions, view/scope controls and task tabs visible; short lists leave more settings in view.
- Add outer sidebar scrolling to reveal settings below the sample area. Keep sample-row scrolling, per-task scrolling and plot/dialog scrolling separate. Selecting a task, including clicking the already-selected tab, reveals its settings without losing its inner scroll position.
- Retain the draggable sample/settings divider and add Settings → Sample list: automatic/manual. Persist manual sizing and outer scroll position; restore old custom-divider workspaces and default missing preferences to automatic sizing.
- Coalesce resize events, remeasure deferred Tk geometry, and fix lost rapid-resize updates and unstable task viewport allocation. Clean up pending callbacks and private wheel bindings when closing population/workspace tabs.
- Account for the outer scrollbar and measured gate-action labels in minimum sidebar width, keeping Rename/Delete/Info / thresholds readable at larger fonts. Preserve all existing settings, tools and RC7 threshold editing.
- Keep numerical algorithms, raw-data handling, gate membership/statistics kernels and ordinary gate serialization unchanged from RC7. Analysis remains audit-4, review policy review-3; layout metadata is optional.
- Validate 1,455 tests, including 25 new native layout cases; 53 frozen and 35 expanded benchmark checks; 39 unchanged corpus hashes; and 57 current native UI views. Exercise 100%, 150% and 200% scaling across all four interface sizes, plus separate-process save → reopen → edit → save → reopen. See IMPLEMENTATION_REPORT_v4.4.3rc8.md for evidence.
- Native macOS/Windows/Retina acceptance remains outstanding. MQD native/export truth, real FCS1.0 reference acceptance and external/vendor FCS3.2 acquisition acceptance remain blocked/pending; no new format-support claim is made.

# vFlow 4.4.3rc7

- Add Delete to every individual X/Y crosshair threshold, retaining checkbox disabling and the existing Undo gate edit history. Remove the matching checkbox state, preserve remaining disabled choices, renumber boundaries and merge adjacent regions. Honor all/current/selected-sample edit scope.
- Surface threshold controls after successful automatic fits, show enabled/stored totals and recovery guidance, and keep the empty-state explanation and Undo visible after deleting the last boundary.
- Fix obsolete scalar-Y fallback reviving a deleted multi-Y boundary, all-disabled/empty-gate statistics exceptions, and shared empty gates hiding valid per-sample overrides. Refit clears the intentional-empty marker when boundaries return.
- Handle a linked subpopulation whose named parent region disappears with a clear unavailable-state message; Undo restores it. Do not silently remap regions or invent zero-count statistics.
- Preserve intentionally empty crosshair gates through workspace/gate-session save and reopen using the exact Boolean field thresholds_empty: true. Continue rejecting malformed unmarked applied-empty geometry. Older pre-RC7 readers may reject the new empty state; ordinary gate snapshots are unchanged.
- Display threshold values with 10 significant digits and expose exact 17-digit values in help. Repair missing/excess threshold flags while preserving existing choices; retain density/transform cache payloads when invalidating gate-dependent results.
- Disable Show sample for zero/multiple/unavailable/excluded selections. Add horizontal/vertical scrolling and full-name help for long folder-file lists. Support keyboard-focus tooltips, Escape dismissal, blank-help suppression and screen-edge placement.
- Preserve numerical estimators, transforms and valid gate-mask/statistics calculations; keep analysis audit-4 / review-3. Validate 1,430 tests, including 34 new regression cases; 53 frozen and 35 expanded benchmark checks; 39 unchanged corpus hashes; and 47 native benchmark-loaded UI views. See IMPLEMENTATION_REPORT_v4.4.3rc7.md.

# vFlow 4.4.3rc6

- Compare the approved task-tab UI against the supplied 4.3.0 reference, restoring direct controls and improving access to existing options without removing settings or analytical tools.
- Enlarge the sample area, retain vertical/horizontal list scrolling, add a draggable sample/settings divider and save its workspace preference. Restore direct Exclude/Restore/Show sample controls and keep the shared Overlay/Cycle selector.
- Restore visible gate Rename/Delete/Actions… and Info / thresholds controls. Preserve copy/reset/promote/drag-to-sample, gate scope/style options, manual/automatic methods, parameters and exports.
- Stack full-width channel selectors, add full-name help, replace ambiguous section headers with disclosure buttons, and expose advanced controls/export sections while respecting saved expansion preferences.
- Improve Rename/Cancel and Return/Escape handling, reserve dialog action footers, wrap long labels and add table/input scrolling in Batch Stats, channel-name/exact/unresolved resolvers and saved-audit lists.
- Add resizable, scrollable Polar/Batch Plot sidebars and statistics tables, retaining coordinate orientation, population selection, visibility and export options. Preserve Ctrl-click multi-selection outside macOS and fix scoped wheel handling on Linux Tk 8/9 and small macOS-style deltas.
- Preserve scientific methods, parsers, gate truth and export calculations from RC5; retain analysis audit-4 / review-3. Validate 1,396 tests, including 25 new native UI cases; 53 frozen and 35 expanded benchmark checks; 39 unchanged corpus hashes; and 38 after/33 before native views. See IMPLEMENTATION_REPORT_v4.4.3rc6.md.

# vFlow 4.4.3rc5

- Implement the approved Data / Plot / Gates / Analysis task tabs with a pinned sample list and one View Mode selector. Preserve activation, source colors/actions, selection, Prev/Next and cycle position, gate-target status and every original setting/export.
- Group Manual and Automatic gates separately; expose all four existing automatic methods through a picker and Calculate gates. Keep GMM counts and contour probability available when relevant, with retained values.
- Move theme, all four interface sizes and Expand/Collapse into Settings; retain advanced controls in collapsible task sections and independent scrolling.
- Persist task, gate-tool and method selection and per-task scroll positions; keep older workspaces compatible.
- Cancel pending sensitivity reruns when choosing a different method; release sidebar wheel callbacks on population/workspace disposal; preserve Settings visibility with long workspace names.
- Keep scientific algorithms and control ranges unchanged; retain analysis audit-4 / review-3. Add 22 native GUI cases. See IMPLEMENTATION_REPORT_v4.4.3rc5.md for final tests, benchmark evidence and native screenshots.

# vFlow 4.4.3rc4

- Prevent extremely small nonconstant data from becoming false zero variance or distance. Stabilize means and standard deviations without relying on a wider long-double exponent range; reject unrepresentable positive results clearly. Record analysis audit-4 / policy review-3.
- Make workspace Save As publish references only after a successful write; preserve immutable imported audit bytes and live dialog reference identity.
- Roll back multi-sample exclusion/restoration if an operation fails after mutation, including inclusion state, gate state and decision history.
- Reject inconsistent audit matrices, counts, variable selections, population hashes and workspace audit references before review or export.
- Protect source files, audit bundles, gate sessions and the current workspace from statistical-export overwrite, including symlink aliases; retain forbidden Unicode in canonical review JSON.
- Guard stale saved-audit lists, validate public input metadata and clarify historical analysis guidance.
- Add 47 regression cases and six native benchmark-loaded sidebar captures. Final validation is recorded in IMPLEMENTATION_REPORT_v4.4.3rc4.md.

# vFlow 4.4.3rc3

- Fix unit-dependent zero-variance, isolation and robust-z handling; stabilize large-value calculations and reject unsupported numeric ranges clearly. Record analysis audit-3 / policy review-3 for new audits.
- Validate audit settings, duplicate measurements and damaged bundles; normalize biological IDs consistently. Record and validate original acquisition member identity.
- Prevent historical dialogs from reviewing a different or reopened workspace; preflight multi-sample review actions and stop closed worker callbacks.
- Preserve long review notes and control characters in Excel/CSV review-context JSON, namespace distance headers and check Excel limits before replacing exports. Display tiny nonzero values in scientific notation.
- Add How to interpret, eligibility reasons, complete-row/peer counts, raw and normalized W1, model reasons, signed influence changes and leave-one-out model fits; make controls accessible at minimum window size.

# vFlow 4.4.3rc2

- Correct projection stability for the robust-z review path; classify using the usable multivariate peer count. Preserve previous immutable audit results; record analysis audit-2 / policy review-2.

- Centralize CSV/FCS/LMD/MQD recognition across ingestion, pickers and discovery. Unknown content and unvalidated MQD fail closed.
- Implement version-aware FCS1.0–3.2 numeric decoding, mixed per-parameter FCS3.2 integer/float/double types, exact uint64 storage and CRC integrity checks. Real FCS1.0 and external FCS3.2 acquisition acceptance remain pending.
- Decode real Gallios LMD chained high-resolution measurements; 14 public acquisitions match independently frozen FlowIO event/column values exactly. Preserve original source/member identity and automatically manage validated, collision-safe tabular derivatives.
- Add full-event univariate Wasserstein and multivariate sliced-Wasserstein QC with deterministic projections, second-seed stability checks and explicit small-N semantics. Flags never exclude samples automatically.
- Add nested random-intercept REML variance components, ICCs and equal-biological-weight leave-one-out influence with model status and identifiability checks.
- Save immutable external audit bundles in workspace schema 2; migrate schema 1, append review decisions, relink missing bundles, and export canonical XLSX/CSV packages.
- Validate 1,268 tests with real Tk, 53 frozen scientific checks, 35 expanded checks, and 39 unchanged corpus checksums. Six malformed supplied FCS fixtures still reject exactly as in the baseline.

# vFlow 4.4.1

- Separate automatic calculation inputs (active pooled, selected rows, current sample) from gate application scope; preserve the all-active default across Cycle/Overlay.
- Add authoritative entire-workspace gate application, sparse Selected-samples editing, and one-step automatic gate undo.
- Fix resolved gate copying, child ancestor refresh, missing-parent reference loss, and native session reference ownership.
- Preserve joint X/Y row alignment in cluster preparation without changing the scientific estimators.
- Retain fitting provenance externally and cancel stale live fits after source/scope/context changes.
- Finalize semantic fonts, tooltips, drag feedback, active checkboxes, and small/high-DPI layouts.
- Final full suite: 1,209 passed. Frozen corpus: 53/53 available science checks, 39 unchanged checksums; nine baseline scientific modules unchanged.

# vFlow 4.4.0

- Reference-only `.vflow` workspaces, atomic saves, recent files, and debounced state recovery.
- Separate per-sample and Overlay views, transform parameters, and locked/fitted limits.
- External gate-session loading, sparse sample gate overrides, and sample-aware lineage resolution.
- Gate copy/drag/drop, selected-sample application, reset, promotion, and undo.
- Identity-verified source/gate relocation, recursive scans, verified root remapping, and ambiguity choice.
- Pinned Samples/scope panel, collapsible analytical controls, semantic fonts, and interface scaling.
- Renderer-only off-scale markers, explicit contour counts, and full-population marginal edge bins.
- Scientific core mathematics and the strict FCS reader retained from the supplied v4.3.0 baseline.

The earlier cumulative changelog follows as historical baseline documentation.

---

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
