"""Composed project/data loading coordinator for the legacy FlowApp shell.

This controller owns the stateful filesystem/session workflows that remain after
v4.3 controller decomposition: dataset admission/loading and gate-session
save/load orchestration.  It intentionally does not reinterpret scientific
state.  Deterministic planning/serialization remains delegated to the existing
Tk-free services, while the host supplies the frozen UI/model side-effect
surface.
"""

from __future__ import annotations

import json
import os

import pandas as pd

from typing import Any, Callable

from vflow.config.constants import FILE_COLORS, _N_FILE_COLORS
from vflow.core.gate_serialization import (
    gate_channel_mismatch_message,
    gate_load_message,
    gate_load_status,
    gate_save_message,
    gate_save_status,
)
from vflow.core.threshold_state import ThresholdSchemaError
from vflow.services.file_load_planning import (
    build_load_warning_plan,
    plan_loaded_frame,
    plan_path_admission,
)
from vflow.services.gate_session import (
    build_gate_session_payload,
    normalize_lineage_contexts,
    prepare_gate_session_load,
    transpose_loaded_gate_for_current_axes,
)
from vflow.services.gate_axis_swap import is_pure_axis_swap


class ProjectDataLoadCoordinator:
    """Own dataset and gate-session I/O orchestration for one FlowApp host.

    The host boundary is deliberately composed rather than inherited.  Public
    ``FlowApp`` methods remain compatibility facades so frozen callers and
    characterization harnesses can still invoke/patch the historical surface.
    """

    def __init__(self, host: Any):
        self.host = host

    def load_paths(self, paths: list, *, messagebox: Any) -> None:
        """Load requested data paths with frozen admission/commit ordering."""
        h = self.host
        cidx = len(h.loaded_files)
        rename_notices: list = []
        alias_notices: list = []
        alias_ambiguities: list = []
        uncompensated_fcs: list = []
        fcs_compat_notices: list = []
        duplicate_file_notices: list = []

        for path in paths:
            admission = plan_path_admission(
                path, h.loaded_files.keys(), h.excluded_files.keys())
            if not admission.should_load:
                if admission.duplicate_notice:
                    duplicate_file_notices.append(admission.duplicate_notice)
                continue
            try:
                df = h._read_data_file(path)

                # Reuse only aliases the user already confirmed in this session.
                # Numeric values and row order are untouched; this changes labels
                # before the frozen case-only planner compares file schemas.
                apply_aliases = getattr(h, '_apply_axis_aliases_to_df', None)
                if callable(apply_aliases):
                    df, alias_details = apply_aliases(df, path)
                else:  # lightweight frozen load-path harnesses have no resolver state
                    alias_details = {'renamed': {}, 'ambiguous': []}
                if alias_details['renamed']:
                    alias_notices.append(
                        f"{os.path.basename(path)}: "
                        + ", ".join(f"'{k}'→'{v}'"
                                    for k, v in alias_details['renamed'].items()))
                if alias_details['ambiguous']:
                    alias_ambiguities.append(
                        f"{os.path.basename(path)}: "
                        + "; ".join(alias_details['ambiguous']))

                # FCS compensation metadata is a safety marker only.  Its
                # presence does not by itself establish whether stored DATA are
                # raw or already compensated, so the planner warns neutrally.
                frame_plan = plan_loaded_frame(
                    path, df, list(h.loaded_files.values()))
                if frame_plan.uncompensated_fcs_name:
                    uncompensated_fcs.append(frame_plan.uncompensated_fcs_name)
                if frame_plan.fcs_compatibility_notice:
                    fcs_compat_notices.append(frame_plan.fcs_compatibility_notice)
                if frame_plan.rename_map:
                    df = df.rename(columns=frame_plan.rename_map)
                    h.axis_aliases.update(frame_plan.rename_map)
                    rename_notices.append(frame_plan.rename_notice)

                # Frozen B27 atomic registration: build UI row before committing
                # data, and roll back any partial row-registration state.
                h.file_colors[path] = FILE_COLORS[cidx % _N_FILE_COLORS]
                try:
                    h._add_file_row(path)
                except Exception as e:
                    h.file_colors.pop(path, None)
                    h.file_vars.pop(path, None)
                    messagebox.showerror(
                        "Load Error",
                        f"UI registration failed for {os.path.basename(path)}:\n{e}")
                    continue
                h._dataset_state_obj().commit_loaded_file(path, df)
                h._data_generation += 1
                h._analysis_cache_obj().clear_all()
                cidx += 1
            except Exception as e:
                messagebox.showerror(
                    "Load Error", f"Could not read {os.path.basename(path)}:\n{e}")

        h._update_channel_menus()
        h._on_active_files_changed()

        # Warning/status order is frozen: refresh first, then append notices.
        warning_plan = build_load_warning_plan(
            duplicate_file_notices=duplicate_file_notices,
            rename_notices=rename_notices,
            mismatch=getattr(h, '_col_mismatch_msg', ''),
            fcs_compat_notices=fcs_compat_notices,
            uncompensated_fcs=uncompensated_fcs,
        )
        if warning_plan.spillover_files_summary:
            messagebox.showwarning(
                "FCS Compensation State Requires Verification",
                "One or more loaded FCS files contain compensation metadata "
                "($SPILLOVER/$SPILL, $COMP, or legacy $DFCiTOj). vFlow does "
                "not automatically apply, reverse, or otherwise modify "
                "compensation. Verify whether the stored DATA are raw or "
                "already compensated, and verify the intended compensation "
                "state upstream before quantitative fluorescence gating or "
                "interpretation.\n\n"
                f"Files: {warning_plan.spillover_files_summary}",
                parent=h.root)
        extra_suffix = []
        if alias_notices:
            extra_suffix.append(
                "✓ Confirmed axis mapping reused: " + "  |  ".join(alias_notices))
        if alias_ambiguities:
            extra_suffix.append(
                "⚠ Confirmed alias not applied where ambiguous: "
                + "  |  ".join(alias_ambiguities))
        suffix_parts = list(warning_plan.suffix_parts) + extra_suffix
        if suffix_parts:
            try:
                h.status_var.set(
                    h.status_var.get() + "  │  " + "  │  ".join(suffix_parts))
            except Exception:
                pass

        offer_resolver = getattr(h, '_offer_axis_name_resolution', None)
        if callable(offer_resolver):
            offer_resolver()

    def save_excluded_list(
        self, *, filedialog: Any, messagebox: Any, last_folder_getter: Callable[[], str | None]
    ) -> None:
        """Persist excluded-file identities with frozen dialog/status behavior."""
        h = self.host
        if not h.excluded_files:
            messagebox.showinfo("Save Excluded List", "No files are currently excluded.")
            return
        init = (last_folder_getter() or
                os.path.dirname(next(iter(h.excluded_files))) or
                os.path.expanduser('~'))
        path = filedialog.asksaveasfilename(
            parent=h.root,
            title="Save excluded file list",
            initialdir=init,
            initialfile="excluded_files.csv",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*")])
        if not path:
            return
        try:
            pd.DataFrame({'Path': list(h.excluded_files.keys())}).to_csv(path, index=False)
            h.status_var.set(
                f"Excluded list saved: {len(h.excluded_files)} file(s) → "
                f"{os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e), parent=h.root)

    def load_excluded_list(
        self, *, filedialog: Any, messagebox: Any, last_folder_getter: Callable[[], str | None]
    ) -> None:
        """Restore an excluded-file list without changing frozen move/register semantics."""
        h = self.host
        init = last_folder_getter() or os.path.expanduser('~')
        path = filedialog.askopenfilename(
            parent=h.root,
            title="Load excluded file list",
            initialdir=init,
            filetypes=[("CSV", "*.csv"), ("All files", "*")])
        if not path:
            return
        try:
            df_csv = pd.read_csv(path)
        except Exception as e:
            messagebox.showerror("Load Error", str(e), parent=h.root)
            return

        if 'Path' not in df_csv.columns:
            messagebox.showerror(
                "Load Error",
                "CSV must have a 'Path' column.\nUse a list saved by 'Save List'.",
                parent=h.root)
            return

        paths = df_csv['Path'].dropna().astype(str).tolist()
        moved = 0
        registered = 0
        already = 0

        for path_item in paths:
            if path_item in h.excluded_files:
                already += 1
                continue
            if path_item in h.loaded_files:
                h._exclude_file(path_item)
                moved += 1
            else:
                h._dataset_state_obj().register_unloaded_exclusion(path_item)
                registered += 1

        h._rebuild_excluded_list()
        h._on_active_files_changed()

        parts = []
        if moved:
            parts.append(f"{moved} moved to excluded")
        if registered:
            parts.append(f"{registered} registered (not loaded)")
        if already:
            parts.append(f"{already} already excluded")
        h.status_var.set(
            "Excluded list loaded: " + ", ".join(parts)
            if parts else "Excluded list loaded: nothing new to exclude.")

    def save_gates(self, *, filedialog: Any, messagebox: Any) -> None:
        """Serialize the current gate session with frozen dialog/error ordering."""
        h = self.host
        if not h.gates:
            messagebox.showwarning("Save Gates", "No gates to save.")
            return

        stem = h._auto_stem()
        path = filedialog.asksaveasfilename(
            defaultextension='.json',
            initialfile=f'{stem}_gates.json',
            filetypes=[("Gate file (JSON)", "*.json"), ("All files", "*.*")])
        if not path:
            return

        try:
            payload = build_gate_session_payload(
                h.gates,
                analysis_state=h._analysis_state_obj(),
                population_lineage=h.population_lineage,
            )
        except (ThresholdSchemaError, ValueError) as exc:
            messagebox.showerror(
                "Save Gates",
                "Cannot save gates because a threshold state is malformed or gate geometry is invalid.\n\n"
                f"{exc}\n\n"
                "Review or recreate the affected gate's threshold toggles, "
                "then save again.")
            return

        with open(path, 'w') as fh:
            json.dump(payload, fh, indent=2)

        n = len(h.gates)
        h.status_var.set(gate_save_status(path, n))
        messagebox.showinfo(
            "Save Gates", gate_save_message(path, n, h.x_channel, h.y_channel))

    def load_gates(
        self,
        *,
        filedialog: Any,
        messagebox: Any,
        boolean_var_factory: Callable[..., Any],
    ) -> None:
        """Load a gate session while preserving provenance/failure ordering."""
        h = self.host
        path = filedialog.askopenfilename(
            filetypes=[("Gate file (JSON)", "*.json"), ("All files", "*.*")])
        if not path:
            return

        try:
            with open(path) as fh:
                payload = json.load(fh)
        except Exception as e:
            messagebox.showerror("Load Gates", f"Could not read file:\n{e}")
            return

        gate_file_version = payload.get('version', 0)
        if gate_file_version not in (1, 2, 3):
            messagebox.showerror(
                "Load Gates",
                f"Unsupported gate file version {gate_file_version!r}. "
                "The file was not loaded because its scientific provenance "
                "cannot be interpreted safely by this version of vFlow.")
            return

        saved_lineage = payload.get('population_lineage', [])
        if not isinstance(saved_lineage, list):
            messagebox.showerror(
                "Load Gates", "Invalid gate file: 'population_lineage' is not a list.")
            return
        if saved_lineage and h._lineage_signature(
                normalize_lineage_contexts(saved_lineage)) != h._lineage_signature(
                    normalize_lineage_contexts(h.population_lineage)):
            messagebox.showerror(
                "Load Gates",
                "This gate file was created inside a different sub-gated population. "
                "Loading it into the current population would silently change its "
                "denominator and biological meaning. Open/recreate the matching "
                "sub-gate lineage first, then load this gate file there.")
            return

        raw_gates = payload.get('gates', [])
        if not isinstance(raw_gates, list):
            messagebox.showerror(
                "Load Gates", "Invalid gate file: 'gates' field is not a list.")
            return

        saved_x = payload.get('x_channel', '')
        saved_y = payload.get('y_channel', '')
        channel_mismatch = (
            saved_x != (h.x_channel or '') or saved_y != (h.y_channel or ''))
        pure_axis_swap = (
            gate_file_version >= 2
            and is_pure_axis_swap(h.x_channel, h.y_channel, saved_x, saved_y)
        )
        if gate_file_version == 1:
            if channel_mismatch:
                messagebox.showerror(
                    "Load Gates",
                    "Legacy v1 gate file channel mismatch.\n\n"
                    f"Saved: X={saved_x or '(none)'}, Y={saved_y or '(none)'}\n"
                    f"Current: X={h.x_channel or '(none)'}, "
                    f"Y={h.y_channel or '(none)'}\n\n"
                    "Switch to the saved X/Y channels first. v1 gates cannot be "
                    "safely rebound to different channels.")
                return
            if not messagebox.askyesno(
                    "Load Legacy v1 Gates",
                    "This legacy v1 gate file does not contain scale/cofactor "
                    "provenance. Its gates will be bound to the CURRENT X/Y "
                    "transform settings.\n\nOnly continue if the current scale "
                    "types and cofactor are the same ones used when these gates "
                    "were created."):
                return
        elif channel_mismatch and not pure_axis_swap:
            if not messagebox.askyesno(
                    "Load Gates",
                    gate_channel_mismatch_message(
                        saved_x=saved_x,
                        saved_y=saved_y,
                        current_x=h.x_channel,
                        current_y=h.y_channel)):
                return

        load_prep = prepare_gate_session_load(
            payload,
            gate_file_version=gate_file_version,
            current_next_id=h._next_gate_id)
        clean_gates = load_prep.clean_gates
        n_skipped = load_prep.skipped_count

        def _dict_to_gate(clean: dict) -> dict:
            return {
                'id': clean['id'],
                'name': clean['name'],
                'type': clean['type'],
                'auto_method': clean['auto_method'],
                'applied': clean['applied'],
                'color': clean['color'],
                'linestyle': clean['linestyle'],
                'linewidth': clean['linewidth'],
                'x_boundaries': clean['x_boundaries'],
                'y_boundary': clean['y_boundary'],
                'x_thresh_vars': [boolean_var_factory(value=bool(a))
                                  for a in clean['x_thresh_active']],
                'y_thresh_var': boolean_var_factory(value=clean['y_thresh_active']),
                'y_boundaries': clean['y_boundaries'],
                'y_thresh_vars': [boolean_var_factory(value=bool(a))
                                  for a in clean['y_thresh_actives']],
                'x0': clean['x0'],
                'y0': clean['y0'],
                'x1': clean['x1'],
                'y1': clean['y1'],
                'vertices': clean['vertices'],
            }

        saved_contexts = load_prep.saved_contexts if gate_file_version >= 2 else {}
        if gate_file_version >= 2:
            if not load_prep.contexts_container_valid:
                messagebox.showerror(
                    "Load Gates",
                    f"Invalid v{gate_file_version} gate file: 'gate_contexts' is not an object.")
                return
            context_errors = list(load_prep.context_errors)
            if context_errors:
                messagebox.showerror(
                    "Load Gates",
                    f"Invalid v{gate_file_version} gate provenance. No gates were loaded:\n"
                    + "\n".join(f"• {e}" for e in context_errors[:10]))
                return

            transposed_clean = []
            for clean in clean_gates:
                gate_id = str(clean['id'])
                moved, moved_context, _ = transpose_loaded_gate_for_current_axes(
                    clean, saved_contexts[gate_id],
                    current_x=h.x_channel, current_y=h.y_channel,
                )
                transposed_clean.append(moved)
                saved_contexts[gate_id] = moved_context
            clean_gates = transposed_clean

        new_gates = [_dict_to_gate(clean) for clean in clean_gates]
        for g in new_gates:
            if gate_file_version >= 2:
                h._bind_gate_context(g, saved_contexts[str(g['id'])])
            else:
                h._bind_gate_context(g, h._current_analysis_context())
        if gate_file_version == 1:
            h.status_var.set(
                "Legacy v1 gate file loaded: gates were bound to the current "
                "channel/transform context because v1 did not store scale provenance.")
        max_id = max((g['id'] for g in new_gates), default=-1)
        if not new_gates:
            messagebox.showwarning(
                "Load Gates",
                "No valid gates found in file."
                + (f"\n({n_skipped} malformed gate(s) skipped.)" if n_skipped else ""))
            return

        h.clear_all_gates()
        h.gates = new_gates
        h._next_gate_id = max_id + 1
        h._sel_gate_id = new_gates[-1]['id']
        h._invalidate_analysis_caches()

        for g in h.gates:
            if g.get('applied') and h._active():
                h._compute_gate_stats_for(g)

        h._rebuild_gate_manager()
        h._rebuild_thresh_panel()
        h._update_stats_display()
        h.refresh_plot()

        n = len(new_gates)
        h.status_var.set(gate_load_status(path, n, n_skipped))
        messagebox.showinfo("Load Gates", gate_load_message(path, n, n_skipped))
