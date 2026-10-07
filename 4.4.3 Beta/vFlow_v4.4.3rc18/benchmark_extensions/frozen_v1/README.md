# vFlow Benchmark Corpus v1.0.0

A deterministic, fully synthetic benchmark corpus for vFlow.

## Why this exists

This corpus is intended to remain frozen across vFlow releases so that parser,
visualization, gating, statistics, sub-gating, batch analysis, workspace state,
and performance changes can be checked against known inputs.

It contains **no patient data**.

## Core rules

- Do not edit the frozen files in-place. Create a new corpus version if the benchmark design changes.
- Gate/statistic truth is based on the full scientific population, never on display subsampling.
- `references/benchmark_gate_definitions.json` is a benchmark truth schema, not a claim about the current app gate-session JSON schema.
- `workspace_future_fixture/Benchmark_Workspace_ProposedSchema1.vflow` targets the agreed workspace design and is intentionally a future fixture for builds that implement it.
- FCS parser fixtures are independently round-trip validated at generation time.

## Recommended release smoke sequence

1. Load `cytometry/Control_01.fcs`.
2. Load `cytometry/Control_01_matched.csv` and verify numeric parity with the FCS scientific matrix.
3. Overlay `Control_01`, `Control_02`, `Treatment_01`, and `Treatment_02`.
4. Exercise linear/log/asinh/logicle/legacy scales on `EdgeCases_01.fcs`.
5. Verify off-scale events remain represented at axis boundaries without changing gate/statistical counts.
6. Recreate the reference gates from `references/benchmark_gate_definitions.json` and compare to `truth/expected_gate_counts.csv`.
7. Exercise sub-gating/lineage using scatter -> singlet -> marker views.
8. Run Otsu/KDE/GMM/cluster polygons on `autogate_edgecases/AutoGate_ThreeClusters.csv`.
9. Confirm KDE fail-closed behavior on `KDE_NoValley_Unimodal.csv`.
10. Confirm Density/Contour do not crash on `ConstantAxis_Degenerate.csv`.
11. Exercise Batch Plot/Stats on `cytometry/Batch_4Samples_SourceFile.csv`.
12. Exercise Polar/Vector analysis on the microscopy samples and compare observed metrics in `truth/polar_expected_metrics.json`.
13. Load every FCS in `parser_variants/`.
14. When workspace support is available, open the proposed workspace fixture, move the corpus directory, and test scan/relink.
15. Repeat key statistics with aggressive display subsampling and verify scientific counts are unchanged.

## Off-scale benchmark

`autogate_edgecases/OffScale_ExactBoundary.csv` uses a simple visible range of 0..100.
It contains events below, exactly on, inside, exactly on the upper boundary, and above
the range on both axes. Display-only changes must not alter scientific event values.

## Performance

The included samples are intentionally modest so they can be committed and run frequently.
For stress tests, replicate rows or use the same generation rules to produce 250k, 1M, and 5M-event files.
Performance measurements should be kept separate from scientific expected-value assertions.
