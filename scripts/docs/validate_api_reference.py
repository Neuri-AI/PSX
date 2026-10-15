"""G4 coverage guard for root API names, reference links and import surface.

Checks a checked-in manifest against real psx.__all__ and makes absent root
documentation symbols fail CI, without claiming behavior-specific certification.
"""
import json
from pathlib import Path

import psx

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/architecture/f5-5-api-exports.json"
REFERENCE = ROOT / "docs/public/reference/api-index.mdx"


def check() -> None:
    snapshot = json.loads(MANIFEST.read_text(encoding="utf-8"))
    names = [item["name"] for item in snapshot["exports"]]
    if len(names) != len(set(names)) or set(names) != set(psx.__all__):
        raise ValueError("Root public API manifest drift")
    doc = REFERENCE.read_text(encoding="utf-8")
    missing = [name for name in names if f"`{name}`" not in doc]
    if missing:
        raise ValueError(f"Public exports missing from reference index: {missing}")
    for name in names:
        if not hasattr(psx, name):
            raise ValueError(f"Public name is not importable: {name}")
    print(f"G4 public root names indexed and importable: {len(names)}")


if __name__ == "__main__":
    check()
