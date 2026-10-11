"""RED first: Chromium align_items geometry, eight generated trees on Rust/Python."""
import pytest
from f2_fuzz_dimension_helpers import generate_dimension, run_dimension, rust_binary

DIMENSION = "align_items"

@pytest.mark.parametrize(
    "case", list(generate_dimension(DIMENSION)),
    ids=lambda case: f"align_items-case-{case[0]:02d}",
)
def test_chromium_dimension_align_items_red(case, page, rust_binary):
    run_dimension(page, rust_binary, DIMENSION, case)


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright
    from test_sfle_chromium_version import reference_version
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            assert browser.version == reference_version()
            yield browser.new_page(viewport={"width":800,"height":600},device_scale_factor=1)
        finally:
            browser.close()

