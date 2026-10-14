"""Validate component-specific pytest execution receipts against C2 contracts.

CLI: python -m psx.sfle.native_operation_receipts --backend qt --junit FILE.xml
Exit nonzero if a declared reference was not executed and passed.
No XML result can certify a pending operation or an N/A cell.
"""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .native_operation_contracts import native_operation_contracts


def certify_junit(backend: str, xml_path: str | Path) -> dict:
    root = ET.parse(xml_path).getroot()
    methods: dict[str, str] = {}
    for case in root.iter("testcase"):
        name = case.get("name", "").split("[", 1)[0]
        if not name:
            continue
        failed = any(case.find(tag) is not None
                     for tag in ("error", "failure", "skipped"))
        # Parametrized pytest cases have distinct raw names but the same
        # referenced test method. Every parameter case must pass.
        previous = methods.get(name)
        methods[name] = ("fail" if failed or previous == "fail" else "pass")
    if not methods:
        raise ValueError("No pytest testcase receipts found")
    contracts = [c for c in native_operation_contracts() if c.backend == backend]
    if not contracts:
        raise ValueError(f"Unknown backend {backend!r}")
    records = []
    missing = []
    for c in contracts:
        if c.applicability == "not_applicable":
            status = "not_applicable"
        elif c.reference is None:
            status = "pending"
        elif methods.get(c.reference) == "pass":
            status = "executed_pass"
        else:
            status = "invalid_reference"
            missing.append((c.key, c.reference, methods.get(c.reference)))
        records.append({
            "backend": c.backend, "component": c.component,
            "operation": c.operation, "applicability": c.applicability,
            "mechanism": c.mechanism, "reference": c.reference,
            "status": status, "reason": c.reason,
        })
    if missing:
        raise ValueError(f"Missing or failing required pytest execution receipts: {missing}")
    return {"backend": backend, "cases": len(methods), "contracts": records}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", required=True)
    parser.add_argument("--junit", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = certify_junit(args.backend, args.junit)
    data = json.dumps(report, sort_keys=True, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(data + "\n", encoding="utf-8")
    print(json.dumps({
        "backend": report["backend"],
        "executed_pass": sum(x["status"] == "executed_pass" for x in report["contracts"]),
        "pending": sum(x["status"] == "pending" for x in report["contracts"]),
        "not_applicable": sum(x["status"] == "not_applicable" for x in report["contracts"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
