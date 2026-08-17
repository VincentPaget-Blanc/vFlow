# README FIRST — vFlow v4.3.0-dev Accuracy Hardening A4

This package continues from the certified **v4.3.0-dev Gate Axis Preservation A3** checkpoint.

## Purpose

A4 is a second scientific-accuracy audit focused specifically on *plausible but
wrong* output: silent sample omission, partial-source aggregation, ambiguous
cross-file channel identity, malformed saved state becoming different geometry,
inconsistent denominators, stale rendering, and FCS metadata/encoding edge cases.

It is not a feature or architecture pass.

## Starting checkpoint

A3 certified ZIP SHA-256:
`e4d6cedfd34186e0466ae82dea70678a824a73bf83c4344f0f1e0ed7b9f9439d`

The A3 archive manifest and complete 1067-test baseline were reproduced before
A4 production edits.

## Main accuracy hardening

A4 makes analysis fail closed instead of returning a compatible-looking subset
when active files cannot all participate in the selected analysis.  It also:

- broadens FCS compensation-metadata detection while reporting the compensation
  state neutrally as requiring verification;
- handles FCS integer unused high bits before range checking;
- rejects malformed inactive gate geometry instead of sanitizing it into a
  different future gate;
- applies A3 X/Y transposition semantics when a saved A/B session is loaded into
  a B/A view;
- treats a zero-resultant circular mean as undefined rather than manufacturing an
  angle from floating-point round-off;
- keeps zero-transform-valid-event samples visible in statistics provenance;
- makes source/input/transform-valid/excluded denominators explicit in exports;
- prevents ambiguous duplicate FCS stains and unnamed CSV columns from automatic
  cross-file channel matching;
- prevents structurally partial concatenated channels from becoming pooled axes;
- requires Batch Stats region partitions to be both disjoint and exhaustive;
- prevents subgate, main stats, multi-shape stats, rendering and auto-gating from
  silently operating on only the compatible subset of active files;
- actively clears stale plots when no valid shared analysis axes remain.

The frozen percentage semantics are not changed: gate percentages continue to use
the transform-valid analysis universe, now with explicit denominator provenance.

## Explicitly rejected hypotheses

A4 does **not** ignore non-unit `$PnG` merely because FCS DATA are floating point;
FCS 3.1 guidance supports gain use with floating DATA.  A4 also does not require
identical schemas for heterogeneous CSV concatenation and does not infer that
compensation is unapplied merely because compensation metadata are present.

## Certification snapshot

- **1102/1102 tests PASS**.
- `compileall` PASS.
- A4 deterministic validator:
  - 300 valid randomized batch partitions;
  - 600 overlap/gap variants correctly rejected;
  - 303 channel-integrity scenarios;
  - 361 antipodal circular-mean cases;
  - malformed inactive-gate rejection checks.
- A2 Logicle/polar validator remains green: 480 independent Logicle root checks
  and 3000 legacy migration membership events.
- A3 axis-swap validator remains **480/480**.
- Frozen scientific fingerprint remains exactly:
  `b9e3da149810d8039b74eb85360cc046a34eb346d2b8aad04f6f109fc4b44aef`
- FlowJo/TextToFCS remains `1473 x 8`, 10 compatibility normalizations, all
  finite, **0.0 DATA difference**, decoded SHA unchanged.
- Dot/Density/Contour/gate-preview render hashes remain exactly equal to A3.

Read next:

- `source/vFlow_v4.3.0-dev/project/V4.3_ACCURACY_AUDIT_A4.md`
- `source/vFlow_v4.3.0-dev/project/V4.3_ACCURACY_A4_VALIDATION.txt`
- `validation_artifacts/`
- `validation_tools/accuracy_hardening_a4_checks.py`

## Version status

This remains a **v4.3.0-dev** scientific checkpoint. Runtime/package metadata
intentionally remains **4.2.0** pending final v4.3 release certification.
