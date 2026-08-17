# vFlow 4.2.0 Release Notes

## Release boundary

v4.2.0 is the first release after the completed structural refactor, post-refactor robustness review, and profiling-driven performance series. The packaged entry point (`python -m vflow` or the installed `vflow` command) is the single source authority; the duplicate standalone Python launcher used during compatibility work has been retired.

## Major changes

- Behavior-preserving decomposition of application state, scientific services, plotting helpers, UI shells, file handling, nomenclature, and platform helpers.
- Transactional robustness for several gate/polygon interaction failure paths and corrected targeted cache invalidation.
- Session-scoped channel nomenclature resolution with safe collision handling and inheritance into sub-gates/Batch Stats.
- Resizable sidebar and platform-native file reveal actions.
- Profiling-driven rendering improvements for hover geometry, Density, Contour, marginals, retained axis/tick lifecycle, gate evaluation, and cold multi-file KDE computation.
- Memory-bounded gate/scatter caches with packed masks and compact scatter payloads.

## Scientific compatibility boundary

The v4.1.11 scientific/FCS baseline remains the certified reference for v4.2 unless a behavior-review item explicitly changed robustness semantics. In particular:

- `$SPILLOVER` is detected and warned about, but compensation is not applied automatically.
- The legacy `biexp` and `logicle` choices retain vFlow's historical signed-log approximations and are not standards-compatible Gating-ML transforms.
- Existing gate denominators, gate serialization/provenance, sub-gate lineage, Batch Plot counting-SE interpretation, and FlowJo TextToFCS compatibility normalizations are preserved.

Scientific/UX behavior-review items that require explicit product/domain decisions remain deferred rather than being changed during release cleanup.
