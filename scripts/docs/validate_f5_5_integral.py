"""Fail-closed static G6 documentation and reproducibility manifest checks.

This supplements, but never substitutes for, Mintlify, behavioral CI and an
independent beginner review or the project owner's final signoff.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.docs.validate_public_site import check as check_site, nav_pages
from scripts.docs.validate_api_reference import check as check_api

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "docs" / "public"
MANIFEST = ROOT / "docs" / "architecture" / "f5-5-g6-example-manifest.json"


def check() -> None:
    problems = check_site(PUBLIC)
    try:
        check_api()
    except Exception as exc:
        problems.append(f"Root API inventory: {exc}")
    nav = set(nav_pages(json.loads((PUBLIC / "docs.json").read_text())["navigation"]))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        problems.append("Unknown example manifest version")
    seen: set[str] = set()
    for record in manifest["examples"]:
        slug = record["slug"]
        if slug in seen:
            problems.append(f"Duplicate example slug: {slug}")
        seen.add(slug)
        if slug not in nav:
            problems.append(f"Example not present in Mintlify navigation: {slug}")
        page = PUBLIC / (slug + ".mdx")
        if not page.is_file():
            problems.append(f"Missing example page: {slug}")
            continue
        page_text = page.read_text(encoding="utf-8")
        if "Troubleshooting" not in page_text:
            problems.append(f"Example missing troubleshooting section: {slug}")
        for field in ("entry", "commands", "test_paths", "coverage"):
            if not record.get(field):
                problems.append(f"{slug}: missing required {field}")
        for source in [record["entry"], *record["test_paths"]]:
            path = ROOT / source
            if not path.is_file():
                problems.append(f"{slug}: missing local source {source}")
        for claim in record["coverage"]:
            if claim["backend"] not in ("headless", "tkinter", "pyside6", "kivy"):
                problems.append(f"{slug}: unsupported backend claim: {claim['backend']}")
            if not claim.get("workflow"):
                problems.append(f"{slug}: untraceable workflow for {claim['backend']}")
    if problems:
        raise ValueError("G6 preflight failures:\n" + "\n".join(problems))
    print(f"G6 static preflight: {len(nav)} Mintlify pages, {len(seen)} example records, API census PASS")
    print("Independent beginner reproduction and explicit owner signoff: NOT asserted by this check")


if __name__ == "__main__":
    check()
