"""Whole-engine Rust/Python equivalence against the installed native wheel.

No mocks, no xfail, no skip. Exercises compute, provisional, incremental,
measurement invalidation, errors, Grid and text through matching public APIs.
"""
from __future__ import annotations

import random
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sfle"))
from test_acceptance_contract_regression import case_snapshot  # noqa: E402

from psx.layout.contracts.engine import LayoutEngine
from psx.layout.contracts.errors import SFLEError
from psx.layout.engine.backend import RustLayoutEngine, load_layout_engine
from psx.layout.fallback.engine import PythonLayoutEngine
from psx.layout.grid.contracts import GridSlot, GridItemConstraints
from psx.layout.inline.semantic_inline_text import InlineTextMetrics, InlineTextSource


ALL_CASES = (
    "A01", "A02", "A03", "A04", "A05", "A06", "A07",
    "A08", "A09-LTR", "A09-RTL", "A10",
    "C01", "C02", "C03", "C04", "C05", "C06", "C99",
    "N01", "N02", "N03", "N04", "N05", "N06", "N07", "N08",
    "F01", "F02", "F04", "F05",
)


@pytest.fixture(scope="module")
def backends():
    native = load_layout_engine()
    assert isinstance(native, RustLayoutEngine)
    assert native.backend_name == "rust"
    python = PythonLayoutEngine()
    for engine in (native, python):
        for method in (
            "compute", "compute_incremental", "compute_provisional",
            "compute_grid", "layout_inline_text",
        ):
            assert callable(getattr(engine, method)), (engine.backend_name, method)
    return native, python


def _outcome(callback):
    try:
        return ("ok", callback())
    except SFLEError as exc:
        return ("error", exc.code, exc.node_id)


def _equal(first, second, context):
    assert first == second, (context, first, second)


@pytest.mark.parametrize("case_id", ALL_CASES)
def test_complete_provisional_and_incremental_are_equivalent(case_id, backends):
    rust, python = backends
    request = case_snapshot(case_id)
    original = [_outcome(lambda engine=engine: engine.compute(request))
                for engine in (rust, python)]
    _equal(*original, (case_id, "compute"))
    provisional = [_outcome(lambda engine=engine: engine.compute_provisional(request))
                   for engine in (rust, python)]
    _equal(*provisional, (case_id, "compute_provisional"))
    if original[0][0] != "ok":
        return
    for invalidate in (False, True):
        incremental = [
            _outcome(lambda engine=engine, previous=previous: engine.compute_incremental(
                request,
                previous_input=request,
                previous_result=previous[1],
                native_measurement_invalidated=invalidate,
            ))
            for engine, previous in zip((rust, python), original)
        ]
        _equal(*incremental, (case_id, "same snapshot", invalidate))
        _equal(incremental[0], original[0],
               (case_id, "incremental vs complete", invalidate))
    changed = replace(request, generation=request.generation + 1)
    incremental = [
        _outcome(lambda engine=engine, previous=previous: engine.compute_incremental(
            changed, previous_input=request, previous_result=previous[1],
        ))
        for engine, previous in zip((rust, python), original)
    ]
    full = [_outcome(lambda engine=engine: engine.compute(changed))
            for engine in (rust, python)]
    _equal(*full, (case_id, "next-generation-full"))
    _equal(*incremental, (case_id, "next-generation-incremental"))
    _equal(incremental[0], full[0],
           (case_id, "incremental reflow equals full", changed.generation))


@pytest.mark.parametrize("case_id,new_width", (
    ("A04", 125), ("A05", 100), ("F01", 144), ("A01", 140),
))
def test_style_mutation_incremental_equals_full_reflow(case_id, new_width, backends):
    rust, python = backends
    initial = case_snapshot(case_id)
    nodes = list(initial.nodes)
    root = nodes[0]
    updated = dict(root.style)
    updated["width"] = f"{new_width}px"
    nodes[0] = replace(root, style=tuple(sorted(updated.items())))
    changed = replace(initial, generation=initial.generation + 1,
                      nodes=tuple(nodes))
    previous = (rust.compute(initial), python.compute(initial))
    for invalidated in (False, True):
        incremental = tuple(_outcome(lambda engine=engine, old=old:
            engine.compute_incremental(
                changed, previous_input=initial, previous_result=old,
                native_measurement_invalidated=invalidated,
            )) for engine, old in zip((rust, python), previous))
        complete = tuple(_outcome(lambda engine=engine:
            engine.compute(changed)) for engine in (rust, python))
        assert incremental[0] == incremental[1] == complete[0] == complete[1], (
            case_id, invalidated, incremental, complete,
        )


@pytest.mark.parametrize("case_id", ("A01", "A04", "A05"))
def test_native_measurement_revision_invalidates_equivalently(case_id, backends):
    rust, python = backends
    initial = case_snapshot(case_id)
    measurements = tuple(replace(m, revision=m.revision + 1)
                         for m in initial.measurements)
    assert measurements
    next_request = replace(initial, generation=initial.generation + 1,
                           measurements=measurements)
    previous = (rust.compute(initial), python.compute(initial))
    incremental = tuple(engine.compute_incremental(
        next_request, previous_input=initial, previous_result=old,
    ) for engine, old in zip((rust, python), previous))
    complete = tuple(engine.compute(next_request) for engine in (rust, python))
    assert incremental[0] == incremental[1] == complete[0] == complete[1]


def test_public_protocol_matches_for_every_engine(backends):
    import inspect
    rust, python = backends
    methods = ("compute", "compute_provisional", "compute_incremental",
               "compute_grid", "layout_inline_text")
    for name in methods:
        expected = inspect.signature(getattr(LayoutEngine, name))
        left = inspect.signature(getattr(type(rust), name))
        right = inspect.signature(getattr(type(python), name))
        assert tuple(expected.parameters) == tuple(left.parameters), name
        assert tuple(expected.parameters) == tuple(right.parameters), name
    for feature in (
        "full_layout_compute", "provisional_layout_compute",
        "incremental_layout_compute", "width_dependent_remeasurement",
    ):
        assert rust.capabilities.status(feature) != "unsupported"
        assert python.capabilities.status(feature) != "unsupported"


@pytest.mark.parametrize("rtl", (False, True))
def test_grid_offsets_order_and_constrained_used_sizes(rtl, backends):
    rust, python = backends
    slots = (
        GridSlot("a", 3, offset=1, order=1),
        GridSlot("b", "auto", offset=0, order=-1),
        GridSlot("c", 4, offset=2, order=0),
        GridSlot("d", 6, offset=0, order=2),
    )
    heights = {"a": 45.125, "b": 30.375, "c": 10.0, "d": 50.5}
    bounds = {
        "a": GridItemConstraints(min_width=250, max_height=20),
        "b": GridItemConstraints(max_width=90, min_height=55),
        "c": GridItemConstraints(min_width=20, max_width=200),
    }
    left = rust.compute_grid(slots, 600.125, 4.25, 8.125,
                             heights, bounds, rtl=rtl)
    right = python.compute_grid(slots, 600.125, 4.25, 8.125,
                                heights, bounds, rtl=rtl)
    assert left == right
    assert any(cell.used_width_raw != cell.width_raw
               or cell.used_height_raw != cell.height_raw
               for row in left for cell in row)


def test_randomized_grid_parity_with_nonzero_offsets_and_minmax(backends):
    rust, python = backends
    rng = random.Random(19732026)
    for case in range(200):
        slots = []
        for i in range(rng.randint(1, 18)):
            span = rng.choice((1, 2, 3, 4, 6, 8, 12, "auto"))
            offset = rng.randint(0, min(3, 12 - span)) if isinstance(span, int) else rng.randint(0, 3)
            slots.append(GridSlot(f"g{i}", span, offset=offset,
                                  order=rng.randint(-3, 3)))
        heights = {slot.id: rng.uniform(0, 125) for slot in slots}
        limits = {
            slot.id: GridItemConstraints(
                min_width=rng.uniform(0, 40),
                max_width=rng.uniform(70, 240),
                min_height=rng.uniform(0, 35),
                max_height=rng.uniform(55, 150),
            ) for slot in slots
        }
        args = (tuple(slots), rng.uniform(30, 1600), rng.uniform(0, 9),
                rng.uniform(0, 8), heights, limits)
        rtl = rng.choice((False, True))
        py = _outcome(lambda: python.compute_grid(*args, rtl=rtl))
        rs = _outcome(lambda: rust.compute_grid(*args, rtl=rtl))
        assert rs == py, (case, args, rtl, rs, py)


def test_text_fragments_share_public_engine_protocol(backends):
    rust, python = backends
    sources = (
        InlineTextSource("before", "Edit "),
        InlineTextSource("span", "main.py"),
        InlineTextSource("after", " and save to test HMR"),
    )
    def measure(node_id, content):
        unit = {"before": 7.5, "span": 8.125, "after": 9.25}[node_id]
        return InlineTextMetrics(len(content) * unit, 19.125, 14.0)
    for width in (20, 97.75, 190, 600):
        for align in ("left", "center", "right"):
            assert rust.layout_inline_text(
                sources, width, measure, text_align=align,
            ) == python.layout_inline_text(
                sources, width, measure, text_align=align,
            ), (width, align)


def test_multileaf_width_dependent_convergence_is_identical(backends):
    """Both real solvers must request the same UI metrics in the same rounds."""
    from psx.layout.runtime.remeasure_session import compute_with_width_measurements
    from test_real_multi_leaf_convergence_regression import test_snapshot

    def run(engine):
        calls = []

        def measure(node_id, allocated_width):
            calls.append((node_id, allocated_width))
            preferred = (50 if allocated_width >= 100 else 90) if node_id == "a" else 100
            from psx.layout.contracts.model import IntrinsicSizes
            return IntrinsicSizes(0, preferred, 20, 20, preferred, 20)

        result = compute_with_width_measurements(
            test_snapshot(), engine.compute, measure,
            compute_provisional=engine.compute_provisional,
            initial_widths={"a": 100, "b": 100},
        )
        return result, calls

    native, python = (run(engine) for engine in backends)
    assert native == python
    assert native[1] == [
        ("a", 100), ("b", 100),
        ("a", 75), ("b", 125),
        ("a", 95), ("b", 105),
    ]


def test_seeded_flex_geometry_and_provisional_parity_across_css_axes(backends):
    """Real Rust and Python solve identical nested CSS Flex configurations.

    Reproducible property combinations include direction, wrap, grow/shrink,
    margins, min-width, padding, order, alignment, gap, and RTL.
    """
    from psx.layout.contracts.model import (
        AvailableSize, LayoutConstraints, LayoutInput, LayoutNode,
        WritingDirection,
    )
    rng = random.Random(61218026)
    for trial in range(256):
        width, height = rng.randint(180, 640), rng.randint(120, 460)
        direction = rng.choice(("row", "column", "row-reverse", "column-reverse"))
        wrap = rng.choice(("nowrap", "wrap", "wrap-reverse"))
        nodes = [LayoutNode("root", None, "Flex", tuple(sorted({
            "direction": direction,
            "wrap": wrap,
            "width": f"{width}px",
            "height": f"{height}px",
            "column_gap": f"{rng.randint(0, 12)}px",
            "row_gap": f"{rng.randint(0, 12)}px",
            "align_items": rng.choice(("flex-start", "center", "stretch")),
            "justify_content": rng.choice(("flex-start", "center", "space-between")),
        }.items())))]
        for i in range(rng.randint(1, 5)):
            child = {
                "width": f"{rng.randint(12, 120)}px",
                "height": f"{rng.randint(12, 90)}px",
                "flex_basis": "auto",
                "flex_grow": float(rng.choice((0, 1, 2))),
                "flex_shrink": float(rng.choice((0, 1, 2))),
                "min_width": "0px",
                "order": rng.randint(-2, 2),
                "layout_margin_left": f"{rng.randint(0, 12)}px",
                "layout_margin_top": f"{rng.randint(0, 8)}px",
                "layout_padding_left": f"{rng.randint(0, 8)}px",
            }
            nodes.append(LayoutNode(f"item{i}", "root", "Box",
                                    tuple(sorted(child.items()))))
        snapshot = LayoutInput(
            1, trial + 1000, rng.choice((WritingDirection.LTR, WritingDirection.RTL)),
            LayoutConstraints(AvailableSize(width, True),
                              AvailableSize(height, True)),
            tuple(nodes), (),
        )
        for mode in ("compute", "compute_provisional"):
            left = _outcome(lambda: getattr(backends[0], mode)(snapshot))
            right = _outcome(lambda: getattr(backends[1], mode)(snapshot))
            assert left == right, (trial, mode, snapshot, left, right)
            assert left[0] == "ok", (trial, mode, snapshot, left)


def test_incremental_reuse_receipts_and_geometry_match_across_100_updates(backends):
    """A stable nested Flex sibling is actually reused by both independent solvers."""
    from psx import psx
    from psx.core.layout_tree import normalize_flex_tree
    from psx.layout.contracts.model import AvailableSize, LayoutConstraints
    from psx.layout.projection.native_layout_snapshot import prepare_native_layout_snapshot

    def snapshot(left_width, generation):
        markup = psx(
            '<Flex direction="row" width="350px" height="100px">'
            f'<Flex width="{left_width}px" height="25px" flex_shrink="0">'
            '<Flex width="20px" height="10px" /></Flex>'
            '<Flex width="50px" height="25px" flex_shrink="0">'
            '<Flex width="20px" height="10px" /></Flex>'
            '</Flex>'
        )
        return prepare_native_layout_snapshot(
            normalize_flex_tree(markup),
            LayoutConstraints(AvailableSize(350, True),
                              AvailableSize(100, True)),
            generation=generation,
        ).snapshot

    rust, python = backends
    prior_snapshot = snapshot(40, 1)
    old_rust, old_python = rust.compute(prior_snapshot), python.compute(prior_snapshot)
    assert old_rust == old_python
    for generation in range(2, 102):
        current = snapshot(40 if generation % 2 else 60, generation)
        rust_receipts, python_receipts = [], []
        next_rust = rust.compute_incremental(
            current, previous_input=prior_snapshot,
            previous_result=old_rust, reused_contexts=rust_receipts,
        )
        next_python = python.compute_incremental(
            current, previous_input=prior_snapshot,
            previous_result=old_python, reused_contexts=python_receipts,
        )
        expected_rust, expected_python = rust.compute(current), python.compute(current)
        assert next_rust == next_python == expected_rust == expected_python, generation
        assert rust_receipts == python_receipts, (
            generation, rust_receipts, python_receipts,
        )
        assert current.nodes[3].node_id in rust_receipts, (
            generation, rust_receipts,
        )
        prior_snapshot, old_rust, old_python = current, next_rust, next_python


@pytest.mark.parametrize("invalid", (
    "missing-height", "duplicate-id", "bad-span", "bad-offset",
    "bad-order", "span-plus-offset", "negative-width", "nan-gap",
    "huge-width", "bad-row-gap", "bad-height", "extra-limit",
    "negative-min", "max-before-min", "bad-limit-type", "bad-rtl",
    "boolean-width",
))
def test_invalid_grid_declarations_have_identical_public_diagnostics(invalid, backends):
    """Rust and Python reject bad Grid input with the same exception and text."""
    from psx.layout.grid.contracts import GridPackingError
    slots = (GridSlot("a", 6),)
    width, gap, row_gap, heights, bounds, rtl = (
        300.0, 4.0, 2.0, {"a": 12.0}, {}, False,
    )
    if invalid == "missing-height":
        heights = None
    elif invalid == "duplicate-id":
        slots = (GridSlot("a", 6), GridSlot("a", 6))
    elif invalid == "bad-span":
        slots = (GridSlot("a", 13),)
    elif invalid == "bad-offset":
        slots = (GridSlot("a", 6, offset=-1),)
    elif invalid == "bad-order":
        slots = (GridSlot("a", 6, order=2.5),)
    elif invalid == "span-plus-offset":
        slots = (GridSlot("a", 7, offset=6),)
    elif invalid == "negative-width":
        width = -1.0
    elif invalid == "nan-gap":
        gap = float("nan")
    elif invalid == "huge-width":
        width = 40_000_000.0
    elif invalid == "bad-row-gap":
        row_gap = -0.25
    elif invalid == "bad-height":
        heights = {"a": float("nan")}
    elif invalid == "extra-limit":
        bounds = {"alien": GridItemConstraints()}
    elif invalid == "negative-min":
        bounds = {"a": GridItemConstraints(min_width=-1.0)}
    elif invalid == "max-before-min":
        bounds = {"a": GridItemConstraints(min_height=20, max_height=10)}
    elif invalid == "bad-limit-type":
        bounds = {"a": object()}
    elif invalid == "bad-rtl":
        rtl = "rtl"
    elif invalid == "boolean-width":
        width = True

    observed = []
    for engine in backends:
        with pytest.raises(GridPackingError) as caught:
            engine.compute_grid(
                slots, width, gap, row_gap, heights, bounds, rtl=rtl,
            )
        observed.append(str(caught.value))
    assert observed[0] == observed[1], (invalid, observed)
