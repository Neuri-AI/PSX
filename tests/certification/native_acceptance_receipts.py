"""C6 executed-operation certificate: fail closed on absent, skipped or failed rows.

Unlike the historical C2 verifier, a required row without an executed test
cannot be reported as successful. C4 external-port evidence remains separate.
"""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .native_operation_contracts import native_operation_contracts

def certify_c6(backend: str, junit: str | Path) -> dict:
    contracts = tuple(c for c in native_operation_contracts() if c.backend == backend)
    if not contracts:
        raise ValueError(f"Unknown C6 backend: {backend!r}")
    root = ET.parse(junit).getroot()
    methods: dict[str, list[str]] = {}
    for case in root.iter("testcase"):
        name = case.get("name", "").split("[", 1)[0]
        if name:
            status = ("failed" if any(case.find(t) is not None
                       for t in ("failure", "error", "skipped"))
                      else "executed_pass")
            methods.setdefault(name, []).append(status)
    if not methods:
        raise ValueError("C6 JUnit contains no testcase executions")
    rows, gaps = [], []
    for c in contracts:
        if c.applicability == "not_applicable":
            status = "not_applicable"
        elif c.applicability != "required" or c.reference is None:
            status = "pending"
        elif methods.get(c.reference) and all(
            x == "executed_pass" for x in methods[c.reference]
        ):
            status = "executed_pass"
        else:
            status = "invalid_reference"
        row = dict(backend=c.backend, component=c.component,
                   operation=c.operation, applicability=c.applicability,
                   reference=c.reference, oracle=c.oracle, status=status,
                   reason=c.reason)
        rows.append(row)
        if c.applicability == "required" and status != "executed_pass":
            gaps.append((c.component, c.operation, status, c.reference))
    if gaps:
        raise ValueError(f"C6 mandatory operation receipts missing/failed: {gaps}")
    return {
        "backend": backend, "junit_cases": sum(map(len, methods.values())),
        "executed_pass": sum(x["status"] == "executed_pass" for x in rows),
        "not_applicable": sum(x["status"] == "not_applicable" for x in rows),
        "pending": 0, "contracts": rows,
    }

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--backend", required=True)
    p.add_argument("--junit", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    report = certify_c6(a.backend, a.junit)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: report[k] for k in ("backend", "executed_pass", "not_applicable", "pending")}, sort_keys=True))

if __name__ == "__main__":
    main()
