# MQD reference-pair research — 2026-10-03

Public researchers have shared native MQD files in repositories that also offer
FCS files. This establishes useful leads. It does **not** establish that any
particular native and exported files represent the same acquisition with matching
values, channel identity, compensation and time semantics.

| Primary source | Public evidence | Retrieval/acceptance status |
| --- | --- | --- |
| [FlowRepository FR-FCM-Z3MR, DAF-2A](https://flowrepository.org/id/RvFrzhOtiB4Hrd9yMMTEF2gAckZvYVa365phD9U0fVTabQb7ibCDqV8Gzbgb02dm) | Indexed record lists `12072019.0001.mqd` through `.0004.mqd` and an FCS download section. | Direct repository retrieval timed out/returned gateway errors. No bytes or verified export pair obtained. |
| [FlowRepository FR-FCM-Z65V, BAL immune cells](https://flowrepository.org/id/FR-FCM-Z65V) | MQD compensation acquisitions, e.g. `BR16130038_2019-08-06_comp_apc_CD8_adm2019-08-06.0022.mqd`, plus an FCS download section. | Indexed listing verified; direct fetch timed out. Compensation MQDs might differ from main experimental FCS acquisitions; pairing must be checked. |
| [FlowRepository FR-FCM-Z6K3, cardiomyocyte aggregates](https://flowrepository.org/id/FR-FCM-Z6K3) | MQD acquisition attachments including `NK2023-04-26_Spinner1_NANOG_OCT.0003.mqd`, plus FCS downloads. | Candidate lead; no downloaded or matched native/export pair. |
| [Dryad DOI 10.5061/dryad.g4f4qrfsd](https://datadryad.org/dataset/doi:10.5061/dryad.g4f4qrfsd) | Authors describe `Flow_cytometry.zip` (1.19 GB) containing FCS/MQD flow-cytometry data, organized by figure and experiment date with sample-description spreadsheets. Published 2022-08-29. | Metadata and API file record accessible. Website file download returned HTTP 403; API download returned HTTP 401. Archive was not inspected. Same-acquisition pairs remain unconfirmed. |

No emails or requests to dataset owners were sent. Public-access failures are
recorded rather than being treated as proof that the data do not exist. No login
or access restriction was bypassed. There is currently no acquired authoritative
MQD/FCS/CSV numeric pair in the delivered corpus.

## Why a guessed decoder is excluded

The [FCSalyzer developer's format notes](https://sourceforge.net/p/fcsalyzer/wiki/FACS%20data/)
describe uncertainty about Miltenyi data scaling and a heuristic for low-valued
measurements. Those notes are evidence that numeric interpretation requires
validation, not a normative MQD specification. An embedded FCS signature alone
cannot establish native MQD scaling, offsets, time, compensation or multiple-member
semantics. The candidate recognizes MQD and reports a specific validation blocker;
it does not produce inferred values or `.vflow.csv` files for MQD.

## Acceptance work once a pair is available

1. Confirm identical acquisition/instrument/software, event identity/order and
   channel mapping; record authoritative originals and cryptographic checksums.
2. Freeze the vendor-export FCS or CSV as the reference. Record gain, log scale,
   negative values, precision, time-step and compensation/export settings.
3. Validate every event/column with predetermined exactness or float tolerances;
   test more than one acquisition and all relevant native variants/members.
4. Implement a decoder only for validated layouts. Exercise source-authoritative
   derivatives, staleness, deletion, collision, read-only fallback and workspace
   reopen; reject all unknown variants.
5. Run the existing and expanded corpora before marking the MQD milestone complete.

## Other format references used

- [NIST Fireflow](https://github.com/usnistgov/fireflow), source commit
  `8e4a795b2ecad0cdfe805d6ab046f83d3d46153d`. Its FCS3.2 standard notes and
  implementation informed numeric type, temporal and CRC checks. Building the
  independent native Python reader failed in this host environment; it is not
  shipped as a dependency and is not claimed as an executed FCS3.2 reference.
- [FCS3.2 publication](https://doi.org/10.1002/cyto.a.24225).
- [Bioconductor flowPloidyData](https://bioconductor.org/packages/flowPloidyData/),
  source commit `8099dbbcdfea894d0ace23b2b65f94c04132d622`. Unlike MQD leads,
  all 14 actual Gallios LMD files were obtained. Their high-resolution members
  match independently decoded FlowIO 1.4.0 values exactly. Originals, reference
  checksums and the GPL-3 attribution/license are included.
