from pathlib import Path
import tomllib

import vflow
from vflow.legacy import vflow_app


def _pyproject():
    path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with path.open("rb") as fh:
        return tomllib.load(fh)


def test_release_version_is_420_everywhere():
    project = _pyproject()["project"]
    assert project["version"] == "4.2.0"
    assert vflow.__version__ == "4.2.0"
    assert vflow_app.APP_VERSION == "4.2.0"


def test_runtime_version_guard_accepts_packaged_release():
    assert vflow_app._VFLOW_PACKAGE_VERSION == vflow_app.APP_VERSION


def test_release_python_requirement_matches_runtime_syntax():
    assert _pyproject()["project"]["requires-python"] == ">=3.10"


def test_release_console_entry_point_is_packaged_main():
    assert _pyproject()["project"]["scripts"]["vflow"] == "vflow.main:main"


def test_scikit_learn_is_optional_advanced_dependency():
    project = _pyproject()["project"]
    assert all(not dep.startswith("scikit-learn") for dep in project["dependencies"])
    assert project["optional-dependencies"]["advanced"] == ["scikit-learn>=1.3"]
