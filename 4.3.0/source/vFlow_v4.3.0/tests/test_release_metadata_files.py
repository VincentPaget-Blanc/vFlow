from pathlib import Path
import json
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_citation_cff_matches_release_version_and_repository():
    text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert "version: 4.3.0" in text
    assert "Paget-Blanc" in text
    assert "https://github.com/VincentPaget-Blanc/vFlow" in text
    assert "license: GPL-3.0-only" in text


def test_zenodo_json_matches_release_version_creator_and_license():
    meta = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    assert meta["version"] == "4.3.0"
    assert meta["upload_type"] == "software"
    assert meta["license"] == "gpl-3.0-only"
    assert meta["creators"] == [{"name": "Paget-Blanc, Vincent", "type": "Researcher"}]


def test_pyproject_exposes_public_repository_urls():
    with (ROOT / "pyproject.toml").open("rb") as fh:
        project = tomllib.load(fh)["project"]
    assert project["version"] == "4.3.0"
    assert project["urls"]["Repository"] == "https://github.com/VincentPaget-Blanc/vFlow"
