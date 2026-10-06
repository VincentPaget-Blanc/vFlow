"""Write the acceptance report and changelog results only after the release gate."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1];V=ROOT/'validation'
def read(name):return json.loads((V/name).read_text())
g=read('release_gate_rc16_final.json');assert g['all_checks_passed']
f=read('full_suite_rc16_receipt.json');e=read('endurance_rc16_final_receipt.json')['result'];t=read('matched_timing_rc16_final.json')
rows=['| Workflow | RC15 median (s) | RC16 median (s) |','| --- | ---: | ---: |']
for task,values in t['summary'].items():rows.append(f"| {task.replace('_',' ')} | {values['rc15_median_seconds']:.6f} | {values['rc16_median_seconds']:.6f} |")
text=f'''# vFlow 4.4.3rc16 — completed release validation

RC16 finishes the scoped workspace integrity and recovery work. All release gates passed against the final application source. It does not introduce another open-ended bug hunt.

## Changes

- Workspace saves retain the opened byte revision, reject external edits/deletion or redirected aliases, and use a nonblocking operating-system writer lock plus a final revision check before replacement. Refused saves preserve live edits for Save As. Locks coordinate cooperating vFlow writers; they do not prevent arbitrary external programs from writing files.
- Recovery checkpoints belong to individual app instances and include unsaved gate geometry, sample overrides, activation, exclusions and audit decisions. Failed checkpoints keep the correct complete revision; corrupt newest snapshots fall back to valid older snapshots. Restored work is dirty and retains its original saved-revision guard.
- New references use full SHA-256; legacy sampled references remain readable and pin full content when accepted. Portable missing locators and verified relocations retain their recorded identity. Legacy acceptance cannot prove bytes outside the originally sampled regions before that acceptance.
- Ingestion records the identity of the bytes decoded. Direct sources receive before/after checks and identity attributes. An owned CSV that redirects to its LMD may be legitimately regenerated: its outer check applies only to samples whose resolved source path is that requested CSV. The original remains checked recursively. `test_derivative_refresh_rc16.py` verifies regeneration, LMD identity, sample-key preservation and rejection of mutation during recursive decoding.
- Audit results explain saved data/gate snapshots separately from current inclusion. True zero scores remain numeric; unavailable joint comparisons are explicit. Inclusion updates in an open results dialog without changing saved calculations. Results sizing uses font metrics and screen bounds. The writer harness now records child diagnostics, bounds waits and cleans up both processes on failure.

## Final validation

| Check | Result |
| --- | --- |
| Ordinary full suite, uncaptured output | 1,663 passed; no failures, errors or skips |
| Full-suite duration | {f['seconds']:.3f} seconds |
| Focused RC16 regressions | 34 passed, including all four compound scenarios |
| Native focused cases with capture fonts | 30 passed |
| Ingestion | 61 passed (the previous 60 plus derivative refresh) |
| Source integrity | 13 passed |
| Frozen / expanded scientific checks | 53 / 35 passed |
| Frozen corpus manifest | 39 files unchanged |
| All original benchmark extension files | 57 files byte-identical to RC15 |
| Real app benchmark workflows | 36 checks; 48,000 events |
| Native release probes | All 15 phases passed; no intentionally fatal controls |
| Separate-process save/reopen/edit/reopen | All four phases passed |
| Actual Spyder with original RC5 cached | Two isolated RC16 launches; 48,000 events each |
| Final-source endurance | {e['active_seconds']:.3f} active seconds; {e['cycles']} cycles; {e['workspace_switches']} switches |
| Endurance audit lifecycle | {e['real_audit_preparations']} preparations, {e['cancelled_closed_workers']} cancelled/closed workers, {e['real_audit_runs']} complete audits; closed dialogs collected |
| Layout checks | Large/200% preparation and results, details, empty Data workspace; no callback errors |
| App-only diagnostics | Passed with pytest/tests imports blocked |

Compound workflows use pandas row oracles for global and per-sample gates, nested populations, exclusion/activation changes, undo, saves/reopens, relocation, removal, historical calculations and CSV/Excel exports. Native probes also check moved trees, Save As revision preservation, process interruption before/after final replacement, and fresh-process saved/unsaved recovery. No raw acquisition bytes were changed.

Full-suite and endurance receipts bind every application Python file to its SHA-256 and verify that it stayed unchanged during the run. The packaging gate rechecks those same hashes. The full suite used ordinary pytest, without a Tk cleanup plugin or application garbage-collection modification. Diagnostics used uncaptured output and external timed signal-based main-thread stack dumps, including setup/teardown, with a two-hour full-suite deadline. Worker-thread stack traversal was excluded in the accepted run after a diagnostic-time native fault. BLAS/OpenMP limits were one thread in validation.

## Timing comparison

One warmup and five measured runs per version, alternating RC15/RC16 in fresh processes with identical dependencies, thread limits and input bytes. Timings ran while no other validation processes were running, before the accepted full-suite retry. Each run used all 48,000 events; gate counts, original LMD values and numerical audit payloads matched exactly. These are local timings, not universal performance guarantees. Full hashing deliberately increases source-verification I/O, particularly for larger acquisitions.

'''+ '\n'.join(rows)+f'''

Machine-readable repetitions and timings: `validation/matched_timing_rc16_final.json` and `validation/matched_timing/`.

## Preservation and limits

All 122 original package modules remain; RC16 adds only `vflow/workspace/file_guard.py`. The 19 core modules, 11 statistical modules apart from release-version metadata, all legacy class methods, population-capture method, automatic-gating input method and source launcher are preserved. Analysis remains `audit-4`, review policy `review-3`. Every existing RC15 changelog byte remains below the new RC16 entry. The rebuilt wheel is checked against all 123 application Python sources and the exact current README; the archive has a verified complete payload manifest.

Acceptance is Linux / Python 3.12.14 / Tk 9.0.4 / Xvfb, including the actual SpyderShell runner. Fresh Tk 8.6 and native macOS/Windows acceptance remain outstanding. Windows locking has a contract test, not native Windows acceptance. Six supplied frozen FCS fixture incompatibilities remain recorded; no additional format-support claim is made. MQD decoding still fails closed pending same-acquisition native/export truth; real FCS1.0 and external/vendor FCS3.2 acquisition acceptance remain pending.

Earlier local attempts remain diagnostic evidence rather than acceptance. One full run was interrupted after about 150 reported passes during teardown; its isolated replay passed. A later run progressed beyond 1,100 cases before it was interrupted in real-LMD ingestion. A subsequent run ended after about 300 passes in a native segmentation fault while its all-thread timed stack dump was traversing a NumPy worker frame. The accepted run used timed main-thread dumps on unchanged application source and crossed the earlier prefixes, writer test and real-LMD ingestion. This does not establish the cause of the earlier stalls, fault or environment disconnection. A subsequent retry was interrupted prematurely after 590 passing cases while still advancing; repeated GC frames belonged to different reopen operations. Its record is corrected in `validation/full_suite_rc16_blocked_receipt.json`, and its log is `validation/full_suite_rc16_premature_interruption.txt`. It is not acceptance evidence. A further ordinary full-suite run reported 1,402 passing cases and no failed cases before the execution environment disconnected; its final receipt was absent after reconnection. That recovered log is retained as `validation/full_suite_rc16_environment_disconnect_1402.txt`. The accepted retry uses a two-hour bounded deadline on identical application source.

A final-source endurance attempt with fallback display fonts and in-process all-thread dumps ended in a native segmentation fault after the cycle-141 heartbeat at 1,364.502 seconds. Its trace stopped while dumping a Matplotlib figure frame. A corrected-font attempt with external all-thread dumps stopped advancing after the cycle-101 heartbeat at about 870 seconds and was interrupted. The accepted fresh run used corrected capture fonts and timed main-thread dumps, with the user-approved 20-minute target. Fault and stall logs are retained as `validation/endurance_rc16_native_fault_attempt.txt`, `validation/endurance_rc16_external_stall_attempt.txt`, `validation/full_suite_rc16_signal_fault_attempt.txt` and `validation/full_suite_rc16_real_lmd_stall_attempt.txt`. The causes remain unresolved; they must not be described as fixed. The earlier pre-CSV-fix endurance claim was not used.

## Reproduce

Use an environment with project dependencies, pytest and a native display. Run `python validation/supervise_rc16.py --timeout 7200 validation/run_full_suite_rc16.py` for uncaptured output and timed stacks on Unix. The supervisor uses timed faulthandler dumps on platforms without SIGUSR1. For safe native phases, run `python validation/native_release_check_rc16.py --output NEW_RESULTS_FOLDER`. The original RC5 archive is required for `validation/check_spyder_launcher_rc16.py --cached-root ORIGINAL_RC5_SOURCE_FOLDER`. Existing historical scripts/results are retained as historical evidence; final RC16 receipts are named explicitly above.
'''
(ROOT/'RELEASE_VALIDATION_v4.4.3rc16.md').write_text(text)
p=ROOT/'CHANGELOG.md';s=p.read_text();key='# vFlow 4.4.3rc15';i=s.index(key)
head=s[:i].rstrip()+f"\n- Validate 1,663 ordinary full-suite tests, 34 focused regressions, 61 ingestion tests, 13 integrity checks, four compound scenarios, 88 scientific benchmark checks, 36 app workflows, 15 native phases, four persistence phases and two actual cached-RC5 Spyder launches. Complete {e['active_seconds']:.3f} seconds of final-source endurance and matched RC15/RC16 timings with identical numerical outputs. Preserve all 57 original benchmark extension files and exact wheel/source/README identity. See RELEASE_VALIDATION_v4.4.3rc16.md for timing and platform limits.\n\n"
p.write_text(head+s[i:]);print('Final report and cumulative changelog updated after release gate.')
