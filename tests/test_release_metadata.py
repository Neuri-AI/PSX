from __future__ import annotations

from pathlib import Path


def test_alpha_package_metadata_and_entry_points_are_declared() -> None:
    root = Path(__file__).resolve().parents[1]
    metadata = (root / "pyproject.toml").read_text(encoding="utf-8")
    for declaration in (
        'name = "psx"',
        'version = "1.0.0a1"',
        'readme = "README.md"',
        'requires-python = ">=3.10"',
        "[project.optional-dependencies]",
        "qt = ",
        "pyqt6 = ",
        "pyqt5 = ",
        "kivy = ",
        "dev = ",
        'psx-transform = "psx.markup.transform:main"',
        'psx-dev = "psx.devtools.__main__:main"',
    ):
        assert declaration in metadata
    assert (root / "README.md").is_file()
    assert (root / "LICENSE").is_file()
    assert (root / "CHANGELOG.md").is_file()
    assert (root / ".github" / "workflows" / "ci.yml").is_file()
