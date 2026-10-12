"""Require real JUnit execution receipts for every C4 ownership scenario."""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .f3_g2_c4 import C4_BY_BACKEND


def certify_c4(backend: str, junit: str | Path) -> dict:
    if backend not in C4_BY_BACKEND:
        raise ValueError(f"Unknown C4 backend: {backend!r}")
    root = ET.parse(junit).getroot()
    executions: dict[str, list[str]] = {}
    for case in root.iter("testcase"):
        method = case.get("name", "").split("[", 1)[0]
        if not method:
            continue
        status = ("failed" if any(case.find(tag) is not None
                   for tag in ("failure", "error", "skipped"))
                  else "executed_pass")
        executions.setdefault(method, []).append(status)
    records = []
    gaps = []
    for c in C4_BY_BACKEND[backend]:
        executions_for_method = executions.get(c.test_name, ())
        status = ("executed_pass" if executions_for_method
                  and all(s == "executed_pass" for s in executions_for_method)
                  else "invalid_or_missing")
        records.append({"backend": c.backend, "variant": c.variant,
                        "expectation": c.expectation, "test": c.test_name,
                        "status": status})
        if status != "executed_pass":
            gaps.append((c.variant, c.test_name, executions_for_method))
    if gaps:
        raise ValueError(f"Missing/failed C4 ownership receipts: {gaps}")
    return {"backend": backend, "executed_cases": len(records), "cases": records}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=tuple(C4_BY_BACKEND), required=True)
    parser.add_argument("--junit", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    report = certify_c4(args.backend, args.junit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    print(json.dumps({"backend": args.backend,
                      "executed_pass": report["executed_cases"]}))


if __name__ == "__main__":
    main()
