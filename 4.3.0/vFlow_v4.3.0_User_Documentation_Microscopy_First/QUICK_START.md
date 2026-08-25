# vFlow v4.3.0 Quick Start — Microscopy-Derived Fluorescence Particles

## 1. Start with the microscopy-style particle CSV

The primary vFlow workflow is population analysis of particle-level measurements exported from microscopy/image-analysis pipelines.

Load `datasets/vFlow_v4.3.0_SemiSynthetic_Demo_Pooled_CytoFile.csv` first. The FCS example is optional and demonstrates cytometry compatibility.

Keep the three pillars in mind:

- **Visualize** the population and marginals before gating.
- **Quality-control** the measurement identity, transform, denominator, and provenance.
- **Automate carefully** to save time without giving up scientific inspection.

After completing the CSV walkthrough, optionally load:

- `datasets/vFlow_v4.3.0_SemiSynthetic_Demo_Cytometry.fcs`

The files deliberately have different schemas. Select the active file before choosing axes.

## 2. Visualize the microscopy particle populations

Select:

- **X:** `Bkgd_Corr_Intensity_Marker_A`
- **Y:** `Bkgd_Corr_Intensity_Marker_B`
- **X scale:** `asinh`
- **Y scale:** `asinh`
- **Cofactor:** `150`
- **Plot Mode:** `Density`
- **Marginal histograms:** on

<img src="figures/17_actual_ui_csv_canonical.png" width="100%" alt="Actual vFlow 4.3.0 CSV UI captured in the documentation environment"/>

Standalone generated representation:

<img src="figures/03_csv_density_asinh.png" width="80%" alt="Generated CSV density view"/>

## 3. Optional: view compatible FCS data

Select:

- **X:** `FSC-H`
- **Y:** `FL1-H`
- **X scale:** `asinh`
- **Y scale:** `asinh`
- **Cofactor:** `150`
- **Plot Mode:** `Density`
- **Marginal histograms:** on

<img src="figures/18_actual_ui_fcs_canonical.png" width="100%" alt="Actual vFlow 4.3.0 FCS UI captured in the documentation environment"/>

Standalone generated representation:

<img src="figures/04_fcs_density_asinh.png" width="80%" alt="Generated FCS density view"/>

## 4. Try the three plot modes

Dot Plot:

<img src="figures/05_csv_dot_asinh.png" width="75%" alt="CSV dot plot"/>

Density:

<img src="figures/03_csv_density_asinh.png" width="75%" alt="CSV density plot"/>

Contour Plot:

<img src="figures/06_csv_contour_asinh.png" width="75%" alt="CSV contour plot"/>

## 5. Create a manual gate

Enable Draw mode and select Crosshair, Rectangle, Ellipse or Polygon.

<img src="figures/09_csv_manual_crosshair.png" width="75%" alt="Manual crosshair gate"/>

## 6. Try automatic gating — then inspect the result

Automatic gates save time, but they remain candidate population separators rather than biological annotations.

Otsu:

<img src="figures/10_csv_otsu_autogate.png" width="75%" alt="Otsu auto gate"/>

GMM Multi:

<img src="figures/19_actual_ui_csv_gmm_multi.png" width="100%" alt="Actual vFlow CSV GMM Multi UI"/>

Cluster Polygons:

<img src="figures/13_fcs_cluster_polygons.png" width="75%" alt="Cluster polygons"/>

## 7. Inspect alternative FCS channels

<img src="figures/15_fcs_fsca_ssca_density.png" width="75%" alt="FSC-A versus SSC-A"/>

<img src="figures/16_fcs_fl1a_fl2a_density.png" width="75%" alt="FL1-A versus FL2-A"/>

## 8. Reveal a loaded source file

Right-click any visible part of a loaded or excluded file row to reveal the corresponding source file in the operating-system file manager.

- **macOS:** `Show in Finder`
- **Windows:** `Show in Explorer`
- **Linux:** `Show in File Manager`

On macOS, Control-click is also supported.

<img src="figures/20_actual_ui_file_context_menu.png" width="100%" alt="Actual vFlow file-row context menu"/>

## 9. Export

Use vFlow's export controls to save figures as PDF/PNG/SVG, export statistics or gated data, and save gates to JSON.


## Scientific quality-control shortcut

Before exporting results, confirm the correct source files, parameters, transforms, parent population, supported thresholds, and saved provenance/session information.
