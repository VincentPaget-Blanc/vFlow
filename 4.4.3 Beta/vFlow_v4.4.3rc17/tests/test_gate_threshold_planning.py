import pytest

from vflow.services.gate_threshold_planning import (
    ThresholdVariablePlan,
    manual_crosshair_threshold_plan,
    multi_y_auto_threshold_plan,
    single_y_auto_threshold_plan,
)


def test_manual_crosshair_plan_is_exact_frozen_pair():
    assert manual_crosshair_threshold_plan() == ThresholdVariablePlan(
        x_values=(True,), y_value=True, y_values=(),
    )


def test_single_y_auto_plan_enables_every_x_and_scalar_y_only():
    plan = single_y_auto_threshold_plan([1.0, 2.0, 3.0])
    assert plan == ThresholdVariablePlan(
        x_values=(True, True, True), y_value=True, y_values=(),
    )


def test_single_y_auto_plan_preserves_empty_x_collection():
    assert single_y_auto_threshold_plan([]) == ThresholdVariablePlan(
        x_values=(), y_value=True, y_values=(),
    )


def test_single_y_auto_plan_preserves_noniterable_exception_boundary():
    with pytest.raises(TypeError):
        single_y_auto_threshold_plan(None)


def test_multi_y_auto_plan_enables_all_crossings_and_has_no_scalar_y_toggle():
    plan = multi_y_auto_threshold_plan([1, 2], [3, 4, 5])
    assert plan == ThresholdVariablePlan(
        x_values=(True, True),
        y_value=None,
        y_values=(True, True, True),
    )


def test_multi_y_auto_plan_preserves_empty_y_state():
    plan = multi_y_auto_threshold_plan([1], [])
    assert plan == ThresholdVariablePlan(
        x_values=(True,), y_value=None, y_values=(),
    )
    assert multi_y_auto_threshold_plan([1], None) == plan


def test_multi_y_auto_plan_preserves_generator_consumption_semantics():
    xs = (value for value in [1, 2])
    ys = (value for value in [3, 4])
    plan = multi_y_auto_threshold_plan(xs, ys)
    assert plan.x_values == (True, True)
    assert plan.y_values == (True, True)
    assert list(xs) == []
    assert list(ys) == []
