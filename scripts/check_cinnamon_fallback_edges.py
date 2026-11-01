#!/usr/bin/env python3
"""Audit static dependencies from Rust UI integration into Python fallback.

The standalone fallback is an optional math backend, never a common utility
module. Importing it from the module body outside fallback is a hard layering
violation even when a particular UI scenario happens not to execute the code.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "psx"
violations = []
for path in sorted(ROOT.rglob("*.py")):
    if path.is_relative_to(ROOT / "layout/fallback"):
        continue
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "psx.layout.fallback"
        ):
            violations.append((str(path.relative_to(ROOT.parent)), node.lineno,
                               node.module))
        elif isinstance(node, ast.Import):
            for name in node.names:
                if name.name.startswith("psx.layout.fallback"):
                    violations.append((str(path.relative_to(ROOT.parent)),
                                       node.lineno, name.name))

# For these public numerical façades even a *lazy* import is a layering leak:
# engine-specific code belongs exclusively to engine/backend.py or
# fallback/engine.py, never to Grid/Inline/recursive coordination.
SHARED_NUMERICAL_ENTRY_POINTS = (
    ROOT / "layout/grid/solver.py",
    ROOT / "layout/inline/semantic_inline_text.py",
    ROOT / "layout/runtime/recursive_geometry.py",
)
for path in SHARED_NUMERICAL_ENTRY_POINTS:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (
            (node.module or "") == "psx.layout.fallback"
            or (node.module or "").startswith("psx.layout.fallback.")
        ):
            violations.append((
                str(path.relative_to(ROOT.parent)), node.lineno, node.module,
            ))
        elif isinstance(node, ast.Import):
            for name in node.names:
                if name.name == "psx.layout.fallback" or name.name.startswith(
                    "psx.layout.fallback."
                ):
                    violations.append((
                        str(path.relative_to(ROOT.parent)), node.lineno, name.name,
                    ))
        elif isinstance(node, ast.Attribute) and node.attr == "backend_name":
            violations.append((
                str(path.relative_to(ROOT.parent)), node.lineno,
                "backend_name selection in shared numerical facade",
            ))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "psx.layout.fallback" in node.value or node.value == "backend_name":
                violations.append((
                    str(path.relative_to(ROOT.parent)), node.lineno,
                    "concrete solver / backend selector in shared numerical facade",
                ))

if violations:
    for path, line, module in violations:
        print(f"ARCHITECTURE VIOLATION {path}:{line}: import {module}")
    raise SystemExit(f"{len(violations)} eager Python fallback imports outside fallback")
print("Architecture OK: no eager fallback imports and no concrete-engine edges in shared numerical facades.")
