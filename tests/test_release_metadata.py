from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib
from packaging.specifiers import SpecifierSet
from packaging.version import Version


def test_package_metadata_and_entry_points_are_declared() -> None:
    root = Path(__file__).resolve().parents[1]
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = metadata["project"]
    assert project["name"] == "velto-core"
    assert Version(project["version"])
    assert project["readme"] == "README.md"
    assert {"pyside6", "pyqt6", "pyqt5", "pyside2", "kivy", "dev"} <= set(
        project["optional-dependencies"])
    assert project["scripts"]["velto-transform"] == "psx.markup.transform:main"
    assert project["scripts"]["velto-dev"] == "psx.devtools.__main__:main"
    supported = SpecifierSet(project["requires-python"])
    assert Version("3.10") in supported
    assert Version("3.9") not in supported
    assert {"include": "psx"} in metadata["tool"]["poetry"]["packages"]
    assert (root / "README.md").is_file()
    assert (root / "LICENSE").is_file()
    assert (root / "CHANGELOG.md").is_file()
    assert (root / ".github" / "workflows" / "ci.yml").is_file()
