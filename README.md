# vFlow

**Visual Flow Cytometry & Immunofluorescence Analysis Tool**

vFlow is a desktop application for interactive 2D gating, visualisation, and quantification of single-particle immunofluorescence data. It is designed for two complementary experimental contexts:

- **Flow cytometry**: standard `.fcs` or `.csv` list-mode files from any flow cytometer
- **Widefield immunofluorescence of nano/microparticles**: specifically the CSV outputs produced by the [IJ-Toolset SynaptosomesMacro](https://github.com/fabricecordelieres/IJ-Toolset_SynaptosomesMacro) for ImageJ/Fiji

In both cases the unit of analysis is the same: one row = one particle, columns = measured channels. vFlow treats these files identically and provides the gating, population quantification, and batch statistics that standard flow cytometry software provides for FCS data, applied to any single-particle measurement table.

<img src="docs/ui_layout.svg" alt="vFlow main interface showing sidebar controls, density scatter plot with crosshair gate, region labels, marginal histograms, and statistics panel" width="100%"/>

---

## Changelog

### v4.0.12  Sub-gate tab: gate placement no longer resets view

- **Sub-gate tab zoom fix**: placing a crosshair or shape gate in a sub-gate tab no longer zooms out to the full instrument scale. Previously, drawing a gate triggered `refresh_plot` which re-applied `_set_axis_scale()`, resetting the view to the full biexp/asinh range and shrinking the sub-population to a tiny speck in one corner. Fix: `_load_filtered` now enables `fit_axes_var = True` for every sub-gate tab on creation, so the existing p0.5/p99.5 fit-to-data logic applies automatically. The **Fit axes to data** checkbox remains visible in the sidebar and can be unchecked to restore the full scale view.

### v4.0.9  Bug fixes and improvements

**Bug fixes**

- **Sub-gate tab: changing X/Y axis now takes effect.** `_update_channel_menus` previously replaced the combobox values list but did not re-sync the StringVars when a channel was already set, causing the displayed selection to go blank on some platforms. Fix: `_update_channel_menus` now always calls `x_var.set` / `y_var.set` after rebuilding the values list. Additionally, `apply_axes` now clears the transform cache (`self._tc`) whenever the channel selection actually changes, preventing stale cached transforms from being served for new columns.

**Improvements**

- **Vector/Polar window: channel mapping UI regrouped by channel.** The four centroid column selectors were previously ordered Y-Ch1, X-Ch1, Y-Ch2, X-Ch2 (axis-first), making it easy to accidentally assign a Ch1 column to a Ch2 slot. They are now ordered Ch1-X, Ch1-Y, Ch2-X, Ch2-Y (channel-first) with an explicit note: "Direction: Ch1 -> Ch2; map X and Y separately for each channel." The vector direction formula (`dx = X_Ch2 - X_Ch1`, `dy = Y_Ch2 - Y_Ch1`) is unchanged.

- **Vector/Polar window: radial scale now explained in title and status bar.** The polar rose plot radial axis was previously unlabelled. It now states "Radial scale = fraction of vectors per bin" in the figure suptitle and the status bar, making clear that each bar height is a proportion (0–1) rather than a raw count. The mean-direction arrow threshold is also shown inline: "Arrow shown when MRL >= \<threshold\>".

- **Folder dialogs: last-used directory persisted within the session.** Every `askdirectory` / `askopenfilenames` call previously opened at the home directory regardless of prior use. A module-level `_last_folder_dir` variable is now updated whenever the user confirms a folder selection in `FolderScanDialog`, `BatchExportDialog`, or `FlowApp.load_files`. Subsequent dialog openings start at the same directory, eliminating repeated navigation across a session.

### v4.0.8  BatchPlotWindow bug fixes and performance

**Bug fixes**

- **Box plot: outlier dots now match their box colour.** `flierprops` previously set a single fixed colour (`T['fg_dim']`) for all outlier points regardless of sample. After `boxplot()` returns, each `bp['fliers'][i]` element is now updated with `colors_ordered[i]` so outlier dots are coloured identically to their parent box.

- **Strip/"points only" view: y-axis scale no longer shifts between renders.** `_get_rng(42)` returned a cached, stateful `Generator`; calling it across multiple renders advanced its internal state, producing different subsample indices and jitter values each time and causing matplotlib to autoscale to a different data range on every redraw. Fix: the strip-plot block now creates a local `np.random.default_rng(42)` on each `_render_figure()` call, making subsampling and jitter identical on every redraw. Y-limits are also explicitly set from the full data range before `scatter()` is called, pinning the axis scale.

- **Stacked bar legend no longer overlaps bars.** The legend was previously drawn at `loc='upper right'` inside the axes bounding box, covering the tallest bars. It is now anchored outside the axes at `bbox_to_anchor=(1.01, 1.0)` with `loc='upper left'`, and the figure right margin is reduced (`right=0.82` / `0.87`) to leave room for the legend panel.

**Performance**

- **`_compute_and_plot`: gate-mask computation halved per sample.** Previously `_get_population_mask` and `_get_region_pcts_and_n` each called `self.app._gate_mask_for` independently (two full gate evaluations per sample). `_compute_and_plot` now calls `_gate_mask_for` exactly once per sample and builds both the population mask and the region-pct dict from that single result. `_get_population_mask` and `_get_region_pcts_and_n` are retained as helpers for other callers.

### v4.0.6  BatchPlotWindow bug fixes

- **Stacked bar: per-bar binomial SEM.** `_pop_sem_cache` previously stored one SEM per region computed as `std(all_samples)/sqrt(n_samples)`, a global cross-sample aggregate drawn identically on every bar regardless of sample size. SEM is now computed per bar as the binomial standard error `sqrt(p*(1-p)/n)`, where `p` is that sample's proportion and `n` is its cell count. `_get_region_pcts_and_n()` was added to return `(pct, n_total)` pairs; `_get_region_pcts()` now wraps it for backward compatibility.

- **x-axis label alignment fixed.** The custom `annotate`-based `_draw_staggered_xlabels` helper mixed data-space x coordinates with axes-space y offsets, causing labels to drift from their tick marks at different figure sizes and DPI values. Replaced with `_set_rotated_xlabels`, which uses the standard `ax.set_xticklabels(labels, rotation=45, ha='right', rotation_mode='anchor')`. The bottom margin was also increased from 0.32 to 0.38 to give rotated labels vertical clearance.

- **Zoom X / Zoom Y toolbar removed from batch-plot panel.** The zoom buttons (-/+/Reset for both axes) have been removed. The scrollable canvas already provides panning; the zoom controls were non-intuitive and cluttered the toolbar. Internal `_zoom_x` / `_zoom_y` variables are retained at their default value (1.0) so `_render_figure` is unchanged.

### v4.0.2  Dead-code cleanup

Ten methods that had become unreachable since earlier refactoring were removed (105 lines):

- `_plot_gated`: superseded by `_plot_gated_multi`; never called
- `_compute_gate_stats`: thin wrapper around `_compute_gate_stats_for`; never called
- `_new_thresh_vars` / `_new_y_thresh_var`: BooleanVars are now created inline; never called
- `_gate_mask` / `_gate_mask_for_id`: convenience aliases for `_gate_mask_for`; never called
- `_region_display_name`: region names built inline in `_region_masks`; never called
- `_collect_2d_transform` / `_deepest_gmm_threshold`: were part of the 2D GMM path removed in v4.0.0; never called
- `BatchPlotWindow._refresh_display`: defined but never wired; `_schedule_replot` replaced it

The **Compute & Plot** button was also removed from the Polar Analysis and Batch Plots windows. Every parameter change already triggers an automatic debounced replot; the button had become pure redundancy.

### v4.0.1  Auto-replot in analysis windows

Both the **Polar Analysis** and **Batch Plots** windows now replot automatically whenever any parameter changes. There is no longer a **Compute & Plot** button in either window. A 300–350 ms debounce ensures that rapid interactions (typing in an entry box, quickly ticking files) collapse into a single replot fired once the user pauses.

Controls that now trigger a live replot:

| Window | Triggers |
|--------|---------| 
| Polar Analysis | Gate, region, all four centroid column combos, bins / alpha / MRL entries, file checkboxes, display checkboxes |
| Batch Plots | Gate, region, distribution column, plot style, sample order, all checkboxes, file checkboxes, Auto: Intensity / Distance buttons |

### v4.0.0  Batch Plots window, population shading, dead code and cleanup

**New: Batch Plots window**

A dedicated analysis window (opened via **📊 Batch Plots…** in the sidebar) that reproduces the core "Batch Export Stats: Folder Mode" figure directly inside the application without writing any files.

- **Left panel: violin / box / points**: one shape per sample showing the full distribution of any chosen numeric column (intensity, distance, etc.). White dot = median, thick bar = IQR, thin whiskers = p5–p95.
- **Right panel: 100 % stacked bar**: one bar per sample showing gate population percentages (Ch1+/Ch2+, Ch1−/Ch2+, etc.) for the applied gate.
- **Sample identity is auto-detected:** if any loaded file contains a `Source_File` column (produced by the Folder Scanner concatenation), each unique value in that column becomes one sample. Otherwise each loaded file is one sample with the same colour as in the scatter view.
- **Gate / region filtering** uses the same `_gate_mask_for` logic as all other windows; fresh per sample, no stale-cache risk.
- **Distribution styles:** violin, box, or points-only (jittered strip plot).
- **Export:** figure (PDF / PNG / SVG) and stats CSV (n, mean, median, std, IQR, p5, p95 per sample plus population % columns).

**New: population band shading on marginal histograms**

When a KDE Valley or Otsu gate is applied and marginal histograms are shown, each population band (positive, negative, intermediate) is shaded and labelled on both marginals with the same colour-coding used for gate regions. This gives the same visual feedback that GMM Multi provides via its Gaussian component curves.

**Removed: "Mixed (GMM X + KDE Y)" auto-gate**

The **Mixed** button and its underlying `auto_gate_both` method have been removed. GMM Multi, KDE Valley, Otsu, and Cluster Polygons remain fully intact and unchanged.

---

### v3.9.9  Export Gated Data

- **Export Gated Data → CSV**: a new export action that writes the raw particle-level data for all gated populations to a single CSV file. For every active file × every applied gate, each particle falling inside at least one gate region is included once (assigned to the region of the first matching gate in gate-manager order). Four annotation columns are appended: `Source_File`, `Gate_Name`, `Gate_Region` (e.g. `IN`, `Ch1+/Ch2+`), and `Gate_Type` (`crosshair` | `rectangle` | `ellipse` | `polygon`). Particles outside all gates are excluded by default. If no gates are applied the function falls back to a plain full-dataset dump with `Source_File` only.

### v3.9.8  GMM overlay curves on marginal histograms

- **Per-component Gaussian curves on marginal histograms**: when a GMM Multi gate is applied, the fitted Gaussian components are drawn as coloured overlaid curves on the top (X) and right (Y) marginal histogram axes. Each curve is scaled to match the histogram bin counts and labelled with its component mean (in raw data units) and weight. The overlay is toggled by the **Legend** checkbox.

### v3.9.7  GMM Multi auto-gate

- **GMM Multi (all crossings, X+Y indep.)**: fits independent 1-D Gaussian Mixture Models on each axis with a user-specified component count (GMM pops X and Y spinboxes, range 1–8, default 3). Every equal-density crossing between adjacent components is placed as an individual threshold line; all crossings appear as independently toggleable checkboxes in the Threshold panel. Requires `scikit-learn`.

### v3.9.6  Rectangle and Ellipse gate shapes

- **Rectangle (▬)** and **Ellipse (⬭)** gate types added. Both integrate with Batch Stats, Export Stats, and the sub-gate workflow identically to crosshair and polygon gates.

### v3.9.5  Concatenate & Export

- **Folder Scanner: Concatenate & Export section**: selected CSV files can be concatenated into a single pooled file directly from the Load from Folder dialog (Save Only or Save & Load), adding a `Source_File` column without needing an external merge step.

### v3.9.4  Bug fixes

- **Stats panel empty after gate placement**: `_gate_sig()` had a `TypeError` crash on `tuple(None)` and read the wrong dict keys for threshold toggle state; both fixed.

### v3.9.3  Bug fixes and Polar Analysis redesign

- **Region % labels not appearing after gating**: `_draw_region_labels()` now called after `_set_axis_scale()`.
- **Polar Analysis window redesigned**: single polar axes, files overlaid with `FILE_COLORS`, MRL + Rayleigh stats annotated per file, all output non-rasterised for true vector PDF/SVG export.

---

## Background: The SynaptosomesMacro Pipeline

The [IJ-Toolset SynaptosomesMacro](https://github.com/fabricecordelieres/IJ-Toolset_SynaptosomesMacro) (Cordélières et al.) is an ImageJ/Fiji toolset that quantifies protein proximity and recruitment on synaptosomes, isolated synaptic terminals imaged by widefield fluorescence microscopy, on a structure-by-structure basis.

**What the toolset does:**
1. Acquires dual- (or multi-) channel widefield images of immunolabelled particles
2. Pre-processes and segments individual structures from a fused multi-channel projection
3. Presents candidates to the user in a gallery for manual validation / rejection (aggregates, antibody precipitate, dust, etc.)
4. For each validated structure, extracts:
   - Mean fluorescence intensity per channel (raw and background-corrected)
   - Centroid coordinates per channel
   - Distance between channel centroids (a sub-resolution colocalization metric, calibrated in µm)
   - Local background from a donut-shaped ROI around each structure
5. Saves per-acquisition results as `___CytoFile.csv` and pools all acquisitions of a condition into `_Pooled_CytoFile.csv`
6. Optionally runs Monte Carlo randomization to produce a null-distribution colocalization reference

**vFlow is a downstream tool.** It reads those CytoFiles directly, provides the full 2D gating and population quantification workflow, and adds batch processing across all acquisitions of an experiment in a single operation.

---

### Typical CytoFile Column Structure

A `___CytoFile.csv` produced by the SynaptosomesMacro toolset typically contains columns such as:

| Column | Description |
|--------|-------------|
| `Intensity_Ch1` | Mean fluorescence intensity, channel 1 (e.g. Ch1-488) |
| `Intensity_Ch2` | Mean fluorescence intensity, channel 2 (e.g. Ch2-647) |
| `Bkgd_Corr_Intensity_Ch1` | Background-corrected intensity, channel 1 |
| `Bkgd_Corr_Intensity_Ch2` | Background-corrected intensity, channel 2 |
| `Background_Ch1` | Local background estimate, channel 1 |
| `Background_Ch2` | Local background estimate, channel 2 |
| `Distance` | Distance between Ch1 and Ch2 centroids (µm) |
| `X_Ch1`, `Y_Ch1` | Centroid coordinates, channel 1 |
| `X_Ch2`, `Y_Ch2` | Centroid coordinates, channel 2 |

Exact column names depend on the labelling tags entered in the toolset GUI and the version used. vFlow reads any CSV header automatically and populates the axis menus from whatever columns are present.

---

## Requirements

| Package | Version | Purpose |
|---------|---------|---------| 
| Python | ≥ 3.9 | Runtime |
| numpy | any | Array math |
| pandas | any | Data loading |
| matplotlib | any | Rendering |
| scipy | any | KDE, signal processing, interpolation |
| scikit-learn | ≥ 1.3 | GMM Multi auto-gating, HDBSCAN clustering |
| tkinter | bundled | GUI (standard library) |

```bash
pip install numpy pandas matplotlib scipy scikit-learn
```

scikit-learn is only required for the GMM Multi and Cluster Polygons auto-gate methods. All other features work without it.

---

## Quick Start

```bash
python vFlow_v4_0_12.py
```

1. Click **Load Files** or **Load from Folder** to open your `___CytoFile.csv`, `_Pooled_CytoFile.csv`, or `.fcs` files.
2. Select X and Y channels (e.g. `Bkgd_Corr_Intensity_Ch1` vs `Bkgd_Corr_Intensity_Ch2`) and click **Apply Axes**.
3. Choose a **Scale** for each axis (`asinh` at cofactor 150 is a good starting point for background-corrected immunofluorescence intensities).
4. Switch to **Density** or **Contour Plot** mode to reveal population structure.
5. Use one of the **Auto-Gate** buttons or draw a gate manually in **Draw** mode.
6. Read per-region counts and percentages in the **Statistics** panel.
7. Use **Batch Plots…** to visualise intensity/distance distributions and gate population percentages per sample across all loaded files.
8. Use **Batch Stats → Folder** to process an entire experiment folder and get one row per acquisition in a single CSV.

---

## Supported File Formats

### FCS files (`.fcs`, `.FCS`)
Pure-Python reader, no external dependencies. Supports:
- FCS 2.0, 3.0, and 3.1 standards
- `DATATYPE F` (float32), `D` (float64), and `I` (integer: 8, 16, 32-bit)
- Big-endian and little-endian byte orders
- `$PnE` log-decade encoding for integer channels
- Non-standard `$BEGINDATA` / `$ENDDATA` offsets written by some instruments
- Channel names prefer the stain/marker label (`$PnS`, e.g. `Ch1-488`) over the technical short name (`$PnN`)

### CSV files (`.csv`)
Standard comma-separated files. Each column is a channel; each row is one particle event. Headers required. This is the format produced by the SynaptosomesMacro toolset.

---

## Loading Data

### Load Files
Opens a file picker. Multiple files can be selected at once. Each file gets a distinct colour and appears as a checkbox row in the **FILES** panel. Uncheck a file to remove it from the plot without losing it.

### Load from Folder
Opens the **Folder Scanner** dialog. Select a root directory and optionally a filename suffix filter; the default `___CytoFile` matches the SynaptosomesMacro naming convention directly. The tool recursively scans all subfolders and lists every matching file. Use **Select All** / **Deselect All** or tick individual files before confirming.

The dialog remembers the last confirmed directory within the session, so repeated openings across a workflow do not require navigating from the home directory each time.

#### Concatenate & Export *(v3.9.5)*
The Folder Scanner dialog includes a **⊞ Concatenate & Export** panel at the bottom. After ticking the files you want:

- **Save Only**: concatenates the selected CSV files into a single pooled file (with a `Source_File` column identifying each row's origin) and saves it to a chosen folder. The dialog remains open.
- **Save & Load**: performs the same concatenation, saves, then immediately loads the result into the app as a single merged dataset.

This replaces a common manual step of merging CSV files in a spreadsheet before loading into vFlow.

### Exclude / Restore
Each file row has an **✕** button. Excluded files move to the **EXCLUDED FILES** panel and can be restored at any time. Exclusion also propagates to Batch Stats: any file sharing an experiment-level filename prefix with an excluded file is automatically skipped, which is particularly useful for excluding a `_Pooled_CytoFile` without having to individually exclude every acquisition from the same condition.

### Clear All Files
Removes all loaded and excluded files after confirmation. Gates are preserved.

---

## View Modes

**Overlay**: all active (checked) files are plotted simultaneously on the same axes, each in its own colour. Useful for comparing conditions or acquisitions side by side.

**Cycle through**: displays one file at a time. Use **◀ Prev** / **Next ▶** to navigate. Useful for inspecting individual acquisitions before deciding to pool them.

---

## Axes and Scales

### Axes
Select any channel for X and Y. The menus show only channels present in all currently loaded files. Click **Apply Axes** to update the plot.

### Scales
Five axis scale types, independently selectable for X and Y:

| Scale | Description | Typical use |
|-------|-------------|-------------|
| **linear** | No transformation | Distance between centroids, raw coordinates |
| **log** | Base-10 logarithm | Strictly positive channels with wide dynamic range |
| **biexp** | Biexponential (linear near zero, log in tails) | Mixed positive/negative intensity values |
| **asinh** | `arcsinh(x / cofactor)` | Standard for immunofluorescence intensities; handles negative background-corrected values gracefully |
| **logicle** | Parameterised logicle transform | Alternative to biexp for data with significant electronic noise |

**Cofactor** controls the linear-to-log transition width for `asinh` and `logicle`. Default is 150. For SynaptosomesMacro data, cofactor 150–300 is typical depending on intensity scale.

---

## Plot Modes

### Dot Plot
Each particle is drawn as a single dot, coloured by file. Subsampled to 50,000 points for display when files are larger; all statistics use the full dataset.

### Density Plot
Points are coloured by local 2D density (dark blue = sparse, red = dense) using a Gaussian KDE evaluated on a 128×128 grid then interpolated per-point. Display is capped at 50,000 randomly sampled points so sparse outlier populations are never hidden.

### Contour Plot
Filled viridis contour levels with an outer boundary at a user-chosen probability level (2 %, 5 %, 10 %, or 20 %). Particles outside the boundary are drawn as individual dots so outlier populations remain visible.

### Display Options (checkboxes)
| Option | Default | Effect |
|--------|---------|--------|
| Marginal histograms | On | Histogram panels above and to the right of the scatter plot; also shows population band shading for KDE/Otsu gates and GMM component curves for GMM Multi gates |
| Region % labels on plot | On | IN / OUT counts and percentages drawn directly on the plot |
| Legend | On | File-name legend; also toggles per-component GMM curves on marginal histograms |
| Grid | On | Background grid |
| Fit axes to data | Off | Zooms to p0.5–p99.5 of the visible data with 5 % breathing room |

---

## Manual Gating

Enable **Draw** mode with the radio button, then select a gate type.

### Gate Types

<img src="docs/gate_types.svg" alt="Four gate types side by side: crosshair (quadrant grid), rectangle, ellipse, and polygon with vertex handles" width="100%"/>

**Crosshair (✛)**
One or more vertical X thresholds and one or more horizontal Y thresholds, dividing the plot into a rectangular grid. Each region is labelled with its channel combination (e.g. `Ch1+/Ch2+`). The natural gate type for classic quadrant analysis: separating single-positive, double-positive, and negative populations.

**Rectangle (▬)**
Click-drag to define a rectangular gate. Resize by right-dragging corner handles.

**Ellipse (⬭)**
Click-drag to define an elliptical gate. Better suited to the elliptical clusters typical in fluorescence scatter plots.

**Polygon (⬠)**
Click to place vertices one by one. Close with **✓ Close Polygon** or by double-clicking near the first vertex. Any shape; useful for irregularly shaped populations.

### Interaction
- **Left-drag in Draw mode**: creates or extends a gate
- **Right-drag on any handle**: reshapes the gate (works in any mode, including Off)
- **Double-click a region label**: opens that population in a new sub-gate tab
- **Gate mode Off**: disables accidental creation; double-click sub-gating still works

---

## Auto-Gating

Four automatic gate methods, all tunable via the **Sensitivity** slider (1–10, default 7). Moving the slider live re-runs the last-used method with a short debounce delay.

### KDE Valley  (X + Y)
Detects the deepest KDE valley between two populations independently on each axis. Validated by requiring both flanking peaks to be substantially taller than the valley. Falls back to the 5 % left-tail edge for unimodal distributions. A reliable first choice for bimodal channels. Population band shading on marginal histograms shows positive/negative regions visually.

### Otsu  (X + Y)
Maximises between-class variance to find one threshold per axis. Fast and robust for clearly bimodal distributions (20/80 to 80/20 splits). Population band shading is shown on marginal histograms.

### GMM Multi  (all crossings, X+Y independent)
Fits independent 1-D Gaussian Mixture Models on X and Y with a **user-specified component count** (set via the **GMM pops X** and **Y** spinboxes in the sidebar, range 1–8, default 3). Places every equal-density crossing between adjacent components as individual threshold lines, all toggleable independently in the **Threshold** panel.

- **Why user-specified N instead of BIC?** BIC penalises complexity; it almost always merges a small negative cloud into the dominant positive population. Giving direct control over component count makes rare sub-populations discoverable: increase the spinbox by 1 at a time and observe where new crossings appear, then uncheck any that sit inside a single population.
- **Per-component GMM curves** are drawn as overlays on the marginal histograms (toggleable via the **Legend** checkbox). Each component is labelled with its mean (in raw data units) and weight.
- Requires `scikit-learn`. Falls back gracefully with an error dialog if not installed.

### Cluster Polygons  (HDBSCAN 2D)
Clusters all visible particles in 2D using HDBSCAN, wraps each cluster in a convex-hull polygon gate. Sensitivity controls minimum cluster size (high sensitivity = finds smaller subpopulations). Ideal for discovering unexpected subpopulations or for non-elliptical cluster shapes. Requires `scikit-learn ≥ 1.3`.

---

## Gate Manager

Lists all gates. For each gate: rename, toggle on/off, delete, or select as active. Multiple gates can be applied simultaneously. When more than one gate is active, statistics and labels switch to Venn partition mode showing every combination of gate memberships.

### Gate Info Panel
Shows numerical threshold values for the selected crosshair gate. Individual threshold lines can be toggled on/off independently.

---

## Sub-Gating

Any applied gate region can be opened as a **sub-gate tab**:

1. Set Gate Mode to **Off**
2. Apply a gate so region labels appear on the plot
3. Double-click any region label (e.g. `Ch1+ ⤵`)

A new tab opens pre-loaded with only the particles from that region, with **Fit axes to data** enabled by default so the view is centred on the sub-population immediately. The sub-gate tab is a fully independent vFlow instance with its own axes, scale, plot mode, auto-gate, statistics, and export. This enables hierarchical gating: for example, first gate on FSC-H vs FM4-64-H to select intact synaptosomes, then sub-gate the positive population on Ch1 vs Ch2 to quantify co-labelled structures.

Right-click a sub-gate tab header to close it. The Main tab cannot be closed.

---

## Statistics Panel

Counts and percentages for all regions of the currently selected gate across all active files.

**Per file**: each file as a collapsible tree node. Useful for comparing individual acquisitions before pooling.

**Merged**: sums all active files into a single breakdown. The appropriate view for a fully pooled `_Pooled_CytoFile`.

When multiple gates are applied the panel shows every Venn combination (exclusive regions, overlaps, outside-all).

---

## Vector / Polar Analysis

The **🧭 Polar / Vector Analysis…** window computes displacement vectors from paired centroid columns (e.g. `X_Ch1_microns`, `Y_Ch1_microns`, `X_Ch2_microns`, `Y_Ch2_microns`) and visualises their angular distribution as a polar rose histogram.

<img src="docs/polar_analysis.svg" alt="Polar analysis window showing overlaid rose histograms for three files with mean-direction arrows and per-file MRL and Rayleigh p-value statistics" width="100%"/>

### Workflow

1. Apply a gate in the main window to select a population of interest (e.g. `Ch1+/Ch2+` double-positive structures).
2. Click **🧭 Polar / Vector Analysis…** in the VECTOR ANALYSIS section.
3. Select the gate and region in the **POPULATION** section of the sidebar.
4. Confirm or manually assign the four centroid columns under **CHANNEL MAPPING**. Click **⟳ Auto-detect** to search for columns matching `X_*_microns` / `Y_*_microns` naming automatically. Columns are grouped **channel-first** (Ch1-X, Ch1-Y, Ch2-X, Ch2-Y) to reduce accidental Ch1/Ch2 swaps; a note clarifies the vector direction (Ch1 → Ch2).
5. Adjust histogram bins, bar alpha, and MRL threshold as needed.

The plot updates automatically whenever any parameter changes. No "Compute" button is needed.

### What is plotted

For each active file, the displacement vector `(Δx, Δy) = Ch2 centroid − Ch1 centroid` is computed per row. The angular distribution is rendered as a normalised polar rose histogram (each bar = fraction of vectors in that angular bin, so multi-file overlays are directly comparable regardless of cell count). The radial scale is stated in the figure title and status bar as "Radial scale = fraction of vectors per bin". All rendering is non-rasterised, so PDF and SVG exports are true vector graphics.

### Statistics

| Statistic | Description |
|-----------|-------------|
| **MRL** (Mean Resultant Length) | Ranges 0 (uniform) to 1 (perfectly aligned). Indicates the strength of directional preference. |
| **Rayleigh p-value** | Tests the null hypothesis of a uniform angular distribution. p < 0.05 indicates significant directionality. |

A mean-direction arrow is drawn when `MRL ≥ threshold` (configurable, default 0.3). The threshold value is shown inline on the figure.

### Export
- **Export figure**: PDF (vector), SVG (vector), or PNG.
- **Export stats → CSV**: one row per file with `N_vectors`, `MRL`, `Rayleigh_p`, `Mean_dir_deg`, `Significant`, and the four centroid column names.

---

## Batch Plots *(v4.0.0)*

The **📊 Batch Plots…** window visualises per-sample distributions and gate population percentages directly inside the application, without needing to run a Batch Stats export first.

<img src="docs/batch_plots.svg" alt="Batch Plots window showing violin distributions on the left and 100% stacked population bars on the right, one column per sample" width="100%"/>

### Sample identity

The window auto-detects which mode to use:

- **Concatenated-file mode**: if any loaded file contains a `Source_File` column (produced by the Folder Scanner concatenation), each unique value in that column becomes one sample. This lets you load a single pooled CSV and still see per-acquisition breakdowns.
- **Individual-files mode**: if no `Source_File` column is present, each loaded+checked file is one sample, coloured to match the scatter view.

### Left panel: distributions

Violin, box, or points-only (jittered strip) plot for any numeric column in the data: intensity, distance, or any other measured value. Select from the **DISTRIBUTION COLUMN** dropdown or use the **Auto: Intensity** / **Auto: Distance** quick-select buttons.

- White dot = median, thick bar = IQR, thin whiskers = p5–p95 (violin/box modes)
- Optional jittered point overlay for all individual values (up to 500 per sample shown)
- Gate + region filtering: only particles matching the selected gate and region contribute to the distribution
- Outlier dots (box mode) are coloured to match their parent box

### Right panel: population percentages

100 % stacked bar chart showing gate region percentages per sample. Rendered only when a gate is selected (otherwise only the distribution panel is shown). Optional percentage labels inside bars (for segments ≥ 5 %). The legend is anchored outside the plot area so it does not overlap the bars. Error bars show per-bar binomial SEM.

### Export
- **Export figure**: PDF / PNG / SVG
- **Export stats → CSV**: per-sample rows with n, mean, median, std, IQR, p5, p95, and one column per gate region percentage

---

## Export

### Save Gates → JSON
Saves all gate geometry, type, name, colour, and threshold toggle states to a `.json` file. Reload later and apply to files from a different condition with the same channel structure.

### Load Gates ← JSON
Restores gates from a `.json` file. Existing gates are replaced after confirmation.

### Export Stats → CSV
Saves the current statistics panel to CSV; one row per region per file, with count and percentage columns.

### Export Gated Data → CSV *(v3.9.9)*
Saves the raw particle-level data for all gated populations. Each row is one particle with additional columns: `Source_File`, `Gate_Name`, `Gate_Region`, `Gate_Type`. Particles outside all gates are excluded. If no gates are applied, all particles from all active files are exported with a `Source_File` column only.

### Batch Stats → Folder

The primary workflow for processing a complete SynaptosomesMacro experiment.

1. Select a root folder (auto-detected from loaded files, or browsable)
2. Set the suffix filter (default `___CytoFile` matches the SynaptosomesMacro output naming exactly) and file type (CSV, FCS, or both)
3. The tool scans the folder tree recursively, applies the current gates to every matching file, and writes one wide-format CSV with **one row per acquisition, one column per gate × region combination**

Excluded files are skipped at two levels:
- **Direct exclusion**: any file whose path matches the excluded-files list
- **Family exclusion**: any file sharing an experiment-level filename prefix with an excluded file (e.g. excluding `20241122_DA-FASS_Pooled_CytoFile` automatically skips all `…_1___CytoFile`, `…_2___CytoFile`, … from the same acquisition set)

A companion `_excluded.csv` log is always written alongside the main results.

### Export Figure → PDF / PNG / SVG
Saves the current scatter plot at 300 dpi. For vector formats (PDF, SVG, EPS) scatter points are automatically de-rasterised before saving for crisp output at any zoom level.

---

## Themes

**☀ Light** / **☾ Dark** toggle in the toolbar. The dark theme is the default.

---

## Performance

vFlow is designed to remain responsive at the dataset sizes typical in single-particle immunofluorescence experiments (5,000–100,000 events per file).

| Operation | Strategy |
|-----------|----------|
| Scatter rendering | Capped at 50,000 points drawn (random subsample); statistics always on full data |
| Density / contour KDE | Fitted on ≤ 30,000 subsampled points; evaluated on a 128×128 grid then interpolated |
| Coordinate transforms | Cached per `(file, x_channel, y_channel, x_scale, y_scale, cofactor)`; partial eviction on overflow |
| Gate masks | Cached per `(file, channels, gate_id, gate_geometry_hash)`; auto-invalidated on geometry or toggle change |
| Auto-gate KDE | Subsampled to 30,000 points before fitting |
| Marginal histograms | Binned from ≤ 30,000 subsampled values; bin edges from full data range |
| Sensitivity slider | Debounced at 350 ms; live re-runs the last auto-gate without a button click |
| Dot-size / alpha sliders | Debounced at 80 ms |
| Analysis windows (Polar, Batch Plots) | Debounced at 300–350 ms; replot fires automatically on any parameter change |

---

## Keyboard & Mouse Reference

| Action | Gesture |
|--------|---------|
| Draw gate | Left-drag (Draw mode on) |
| Reshape gate handle | Right-drag on handle dot (any mode) |
| Sub-gate into region | Double-click region label (Draw mode off) |
| Navigate files (Cycle mode) | **◀ Prev** / **Next ▶** buttons |
| Pan / zoom | Matplotlib toolbar at bottom of plot |
| Close sub-gate tab | Right-click tab header → Close Tab |

---

## Typical Workflow: SynaptosomesMacro Experiment

```
Upstream  (ImageJ/Fiji  IJ-Toolset SynaptosomesMacro)
───────────────────────────────────────────────────────
1. Acquire dual-channel widefield images of immunolabelled synaptosomes
2. Run toolset GUI → set labelling tags and segmentation parameters
3. Validate candidates in the gallery (click to reject aggregates/debris)
4. Output per acquisition:
     ___CytoFile.csv        <- per-particle intensities, backgrounds,
                               centroid coordinates, inter-channel distance
5. Pooled across acquisitions:
     _Pooled_CytoFile.csv   <- all validated particles from one condition
6. Optional colocalization control:
     Analysis_RandomizationResults.csv  <- Monte Carlo null distribution

Downstream  (vFlow)
───────────────────
7.  Load from Folder -> suffix ___CytoFile
    -> select all acquisitions from one condition
    Optional: use ⊞ Concatenate & Export -> Save & Load to merge them
    into a single pooled file in one step

8.  Apply axes:
      X -> Bkgd_Corr_Intensity_Ch1      (channel 1 background-corrected)
      Y -> Bkgd_Corr_Intensity_Ch2      (channel 2 background-corrected)

9.  Set both scales to asinh, cofactor 150-300
    Enable Density or Contour Plot to reveal population structure

10. Run KDE Valley or GMM Multi auto-gate for an initial threshold,
    fine-tune by dragging handles
    Optional: use GMM Multi with pops-X/Y spinboxes to separate
    dim-positive sub-populations; uncheck unwanted crossings

11. Statistics panel -> Merged:
      Ch1+/Ch2+     double-positive (co-labelled structures)
      Ch1+/Ch2-     Ch1-only
      Ch1-/Ch2+     Ch2-only
      Ch1-/Ch2-     double-negative

12. Double-click Ch1+/Ch2+ ⤵ -> sub-gate tab opens with only
    those particles (view auto-fitted to the sub-population)
    -> gate on Distance or a third channel

13. Export Stats -> CSV for the gate breakdown
    Export Gated Data -> CSV for particle-level data with Gate_Name /
    Gate_Region / Gate_Type columns
    (import to R / Python / Prism for statistical testing)

14. Back in the main tab:
    Batch Stats -> Folder -> suffix ___CytoFile -> experiment root
    -> one output CSV, one row per acquisition, across all conditions

15. Batch Plots -> visualise distance/intensity distributions per
    acquisition side by side (violin/box/points), and gate population
    % stacked bars: works directly on the concatenated CSV or on
    individually loaded files

16. Optional  Vector Analysis:
    Select Ch1+/Ch2+ gate -> map Ch1-X/Ch1-Y and Ch2-X/Ch2-Y
    (channel-first selector order)
    -> polar rose histogram per condition with MRL and Rayleigh p
    -> Export figure (PDF/SVG) or stats CSV
```

---

## Architecture

vFlow is a single-file Python application (~8,300 lines, v4.0.12).

**`FlowApp`**: complete analysis environment for one dataset view. Owns the matplotlib figure, all gate state, all file state, and the control panel. Runs standalone or embedded as a tab inside `FlowTabManager`.

**`FlowTabManager`**: manages a `ttk.Notebook` of multiple independent `FlowApp` instances. Handles sub-gate tab creation and passes filtered particle data from parent to child.

**`PolarAnalysisWindow`**: dedicated `tk.Toplevel` for vector directionality analysis. Reads paired centroid columns (grouped channel-first: Ch1-X, Ch1-Y, Ch2-X, Ch2-Y), computes displacement vectors, renders a polar rose histogram with one overlay per active file. Replots automatically on any parameter change (300 ms debounce). All output is non-rasterised.

**`BatchPlotWindow`**: dedicated `tk.Toplevel` for per-sample distribution and population % visualisation. Auto-detects whether samples come from individual files or from a `Source_File` column in a concatenated CSV. Replots automatically on any parameter change (300 ms debounce).

**`FolderScanDialog`**: modal dialog for recursive folder scanning with suffix filtering. Includes the Concatenate & Export panel for merging selected CSV files into a single pooled dataset. Persists the last-used directory within the session.

**`BatchStatsDialog`**: modal dialog for configuring and previewing a batch statistics run.

Custom matplotlib scale classes (`BiexpScale`, `AsinhScale`, `LogicleScale`) are registered globally and work as first-class axis scales.

The FCS reader (`read_fcs`) has no external dependencies beyond numpy/pandas and Python's standard library.

---

## About

**vFlow** was designed as the downstream analysis complement to the [IJ-Toolset SynaptosomesMacro](https://github.com/fabricecordelieres/IJ-Toolset_SynaptosomesMacro) pipeline for single-particle immunofluorescence quantification of nano- and microparticles, and generalises naturally to any flow cytometry or single-particle measurement dataset.
