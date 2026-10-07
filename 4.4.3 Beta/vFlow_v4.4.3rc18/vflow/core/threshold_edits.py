"""Plans for explicit threshold edits; gate evaluation is unchanged."""
from vflow.core.threshold_state import flag_value


def threshold_delete_plan(gate, axis, index):
    """Return replacement fields, or None for an invalid/stale row.

    Multi-Y deletion clears the legacy single-Y fallback when the last boundary
    is removed. Removing a boundary also removes its corresponding enabled flag.
    Missing flags default to enabled, matching the threshold panel's repair.
    """
    if not gate or gate.get('type') != 'crosshair' or axis not in ('x', 'y'):
        return None
    if type(index) is not int or index < 0:
        return None
    def finish(changes):
        after = dict(gate, **changes)
        if not (after.get('x_boundaries') or after.get('y_boundaries') or after.get('y_boundary') is not None):
            changes['thresholds_empty'] = True
        return changes
    multi = axis == 'x' or bool(gate.get('y_boundaries'))
    if not multi:
        if index != 0 or gate.get('y_boundary') is None:
            return None
        return finish({'y_boundary': None, 'y_boundaries': None,
                'y_thresh_var': False, 'y_thresh_vars': []})
    boundaries = list(gate.get(axis + '_boundaries') or [])
    if index >= len(boundaries):
        return None
    original_flags = list(gate.get(axis + '_thresh_vars') or [])
    flags = [flag_value(original_flags[i], field=axis+'_thresh_vars')
             if i < len(original_flags) else True for i in range(len(boundaries))]
    del boundaries[index]
    del flags[index]
    changes = {axis + '_boundaries': boundaries, axis + '_thresh_vars': flags}
    if axis == 'y':
        # Never resurrect an obsolete single-Y boundary after a multi-Y edit.
        changes['y_boundary'] = None
        changes['y_thresh_var'] = False
        if not boundaries:
            changes['y_boundaries'] = None
    return finish(changes)
