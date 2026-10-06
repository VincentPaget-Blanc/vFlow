# vFlow 4.3.0 Release Notes

## Release boundary

vFlow **4.3.0** is the public source release built from the Refactor Integrity B6 baseline. B6 is retained only as an internal validation checkpoint name; it is **not** part of the public version number. This source package intentionally excludes the separate unreleased build-kit-only startup/icon/native-packaging follow-up.

The packaged entry point (`python -m vflow` or the installed `vflow` command) is the single source authority. Public version declarations in `pyproject.toml`, `vflow.__version__`, and `APP_VERSION` are synchronized to **4.3.0**.

## Major changes relative to v4.1.4

- Refactored the former monolithic application into an installable `vflow` package with explicit scientific, state, rendering, controller, workflow, export and UI boundaries.
- Hardened scientific correctness around gate denominators, transform-valid event universes, saved-gate provenance, multi-file channel identity, axis swaps, FCS/CSV parsing, Batch Stats/Batch Plot outputs, polar/vector statistics and gated-data export.
- Added standards-reproducible Gating-ML Logicle (`logicle_gml2`) with explicit `T/W/M/A` parameters while preserving historical vFlow signed-log transforms as explicit legacy compatibility modes.
- Added transactional X/Y gate-axis transposition so a true axis swap preserves gate membership rather than reinterpreting geometry.
- Repaired post-refactor regressions affecting gate preview rendering, scale-transition axis reversal, gate rebinding after scale/cofactor changes, Derivative/Otsu auto-gating API drift, Clear/reload stale state, sub-gate tab destruction and constant/degenerate Density/Contour rendering.
- Added stronger provenance and fail-closed behavior for ambiguous or malformed inputs instead of returning plausible but unsafe results.

## Refactor-integrity validation

The B6 application baseline passes **1,115 automated tests**. The release-ready v4.3.0 source adds three metadata/repository checks, for **1,118/1,118** passing tests after version finalization. Additional generated-data validation exercised all scale combinations, manual and automatic gates, gate movement/resizing, marginals, multi-file state, save/reload, Clear→reload with distant numeric ranges, constant/NaN/Inf data, repeated sub-gate lifecycle and randomized GUI state transitions. Refactor host/UI wiring scans reported zero missing extracted attributes in the audited boundaries.

Scientific-reference safeguards remain preserved where intended: the frozen scientific fingerprint, FlowJo/TextToFCS reference comparison, gate-axis membership validation and normal render fingerprints remain unchanged from the certified reference artifacts.

## Compatibility / explicit boundaries

- vFlow detects compensation/spillover-related FCS metadata but does **not** automatically apply or infer compensation.
- `legacy_biexp` and `legacy_logicle` retain historical vFlow signed-log behavior for compatibility; they are not claimed to be standards Gating-ML transforms.
- `logicle_gml2` is the standards-reproducible Logicle path with explicit parameters; it is not a claim of pixel-identical FlowJo Biex display parity.
- Ambiguous multi-file channel identity fails conservatively rather than being guessed.
- Historical validation documents under `project/` intentionally preserve statements from internal `v4.3.0-dev` checkpoints. They are provenance records, not current public version declarations.

## Citation and archival metadata

The release includes `CITATION.cff` for GitHub citation support and `.zenodo.json` for Zenodo GitHub-release metadata. The repository metadata is aligned with the existing vFlow Zenodo record and GitHub repository.

See `CHANGELOG.md` for the full cumulative v4.1.4 → v4.3.0 change history.
