"""Reject new certification-only modules in the production SFLE package.

Existing misplacements are pinned as migration debt, not a precedent.
Run: python scripts/check_runtime_boundaries.py
"""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SFLE = ROOT / "psx" / "sfle"
LEGACY = frozenset({
    "f3_g2_c4.py",
    "f3_g2_c4_receipts.py",
    "f3_g2_contracts.py",
    "f3_g2_evidence.py",
    "f3_g2_matrix.py",
    "f3_g2_oracles.py",
    "f3_g2_receipts.py",
})
CERTIFICATION = re.compile(
    r"^(?:f\d+(?:_g\d+)?(?:_c\d+)?_)?(?:"
    r".*_(?:receipts|evidence|matrix|oracles|contracts)|"
    r"(?:receipts|evidence|matrix|oracles|contracts)"
    r")\.py$"
)


def check() -> list[str]:
    violations = []
    for item in SFLE.glob("*.py"):
        if not CERTIFICATION.fullmatch(item.name):
            continue
        if item.name not in LEGACY:
            violations.append(item.name)
        elif f"from tests.certification.{item.stem} import *" not in item.read_text(encoding="utf-8"):
            violations.append(f"{item.name}: legacy module must remain a thin compatibility shim")
    return sorted(violations)


if __name__ == "__main__":
    violations = check()
    if violations:
        raise SystemExit(
            "Certification-only modules cannot live in psx/sfle/: "
            + ", ".join(violations)
        )
    print("Runtime/certification boundary check passed.")
