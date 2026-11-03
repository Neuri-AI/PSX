"""Mandatory browser-version gate for all SFLE Chromium geometry fixtures."""
from __future__ import annotations

import json
from importlib.metadata import version as package_version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "tests/sfle/fixtures/f2_alpha_acceptance.json"

LIVE_ORACLES = {"1.63.0": "153.0.8010.12", "1.64.1": "156.0.8078.4"}


def reference_version(playwright_version: str | None = None) -> str:
    """Reviewed live oracle; archived JSON fixtures retain their provenance."""
    installed = playwright_version or package_version("playwright")
    assert installed in LIVE_ORACLES, (
        f"Playwright {installed} has no reviewed Chromium oracle; "
        "validate the geometry suite before adding its exact browser version."
    )
    return LIVE_ORACLES[installed]


def test_chromium_matches_reviewed_live_oracle_and_archive_provenance() -> None:
    from playwright.sync_api import sync_playwright

    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    version = reference["chromium_reference"]["version"]
    assert version == "153.0.8010.12", "Reference upgrade requires explicit fixture regeneration and review."
    assert reference["chromium_reference"]["playwright"] == "1.63.0"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            assert browser.version == reference_version(), (
                f"Chromium {browser.version} differs from the reviewed live oracle; "
                "keep archived fixture provenance and the 0.01px tolerance intact."
            )
        finally:
            browser.close()


def test_unreviewed_playwright_version_does_not_silently_change_the_oracle():
    import pytest
    with pytest.raises(AssertionError, match="no reviewed"):
        reference_version("0.0.0")
