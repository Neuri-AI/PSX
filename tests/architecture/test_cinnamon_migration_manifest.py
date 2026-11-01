"""Check all 113 original layout modules have well-defined new ownership."""
from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads(
    (ROOT / "scripts/layout_migration_manifest.json").read_text(encoding="utf-8")
)["sourceToTarget"]


@pytest.mark.parametrize("source,target", list(MANIFEST.items()))
def test_every_historical_module_is_migrated_with_valid_python(source, target):
    assert source.startswith("psx/sfle/")
    assert not (ROOT / source).exists(), source
    candidate = ROOT / target
    assert candidate.is_file(), (source, target)
    ast.parse(candidate.read_text(encoding="utf-8"), filename=str(candidate))


def test_exact_original_module_inventory_is_accounted_for():
    assert len(MANIFEST) == 113
    assert len(set(MANIFEST.values())) == len(MANIFEST)
    assert MANIFEST["psx/sfle/__init__.py"] == "psx/layout/__init__.py"
    assert MANIFEST["psx/sfle/backend.py"] == "psx/layout/engine/backend.py"
    assert MANIFEST["psx/sfle/engine.py"] == "psx/layout/fallback/engine.py"


@pytest.mark.parametrize(
    "module",
    sorted({
        target.removesuffix(".py").replace("/", ".")
        for target in MANIFEST.values()
        if target.startswith("psx/layout/")
        and not target.startswith(("psx/layout/fallback/", "psx/layout/compat/"))
        and not target.endswith("/__init__.py")
    }),
)
def test_migrated_shared_modules_import_without_python_solver(module):
    # Import contract only: a module body must not eagerly load optional math.
    importlib.import_module(module)
