"""Fitting-source selection and transactions; numerical estimators stay unchanged."""
import functools


def auto_gate_transaction(method):
    @functools.wraps(method)
    def run(app, *args, **kwargs):
        owner = getattr(app, '_workspace', None)
        if owner is None:
            return method(app, *args, **kwargs)
        if not owner.gate_editing_available(app): return
        owner.capture(app)
        store = owner.stores[app._workspace_tab_id]
        before = store.snapshot()
        previous_editing = store.editing
        store.checkpoint()
        store.editing = True
        try:
            result = method(app, *args, **kwargs)
            gate = app._sel_gate()
            if gate and (gate.get('x_boundaries') or gate.get('y_boundaries') or gate.get('y_boundary') is not None):
                gate.pop('thresholds_empty',None)
        finally:
            owner.commit_gates(app)
            store.editing = previous_editing
            if store.snapshot() == before:
                store._undo.pop()
            else:
                owner.gates_dirty = True
                owner.mark_dirty()
        # Surface the existing editing controls after a successful changed fit.
        show = getattr(app, '_show_gate_info', None)
        gate = app._sel_gate() if callable(show) else None
        if store.snapshot() != before and gate and gate.get('type') == 'crosshair':
            show(gate['id'])
        return result
    return run
