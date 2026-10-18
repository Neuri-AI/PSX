"""P0 C05 local manifest consistency checker regressions (no network)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.verify_velto_dependency_graph import audit, metadata
from packaging.utils import canonicalize_name


def load(*documents: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as root:
        values = []
        for index, document in enumerate(documents):
            path = Path(root) / f"project{index}.toml"
            path.write_text(document, encoding="utf-8")
            values.append(metadata(path))
    return {canonicalize_name(item.name): item for item in values}


class DependencyGraphTests(unittest.TestCase):
    def test_catches_renamed_distribution(self) -> None:
        providers = load(
            '[project]\nname="velto-core"\nversion="0.1.0"\n',
            '[project]\nname="velto"\nversion="0.1.0"\ndependencies=["psx>=1.0.0a1,<2"]\n',
        )
        problems = audit(providers)
        self.assertEqual(len(problems), 1)
        self.assertIn("psx", problems[0])
        self.assertIn("no local provider", problems[0])

    def test_checks_optional_dependencies_and_normalized_names(self) -> None:
        providers = load(
            '[project]\nname="qyro_engine"\nversion="1.0.0a1"\n',
            '[project]\nname="velto"\nversion="0.1.0"\n'
            '[project.optional-dependencies]\n'
            'pyside6=["qyro-engine>=0.1.0,<0.2.0"]\n',
        )
        problems = audit(providers)
        self.assertEqual(len(problems), 1)
        self.assertIn("extra:pyside6", problems[0])
        self.assertIn("excludes", problems[0])

    def test_compatible_local_manifest_returns_no_conflict(self) -> None:
        providers = load(
            '[project]\nname="velto-core"\nversion="0.1.0"\n',
            '[project]\nname="velto"\nversion="0.1.0"\n'
            'dependencies=["velto-core>=0.1.0,<1"]\n',
        )
        self.assertEqual(audit(providers), [])

    def test_reads_poetry_distribution_identity(self) -> None:
        providers = load(
            '[tool.poetry]\nname="qyro-engine"\nversion="1.0.0a1"\n',
            '[project]\nname="velto"\nversion="0.1.0"\n'
            'dependencies=["qyro-engine>=1.0.0a1,<2"]\n',
        )
        self.assertEqual(audit(providers), [])


if __name__ == "__main__":
    unittest.main()
