from pathlib import Path
from types import SimpleNamespace

import pytest

from vflow.core.gate_serialization import gate_to_json_dict
from vflow.core.threshold_state import (
    ThresholdSchemaError,
    flag_value,
    serialized_threshold_flags,
)
from vflow.legacy import vflow_app as app_module
from vflow.legacy.vflow_app import FlowApp


class ExplodingFlag:
    def get(self):
        raise RuntimeError("sensor disconnected")


class NonCallableGetter:
    get = True


class PlainTruthy:
    def __bool__(self):
        return True


def test_valid_plain_and_tk_like_threshold_values_keep_legacy_semantics():
    class Flag:
        def __init__(self, value):
            self.value = value
        def get(self):
            return self.value

    flags = serialized_threshold_flags({
        "x_thresh_vars": [Flag(True), False, 1, ""],
        "y_thresh_var": Flag(False),
        "y_thresh_vars": [PlainTruthy()],
    })
    assert flags.x_active == (True, False, True, False)
    assert flags.y_active is False
    assert flags.y_actives == (True,)


def test_explicit_none_serialization_lists_are_actionable_schema_errors():
    for field in ("x_thresh_vars", "y_thresh_vars"):
        with pytest.raises(ThresholdSchemaError) as excinfo:
            serialized_threshold_flags({field: None})
        message = str(excinfo.value)
        assert field in message
        assert "iterable threshold-flag sequence" in message
        assert "None" in message


def test_non_iterable_serialization_container_reports_field_and_type():
    with pytest.raises(ThresholdSchemaError) as excinfo:
        serialized_threshold_flags({"x_thresh_vars": 7})
    assert "x_thresh_vars" in str(excinfo.value)
    assert "int" in str(excinfo.value)


def test_non_callable_getter_is_rejected_deliberately():
    with pytest.raises(ThresholdSchemaError) as excinfo:
        flag_value(NonCallableGetter(), field="x_thresh_vars[2]")
    message = str(excinfo.value)
    assert "x_thresh_vars[2]" in message
    assert "not callable" in message


def test_getter_failure_is_wrapped_with_field_and_preserves_cause():
    with pytest.raises(ThresholdSchemaError) as excinfo:
        flag_value(ExplodingFlag(), field="y_thresh_var")
    assert "y_thresh_var" in str(excinfo.value)
    assert "sensor disconnected" in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, RuntimeError)


def test_gate_serialization_adds_gate_identity_to_threshold_schema_error():
    with pytest.raises(ThresholdSchemaError) as excinfo:
        gate_to_json_dict({
            "id": 0,
            "name": "",
            "x_thresh_vars": [ExplodingFlag()],
        })
    message = str(excinfo.value)
    assert "Gate 0" in message
    assert "x_thresh_vars[0]" in message
    assert "sensor disconnected" in message


def test_save_gates_shows_actionable_error_and_does_not_create_file(monkeypatch, tmp_path):
    output = tmp_path / "bad_gates.json"
    dialogs = []

    monkeypatch.setattr(
        app_module.filedialog, "asksaveasfilename", lambda **kwargs: str(output))
    monkeypatch.setattr(
        app_module.messagebox, "showerror", lambda title, message: dialogs.append((title, message)))

    fake = SimpleNamespace(
        gates=[{"id": 4, "name": "Broken gate", "x_thresh_vars": None}],
        population_lineage=[],
        x_channel="X",
        y_channel="Y",
        _auto_stem=lambda: "sample",
        _analysis_state_obj=lambda: SimpleNamespace(x_channel="X", y_channel="Y"),
    )

    FlowApp.save_gates(fake)

    assert not output.exists()
    assert len(dialogs) == 1
    title, message = dialogs[0]
    assert title == "Save Gates"
    assert "Cannot save gates because a threshold state is malformed" in message
    assert "Broken gate" in message
    assert "x_thresh_vars" in message
    assert "Review or recreate" in message


def test_save_controller_catches_only_expected_validation_errors_source_contract():
    import inspect
    from vflow.controllers.project_data_load_coordinator import ProjectDataLoadCoordinator

    block = inspect.getsource(ProjectDataLoadCoordinator.save_gates)
    assert "except (ThresholdSchemaError, ValueError) as exc:" in block
    assert "except Exception" not in block
    assert block.index("build_gate_session_payload(") < block.index("with open(path, 'w') as fh:")
