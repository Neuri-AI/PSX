"""F2 independent 10 x 200 CSS dimension holdout versus Chromium 153.

This goes beyond the existing 5x200 row/nowrap holdouts: each new seed
randomly draws from RTL, row/column reversal, fixed wrap, nested columns,
min/max, main/cross alignment, margins and wrapped align-content. No class
is silently counted as accepted when an engine rejects it.
"""
import random
import pytest

from f2_fuzz_dimension_helpers import (
    DIMENSION_SEEDS, generate_dimension, run_dimension, rust_binary,
)

SEEDS=(
    0x7C110026, 0x7C220026, 0x7C330026, 0x7C440026, 0x7C550026,
    0x7C660026, 0x7C770026, 0x7C880026, 0x7C990026, 0x7CAA0026,
)
COUNT=200
DIMENSIONS=tuple(DIMENSION_SEEDS)


def scenarios():
    for seed in SEEDS:
        rng=random.Random(seed)
        variants={
            dimension:tuple(generate_dimension(
                dimension, seed=seed ^ DIMENSION_SEEDS[dimension],
                count=COUNT,
            ))
            for dimension in DIMENSIONS
        }
        for index in range(COUNT):
            dimension=rng.choice(DIMENSIONS)
            yield seed,index,dimension,variants[dimension][index]


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright
    from test_sfle_chromium_version import reference_version
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        try:
            assert browser.version==reference_version()
            yield browser.new_page(viewport={"width":800,"height":600},
                                   device_scale_factor=1)
        finally:
            browser.close()


@pytest.mark.parametrize(
    "scenario",tuple(scenarios()),
    ids=lambda case:f"seed-{case[0]:08x}-case-{case[1]:03d}-{case[2]}",
)
def test_2000_fresh_cross_dimension_chromium_parity(scenario,page,rust_binary):
    seed,index,dimension,case=scenario
    # run_dimension tests the whole tree, every border axis and both engines
    # at the strict 0.01px Chromium tolerance. Unexpected rejection is FAIL.
    run_dimension(page,rust_binary,dimension,case)
