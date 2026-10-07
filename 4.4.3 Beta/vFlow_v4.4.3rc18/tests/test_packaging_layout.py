from pathlib import Path
import ast


def test_packaged_application_is_single_source_authority():
    root = Path(__file__).resolve().parents[1]
    packaged = root / "vflow" / "legacy" / "vflow_app.py"
    assert packaged.exists()
    assert not (root / "vflow 1.4.11.py").exists()
    assert not list(root.glob("vflow 1.*.py"))


def test_legacy_loader_targets_standard_packaged_module():
    from vflow import main

    assert main.LEGACY_MODULE_NAME == "vflow.legacy.vflow_app"
    module = main._load_legacy_module()
    assert module.__name__ == main.LEGACY_MODULE_NAME


def test_source_checkout_launcher_is_thin_package_delegate():
    root = Path(__file__).resolve().parents[1]
    launcher = root / "run_vflow.py"
    text = launcher.read_text(encoding="utf-8")
    assert "from vflow.main import main" in text
    assert "FlowApp" not in text
    # The Spyder process bootstrap includes path/environment/log handling.
    # Preserve the single app authority rather than an arbitrary line count.
    tree = ast.parse(text)
    imports = {node.module if isinstance(node, ast.ImportFrom) else alias.name
               for node in ast.walk(tree)
               if isinstance(node, (ast.Import, ast.ImportFrom))
               for alias in node.names}
    assert imports <= {'pathlib', 'os', 'subprocess', 'sys', 'tempfile', 'vflow.main'}
    assert 'vflow.main' in imports
    assert not any(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
