"""RED first: Chromium alignment geometry, eight generated trees on Rust/Python."""
import pytest
from f2_fuzz_dimension_helpers import generate_dimension, run_dimension

DIMENSION = "alignment"

@pytest.mark.parametrize(
    "case", list(generate_dimension(DIMENSION)),
    ids=lambda case: f"alignment-case-{case[0]:02d}",
)
def test_chromium_dimension_alignment_red(case, page, rust_binary):
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

@pytest.fixture(scope="module")
def rust_binary():
    from f2_fuzz_dimension_helpers import rust_binary as compiled_runner
    return compiled_runner.__wrapped__()
