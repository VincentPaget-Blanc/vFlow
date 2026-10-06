# vFlow 4.4.3rc17 — final validation

All final acceptance checks pass. See UI_INTERACTION_REVIEW_v4.4.3rc17.md for behavior, review coverage and platform scope.

| Check | Result |
|---|---|
| Complete ordinary pytest coverage | 1,690 unique cases across 162 modules |
| Final application source identity | All four source receipts match the 123 delivered Python modules |
| Updated release/source expectations | 24 cases rerun; seven stale RC16/old double-click assertions corrected |
| Focused interaction checks | 28 passed: 27 new cases plus existing keyboard-tooltip coverage |
| Fresh Tk 8.6 interaction/audit checks | 51 passed |
| Frozen and expanded scientific truth | 53 + 35 = 88 checks passed |
| Real benchmark app replay | 36 workflows passed; 48,000 events |
| Benchmark mouse/keyboard visual review | 8 checks passed; 6 screenshots |
| Original raw benchmark-extension bytes | All 57 files unchanged |
| Scientific core preservation | 19 modules byte-identical |
| Statistical calculations/export preservation | 11 modules unchanged apart from release metadata |
| Original application surface | No original classes or methods removed |
| Source launcher / RC16 ingestion registry | Byte-identical |
| Current wheel | Exact final Python sources and embedded README |

Full-suite shard durations: 166.311 seconds, 403.866 seconds, 473.421 seconds, 297.59 seconds. The raw group logs retain seven initial expectation failures; `release_expectation_recheck_rc17.xml` records the successful rerun of all four affected test modules. `release_gate_rc17.json` validates every unique case using its latest accepted result. App code remained unchanged during these assertion updates. Partial/prefinal runs and expected RC16 reproduction failures are retained separately and do not count as acceptance.

Native validation: Linux/Python 3.12/Tk 9.0.4; focused and rendered checks also use fresh Tk 8.6.14. Native macOS and Windows event verification remains outstanding. Older RC16 endurance/performance receipts are historical, not newly repeated RC17 claims. Six pre-existing supplied FCS fixture incompatibilities remain separately reported by the frozen scientific runner.

Current wheel SHA-256: `adb9edf54f9c6c725c3b339de41ba27b2388771b9765ab18e83865ae2a38bd0d`.

Machine-readable source hashes, test coverage, benchmark preservation and acceptance results are under `validation/`. Run `python validation/release_gate_rc17.py` to recheck the delivered acceptance inputs.
