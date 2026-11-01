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
if violations:
    for path, line, module in violations:
        print(f"ARCHITECTURE VIOLATION {path}:{line}: import {module}")
    raise SystemExit(f"{len(violations)} eager Python fallback imports outside fallback")
print("Architecture OK: zero eager Python fallback imports outside fallback.")
