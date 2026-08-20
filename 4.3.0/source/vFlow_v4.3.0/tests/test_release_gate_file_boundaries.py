import json

from vflow.legacy import vflow_app as vf


class _Messages:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.infos = []

    def showerror(self, title, message):
        self.errors.append((title, message))

    def showwarning(self, title, message):
        self.warnings.append((title, message))

    def showinfo(self, title, message):
        self.infos.append((title, message))

    def askyesno(self, title, message):
        raise AssertionError(f"unexpected confirmation: {title}: {message}")


class _FakeVar:
    def __init__(self, value=False):
        self.value = value

    def get(self):
        return self.value


def _write(tmp_path, payload):
    path = tmp_path / "gates.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _early_app():
    app = vf.FlowApp.__new__(vf.FlowApp)
    app.gates = [{"id": 99}]
    app.population_lineage = []
    app.x_channel = "X"
    app.y_channel = "Y"
    app._next_gate_id = 100
    return app


def test_unknown_gate_schema_fails_closed_before_state_mutation(tmp_path, monkeypatch):
    app = _early_app()
    messages = _Messages()
    path = _write(tmp_path, {"version": 99, "gates": []})
    monkeypatch.setattr(vf.filedialog, "askopenfilename", lambda **_: path)
    monkeypatch.setattr(vf, "messagebox", messages)

    app.load_gates()

    assert app.gates == [{"id": 99}]
    assert messages.errors
    assert "Unsupported gate file version" in messages.errors[0][1]


def test_legacy_v1_gate_file_cannot_rebind_across_channels(tmp_path, monkeypatch):
    app = _early_app()
    messages = _Messages()
    path = _write(tmp_path, {
        "version": 1,
        "x_channel": "OtherX",
        "y_channel": "Y",
        "gates": [],
    })
    monkeypatch.setattr(vf.filedialog, "askopenfilename", lambda **_: path)
    monkeypatch.setattr(vf, "messagebox", messages)

    app.load_gates()

    assert app.gates == [{"id": 99}]
    assert messages.errors
    assert "Legacy v1 gate file channel mismatch" in messages.errors[0][1]


def test_invalid_v2_gate_provenance_fails_closed_before_replacing_gates(tmp_path, monkeypatch):
    app = _early_app()
    messages = _Messages()
    path = _write(tmp_path, {
        "version": 2,
        "x_channel": "X",
        "y_channel": "Y",
        "gates": [{
            "id": 1,
            "name": "R",
            "type": "rectangle",
            "applied": True,
            "x0": 0.0,
            "y0": 0.0,
            "x1": 1.0,
            "y1": 1.0,
        }],
        "gate_contexts": {},
    })
    monkeypatch.setattr(vf.filedialog, "askopenfilename", lambda **_: path)
    monkeypatch.setattr(vf, "messagebox", messages)
    monkeypatch.setattr(vf.tk, "BooleanVar", lambda value=False: _FakeVar(value))

    app.load_gates()

    assert app.gates == [{"id": 99}]
    assert messages.errors
    assert "Invalid v2 gate provenance" in messages.errors[0][1]
