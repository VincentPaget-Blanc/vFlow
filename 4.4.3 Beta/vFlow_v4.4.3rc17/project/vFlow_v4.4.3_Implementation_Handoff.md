# vFlow v4.4.3 — Implementation Handoff
## Universal Data Ingestion + Statistical Replicate Audit

**Baseline:** `vFlow_v4.4.1_Workspace_PerSample_Gating_Final`  
**Target:** vFlow **4.4.3**  
**Purpose:** implement the two features agreed after v4.4.1 without changing the existing scientific gating behavior:

1. **Low-friction file ingestion** for CSV, every standardized FCS generation through FCS 3.2, Miltenyi MQD, and Beckman Coulter LMD.
2. **Post-acquisition statistical audit** for within-group sample quality/concordance and hierarchical replication structure, with complete XLSX/CSV export and auditable workspace-linked user decisions.

This handoff is intentionally implementation-oriented. The implementing agent should modify and test the supplied v4.4.1 baseline rather than redesigning unrelated areas of the application.

---

# 1. Non-negotiable product decisions

## 1.1 File ingestion

The normal user workflow must be frictionless:

```text
Select / drag supported source
        ↓
vFlow identifies the format
        ↓
CSV  → load directly
FCS  → decode directly
LMD  → decode automatically → create .vflow.csv beside source → load
MQD  → decode automatically → create .vflow.csv beside source → load
```

There must be **no normal conversion dialog**, no requirement to export manually in vendor software, and no vendor-specific workflow exposed to the user.

For proprietary files:

- the **original MQD/LMD remains the authoritative source**;
- vFlow automatically creates a derived CSV next to the original when the directory is writable;
- generated files must never overwrite a user file;
- generated derivatives are reused when valid;
- stale/missing derivatives are regenerated automatically;
- if the source directory is read-only, use an internal cache as an exceptional fallback rather than refusing to load;
- downstream plotting, gating, statistics, batch behavior, workspace behavior, and exports must see the same normalized DataFrame abstraction regardless of original file format.

FCS should **not** be converted to CSV automatically. FCS remains a directly decoded standard interchange format.

## 1.2 Statistical audit

The statistical feature is a **post-acquisition audit**, not instrument QC and not the final biological statistical analysis.

It must:

- compare samples selected by the user that are expected to belong to the same experimental condition/procedure/population;
- work on any numerical variables present in vFlow data, not only flow-cytometry channels;
- therefore support fluorescence, background values, distances, morphology, particle measurements, synaptosome variables, etc.;
- use all available valid data points for the selected variables by default;
- identify statistically/distributionally discordant samples and flag them **for review**;
- never infer that a discordant sample is necessarily an experimental failure rather than true biology;
- never automatically remove/exclude a sample;
- allow the user to keep or exclude a sample after reviewing the audit;
- preserve that decision in workspace audit history;
- support multiple independent audits in one workspace (e.g. Control audit, Treatment A audit, Treatment B audit, different populations, later repeated audit);
- export the complete audit as a multi-sheet Excel workbook by default, with a CSV package as an alternative;
- provide hierarchical replication information without performing condition-vs-condition inferential statistics.

## 1.3 Explicitly out of scope

Do **not** add in v4.4.3:

- instrument/acquisition-rate QC;
- laser/drift/clog detection;
- condition 1 vs condition 2 hypothesis tests;
- automatic sample deletion/exclusion;
- claims that a statistical outlier is an experimental failure;
- power calculations;
- an “optimal number of acquisitions” calculator;
- a replacement for R/Prism/Python/SPSS/SAS final statistics;
- vendor analysis-template/workspace emulation;
- proprietary vendor gating/report reproduction;
- silent downsampling of statistical audit data.

---

# 2. Baseline v4.4.1 observations that must guide the implementation

The current source has useful separation of concerns, but file-format assumptions remain hard-coded.

## 2.1 Current loader

`vflow/core/data_io.py`

```python
def read_flow_data_file(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".fcs":
        df, _ = read_fcs(path)
        ...
        return df
    return smart_read_csv(path)
```

Every non-`.fcs` source currently falls through to CSV parsing. This must be replaced by explicit format detection/dispatch. Unknown files must fail closed with a clear unsupported-format error.

## 2.2 Current FCS reader

`vflow/core/fcs_reader.py` currently documents and accepts only:

```text
FCS 2.0
FCS 3.0
FCS 3.1
```

and explicitly rejects any other version header.

FCS 3.2 is **not** safely enabled by merely adding `"FCS3.2"` to the accepted-version set. FCS 3.2 contains incompatible reader changes, notably support for mixed per-measurement data representations. Implement against the FCS 3.2 standard/reference behavior, not by version-string bypass.

The project should target standardized FCS generations:

```text
FCS 1.0
FCS 2.0
FCS 3.0
FCS 3.1
FCS 3.2
```

within vFlow's supported list-mode/event-data scope. Unsupported modes or malformed datasets must be rejected explicitly rather than partially interpreted.

## 2.3 Hard-coded CSV/FCS discovery/UI

Known examples in v4.4.1:

- `vflow/legacy/vflow_app.py` — “Select CSV or FCS Files” picker and wording.
- `vflow/ui/folder_scan_dialog.py` — scans only `.csv` / `.fcs`.
- `vflow/ui/batch_stats_dialog.py` — CSV/FCS-specific filters.
- `vflow/services/batch_stats_export.py` — CSV/FCS extension lists.
- `vflow/services/concat_export.py` — raw extension logic and CSV-only semantics.

Do not patch each with another independent extension list. Create one authoritative registry and consume it everywhere.

## 2.4 Workspace foundation

`vflow/workspace/model.py` already provides:

- `FileReference` with absolute/relative path, size, and sampled SHA-256 fingerprint;
- `SampleReference.active`;
- `SampleReference.excluded`;
- atomic workspace JSON writing;
- reference relinking/identity validation;
- a reference-only workspace design.

This is the correct foundation for both derivative provenance and statistical audit traceability.

Current `SCHEMA = 1`. Adding audit persistence should be treated as a schema evolution with a backward-compatible migration path rather than breaking v4.4.1 workspaces.

## 2.5 Existing exclusion behavior

Existing dataset ownership already separates active and excluded files (`vflow/app/dataset.py`), and `FlowApp._exclude_file()` moves a sample into the excluded set.

The new audit UI should call/reuse this existing exclusion behavior. It must **not** create a second independent exclusion state.

---

# 3. Workstream A — Universal low-friction data ingestion

## 3.1 Architecture: one reader registry

Introduce a centralized format layer. Exact names can vary, but a structure such as this is recommended:

```text
vflow/io/
    __init__.py
    registry.py
    models.py
    derivatives.py
    readers/
        __init__.py
        csv_reader.py
        fcs_reader_adapter.py
        lmd_reader.py
        mqd_reader.py
```

Do not unnecessarily move the mature `vflow/core/fcs_reader.py`; it can remain the low-level FCS implementation while an adapter exposes it through the registry.

### Suggested reader contract

```python
class FlowFormatReader(Protocol):
    format_id: str
    extensions: tuple[str, ...]

    def probe(self, path: str) -> ProbeResult: ...
    def read(self, path: str) -> FlowReadResult: ...
```

`probe()` must inspect content/signature where possible, not only the extension.

Suggested normalized result:

```python
@dataclass
class FlowSamplePayload:
    dataframe: pd.DataFrame
    logical_name: str
    source_path: str
    source_member_id: str | None = None
    source_format: str = ""
    metadata: dict = field(default_factory=dict)
    materialized_path: str | None = None

@dataclass
class FlowReadResult:
    samples: list[FlowSamplePayload]
    warnings: list[str] = field(default_factory=list)
```

The one-to-many shape is deliberate. Ordinary CSV/FCS/MQD/LMD will normally return one sample, but a container that legitimately contains several logical datasets must not force an architectural rewrite later.

### Central registry API

At minimum provide:

```python
supported_flow_extensions()
supported_flow_filetypes_for_tk()
probe_flow_format(path)
reader_for(path)
read_flow_source(path)
```

Then make `vflow/core/data_io.read_flow_data_file()` a compatibility facade over the new registry for paths resolving to exactly one logical sample.

Unknown files must raise a specific error such as:

```text
UnsupportedFlowFormatError
```

rather than falling through to `pandas.read_csv()`.

---

# 4. FCS support: 1.0 through 3.2

## 4.1 Required behavior

The reader must support, with benchmark fixtures:

- FCS 1.0 compatibility;
- FCS 2.0;
- FCS 3.0;
- FCS 3.1;
- FCS 3.2.

Existing v4.4.1 compatibility fixes and strict malformed-file behavior must be preserved unless a normative standard difference requires a version-specific path.

## 4.2 FCS 3.2 is a parser feature, not a header feature

The implementation must account for FCS 3.2-specific representation rules, especially mixed measurement data types in one dataset, and new/changed metadata semantics relevant to correctly identifying measurements.

Do not silently coerce mixed integer/floating measurements in ways that lose exact values. Preserve an appropriate pandas/numpy dtype per channel where practical.

The reader must continue to validate:

- segment offsets/bounds;
- required metadata for the relevant FCS version;
- TEXT escaping/delimiters;
- declared byte order;
- per-parameter widths/types/ranges;
- list-mode compatibility;
- payload length;
- channel-name ambiguity;
- optional supplemental TEXT where applicable;
- compensation/spillover metadata where present;
- CRC/integrity information where the standard supplies it and it is present.

Do not add compensation mathematics or transform raw values automatically. Preserve metadata and existing vFlow semantics.

## 4.3 FCS 1.0

FCS 1.0 is historically compatible with later standard evolution but is old enough that a dedicated validated compatibility path is required. Do not claim support without at least one real or authoritative fixture and reference-decoded values.

If the supplied implementation environment lacks a trustworthy FCS 1.0 fixture initially, build the parser path and mark the release acceptance item **blocked pending fixture** rather than fabricating support.

## 4.4 FCS tests

Add fixtures covering at minimum:

```text
fcs10/
fcs20/
fcs30/
fcs31/
fcs32/
```

For 3.2 include a fixture that actually exercises **mixed per-parameter representations**; a 3.2 file containing only legacy-compatible homogeneous float data is insufficient.

Each fixture should validate:

- event count;
- parameter count;
- parameter order;
- parameter names;
- representative first/middle/last values;
- complete-column checksum where possible;
- metadata expected by vFlow;
- no dtype corruption;
- round-trip downstream gating/plotting compatibility.

---

# 5. LMD support

## 5.1 Scope

Support Beckman Coulter LMD sources only to the extent required to recover their embedded event dataset(s) for vFlow.

LMD files from relevant Beckman instruments are known to contain FCS-compatible portions. Prefer the highest-quality/most modern embedded representation when more than one equivalent FCS portion exists (for example an FCS 3.0 portion over a legacy 2.0 display representation), while preserving provenance of which embedded member was selected.

## 5.2 Decoder

The LMD reader should:

1. verify LMD/container identity;
2. locate embedded FCS dataset boundaries safely;
3. delegate event decoding to the common FCS parser rather than implementing a second FCS decoder;
4. return the normalized payload;
5. materialize the decoded event table to `.vflow.csv` beside the LMD source;
6. write derivative provenance metadata atomically.

Do not locate embedded FCS by a naive unbounded byte-string match alone. Validate candidate headers, offsets, declared segments, and payload bounds before accepting a candidate.

If multiple logical datasets are present, expose them separately and create deterministic derivative names.

---

# 6. MQD support

## 6.1 Scope

Target Miltenyi:

- MACSQuant;
- MACSQuant Tyto;
- MQD acquisition files that contain event data usable by vFlow.

Miltenyi software stores acquisition data as MQD and can export MQD to FCS/CSV. vFlow should remove that manual step for the user.

## 6.2 Do not guess the format

MQD is proprietary. The implementation must **not** infer event values from undocumented structures and then call the result supported without validation.

A proper MQD acceptance corpus must include, from the **same acquisition**:

```text
original.mqd
vendor_export.fcs
vendor_export.csv   # strongly preferred
```

The decoder can be reverse-engineered only for the information vFlow requires:

- event-level numeric measurements;
- channel/parameter identity and order;
- event count;
- ranges/dtypes required to reproduce values;
- useful sample metadata;
- compensation/spillover metadata if present and applicable;
- time/index measurements if present.

Do not attempt to reproduce:

- vendor plots;
- vendor worksheets;
- vendor gating strategies;
- reports;
- acquisition-control features;
- unrelated proprietary metadata.

## 6.3 Acceptance criterion

“MQD opens” is not sufficient.

For each validated MQD fixture, compare to the vendor export from the same acquisition:

- identical event count;
- identical channel count and order;
- correct names;
- exact values when the vendor export is value-preserving;
- otherwise documented transformation/tolerance with a reason;
- correct missing/non-finite handling;
- preserved integer identity where relevant;
- no row shifts/channel shifts.

Use whole-column hashes/checksums where exact equality is possible.

If native MQD decoding cannot yet be validated because representative MQD/reference pairs are absent, keep the format registry and derivative infrastructure complete but mark MQD scientific acceptance as blocked pending corpus. Do not silently substitute a vendor-software automation dependency unless explicitly approved later.

---

# 7. Proprietary derivative CSV behavior

## 7.1 Naming

Default single-dataset names:

```text
Sample.mqd  → Sample.vflow.csv
Sample.lmd  → Sample.vflow.csv
```

For multiple logical members:

```text
Plate.lmd → Plate__dataset-01.vflow.csv
          → Plate__dataset-02.vflow.csv
```

Never overwrite:

- `Sample.csv`;
- an unrelated pre-existing `Sample.vflow.csv`;
- any file not provably generated from the exact source by vFlow.

If the normal derivative name exists but provenance does not match, generate a collision-safe name such as:

```text
Sample.vflow-<short_source_fingerprint>.csv
```

## 7.2 Provenance sidecar

Create a small automatic sidecar, e.g.:

```text
Sample.vflow.meta.json
```

Minimum content:

```json
{
  "schema": 1,
  "generated_by": "vFlow 4.4.3",
  "decoder_version": "...",
  "source_format": "mqd",
  "source_path_basename": "Sample.mqd",
  "source_size": 123,
  "source_fingerprint": "sampled-sha256:...",
  "source_member_id": null,
  "event_count": 12345,
  "columns": ["..."],
  "generated_csv_fingerprint": "..."
}
```

Use the existing workspace `fingerprint()` strategy or a centralized equivalent. Avoid duplicating incompatible fingerprint algorithms.

## 7.3 Reuse/staleness

On every proprietary load:

1. probe source;
2. locate candidate derivative + sidecar;
3. validate source fingerprint/size + decoder schema/version;
4. validate derivative existence and fingerprint;
5. if valid, reuse without decoding;
6. otherwise regenerate atomically.

A changed/replaced source with the same filename must never reuse stale events.

## 7.4 Atomic writes

Write CSV and metadata to temporary files in the target directory, flush/fsync where practical, then replace atomically. Never leave a half-written `.vflow.csv` that a later launch may trust.

## 7.5 Read-only source directories

Normal requirement: derivative next to source.

Exceptional fallback when writing beside the source is impossible:

- materialize under an application-controlled cache keyed by source fingerprint;
- load successfully;
- preserve the original source path as authoritative;
- show a non-blocking status/warning that the derivative could not be stored beside the source;
- do not ask the user to choose another location in the normal flow.

---

# 8. Source identity and workspace behavior for proprietary data

The workspace must reference the **original MQD/LMD**, not only the generated CSV.

Recommended DataFrame attrs:

```python
df.attrs["vflow_source_path"] = original_source_path
df.attrs["vflow_source_format"] = "mqd"  # or lmd/fcs/csv
df.attrs["vflow_materialized_path"] = generated_csv_path_or_none
df.attrs["vflow_source_member_id"] = member_id_or_none
```

On workspace reopen:

```text
resolve original source
    ↓
validate/recreate derivative if proprietary
    ↓
load normalized DataFrame
```

Deleting a generated `.vflow.csv` must not permanently break the workspace; it is reproducible and should be regenerated.

Relinking continues to operate on original source identity.

If a single proprietary container produces multiple logical samples, extend sample provenance so each logical sample has the same original `FileReference` plus a stable `source_member_id`. Do not copy the original container once per logical sample.

---

# 9. Replace all independent format lists

Use the central format registry in:

- normal file picker;
- drag/drop, if present;
- folder scan;
- batch-stat target discovery;
- preview lists;
- workspace reload;
- file-load planning;
- any “supported files” wording.

Default user-facing category should become something like:

```text
Supported data files (*.csv *.fcs *.lmd *.mqd)
```

Do not keep CSV/FCS-specific `both` logic as the global abstraction. Where a feature truly has a narrower semantic scope, name that scope explicitly.

### Concatenation

`concat_export.py` is currently explicitly CSV-oriented. Do not casually change scientific behavior by concatenating arbitrary FCS/proprietary files just because the registry can read them.

For v4.4.3 either:

1. keep “Concatenate” explicitly as a tabular CSV operation and update wording accordingly; generated proprietary `.vflow.csv` files are ordinary CSVs if selected directly; or
2. refactor concatenation to operate on normalized DataFrames with explicit provenance after dedicated tests.

Option 1 is lower risk and acceptable for this handoff.

---

# 10. Workstream B — Statistical Audit domain model

## 10.1 Two audit types

Implement two related but distinct analyses:

```text
A. Sample Concordance / QC Audit
B. Hierarchical Replication Audit
```

Both are within-group/post-acquisition audits.

They are **not** comparisons of treatment effects.

## 10.2 Audit identity

Each run must receive an immutable ID and name, for example:

```text
QC-20261003-001  Control — parent population
HIER-20261003-001 Treatment A — P2
```

The user may rename the display name, but historical result content must not be rewritten when later decisions change.

## 10.3 Multiple audits per workspace

A workspace can contain any number of audits, e.g.:

```text
Control QC
Treatment A QC
Treatment B QC
Control P2 QC
Control hierarchy audit
Treatment A hierarchy audit
```

Audits must be independently selectable/reviewable and never replace one another implicitly.

---

# 11. Workspace audit persistence

## 11.1 Do not bloat the workspace JSON with giant matrices

Follow the existing reference-only philosophy.

Recommended design:

```python
@dataclass
class AuditReference:
    audit_id: str
    name: str
    audit_type: str
    created_at: str
    result: FileReference
    selected_sample_ids: list[str]
    population_label: str
    status_summary: dict
    decision_history: list[dict]
```

Add e.g.:

```python
Workspace.audits: dict[str, AuditReference]
```

The full immutable calculation payload should live in an external generated audit bundle, for example:

```text
<workspace stem>_audits/
    <audit_id>.vflowaudit.json.gz
```

This is generated analysis state, not a duplicate of source data.

XLSX and CSV are **exports of the audit bundle**, not the canonical storage format.

## 11.2 Audit bundle must contain enough to reproduce/understand the result

At minimum:

- audit schema/version;
- audit ID/name/type;
- vFlow version;
- analysis implementation version;
- timestamp;
- selected sample IDs/display names;
- original source paths + fingerprints;
- selected population/tab/lineage;
- a resolved gate snapshot per sample when sample-specific gate overrides exist;
- selected variables and their order;
- numeric eligibility/exclusion reasons;
- finite/missing counts;
- transformation/normalization policy;
- algorithm parameters and deterministic random/projection seed;
- all pairwise distances;
- all sample scores;
- flags;
- hierarchy mapping;
- variance/ICC results where requested;
- influence results;
- warnings/model failures;
- no user decision silently folded into the original statistical result.

## 11.3 Population snapshot is essential

Because v4.4.1 supports sample-specific gate overrides, storing only a gate ID is insufficient.

An audit must capture the **resolved population definition actually applied to each sample at audit time**. Later gate edits must not mutate the historical meaning of the audit.

Reuse existing gate serialization/plain-dict helpers and lineage resolution rather than inventing a new gate geometry format.

## 11.4 Workspace schema migration

Bump workspace schema (recommended `SCHEMA = 2`) and implement migration from schema 1.

Requirements:

- all valid v4.4.1 schema-1 workspaces must still open;
- missing `audits` migrates to `{}`;
- saving after migration produces schema 2;
- invalid future schemas still fail closed;
- add dedicated migration tests.

---

# 12. Audit type A — Sample Concordance / QC Audit

## 12.1 Scientific question

Given samples the user declares should be comparable within the same condition/procedure/population:

> Is one sample distributionally much more different from its peers than the peers are from each other?

The audit may flag a sample as **discordant / review recommended**. It must not claim why the difference exists.

Use terms such as:

```text
Concordant
Mildly discordant
Flagged for review
Low-N review candidate
Insufficient peers for classification
```

Avoid:

```text
Bad sample
Failed sample
Experimental failure
Must remove
```

## 12.2 Variable eligibility

Default candidate variables:

- numeric pandas columns;
- shared across every selected sample;
- at least a minimum number of finite values in each sample;
- non-constant after finite-value filtering.

Do not assume channel semantics.

Present all eligible numeric variables with all selected by default; allow the user to deselect variables.

Record excluded variables and reasons such as:

```text
non_numeric
missing_in_sample
insufficient_finite_values
constant_or_zero_scale
```

## 12.3 Per-variable distribution audit

For each selected variable `v` and sample pair `(i, j)`:

1. use every finite value in each sample for that variable;
2. compute first Wasserstein distance `W1(i,j,v)`;
3. normalize it by a robust pooled scale so variables can be ranked:

```text
scale_v = pooled IQR
fallback = 1.4826 × pooled MAD
fallback = pooled SD
if all are zero/non-finite → variable not informative
```

Store both raw and normalized distance.

Also export descriptive statistics per sample/variable:

- count;
- missing/non-finite count;
- mean;
- median;
- standard deviation;
- MAD;
- Q05;
- Q25;
- Q75;
- Q95;
- IQR;
- min/max if finite and useful.

Do not use a per-variable significance p-value as the primary QC criterion. Large event counts would make trivial distribution differences appear “significant,” and selected variables are correlated.

### Per-sample/per-variable discordance score

For sample `i`:

```text
variable_peer_distance(i,v)
    = median_j!=i normalized_W1(i,j,v)
```

Also calculate a peer-cohesion isolation ratio:

```text
variable_isolation_ratio(i,v)
    = median distance from i to peers
      / median pairwise distance among peers excluding i
```

Handle denominator≈0 explicitly; if peers are essentially identical and sample `i` is not, report a high/infinite-isolation condition in a bounded machine-readable way rather than numeric overflow.

These values drive the “main contributing variables” explanation.

## 12.4 Multivariate audit

Use **Sliced Wasserstein Distance (SWD)** across all selected numeric variables after robust pooled scaling.

Recommended normalization per variable:

```text
z = (x - pooled median) / robust_scale
```

where robust scale follows the IQR/MAD fallback above.

Important requirements:

- all valid rows should contribute by default;
- no silent random event subsampling;
- use a deterministic set of projection directions;
- process projections/chunks in a memory-bounded way;
- use the same projection set for every sample pair in one audit;
- record `n_projections` and seed/derivation in the audit bundle;
- default e.g. 64 deterministic directions, benchmarked for stability/performance;
- expose the parameter in audit provenance, not necessarily in the simple UI.

For a row to enter multivariate SWD it must have finite values across the selected variables. Record per-sample multivariate complete-row count and fraction. If too few complete rows remain, global SWD for that sample must be marked unavailable rather than silently imputed.

Do not median-impute missing event measurements in v4.4.3.

Output:

```text
sample × sample global SWD matrix
```

and per-sample:

```text
global_peer_distance(i) = median SWD(i,j)
global_isolation_ratio(i)
```

## 12.5 Flagging policy

This is a review flag, not a deletion rule.

Implement deterministic, explicit criteria and export the exact reason codes.

Recommended default policy:

### N = 1

No comparison possible.

```text
status = insufficient_peers
```

### N = 2

Report pairwise differences only. Do not identify which sample is the outlier.

```text
status = pairwise_only
```

### N = 3–4

Small-N outlier classification is intrinsically weak.

Allow a conservative **low-N review candidate** when:

- global isolation ratio is very large relative to peer cohesion (default threshold 2.5), **and**
- either at least two variables show similarly high isolation or the global multivariate difference is extreme and numerically stable across projection-repeat validation.

Always label the result `low_n` and never “confirmed outlier.”

### N ≥ 5

Compute robust z-score across sample global peer-distance scores:

```text
robust_z_i = 0.67448975 * (score_i - median(scores)) / MAD(scores)
```

with explicit zero-MAD handling.

Default review rule can be:

```text
flag if robust_z >= 3.5
OR
(global_isolation_ratio >= 2.5 AND multiple variable-level contributors agree)
```

The exact thresholds must live in a versioned policy/config constant and be written to every audit. They must be easy to revise later without changing historical audits.

Do not present the threshold as proof of technical failure.

## 12.6 Stability check for SWD flagging

Because SWD uses projected directions, a flagged multivariate sample should be re-evaluated using a second deterministic projection set (or doubled projections) before finalizing a flag. Record whether the flag was stable.

This is **projection stability**, not particle resampling and not a biological p-value.

## 12.7 Output explanation

For every flagged sample include:

- global SWD peer score;
- isolation ratio;
- robust z if available;
- low-N indicator;
- top contributing variables ranked by variable isolation/peer distance;
- per-variable distribution summaries;
- data completeness warnings;
- projection stability;
- explicit text equivalent to:

> “This sample is distributionally discordant from the selected peer group. The audit does not determine whether the cause is technical or biological.”

---

# 13. Audit type B — Hierarchical Replication Audit

## 13.1 Scientific question

Retain lower-level biological information without pretending particles/cells from the same biological replicate are independent biological replicates.

Conceptual hierarchy:

```text
biological replicate
    → sample / subsample / region / repeated acquisition
        → particle / cell / event
```

vFlow deliberately uses the neutral term **nested sample**. The program does not need to know whether that file represents a region, time point, acquisition, imaging field, aliquot, etc.

## 13.2 User mapping

For selected files, the user assigns a biological replicate ID in a simple table:

| vFlow sample | Biological replicate |
|---|---|
| region_01.csv | Bio1 |
| region_02.csv | Bio1 |
| region_03.csv | Bio1 |
| region_04.csv | Bio2 |

The vFlow sample/file is the nested-sample level; DataFrame rows are particles/cells/events.

Do not overload workspace gate groups for this. Store the hierarchy mapping inside the audit config unless a future explicit metadata system is introduced.

## 13.3 Required counts

Always report:

```text
N biological replicates
N nested samples total
N nested samples per biological replicate
N particles/events total
N particles/events per nested sample
```

Use uppercase/labeled concepts in UI/export rather than reporting one misleading single `n`.

Example:

```text
Biological units: 5
Nested samples: 50
Particles: 487,219
```

## 13.4 Variance model

For each selected variable, fit/estimate the nested random-intercept structure:

```text
y_ijk = μ + B_i + S_j(i) + ε_ijk
```

where:

- `B_i` = biological-replicate component;
- `S_j(i)` = nested-sample-within-biological-replicate component;
- `ε_ijk` = particle/cell/event component.

Primary output:

```text
sigma2_bio
sigma2_nested_sample
sigma2_particle
variance proportion at each level
ICC_bio
ICC_same_nested_sample
model/convergence status
```

Interpretation:

```text
ICC_bio = sigma2_bio / total_variance
ICC_same_nested_sample = (sigma2_bio + sigma2_nested_sample) / total_variance
```

### Estimation method

Use a statistically recognized variance-component estimator, preferably REML for the nested random-intercept model.

Implementation options:

- use `statsmodels` MixedLM if benchmarked memory/runtime is acceptable on representative particle counts; or
- implement an algebraically equivalent sufficient-statistics estimator optimized for this exact nested random-intercept structure.

**Do not silently downsample events to make the model fit.**

If the full model cannot be estimated:

- return `model_status` and a clear reason;
- still export raw hierarchy counts/descriptives;
- do not invent missing variance components;
- do not silently fall back to a numerically different estimator without recording it.

Boundary estimates at zero are allowed and must be represented as such with a boundary/convergence indicator.

### Identifiability handling

Examples:

- one nested sample per biological replicate → nested-sample variance is not separately identifiable from lower-level structure in the same way; report appropriately or fit a reduced model;
- fewer than three biological replicates → label variance-component interpretation as low-N/descriptive;
- a biological replicate with one nested sample while others have several → allow unbalanced design, record counts, and do not discard it automatically.

## 13.5 No final between-condition test

Do not add a condition fixed effect in v4.4.3.

The hierarchy audit is descriptive/structural. The user will perform final condition comparisons elsewhere using the exported information/data and a model appropriate to the experiment.

---

# 14. Biological-replicate influence / leave-one-out audit

The feature must address the user's concern that one biological replicate may drive the apparent behavior because its lower-level samples/particles differ markedly.

For each selected variable:

1. compute the full-data hierarchy result/descriptive center;
2. remove each biological replicate in turn;
3. recompute the defined influence outputs;
4. report how much the result changes.

At minimum export:

```text
full equal-biological-replicate-weighted center
LOO center for each biological replicate
absolute change
relative/standardized change
full variance components
LOO variance components where estimable
```

Higher-level summaries must give each biological replicate appropriate equal inferential standing rather than allowing a biological replicate with more particles to dominate simply because it contributed more rows.

Flag language:

```text
Bio5: influential
```

not:

```text
Bio5: invalid
```

Influence is evidence for review, not an exclusion command.

---

# 15. Population/data selection for audits

The audit should operate on the user-selected vFlow population.

Possible sources:

- root/all events;
- current workspace population tab;
- selected resolved gate/subpopulation.

Use existing population/gate evaluation services and the per-sample resolved gate geometry.

Important invariant:

> A statistical audit must see exactly the rows corresponding to the resolved population for each selected sample at audit time.

If a required gate/population is unavailable for one selected sample, fail the transaction before calculating a partial peer set unless the user explicitly removes that sample from the audit selection.

Do not silently compare different populations.

---

# 16. User decisions and sample exclusion

## 16.1 Statistical result is immutable

An audit produces:

```text
Sample X → flagged for review
```

That result must remain historically unchanged.

## 16.2 User decision is a separate append-only event

Suggested event:

```json
{
  "timestamp": "...",
  "sample_id": "...",
  "action": "exclude",
  "reason_code": "data_quality",
  "note": "..."
}
```

Recommended actions:

```text
keep / reviewed
exclude
restore
note
```

Suggested optional reason codes:

```text
experimental_issue
sample_preparation_issue
data_quality
known_biological_or_experimental_reason
other
no_reason_supplied
```

Do not require a reason to exclude, but preserve one when supplied.

## 16.3 Reuse existing exclusion state

“Exclude sample” from the audit result should invoke the existing dataset/workspace exclusion workflow.

Do not auto-exclude when a flag is created.

If the user later restores the sample, append a restore event; do not delete the earlier exclusion decision from history.

An exclusion performed elsewhere in the main UI should change workspace sample state as it already does; do not retroactively claim that a specific audit caused that decision unless it originated through the audit action or the user explicitly links a note.

---

# 17. Minimal UI — keep scope small

The user explicitly prefers a simple UI rather than a large statistics application.

## 17.1 Entry point

Add a workspace/menu action such as:

```text
Statistical Audit…
```

## 17.2 Run dialog

Keep it compact:

### Audit type

```text
○ Sample concordance / QC
○ Hierarchical replication
```

### Samples

Workspace checklist/table.

### Population

Default to the current population/tab, clearly shown.

### Variables

Shared eligible numeric variables, selected by default, with select-all/none.

### Hierarchy-only mapping

Simple editable biological replicate ID column.

### Audit name

Auto-generated but editable.

### Run

Do not expose advanced statistical tuning unless needed for troubleshooting. Algorithm parameters remain recorded in provenance.

## 17.3 Results view

A simple table is sufficient.

Example QC view:

| Sample | Status | Global discordance | Isolation | Top contributors | Current state |
|---|---|---:|---:|---|---|
| C1 | Concordant | 0.14 | 1.02 | — | Included |
| C2 | Concordant | 0.12 | 0.96 | — | Included |
| C3 | Review | 0.71 | 4.8 | Distance, BG2, Area | Included |

Actions:

```text
Review details
Mark keep/reviewed
Exclude from analysis
Restore (if excluded)
Add note
Export…
```

A details pane/table can show variable-level metrics. Do not build a new plotting/dashboard framework in v4.4.3.

## 17.4 Workspace audit list

Add a compact workspace section such as:

```text
Statistical audits
  Control QC                  03 Oct 2026
  Treatment A QC              03 Oct 2026
  Control hierarchy           03 Oct 2026
```

Opening an audit reads its stored immutable audit bundle; it does not silently rerun with current gates/data.

If source fingerprints no longer match current files, display that the historical audit remains valid for its recorded snapshot but current source identity has changed.

---

# 18. Export behavior

## 18.1 User choice

Export dialog:

```text
○ Excel workbook (.xlsx)   Recommended
○ CSV package
```

The audit can be exported again later without rerunning because the canonical audit bundle is stored with the workspace.

## 18.2 Excel workbook

Add `openpyxl` as a dependency (or a comparably lightweight XLSX writer, but do not use a GUI office dependency).

Recommended sheets:

### `Summary`

- audit ID/name/type;
- date/time;
- vFlow version;
- analysis version;
- population;
- selected samples;
- selected variable count;
- biological/nested/particle counts if relevant;
- status counts;
- warnings;
- plain-language interpretation caveat.

### `Sample_QC`

One row per sample:

- sample ID/name;
- original source;
- source format;
- event count;
- multivariate complete count;
- global peer distance;
- global isolation ratio;
- robust z if available;
- projection stability;
- status;
- top contributing variables;
- current included/excluded state;
- latest audit decision.

### `Variable_QC`

One row per sample × variable:

- descriptive statistics;
- finite/missing counts;
- peer distance;
- isolation ratio;
- normalized/raw distance summaries;
- rank/contribution.

### `Global_Distance_Matrix`

Square sample × sample SWD matrix.

### `Variable_Distances`

Machine-readable long form:

```text
variable, sample_a, sample_b, raw_w1, normalized_w1
```

### `Variable_Matrices`

Human-readable stacked matrix blocks for each variable when workbook size is reasonable. If there are too many variables for practical blocks, include a note pointing to `Variable_Distances`, which is authoritative.

### `Hierarchy`

- sample → biological replicate mapping;
- nested sample counts;
- particle counts;
- completeness.

### `Variance_Components`

Per variable:

- sigma² biological;
- sigma² nested sample;
- sigma² particle;
- proportions;
- ICCs;
- estimator;
- convergence/status;
- warnings.

### `Influence`

Per variable × omitted biological replicate:

- full estimate;
- leave-one-out estimate;
- delta;
- standardized delta;
- optional variance-component deltas;
- influence status.

### `Flags_Decisions`

Chronological flag/decision history:

- statistical flag reason;
- keep/exclude/restore/note events;
- timestamps;
- reason codes;
- notes.

### `Provenance`

- source fingerprints;
- resolved population/gate hashes/snapshots references;
- variable order;
- robust scaling rules;
- SWD projection count/seed;
- thresholds;
- software versions;
- dependency versions;
- audit bundle schema;
- model settings.

## 18.3 Workbook formatting

Keep formatting functional:

- freeze header rows;
- autofilter tabular sheets;
- sensible column widths;
- numeric formats;
- no decorative merged-cell complexity;
- use conditional formatting sparingly for status/flags;
- do not encode meaning only by color.

## 18.4 CSV package

CSV export should produce multiple machine-readable files using one chosen base name, e.g.:

```text
Audit_Control__summary.csv
Audit_Control__sample_qc.csv
Audit_Control__variable_qc.csv
Audit_Control__global_distance_matrix.csv
Audit_Control__variable_distances.csv
Audit_Control__hierarchy.csv
Audit_Control__variance_components.csv
Audit_Control__influence.csv
Audit_Control__flags_decisions.csv
Audit_Control__provenance.csv
```

Alternatively a ZIP containing these CSVs is acceptable if it reduces filesystem clutter, but the user must still be explicitly choosing “CSV package.”

CSV content must be sufficient to reconstruct matrices and reproduce interpretation. XLSX and CSV must be generated from the same canonical audit bundle.

---

# 19. Statistical engine implementation notes

Recommended modules:

```text
vflow/statistics/
    __init__.py
    models.py
    variable_eligibility.py
    wasserstein.py
    sliced_wasserstein.py
    discordance.py
    hierarchy.py
    influence.py
    audit_runner.py
    audit_serialization.py
    audit_export_xlsx.py
    audit_export_csv.py
```

Keep these Tk-free and unit-testable.

### Dependencies

Existing:

```text
numpy
pandas
scipy
```

Likely additions:

```text
openpyxl>=3.1
statsmodels>=0.14   # only if chosen after performance benchmarking for REML
```

Do not add a large optimal-transport library merely for 1-D/Sliced Wasserstein unless there is a demonstrated need; SciPy + NumPy are sufficient for the planned algorithms.

### Long-running execution

Audit calculation must not freeze Tk.

Run calculations in a worker (thread/process selected according to numerical library behavior) with:

- progress stages;
- cancellation;
- atomic result commit only after successful completion;
- no partially registered workspace audit on failure/cancel;
- no mutation of sample exclusion state during calculation.

Example progress stages:

```text
Preparing populations
Validating variables
Per-variable distributions
Multivariate distances
Hierarchy variance components
Influence analysis
Writing audit bundle
```

---

# 20. Reproducibility requirements

Every audit must be deterministic given:

- the same source fingerprints;
- the same resolved population snapshots;
- same selected variables/order;
- same algorithm version/settings.

Use deterministic projection generation for SWD.

Do not use Python's process-randomized `hash()` as a persisted seed.

Use a stable SHA-256-derived integer seed from serialized audit configuration or an explicit fixed algorithm seed.

Floating results should serialize with enough precision for later export/review.

Do not serialize NaN/Infinity in JSON; use `null` + status/reason fields.

---

# 21. Benchmark/test corpus expansion

Extend the existing benchmark philosophy rather than relying only on unit tests.

Recommended structure:

```text
benchmark/
  formats/
    fcs10/
    fcs20/
    fcs30/
    fcs31/
    fcs32/
    lmd/
    mqd/
    malformed/
  statistics/
    qc_concordant/
    qc_single_shifted_sample/
    qc_multivariate_only_shift/
    qc_small_n/
    hierarchy_balanced/
    hierarchy_unbalanced/
    hierarchy_influential_bio/
    hierarchy_zero_component/
    missing_values/
```

## 21.1 Format truth fixtures

For proprietary data:

```text
source.mqd
reference_vendor_export.fcs
reference_vendor_export.csv
expected.json
```

and similarly LMD/FCS reference where available.

`expected.json` can contain:

- row/column counts;
- ordered column names;
- representative values;
- column hashes;
- source/derivative expectations.

## 21.2 Synthetic statistics truth fixtures

Create synthetic data where ground truth is known.

### Concordant set

Five samples generated from the same distributions with different row counts. Expect no review flag.

### Single shifted sample

Four comparable samples + one strongly shifted in several variables. Expect that sample to rank highest and be flagged for review.

### Multivariate-only discordance

Construct a sample where marginals remain similar but inter-variable joint structure differs. Per-variable flags should be weak while SWD identifies global discordance.

### Small N

- N=1 → insufficient;
- N=2 → pairwise only;
- N=3 → low-N semantics, no overclaim.

### Hierarchy balanced

Known simulated random-effects variances. Estimated components/ICCs should fall within predetermined tolerances.

### Hierarchy unbalanced

Different particle counts and nested-sample counts. Ensure one biological replicate is not given extra biological weight merely because it has more events.

### Influential biological replicate

One biological replicate deliberately shifted. Expect leave-one-bio-out influence to identify it as influential without marking it invalid.

### Missingness

Validate finite-value handling, multivariate complete-row reporting, and no silent imputation.

---

# 22. Required regression tests

At minimum add tests for:

## Format registry

- extension list has one source of truth;
- uppercase/lowercase extensions;
- content probing beats misleading extension;
- unknown file fails with unsupported-format error;
- existing CSV behavior preserved;
- file picker/folder scan/batch discovery use registry.

## Proprietary derivatives

- first load creates `.vflow.csv` + provenance;
- second load reuses valid derivative;
- deleted derivative regenerates;
- modified source invalidates derivative;
- modified derivative invalidates/rebuilds;
- pre-existing unrelated `.vflow.csv` never overwritten;
- failed conversion leaves no trusted partial file;
- read-only fallback works;
- workspace refers to original proprietary source;
- relink works from original source;
- derivative deletion followed by workspace reopen regenerates.

## FCS

- old v4.4.1 FCS fixtures remain green;
- FCS 1.0 fixture;
- FCS 2.0;
- FCS 3.0;
- FCS 3.1;
- real FCS 3.2 mixed-type fixture;
- malformed offsets;
- duplicate channel ambiguity;
- endian variants where standard permits;
- supplemental text;
- relevant integrity/CRC behavior;
- values/checksums against reference decoder.

## LMD

- embedded FCS detected;
- correct embedded representation selected;
- event equivalence to reference export;
- invalid false `FCS` byte patterns ignored;
- multiple dataset/member handling if fixture available.

## MQD

- probe correctness;
- same-acquisition equivalence to vendor exports;
- channel/event/order checks;
- decoder fails closed on unknown MQD variant;
- no “best effort” fabricated data.

## Audit QC

- numeric eligibility;
- W1 exact/simple known examples;
- robust scaling fallback;
- pairwise symmetry + zero diagonal;
- all finite rows used;
- deterministic SWD;
- multivariate shift detection;
- low-N semantics;
- robust-z zero-MAD behavior;
- contributor ranking;
- no automatic exclusion;
- immutable statistical result after decision.

## Hierarchy

- mapping validation;
- balanced simulated variance recovery;
- unbalanced design;
- reduced/unidentifiable model handling;
- boundary-zero variance;
- low biological N warning;
- influence identifies known influential biological replicate;
- lower-level particle counts do not change biological-unit count.

## Workspace/audit persistence

- schema-1 → schema-2 migration;
- multiple audits persist/reopen;
- missing audit bundle is reported without corrupting workspace;
- relocated audit bundle can be relinked;
- historical gate snapshot preserved after gates are edited;
- source replacement is detectable by fingerprint;
- exclude/restore audit decision history persists;
- current sample exclusion state remains the existing authoritative state.

## Export

- XLSX opens with all required sheets;
- XLSX values match canonical audit bundle;
- global matrix cell values correct;
- CSV package values match XLSX/canonical bundle;
- no NaN/Inf invalid JSON provenance;
- long-form variable distances reconstruct expected matrices.

---

# 23. Performance expectations

## 23.1 File loading

- Reopening a previously decoded proprietary source should be close to ordinary CSV load cost because the valid derivative is reused.
- Fingerprinting must remain bounded for multi-GB sources (reuse the existing sampled SHA-256 approach unless stronger validation is demonstrably needed).
- Do not read an entire multi-GB source twice unnecessarily.

## 23.2 Statistical audit

- per-variable W1 should use efficient sorted/weighted routines and all finite values;
- SWD should be chunked/memory-bounded;
- avoid building one giant pooled copy of all samples if unnecessary;
- hierarchy analysis should process variables sequentially/reuse group indexes;
- UI stays responsive;
- cancellation leaves workspace unchanged;
- benchmark representative datasets from small to large.

Record runtime and peak-memory benchmark numbers in release validation.

---

# 24. Implementation milestones

## Milestone 0 — Baseline lock

Before changes:

- run full v4.4.1 tests;
- run current benchmark corpus;
- record hashes/results;
- do not proceed from an already-broken baseline.

## Milestone 1 — Format registry without behavior change

- add registry/contracts;
- route CSV/FCS through it;
- update picker/folder/batch discovery;
- keep existing CSV/FCS numerical behavior identical;
- run full regression.

## Milestone 2 — FCS expansion

- version-aware reader refactor;
- FCS 1.0 compatibility path;
- FCS 3.2 true mixed-type support;
- authoritative fixtures/reference validation;
- full regression.

## Milestone 3 — LMD + derivative infrastructure

- derivative service;
- provenance/staleness;
- atomic writes;
- LMD extraction through FCS parser;
- workspace original-source identity;
- full regression.

## Milestone 4 — MQD

- collect same-acquisition MQD/FCS/CSV truth corpus;
- implement only validated structures;
- event-level equivalence tests;
- fail closed on unsupported variants;
- full regression.

If corpus is unavailable, explicitly report MQD as blocked rather than marking milestone complete.

## Milestone 5 — Audit domain + workspace schema

- audit model/bundle serialization;
- schema 2 + schema-1 migration;
- multiple audit references;
- immutable result + append-only decisions;
- population/gate snapshots;
- tests before UI.

## Milestone 6 — QC statistical engine

- eligibility;
- per-variable W1;
- SWD;
- scores/flags/contributors;
- small-N policy;
- synthetic truth tests.

## Milestone 7 — Hierarchy/influence engine

- hierarchy mapping;
- variance components/ICCs;
- identifiability/convergence handling;
- leave-one-biological-replicate-out influence;
- synthetic truth tests.

## Milestone 8 — XLSX/CSV exports

- canonical bundle → XLSX;
- canonical bundle → CSV package;
- cross-format equality tests.

## Milestone 9 — Minimal UI

- run dialog;
- result table;
- audit workspace list;
- keep/exclude/restore/note actions;
- export action;
- no statistical-dashboard scope creep.

## Milestone 10 — Integrated validation/finalization

- full baseline suite;
- expanded format corpus;
- expanded statistics corpus;
- actual workspace save/reopen/relink;
- proprietary derivative lifecycle;
- UI smoke pass;
- package/release metadata update to 4.4.3 only after all acceptance items are resolved.

---

# 25. Acceptance checklist for v4.4.3

## File formats

- [ ] Existing CSV files load unchanged.
- [ ] FCS 1.0 validated fixture loads correctly.
- [ ] FCS 2.0 validated fixture loads correctly.
- [ ] FCS 3.0 validated fixture loads correctly.
- [ ] FCS 3.1 validated fixture loads correctly.
- [ ] FCS 3.2 mixed-type validated fixture loads correctly.
- [ ] LMD opens with no manual conversion.
- [ ] LMD creates/reuses `.vflow.csv` next to source.
- [ ] MQD opens with no manual conversion **only after same-acquisition truth validation**.
- [ ] MQD creates/reuses `.vflow.csv` next to source.
- [ ] No user file is overwritten.
- [ ] stale derivative detection works.
- [ ] read-only fallback works.
- [ ] workspace stores authoritative original proprietary source.
- [ ] downstream gates/plots/stats behave identically after normalization.

## Statistical audit

- [ ] User can select same-condition samples and population.
- [ ] All shared eligible numeric variables can be audited regardless of domain.
- [ ] Per-variable whole-distribution metrics are produced.
- [ ] Multivariate SWD matrix is produced.
- [ ] Discordant samples can be flagged for review.
- [ ] Low-N behavior does not overclaim.
- [ ] No sample is automatically excluded.
- [ ] User can keep/exclude/restore and optionally record reason/note.
- [ ] Multiple audits coexist in one workspace.
- [ ] Historical statistical result remains immutable after later decisions.
- [ ] Biological replicate → nested sample → particle mapping works.
- [ ] Variance components and ICCs are exported with model status.
- [ ] Leave-one-biological-replicate-out influence is produced.
- [ ] vFlow does not run final condition-vs-condition tests.

## Export/audit trail

- [ ] XLSX default export works.
- [ ] Required sheets exist.
- [ ] CSV package alternative works.
- [ ] XLSX and CSV match canonical audit bundle.
- [ ] Pairwise matrices are reconstructable.
- [ ] source fingerprints/population snapshots/algorithm parameters are present.
- [ ] workspace schema-1 workspaces migrate safely.
- [ ] audit bundle relinking/missing-file handling is explicit.

---

# 26. Scientific/behavioral guardrails

These are release blockers if violated.

1. **No silent sample removal.** Statistical flags are advisory review signals only.
2. **No technical-cause claim from endpoint discordance alone.** A sample can be biologically unusual.
3. **No pseudoreplication claim.** Report biological units, nested samples, and particles separately.
4. **No final treatment-effect statistics.** This feature audits structure/quality within user-selected peer groups.
5. **No silent event subsampling in the audit.** If a future approximation mode is added, it must be explicit and recorded; not part of v4.4.3 default behavior.
6. **No mixed populations.** If the resolved selected population is unavailable for one selected sample, fail before partial calculation.
7. **No extension-only trust.** Probe file content and fail closed on unsupported/corrupt formats.
8. **No fake MQD support.** Same-acquisition vendor-export validation is mandatory.
9. **No FCS 3.2 header-only support.** Mixed data types and version semantics must actually be handled.
10. **No workspace history rewriting.** Audit result is immutable; decisions append history.

---

# 27. Recommended release documentation

On completion, add:

```text
IMPLEMENTATION_REPORT_v4.4.3.md
HANDOFF_REVIEW_v4.4.3.md
validation/v4.4.3_format_results.json
validation/v4.4.3_statistical_audit_results.json
validation/v4.4.3_workspace_migration_results.json
validation/v4.4.3_performance_results.json
```

The final report should explicitly state:

- which FCS versions have actual fixtures;
- which MQD/LMD instrument/software variants were validated;
- hashes of proprietary/reference pairs used for equivalence testing;
- statistical synthetic truth tolerances;
- any model-convergence limitations;
- platform UI checks performed;
- full regression pass count.

Do not describe unvalidated vendor variants as supported.

---

# 28. External technical references used for scope

These references are implementation context, not substitutes for test fixtures.

- FCS 3.2 standard paper: Josef Spidlen et al., *Data File Standard for Flow Cytometry, Version FCS 3.2*, Cytometry A (2021), DOI `10.1002/cyto.a.24225`; FCS 3.2 retains the overall format but introduces incompatible reader changes including mixed measurement data types.
- FCS 3.1 paper/history: Josef Spidlen et al., *Data File Standard for Flow Cytometry, version FCS 3.1*, Cytometry A (2010), DOI `10.1002/cyto.a.20825`; describes FCS 1.0 (1984), 2.0 (1990), 3.0 (1997), and 3.1.
- Miltenyi MACSQuant/MACSQuantify documentation: acquisition data are stored in `.mqd` and can be exported as FCS or CSV; this provides the required same-acquisition reference-validation route.
- Miltenyi MACSQuant Tyto documentation: Tyto acquisition data are stored in MQD and can be exported as FCS/CSV.
- FlowJo Beckman documentation: FC500/Gallios/Navios LMD files contain FCS-compatible portions, including FCS 3.0 representations in relevant instruments.

Implementation should consult the normative/version-specific FCS specification where available rather than relying only on summary papers.

---

# 29. Final implementation principle

The safest architectural boundary for v4.4.3 is:

```text
SOURCE FORMAT
    ↓
validated reader / proprietary decoder
    ↓
normalized event DataFrame + provenance
    ↓
existing vFlow plotting / gating / workspace science
    ↓
optional statistical audit
    ↓
immutable audit bundle
    ↓
XLSX or CSV export + user decision history
```

Vendor-specific decoding must stop at normalization. Statistical auditing must stop before final biological inference. This keeps vFlow extensible, scientifically auditable, and consistent with the existing v4.4.1 workspace/per-sample-gating architecture.
