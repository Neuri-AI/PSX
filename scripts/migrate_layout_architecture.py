#!/usr/bin/env python3
"""One-time, deterministic migration of psx.layout to capability-owned modules.

Run from the PSX repository root:
    python scripts/migrate_layout_architecture.py

All 113 original modules must already have been copied to the destinations
listed in scripts/layout_migration_manifest.json. This command rewrites
consumers and REMOVES the obsolete psx/sfle directory. It deliberately does
not touch the git index, branch, tags, or change the numerical algorithms.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts/layout_migration_manifest.json"
MAPPING = json.loads(MANIFEST.read_text())["sourceToTarget"]
MODULES = {source.removesuffix(".py").replace("/", "."):
           target.removesuffix(".py").replace("/", ".")
           for source, target in MAPPING.items()}
REWRITE = re.compile(r"\bpsx\.sfle\.([A-Za-z_]\w*)\b")
OLD_IMPORT = re.compile(r"\bpsx\.sfle\b")


def migrate() -> dict[str, int]:
    missing = [dest for dest in MAPPING.values()
               if not (ROOT / dest).is_file()]
    if missing:
        raise SystemExit(f"Migration aborted: missing copied modules: {missing!r}")
    paths = (ROOT / "psx", ROOT / "tests", ROOT / "scripts",
             ROOT / "benchmarks", ROOT / "examples")
    modified = 0
    for directory in paths:
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.py")):
            if "sfle" in path.relative_to(ROOT).parts and "psx" in path.parts:
                # Only legacy psx/sfle is removed; tests/sfle remains.
                if path.is_relative_to(ROOT / "psx/sfle"):
                    continue
            before = path.read_text(encoding="utf-8")
            def replace(match: re.Match[str]) -> str:
                key = "psx.layout." + match.group(1)
                if key not in MODULES:
                    raise RuntimeError(
                        f"Unmapped old module {key} referenced from {path}"
                    )
                return MODULES[key]
            after = REWRITE.sub(replace, before)
            after = OLD_IMPORT.sub("psx.layout", after)
            if after != before:
                path.write_text(after, encoding="utf-8")
                modified += 1
    # A no-symlink, complete removal ensures Rust-only mode cannot
    # accidentally import Python files from the old namespace.
    import shutil
    old = ROOT / "psx/sfle"
    assert len(MAPPING) == 113
    if old.exists():
        shutil.rmtree(old)
    assert not old.exists()
    return {"rewritten_python_files": modified,
            "relocated_modules": len(MAPPING)}


if __name__ == "__main__":
    print(json.dumps(migrate(), sort_keys=True))
