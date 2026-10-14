"""Fail-closed, dependency-free audit of the documented top-level PSX export surface.

Usage: python scripts/docs/api_census.py --check docs/architecture/f5-5-api-exports.json
       python scripts/docs/api_census.py --write docs/architecture/f5-5-api-exports.json

Run from repository root. This checks only psx.__all__, not completeness of
submodule exports, signatures, contracts, tests or backend verification.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "psx" / "__init__.py"


def census(source: str) -> dict[str, object]:
    tree = ast.parse(source)
    imports: dict[str, str] = {}
    exports: list[str] | None = None
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports[alias.asname or alias.name] = module + "." + alias.name
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            literal = ast.literal_eval(node.value)
            if not isinstance(literal, (list, tuple)) or any(
                not isinstance(name, str) for name in literal
            ):
                raise ValueError("__all__ must contain only literal strings")
            exports = list(literal)
    if exports is None:
        raise ValueError("Missing literal __all__")
    if len(exports) != len(set(exports)):
        raise ValueError("Duplicate exports in __all__")
    missing = sorted(set(exports) - imports.keys())
    if missing:
        raise ValueError(f"Exports without an explicit imported binding: {missing}")
    return {
        "schema_version": 1,
        "source": "psx/__init__.py",
        "export_count": len(exports),
        "exports": [{"name": name, "imported_from": imports[name]} for name in sorted(exports)],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    operations = parser.add_mutually_exclusive_group(required=True)
    operations.add_argument("--check", type=Path)
    operations.add_argument("--write", type=Path)
    args = parser.parse_args()
    content = json.dumps(census(SOURCE.read_text(encoding="utf-8")), indent=2) + "\n"
    if args.write is not None:
        args.write.write_text(content, encoding="utf-8")
    elif args.check.read_text(encoding="utf-8") != content:
        raise SystemExit("Public root export snapshot drift: rerun census and audit changed APIs")
    print("Top-level public export snapshot consistent")


if __name__ == "__main__":
    main()
