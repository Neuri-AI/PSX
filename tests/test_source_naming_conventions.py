"""Executable source naming contract: no planning gates in identifiers.

Milestone labels remain welcome in dated docs and historical commit notes,
not in import paths, filenames, Python symbols or CI workflow filenames.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CODE_ROOTS = ("psx", "tests", "scripts", ".github/workflows")
MILESTONE = re.compile(r"(?:^|[_-])(?:f[1-9]|g[1-9]|c[1-9])(?=[_-])", re.I)

# Existing published workflow names and documentation tools are retained as
# auditable migration debt. New files cannot extend this finite exception set.
HISTORICAL_EXECUTABLE_NAMES = frozenset({
    ".github/workflows/f5-5-api-reference.yml",
    ".github/workflows/f5-5-beginner-examples.yml",
    ".github/workflows/f5-5-clean-room-reproduction.yml",
    ".github/workflows/f5-5-g1-audit.yml",
    ".github/workflows/f5-5-integral-certification.yml",
    ".github/workflows/f5-5-kivy-gallery.yml",
    ".github/workflows/f5-5-native-gallery.yml",
    ".github/workflows/f5-5-public-api.yml",
    ".github/workflows/f5-5-public-docs.yml",
    ".github/workflows/f5-5-qt-gallery.yml",
    ".github/workflows/f5-5-task-board.yml",
    "scripts/docs/generate_g4_reference.py",
    "scripts/docs/validate_f5_5_integral.py",
})


def test_executable_filenames_describe_behavior_instead_of_milestones():
    bad = []
    for dirname in CODE_ROOTS:
        for path in (ROOT / dirname).rglob("*"):
            if path.suffix not in {".py", ".yml", ".yaml"}:
                continue
            if MILESTONE.search(path.stem):
                relative = str(path.relative_to(ROOT))
                if relative not in HISTORICAL_EXECUTABLE_NAMES:
                    bad.append(relative)
    assert not bad, "Milestone-named executable files: " + ", ".join(sorted(bad))


def test_python_identifiers_have_no_phase_gate_prefixes():
    bad = []
    for dirname in ("psx", "tests", "scripts"):
        for path in (ROOT / dirname).rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                candidates = []
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    candidates.append(node.name)
                if isinstance(node, (ast.Name, ast.arg)):
                    candidates.append(node.id if isinstance(node, ast.Name) else node.arg)
                for name in candidates:
                    if MILESTONE.search(name):
                        bad.append(f"{path.relative_to(ROOT)}:{node.lineno}:{name}")
    assert not bad, "Milestone-named Python symbols:\n" + "\n".join(sorted(bad)[:150])
