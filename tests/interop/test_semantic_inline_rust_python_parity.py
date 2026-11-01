"""Installed Rust/Python inline kernel must match exactly at 1/64 CSS px.

Run only in the PyO3-wheel CI job. There must be NO mock and NO fallback:
the primary Rust implementation must execute on every parameterized case.
"""
from __future__ import annotations

import random

import pytest

from psx.sfle.backend import RustLayoutEngine, load_layout_engine
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.semantic_inline_text import (
    InlineTextMetrics, InlineTextSource, layout_inline_text,
)


def _native():
    engine = load_layout_engine()
    assert isinstance(engine, RustLayoutEngine)
    assert engine.backend_name == "rust"
    assert callable(getattr(engine._module, "compute_inline_text_json", None))
    return engine


def _measure(node_id, content):
    # Deterministic synthetic 'native font' metrics, varying by semantic run.
    font = {"before": 8.115, "span": 9.13125, "after": 7.171875}
    size = font.get(node_id, 8.93)
    width = len(content) * size + (0.03125 if len(content) > 1 else 0)
    return InlineTextMetrics(width, 18.09375 + size, 12.078125 + size)


@pytest.mark.parametrize("width", [0, 16.03125, 35, 90, 140, 190, 800, 2048])
@pytest.mark.parametrize("align", ["left", "center", "right"])
@pytest.mark.parametrize("texts", [
    ("Edit ", "main.py", " and save to test HMR"),
    ("hel", "lo", " world"),
    ("alpha  beta", " gamma", " delta   epsilon"),
    ("", "word", ""),
    ("  \\n ", "hello", " \\t"),
    ("Inicio ", "archivo.py", " y guardar"),
    ("hello", "🌎", "  another sentence"),
])
def test_rust_python_line_fragments_match_exactly(width, align, texts):
    sources = tuple(InlineTextSource(node_id, text)
                    for node_id, text in zip(("before", "span", "after"), texts))
    python = layout_inline_text(sources, width, _measure, text_align=align,
                                engine=PythonLayoutEngine())
    rust = layout_inline_text(sources, width, _measure, text_align=align,
                              engine=_native())
    assert rust == python, (width, align, texts, rust, python)
    for fragment in rust.fragments:
        for attribute in ("x", "y", "width", "height", "baseline"):
            value = getattr(fragment, attribute)
            assert value * 64 == int(value * 64), (attribute, fragment)


def test_rust_python_fractional_randomized_corpus_is_bit_identical():
    native = _native()
    rng = random.Random(1396)
    words = ("a", "ab", "ab c", "zero", "main.py", "testing",
             "with", "more words", "🌎", "and space", "x  y")
    for _ in range(128):
        sources = tuple(
            InlineTextSource(name, rng.choice(words))
            for name in ("before", "span", "after")
        )
        width = rng.uniform(0, 750)
        alignment = rng.choice(("left", "center", "right"))
        python = layout_inline_text(
            sources, width, _measure, text_align=alignment,
            engine=PythonLayoutEngine(),
        )
        rust = layout_inline_text(
            sources, width, _measure, text_align=alignment, engine=native,
        )
        assert rust == python, (sources, width, alignment, rust, python)


def test_selected_rust_engine_refuses_missing_inline_abi_without_python_fallback():
    native = RustLayoutEngine(type("OldNative", (), {})())
    sources = (InlineTextSource("before", "Text here"),)
    with pytest.raises(SFLEError) as error:
        layout_inline_text(sources, 250, _measure, engine=native)
    assert error.value.code == DiagnosticCode.BACKEND_MISMATCH
