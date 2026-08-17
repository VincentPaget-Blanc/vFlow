from pathlib import Path
import re


def test_readme_describes_v420_package_entry_point():
    root = Path(__file__).resolve().parents[1]
    text = (root / "README.md").read_text(encoding="utf-8")
    assert "### v4.2.0" in text
    assert "python -m vflow" in text
    assert "vflow 1.4.11.py" not in text
    assert "staged package refactor" not in text


def test_all_local_readme_images_exist():
    root = Path(__file__).resolve().parents[1]
    text = (root / "README.md").read_text(encoding="utf-8")
    local = [src for src in re.findall(r'<img\s+src="([^"]+)"', text)
             if "://" not in src]
    assert local
    missing = [src for src in local if not (root / src).is_file()]
    assert missing == []
