import py_compile
from pathlib import Path


def test_packaged_application_module_compiles():
    script = Path(__file__).resolve().parents[1] / "vflow" / "legacy" / "vflow_app.py"
    py_compile.compile(str(script), doraise=True)
