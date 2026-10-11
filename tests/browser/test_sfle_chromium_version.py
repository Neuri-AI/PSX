"""Mandatory browser-version gate for all SFLE Chromium geometry fixtures."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "tests/sfle/fixtures/f2_alpha_acceptance.json"

def reference_version() -> str:
    return json.loads(REFERENCE.read_text(encoding="utf-8"))["chromium_reference"]["version"]


def test_chromium_version_matches_immutable_fixture_reference() -> None:
    from playwright.sync_api import sync_playwright

    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    version = reference["chromium_reference"]["version"]
    assert version == "153.0.8010.12", "Reference upgrade requires explicit fixture regeneration and review."
    assert reference["chromium_reference"]["playwright"] == "1.63.0"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            assert browser.version == version, (
                f"Chromium {browser.version} differs from fixture reference {version}; "
                "regenerate every affected oracle explicitly, never relax 0.01px."
            )
        finally:
            browser.close()
