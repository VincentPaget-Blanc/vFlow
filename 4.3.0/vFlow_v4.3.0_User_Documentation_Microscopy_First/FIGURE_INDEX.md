# Figure Index

PNG files are recommended for GitHub/general documentation. Matching SVG files are supplied for every generated analytical figure and are preferable for a scientific manuscript.

## Microscopy-first overview

### Figure 21 — Primary workflow and FCS compatibility
<img src="figures/21_microscopy_first_overview.png" width="100%" alt="Microscopy-first vFlow overview"/>

Panels A–B show the primary microscopy-derived particle workflow: corrected-intensity visualization and GMM population analysis. Panel C shows FCS compatibility using the same application.

## UI/reference figures

### Figure 1 — CSV UI reference
<img src="figures/01_ui_csv_reference.jpeg" width="100%" alt="CSV UI reference"/>

### Figure 2 — FCS UI reference
<img src="figures/02_ui_fcs_reference.jpeg" width="100%" alt="FCS UI reference"/>

### Interface map
<img src="figures/ui_layout.svg" width="100%" alt="vFlow interface map"/>

### Gate types
<img src="figures/gate_types.svg" width="100%" alt="vFlow gate types"/>

### Polar/vector analysis
<img src="figures/polar_analysis.svg" width="100%" alt="vFlow polar analysis"/>

## Generated analytical figures

### Figure 3 — CSV canonical Density
<img src="figures/03_csv_density_asinh.png" width="80%" alt="CSV canonical density"/>

### Figure 4 — FCS canonical Density
<img src="figures/04_fcs_density_asinh.png" width="80%" alt="FCS canonical density"/>

### Figure 5 — CSV Dot Plot
<img src="figures/05_csv_dot_asinh.png" width="80%" alt="CSV dot plot"/>

### Figure 6 — CSV Contour representation
<img src="figures/06_csv_contour_asinh.png" width="80%" alt="CSV contour"/>

### Figure 7 — CSV linear-scale comparison
<img src="figures/07_csv_linear_density.png" width="80%" alt="CSV linear display"/>

### Figure 8 — FCS linear-scale comparison
<img src="figures/08_fcs_linear_density.png" width="80%" alt="FCS linear display"/>

### Figure 9 — Manual crosshair illustration
<img src="figures/09_csv_manual_crosshair.png" width="80%" alt="CSV manual crosshair"/>

### Figure 10 — Otsu auto-gate
<img src="figures/10_csv_otsu_autogate.png" width="80%" alt="CSV Otsu auto-gate"/>

Calculated with the vFlow 4.3.0 `otsu_threshold` helper in asinh transform space.

### Figure 11 — Manual ellipse illustration
<img src="figures/11_fcs_manual_ellipse.png" width="80%" alt="FCS ellipse gate"/>

### Figure 12 — CSV GMM Multi
<img src="figures/12_csv_gmm_multi.png" width="80%" alt="CSV GMM multi"/>

Calculated on `Bkgd_Corr_Intensity_Marker_A × Bkgd_Corr_Intensity_Marker_B` with the vFlow 4.3.0 exact-N GMM Multi workflow using 3 components independently on X and Y.

X crossings: 155,446.3, 837,002.1  
Y crossing: -149.8


### Figure 13 — Cluster Polygons-style HDBSCAN example
<img src="figures/13_fcs_cluster_polygons.png" width="80%" alt="FCS HDBSCAN cluster polygons"/>

Detected clusters: 2. Cluster sizes: 211, 3447 events.

### Figure 14 — CSV distance distribution
<img src="figures/14_csv_distance_histogram.png" width="80%" alt="CSV distance histogram"/>

### Figure 15 — FSC-A × SSC-A
<img src="figures/15_fcs_fsca_ssca_density.png" width="80%" alt="FSC-A versus SSC-A"/>

### Figure 16 — FL1-A × FL2-A
<img src="figures/16_fcs_fl1a_fl2a_density.png" width="80%" alt="FL1-A versus FL2-A"/>


## Actual vFlow 4.3.0 UI captures

### Figure 17 — Canonical CSV UI
<img src="figures/17_actual_ui_csv_canonical.png" width="100%" alt="Actual CSV UI capture"/>

Captured from the real vFlow 4.3.0 application using the frozen CSV demonstration file, canonical corrected-intensity axes, `asinh / asinh`, cofactor 150, Density mode and marginal histograms.

### Figure 18 — Canonical FCS UI
<img src="figures/18_actual_ui_fcs_canonical.png" width="100%" alt="Actual FCS UI capture"/>

Captured from the real vFlow 4.3.0 application using `FSC-H × FL1-H`, `asinh / asinh`, cofactor 150, Density mode and marginal histograms.

### Figure 19 — CSV GMM Multi workflow in the actual UI
<img src="figures/19_actual_ui_csv_gmm_multi.png" width="100%" alt="Actual CSV GMM Multi UI"/>

Shows the Auto-Gate controls, GMM population-count selectors, Gate Manager, Gate Info crossing toggles, per-file Statistics and fitted marginal Gaussian components together with the gated graph.

### Figure 20 — Right-click source-file location menu
<img src="figures/20_actual_ui_file_context_menu.png" width="100%" alt="Actual file context menu"/>

Linux capture showing `Show in File Manager`. The same action is labelled `Show in Finder` on macOS and `Show in Explorer` on Windows.

## Suggested scientific-paper reuse

A compact paper figure set could use:

- software/interface: Figures 1–2 plus `ui_layout.svg`;
- dual-format demonstration: Figures 3–4;
- gating methods: Figures 9–13, with the complete GMM UI workflow shown in Figure 19;
- transform behavior: Figures 3 versus 7 and 4 versus 8;
- domain-specific examples: Figure 14 and Figure 15.

Prefer the matching SVG files for journal submission when vector graphics are accepted.
