# vFlow v4.3.0 — Illustrated User Documentation: Fluorescence Particle Population Analysis

This bundle contains a GitHub/Zenodo-ready illustrated user guide for **vFlow 4.3.0**.

The guide is **microscopy-first**: vFlow is presented primarily as a downstream population-analysis environment for particle-level fluorescence measurements exported by microscopy/image-analysis pipelines, with FCS cytometry as a compatible extension.

The manual is organized around the three development pillars:

1. **Visualization & interaction**
2. **Scientific robustness & quality control**
3. **Automation & performance**

## Contents

- [`vFlow_v4.3.0_User_Guide.md`](vFlow_v4.3.0_User_Guide.md) — full illustrated manual
- [`QUICK_START.md`](QUICK_START.md) — short tutorial using the two demo files
- [`DEMO_DATASETS.md`](DEMO_DATASETS.md) — dataset provenance, anonymisation and reproducibility notes
- [`FIGURE_INDEX.md`](FIGURE_INDEX.md) — figure-by-figure index and suggested paper reuse
- [`figures/`](figures/) — raster figures for GitHub/manual use plus SVG versions of generated analytical plots
- [`datasets/`](datasets/) — frozen semi-synthetic CSV and FCS demonstration files
- [`demo_dataset_summary.csv`](demo_dataset_summary.csv) — machine-readable demo summary
- [`figure_manifest.csv`](figure_manifest.csv) — machine-readable figure manifest
- [`checksums.sha256`](checksums.sha256) — SHA-256 checksums

## Canonical demonstration views

### CSV

- X: `Bkgd_Corr_Intensity_Marker_A`
- Y: `Bkgd_Corr_Intensity_Marker_B`
- scale: `asinh / asinh`
- cofactor: `150`
- primary plot mode: `Density`
- marginal histograms: enabled in the supplied vFlow UI reference

### FCS

- X: `FSC-H`
- Y: `FL1-H`
- generated-documentation scale: `asinh / asinh`
- cofactor: `150`
- primary plot mode: `Density`
- marginal histograms: enabled in the supplied vFlow UI reference

The two UI screenshots are the supplied reference screenshots. Analytical figures were regenerated directly from the frozen semi-synthetic datasets.

## Revised real-UI screenshots

This revision adds screenshots captured directly from the vFlow 4.3.0 application:

- `figures/17_actual_ui_csv_canonical.png`
- `figures/18_actual_ui_fcs_canonical.png`
- `figures/19_actual_ui_csv_gmm_multi.png`
- `figures/20_actual_ui_file_context_menu.png`

GMM Multi is now demonstrated on the CSV corrected-intensity data. The source-file context-menu screenshot was captured under Linux; the equivalent menu labels are `Show in Finder` on macOS and `Show in Explorer` on Windows.
