"""Width dependency and invalidation contracts for accepted native Grid hints."""

from types import SimpleNamespace

from psx.core.vnode import NodeKind
from psx.sfle.grid_intrinsic_reuse import GridIntrinsicReuse
from psx.sfle.model import IntrinsicSizes


class TextWidget:
    def __init__(self, *, wrapped=False):
        self.wrapped = wrapped

    def hasHeightForWidth(self):
        return self.wrapped


def text_node(text="hello", *, color="#333333"):
    source = SimpleNamespace(
        type="Text",
        props={"text": text},
        css_computed={"color": color},
        css_stylesheet=None,
        children=(),
    )
    return SimpleNamespace(
        kind=NodeKind.HOST, type="Text", effective_children=(), source=source,
    )


def metric(value):
    return IntrinsicSizes(0, value, 0, 20, value, 20)


def test_qt_nonwrapping_text_reuses_width_invariant_hint_after_commit():
    cache = GridIntrinsicReuse()
    widget = TextWidget()
    node = text_node()
    measured = []
    transaction = cache.begin(0)

    def measure_at(width):
        measured.append(width)
        return metric(width)

    first = transaction.measure("qt", widget, node, 180, lambda: measure_at(180))
    same = transaction.measure("qt", widget, node, 280, lambda: measure_at(280))
    assert first is same
    assert measured == [180]
    transaction.accept(0)

    after_commit = cache.begin(0).measure(
        "qt", widget, node, 420, lambda: measure_at(420))
    assert after_commit is first
    assert measured == [180]


def test_qt_wrapped_text_remains_width_sensitive():
    cache = GridIntrinsicReuse()
    widget = TextWidget(wrapped=True)
    node = text_node()
    measured = []
    transaction = cache.begin(0)
    transaction.measure(
        "qt", widget, node, 180,
        lambda: (measured.append(180), metric(180))[1])
    transaction.measure(
        "qt", widget, node, 280,
        lambda: (measured.append(280), metric(280))[1])
    assert measured == [180, 280]


def test_non_qt_text_remains_width_specific():
    cache = GridIntrinsicReuse()
    widget = TextWidget()
    node = text_node()
    measured = []
    transaction = cache.begin(0)
    for width in (180, 280):
        transaction.measure(
            "tk", widget, node, width,
            lambda width=width: (measured.append(width), metric(width))[1])
    assert measured == [180, 280]


def test_qt_nonwrapping_reuse_respects_style_and_invalidation_epoch():
    cache = GridIntrinsicReuse()
    widget = TextWidget()
    node = text_node()
    calls = []
    transaction = cache.begin(0)
    transaction.measure(
        "qt", widget, node, 180,
        lambda: (calls.append("initial"), metric(180))[1])
    transaction.accept(0)

    new_style = text_node(color="#777777")
    transaction = cache.begin(0)
    transaction.measure(
        "qt", widget, new_style, 280,
        lambda: (calls.append("style"), metric(280))[1])
    transaction.accept(0)

    cache.begin(1).measure(
        "qt", widget, new_style, 380,
        lambda: (calls.append("epoch"), metric(380))[1])
    assert calls == ["initial", "style", "epoch"]
