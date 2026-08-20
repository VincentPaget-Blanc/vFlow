from vflow.services.active_file_changes import (
    ActiveFileChangePlan,
    plan_active_file_change,
)


def ctx(x='X', y='Y', xs='asinh', ys='asinh', cofactor=150.0):
    return {
        'x_channel': x,
        'y_channel': y,
        'x_scale': xs,
        'y_scale': ys,
        'cofactor': cofactor,
    }


def test_unchanged_context_without_applied_gates_only_refreshes():
    assert plan_active_file_change(ctx(), ctx(), []) == ActiveFileChangePlan(
        context_changed=False,
        recompute_gate_stats=False,
    )


def test_unchanged_context_with_any_truthy_applied_gate_recomputes_stats():
    gates = [
        {'applied': False},
        {'applied': 1},
        {'applied': False},
    ]
    assert plan_active_file_change(ctx(), ctx(), gates) == ActiveFileChangePlan(
        context_changed=False,
        recompute_gate_stats=True,
    )


def test_context_change_suppresses_direct_stats_recompute_path():
    plan = plan_active_file_change(ctx(), ctx(x='Other'), [{'applied': True}])
    assert plan == ActiveFileChangePlan(
        context_changed=True,
        recompute_gate_stats=False,
    )


def test_context_equality_preserves_exact_cofactor_tolerance():
    assert plan_active_file_change(
        ctx(cofactor=150.0), ctx(cofactor=150.0 + 5e-13), []
    ).context_changed is False
    assert plan_active_file_change(
        ctx(cofactor=150.0), ctx(cofactor=150.0 + 2e-12), []
    ).context_changed is True


def test_non_mapping_contexts_fail_closed_as_changed():
    assert plan_active_file_change(None, ctx(), []).context_changed is True
    assert plan_active_file_change(ctx(), None, []).context_changed is True


def test_incompatible_gate_status_preserves_names_fallback_and_four_gate_truncation():
    from vflow.services.active_file_changes import build_incompatible_gate_status

    gates = [
        {'name': 'A', 'id': 1},
        {'id': 2},
        {'name': '', 'id': 3},
        {'name': 'D', 'id': 4},
        {'name': 'E', 'id': 5},
        {'name': 'F', 'id': 6},
    ]
    assert build_incompatible_gate_status(gates) == (
        'Analysis context changed. 6 gate(s) are inactive in this coordinate '
        'system: A, 2, , D +2 more. Switch back to reuse them.'
    )


def test_incompatible_gate_status_none_when_no_incompatible_gates():
    from vflow.services.active_file_changes import build_incompatible_gate_status
    assert build_incompatible_gate_status([]) is None
