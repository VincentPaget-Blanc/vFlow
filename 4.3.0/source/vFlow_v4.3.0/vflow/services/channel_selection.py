"""Pure channel-menu planning for vFlow.

The frozen v4.1.11 UI only lets checked/active files constrain the common axis
channel set. This module preserves that exact selection/fallback policy and the
order of the resulting X/Y assignments while leaving Tk mutation in ``FlowApp``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


_PROVENANCE_COLUMNS = frozenset({"Source_File", "Source_Path"})


def _numeric_axis_columns(df) -> tuple[list, list]:
    """Return safe numeric axis columns and structurally incomplete concat channels.

    Reserved source-provenance columns are never analysis axes. For concatenated
    data, a channel is also withheld when any constituent source has zero finite
    measurements for it; otherwise vFlow could silently analyse only a subset of
    the pooled sources.
    """
    candidates = []
    for column in df.columns:
        if str(column) in _PROVENANCE_COLUMNS:
            continue
        series = df[column]
        if pd.api.types.is_bool_dtype(series.dtype):
            continue
        if pd.api.types.is_numeric_dtype(series.dtype):
            candidates.append(column)
            continue
        # Permit object columns only when every non-missing value is numeric.
        present = series.notna()
        if present.any():
            numeric = pd.to_numeric(series, errors="coerce")
            if numeric[present].notna().all():
                candidates.append(column)

    source_col = None
    if "Source_Path" in df.columns:
        source_col = "Source_Path"
    elif "Source_File" in df.columns:
        source_col = "Source_File"

    incomplete = []
    if source_col is not None:
        source_values = df[source_col]
        if source_values.dropna().astype(str).nunique() > 1:
            for column in list(candidates):
                numeric = pd.to_numeric(df[column], errors="coerce")
                finite = pd.Series(np.isfinite(numeric.to_numpy(dtype=float, copy=False)), index=df.index)
                source_keys = source_values.where(source_values.notna(), "<missing-source>")
                per_source_has_value = finite.groupby(source_keys, dropna=False).any()
                if not bool(per_source_has_value.all()):
                    incomplete.append(column)
            if incomplete:
                blocked = set(incomplete)
                candidates = [column for column in candidates if column not in blocked]

    return candidates, incomplete


@dataclass(frozen=True)
class ChannelMenuPlan:
    values: tuple
    mismatch_message: str
    operations: tuple[tuple[str, object], ...] = ()


def plan_channel_menu(menu_files: dict, x_channel, y_channel) -> ChannelMenuPlan:
    """Return the exact frozen channel-menu update plan for ``menu_files``."""
    safe_columns_by_file = []
    incomplete_concat_by_file = []
    for df in menu_files.values():
        safe, incomplete = _numeric_axis_columns(df)
        safe_columns_by_file.append(set(safe))
        incomplete_concat_by_file.append(set(incomplete))
    all_cols = safe_columns_by_file
    cols = sorted(set.intersection(*all_cols)) if all_cols else []

    ambiguous_multi_file = []
    has_fcs_ambiguity = False
    has_csv_ambiguity = False
    if len(menu_files) > 1 and cols:
        ambiguous_by_file = []
        for df in menu_files.values():
            attrs = getattr(df, "attrs", {}) or {}
            fcs_names = tuple(attrs.get("fcs_ambiguous_channel_names", ()) or ())
            csv_names = tuple(attrs.get("csv_ambiguous_channel_names", ()) or ())
            has_fcs_ambiguity = has_fcs_ambiguity or bool(fcs_names)
            has_csv_ambiguity = has_csv_ambiguity or bool(csv_names)
            names = {str(name).casefold() for name in (*fcs_names, *csv_names)}
            ambiguous_by_file.append(names)
        ambiguous_multi_file = [
            col for col in cols
            if any(str(col).casefold() in names for names in ambiguous_by_file)
        ]
        if ambiguous_multi_file:
            blocked = {str(col).casefold() for col in ambiguous_multi_file}
            cols = [col for col in cols if str(col).casefold() not in blocked]

    ambiguity_notes = []
    if has_fcs_ambiguity:
        ambiguity_notes.append(
            "Duplicate FCS stain/channel labels require an explicit nomenclature mapping"
        )
    if has_csv_ambiguity:
        ambiguity_notes.append(
            "Unnamed CSV measurement columns require explicit nomenclature before multi-file matching"
        )
    ambiguity_note = "; ".join(ambiguity_notes)

    # With multiple active files, an empty intersection means there is no axis
    # on which all selected samples can be analysed. Falling back to the first
    # file's columns silently caused downstream statistics to omit every other
    # incompatible file. Keep loading permissive, but make analysis fail closed
    # until the user deactivates/resolves the incompatible files.
    if len(menu_files) > 1 and not cols:
        if ambiguous_multi_file:
            empty_message = (
                "⚠ No unambiguous channels are shared across all active files; axes cleared. "
                "Deactivate incompatible files or resolve channel names before analysis. "
                + ambiguity_note + "."
            )
        else:
            empty_message = (
                "⚠ No channels are shared across all active files; axes cleared. "
                "Deactivate incompatible files or resolve channel names before analysis."
            )
        return ChannelMenuPlan(
            (), empty_message,
            (('x_var', ''), ('y_var', ''), ('x_channel', None), ('y_channel', None)),
        )
    if not cols and menu_files and len(menu_files) == 1:
        # Single-file analysis has no cross-file intersection, but it still
        # must use the same numeric/provenance-safe axis candidate set.
        cols = sorted(next(iter(safe_columns_by_file), set()))

    mismatch_message = ''
    if len(menu_files) > 1:
        all_union = set.union(*all_cols) if all_cols else set()
        hidden = sorted(all_union - set(cols))
        if hidden:
            sample = ', '.join(f"'{c}'" for c in hidden[:5])
            more = f' … +{len(hidden) - 5} more' if len(hidden) > 5 else ''
            if ambiguous_multi_file:
                mismatch_message = (
                    f"⚠ {len(hidden)} column(s) not safely shared across all files "
                    f"(hidden from axis menus): {sample}{more}  "
                    + ambiguity_note + "."
                )
            else:
                mismatch_message = (
                    f"⚠ {len(hidden)} column(s) not shared across all files "
                    f"(hidden from axis menus): {sample}{more}"
                )


    incomplete_concat = sorted(set().union(*incomplete_concat_by_file)) if incomplete_concat_by_file else []
    if incomplete_concat:
        sample = ', '.join(f"'{c}'" for c in incomplete_concat[:5])
        more = f' … +{len(incomplete_concat) - 5} more' if len(incomplete_concat) > 5 else ''
        concat_note = (
            f"⚠ {len(incomplete_concat)} concatenated channel(s) have no finite "
            f"measurements for one or more source files and are hidden from axis "
            f"menus to prevent partial-source analysis: {sample}{more}"
        )
        mismatch_message = (mismatch_message + "  " + concat_note).strip() if mismatch_message else concat_note

    operations: list[tuple[str, object]] = []
    if x_channel is None and len(cols) >= 2:
        # Preserve the legacy statement order exactly:
        # x_var.set; y_var.set; x_channel =; y_channel =.
        operations.extend((
            ('x_var', cols[0]),
            ('y_var', cols[1]),
            ('x_channel', cols[0]),
            ('y_channel', cols[1]),
        ))
        return ChannelMenuPlan(tuple(cols), mismatch_message, tuple(operations))

    x_was_replaced = False
    if x_channel and x_channel in cols:
        operations.append(('x_var', x_channel))
    elif x_channel and cols:
        x_channel = cols[0]
        x_was_replaced = True
        operations.extend((('x_channel', x_channel), ('x_var', x_channel)))

    if y_channel and y_channel in cols:
        # If X was automatically replaced because its old channel disappeared,
        # do not accidentally collapse X and Y onto the same remaining channel.
        # Preserve explicitly user-selected same-axis plots when neither side
        # was forced to change.
        if x_was_replaced and y_channel == x_channel and len(cols) >= 2:
            y_channel = next(c for c in cols if c != x_channel)
            operations.extend((('y_channel', y_channel), ('y_var', y_channel)))
        else:
            operations.append(('y_var', y_channel))
    elif y_channel and cols:
        fallback_y = next((c for c in cols if c != x_channel), cols[0])
        operations.extend((('y_channel', fallback_y), ('y_var', fallback_y)))

    return ChannelMenuPlan(tuple(cols), mismatch_message, tuple(operations))
