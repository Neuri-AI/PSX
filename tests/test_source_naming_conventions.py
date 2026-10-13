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


def test_executable_filenames_describe_behavior_instead_of_milestones():
    bad = []
    for dirname in CODE_ROOTS:
        for path in (ROOT / dirname).rglob("*"):
            if path.suffix not in {".py", ".yml", ".yaml"}:
                continue
            if MILESTONE.search(path.stem):
                bad.append(str(path.relative_to(ROOT)))
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
