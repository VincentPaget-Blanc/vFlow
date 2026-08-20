import math

import pytest

from vflow.services.axis_input_planning import (
    plan_axis_apply,
    plan_cofactor_entry,
    plan_cofactor_trace,
    plan_scale_apply,
)


def test_axis_apply_requires_both_channels():
    assert plan_axis_apply('', 'Y', 'X', 'Y').missing_axis is True
    assert plan_axis_apply('X', '', 'X', 'Y').missing_axis is True


def test_axis_apply_refreshes_only_when_both_channels_are_unchanged():
    same = plan_axis_apply('X', 'Y', 'X', 'Y')
    assert same.refresh_only is True
    assert same.context_changed is False

    changed = plan_axis_apply('Z', 'Y', 'X', 'Y')
    assert changed.refresh_only is False
    assert changed.context_changed is True


def test_scale_apply_preserves_valid_values_without_replacement_text():
    plan = plan_scale_apply('linear', 'logicle', '42.5')
    assert plan.x_scale == 'linear'
    assert plan.y_scale == 'logicle'
    assert plan.cofactor == 42.5
    assert plan.replacement_cofactor_text is None


@pytest.mark.parametrize('text', ['', 'abc', '0', '-2', 'nan', 'inf', '-inf'])
def test_scale_apply_invalid_cofactor_falls_back_to_frozen_150(text):
    plan = plan_scale_apply('asinh', 'asinh', text)
    assert plan.cofactor == 150.0
    assert plan.replacement_cofactor_text == '150'


def test_scale_apply_retains_legacy_broad_exception_fallback():
    class BadFloat:
        def __float__(self):
            raise RuntimeError('synthetic float failure')

    plan = plan_scale_apply('asinh', 'linear', BadFloat())
    assert plan.cofactor == 150.0
    assert plan.replacement_cofactor_text == '150'


def test_cofactor_trace_ignores_malformed_nonfinite_nonpositive_and_tolerance_values():
    for text in ('', 'abc', 'nan', 'inf', '0', '-1'):
        assert plan_cofactor_trace(text, 150.0).apply_value is None
    assert plan_cofactor_trace(str(150.0 + 5e-13), 150.0).apply_value is None


def test_cofactor_trace_applies_only_a_real_change_outside_absolute_tolerance():
    plan = plan_cofactor_trace(str(150.0 + 2e-12), 150.0)
    assert plan.apply_value == float(str(150.0 + 2e-12))


def test_cofactor_entry_invalid_text_restores_current_value_and_sets_legacy_status():
    plan = plan_cofactor_entry('nan', 37.5)
    assert plan.cofactor == 37.5
    assert plan.context_changed is False
    assert plan.display_text == '37.5'
    assert plan.status_text == 'Invalid cofactor rejected; continuing with 37.5.'


def test_cofactor_entry_within_tolerance_reformats_using_current_value():
    plan = plan_cofactor_entry(str(150.0 + 5e-13), 150.0)
    assert plan.context_changed is False
    assert plan.cofactor == 150.0
    assert plan.display_text == '150'
    assert plan.status_text is None


def test_cofactor_entry_real_change_returns_new_value_and_no_status():
    plan = plan_cofactor_entry('200.25', 150.0)
    assert plan.context_changed is True
    assert plan.cofactor == 200.25
    assert plan.display_text == '200.25'
    assert plan.status_text is None
