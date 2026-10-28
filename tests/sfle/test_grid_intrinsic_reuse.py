"""Cross-commit native Grid measurement reuse and invalidation contracts."""
from types import SimpleNamespace

from psx.core.vnode import NodeKind
from psx.sfle.grid_intrinsic_reuse import GridIntrinsicReuse
from psx.sfle.model import IntrinsicSizes


class Widget:
    pass


def leaf(text="hello", css="font:12px"):
    source = SimpleNamespace(
        type="Text", props={"text": text}, children=(),
        css_computed=css, css_stylesheet=None,
    )
    return SimpleNamespace(kind=NodeKind.HOST, type="Text",
                           effective_children=(), source=source)


def metric(height):
    return IntrinsicSizes(12, 12, height, height, 12, height)


def test_cross_commit_reuses_only_matching_width_widget_and_semantics():
    cache = GridIntrinsicReuse()
    widget = Widget()
    calls = []
    def read():
        calls.append(1)
        return metric(len(calls))

    txn = cache.begin(2)
    assert txn.measure("tk", widget, leaf(), 100, read) == metric(1)
    assert txn.measure("tk", widget, leaf(), 100, read) == metric(1)
    assert len(calls) == 1
    txn.accept(2)

    txn = cache.begin(2)
    assert txn.measure("tk", widget, leaf(), 100, read) == metric(1)
    assert len(calls) == 1
    assert txn.measure("tk", widget, leaf(), 90, read) == metric(2)
    assert txn.measure("tk", widget, leaf("changed"), 100, read) == metric(3)
    assert txn.measure("tk", widget, leaf(css="font:20px"), 100, read) == metric(4)
    assert txn.measure("qt", widget, leaf(), 100, read) == metric(5)
    assert txn.measure("tk", Widget(), leaf(), 100, read) == metric(6)
    txn.accept(2)

    txn = cache.begin(3)
    assert txn.measure("tk", widget, leaf(), 100, read) == metric(7)
    assert len(cache) == 0


def test_failed_transaction_never_publishes_and_cache_is_bounded():
    cache = GridIntrinsicReuse(limit=2)
    widget = Widget()
    pending = cache.begin(1)
    assert pending.measure("tk", widget, leaf(), 100, lambda: metric(15)) == metric(15)
    # Simulate commit rollback by discarding the pending transaction.
    assert len(cache) == 0
    accepted = cache.begin(1)
    accepted.measure("tk", widget, leaf(), 100, lambda: metric(20))
    accepted.measure("tk", widget, leaf(), 90, lambda: metric(30))
    accepted.measure("tk", widget, leaf(), 80, lambda: metric(40))
    accepted.accept(1)
    assert len(cache) == 2
    changed = cache.begin(2)
    changed.accept(1)
    assert len(cache) == 0


def test_non_text_widgets_are_never_cached():
    cache = GridIntrinsicReuse()
    native = leaf()
    native.type = "Input"
    calls = []
    txn = cache.begin(1)
    for _ in range(2):
        txn.measure("tk", object(), native, 100, lambda: calls.append(1) or metric(1))
    txn.accept(1)
    assert len(calls) == 2
    assert len(cache) == 0
