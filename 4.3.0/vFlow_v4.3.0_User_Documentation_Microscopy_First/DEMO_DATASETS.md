# Demonstration Dataset Notes

## Purpose

The **CSV file is the primary microscopy-style scientific example**, representing particle-level fluorescence measurements of the type exported by an upstream image-analysis pipeline. The **FCS file is a secondary compatibility example** demonstrating that the same event-table analysis model also works with conventional cytometry.

The two files in this bundle are intended for:

1. vFlow user documentation and training;
2. reproducible screenshots and worked examples;
3. software-methods figures in a scientific manuscript;
4. regression/demo workflows that should not expose biological marker identities.

They are **semi-synthetic**, not raw experimental datasets.

## CSV file

**File:** `datasets/vFlow_v4.3.0_SemiSynthetic_Demo_Pooled_CytoFile.csv`

- rows: **2,029**
- columns: **8**
- canonical X channel: `Bkgd_Corr_Intensity_Marker_A`
- canonical Y channel: `Bkgd_Corr_Intensity_Marker_B`
- distance channel: `Distance_Marker_A-Marker_B_microns`

Columns:

- `Label`
- `Intensity_Marker_A`
- `Bkgd_Intensity_Marker_A`
- `Bkgd_Corr_Intensity_Marker_A`
- `Intensity_Marker_B`
- `Bkgd_Intensity_Marker_B`
- `Bkgd_Corr_Intensity_Marker_B`
- `Distance_Marker_A-Marker_B_microns`

Marker identities were replaced by `Marker_A` and `Marker_B`. Numeric values were deterministically perturbed rather than copied verbatim. The analytical identity

`Bkgd_Corr_Intensity = Intensity - Bkgd_Intensity`

is preserved exactly for both markers.

## FCS file

**File:** `datasets/vFlow_v4.3.0_SemiSynthetic_Demo_Cytometry.fcs`

- FCS version: **3.1**
- events: **6,192**
- parameters: **14**
- canonical X channel: `FSC-H`
- canonical Y channel: `FL1-H`

Parameters:

- `FSC-A`
- `FSC-H`
- `FSC-W`
- `SSC-A`
- `SSC-H`
- `SSC-W`
- `FL1-A`
- `FL1-H`
- `FL1-W`
- `FL2-A`
- `FL2-H`
- `FL3-A`
- `FL3-H`
- `Time`

Familiar pulse geometry was retained as `FSC-A/H/W`, `SSC-A/H/W` and `Time`. Reagent-specific fluorescence names were replaced by generic `FL1`, `FL2` and `FL3` detector-style names. Event values were reproducibly perturbed while preserving recognisable distributional geometry.

## Capability coverage

| Capability | CSV demo | FCS demo |
|---|---:|---:|
| File loading | ✓ | ✓ |
| Arbitrary X/Y selection | ✓ | ✓ |
| Linear/log/asinh/Logicle display | ✓ | ✓ |
| Dot/Density/Contour modes | ✓ | ✓ |
| Marginal histograms | ✓ | ✓ |
| Manual gates | ✓ | ✓ |
| Otsu/GMM/cluster auto-gating | ✓ | ✓ |
| Statistics | ✓ | ✓ |
| Gate JSON save/reload | ✓ | ✓ |
| Gated-data export | ✓ | ✓ |
| Distance-column analysis | ✓ | — |
| Polar/Vector analysis | Requires paired centroid X/Y columns not present in this closer-to-source demo | — |

The original README's Polar/Vector diagram is included as `figures/polar_analysis.svg` so the capability is documented without fabricating centroid columns.

## Reproducibility hashes

- CSV SHA-256: `11d966c9b5a68c08c78ca4b04dc22df423005c95ad99700ab0bf0d3fe8ea4788`
- FCS SHA-256: `0f7fa9c971c270221ff235e8d4488a9026c0abf0a9ddc6ce9b63eec52337a677`

## Suggested manuscript wording

> Demonstration analyses were performed on semi-synthetic datasets generated from representative CSV and FCS data structures. Biological marker and specimen identifiers were removed. Numeric measurements were deterministically transformed and perturbed while preserving the principal distributional structure and, for the CSV data, the exact relationship between raw, background and background-corrected intensity columns. The resulting demonstration files were used solely for software illustration and reproducible workflow examples.
