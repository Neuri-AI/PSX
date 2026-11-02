"""The native layout cache must never hide CSS, content, or geometry changes."""
from dataclasses import replace

from psx.layout.engine import backend as module
from psx.layout.contracts.model import (
    AvailableSize, BoxRect, IntrinsicSizes, LayoutConstraints, LayoutInput,
    LayoutNode, LayoutResult, MeasuredBox, Rect, WritingDirection,
)


def snapshot(generation, width=120, *, text_height=20, color="#333"):
    sizes = LayoutConstraints(
        AvailableSize(width, True), AvailableSize(250, True)
    )
    return LayoutInput(
        1, generation, WritingDirection.LTR, sizes,
        (
            LayoutNode("root", None, "div", (("layout_width", "120px"),)),
            LayoutNode("text", "root", "Text", (("color", color),)),
        ),
        (MeasuredBox(
            "text", IntrinsicSizes(15, 50, text_height, text_height,
                                   50, text_height),
            LayoutConstraints(AvailableSize(None, False),
                              AvailableSize(None, False)),
            generation,
        ),),
    )


class FakeRust:
    def __init__(self):
        self.calls = []

    def compute_json(self, request):
        self.calls.append(request)
        return request


def test_exact_cache_reuses_unchanged_html_across_generations_and_width_cycles(monkeypatch):
    fake = FakeRust()
    monkeypatch.setattr(module, "serialize_snapshot", lambda request: request)

    def deserialize(request, original):
        sizes = original.measurements[0].intrinsic
        w = original.constraints.width.value
        box = BoxRect(Rect(0, 0, w, sizes.preferred_height),
                      Rect(0, 0, w, sizes.preferred_height),
                      Rect(0, 0, w, sizes.preferred_height),
                      Rect(0, 0, w, sizes.preferred_height))
        return LayoutResult(1, original.generation,
                            (("root", box), ("text", box)))

    monkeypatch.setattr(module, "deserialize_response", deserialize)
    engine = module.RustLayoutEngine(fake)
    for generation, width in enumerate((120, 200, 120, 200, 120), 1):
        result = engine.compute(snapshot(generation, width))
        assert result.generation == generation
    assert len(fake.calls) == 2
    assert engine._exact_hits == 3
    assert len(engine._exact_results) == 2


def test_exact_cache_invalidates_for_intrinsic_css_and_constraints(monkeypatch):
    fake = FakeRust()
    monkeypatch.setattr(module, "serialize_snapshot", lambda req: req)
    def deserialize(_wire, request):
        rect = Rect(0, 0, 100, 20)
        box = BoxRect(rect, rect, rect, rect)
        return LayoutResult(1, request.generation, tuple(
            (node.node_id, box) for node in request.nodes
        ))
    monkeypatch.setattr(module, "deserialize_response", deserialize)
    engine = module.RustLayoutEngine(fake)
    for source in (
        snapshot(1), snapshot(2),
        snapshot(3, text_height=32),
        snapshot(4, color="#999"),
        snapshot(5, width=256),
    ):
        engine.compute(source)
    assert len(fake.calls) == 4


def test_exact_cache_is_bounded_and_never_caches_failed_results(monkeypatch):
    fake = FakeRust()
    monkeypatch.setattr(module, "serialize_snapshot", lambda req: req)
    def deserialize(_wire, request):
        rect = Rect(0, 0, 100, 20)
        box = BoxRect(rect, rect, rect, rect)
        return LayoutResult(1, request.generation, tuple(
            (node.node_id, box) for node in request.nodes
        ))
    monkeypatch.setattr(module, "deserialize_response", deserialize)
    engine = module.RustLayoutEngine(fake)
    engine._exact_limit = 2
    for width in (120, 130, 140, 120):
        engine.compute(snapshot(1, width))
    assert len(engine._exact_results) == 2
    assert len(fake.calls) == 4


def test_exact_cache_does_not_apply_to_large_snapshots(monkeypatch):
    fake = FakeRust()
    monkeypatch.setattr(module, "serialize_snapshot", lambda req: req)
    def deserialize(_wire, request):
        rect = Rect(0, 0, 100, 20)
        box = BoxRect(rect, rect, rect, rect)
        return LayoutResult(1, request.generation, tuple(
            (node.node_id, box) for node in request.nodes
        ))
    monkeypatch.setattr(module, "deserialize_response", deserialize)
    engine = module.RustLayoutEngine(fake)
    base = snapshot(1)
    children = tuple(
        LayoutNode(f"extra-{i}", "root", "Text", ())
        for i in range(25)
    )
    large = replace(base, nodes=base.nodes+children)
    engine.compute(large)
    engine.compute(replace(large, generation=2))
    assert len(fake.calls) == 2
    assert len(engine._exact_results) == 0
