# vFlow v4.3.0 — Refactor Integrity B6 release baseline

This archive is the **release-ready v4.3.0 source package** derived from the certified Refactor Integrity B6 checkpoint. `B6` is an internal validation label only; the public software version is **v4.3.0**.

Start with:

- `source/vFlow_v4.3.0/`
- `source/vFlow_v4.3.0/README.md`
- `source/vFlow_v4.3.0/CHANGELOG.md`
- `source/vFlow_v4.3.0/RELEASE_NOTES_v4.3.0.md`
- `source/vFlow_v4.3.0/CITATION.cff`
- `source/vFlow_v4.3.0/.zenodo.json`
- `source/vFlow_v4.3.0/project/V4.3_REFACTOR_INTEGRITY_B6_AUDIT.md`
- `source/vFlow_v4.3.0/project/V4.3_REFACTOR_INTEGRITY_B6_VALIDATION.txt`

The B6 application baseline contains **1,115 passing automated tests** plus generated real-GUI, edge-data, state-fuzz, A5 interaction/scale, scientific fingerprint, FlowJo reference, frozen-render and refactor-wiring validation. The release-ready source adds three metadata/repository checks for **1,118/1,118 passing tests**.

## Important provenance note

Files under `project/` and `validation_artifacts/` are retained as historical audit evidence. Some record the internal checkpoint name `v4.3.0-dev` or the then-frozen `4.2.0` metadata because that was the state when those validations were executed. They have **not** been rewritten retroactively. The current public release declarations are the source-root metadata files and runtime constants, all synchronized to **4.3.0**.

## Build-kit boundary

The separately supplied `Built_Kit_v4_3_0` was used only to confirm the intended final `4.3.0` version convention. Its later startup-splash/icon/native-build follow-up is **not merged into this B6 source archive**, because that build kit is not the release baseline requested here.
