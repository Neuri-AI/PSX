"""Bounded, commit-accepted intrinsic reuse for immutable native Grid text leaves.

This cache never stores native handles or geometry. Entries are published only
after a complete, successful layout commit. Non-text controls remain measured
by the owning toolkit on every commit.
"""
from __future__ import annotations

from collections import OrderedDict
from weakref import ref

from psx.core.vnode import NodeKind, VNode
from .model import IntrinsicSizes


class _Identity:
    """Hash an immutable VNode/style by identity, never its enormous CSS repr.

    Holding the referent prevents object-id recycling while the bounded
    cache entry is alive. This wrapper does not retain a native widget.
    """
    __slots__ = ("referent",)

    def __init__(self, referent):
        self.referent = referent

    def __hash__(self):
        return id(self.referent)

    def __eq__(self, other):
        return isinstance(other, _Identity) and self.referent is other.referent


class GridIntrinsicReuse:
    def __init__(self, limit: int = 4096):
        self._entries: OrderedDict[tuple, IntrinsicSizes] = OrderedDict()
        self.limit = limit
        self.epoch: int | None = None

    def clear(self):
        self._entries.clear()
        self.epoch = None

    def begin(self, epoch: int):
        if self.epoch != epoch:
            self._entries.clear()
            self.epoch = epoch
        return GridIntrinsicTransaction(self)

    def __len__(self):
        return len(self._entries)


class GridIntrinsicTransaction:
    def __init__(self, owner: GridIntrinsicReuse):
        self.owner = owner
        self.pending: dict[tuple, IntrinsicSizes] = {}

    @staticmethod
    def key(backend, widget, node, width):
        # Native widgets, images, inputs and external objects can change
        # independently of a VNode: they must never use this cache.
        if (node.kind is not NodeKind.HOST or node.type != "Text"
                or node.effective_children):
            return None
        try:
            widget_ref = ref(widget)
            hash(widget_ref)
        except TypeError:
            # Un-weakrefable or unhashable wrappers must not reuse object IDs.
            return None
        source = node.source
        # CSS computed state lives outside VNode.props; include its value and
        # stylesheet scope so text/font/style changes cannot reuse stale hints.
        # Qt's native measurement is width-invariant when the widget does
        # not advertise height-for-width: QtMeasurementSource.measure_width()
        # only uses the supplied width for hasHeightForWidth() widgets.
        # Reuse one certified hint across viewport widths for those leaves.
        # Wrapped labels and other backends keep width-specific cache keys.
        width_key = float(width)
        if backend == "qt":
            has_height_for_width = getattr(widget, "hasHeightForWidth", None)
            if callable(has_height_for_width) and not has_height_for_width():
                width_key = None
        if isinstance(source, VNode):
            # Public VNodes and the CSS snapshots attached by the compiler
            # are immutable. Identity changes on reconciliation, stylesheet
            # application or derived CSS updates; both snapshots are kept
            # alive by _Identity until cache eviction. Native widgets remain
            # represented only by weakref.
            return (
                backend, widget_ref, width_key,
                _Identity(source), _Identity(source.props),
                _Identity(source.css_computed),
                _Identity(source.css_stylesheet),
                _Identity(source.css_source),
            )
        # Test doubles and non-VNode sources do not carry the immutability
        # contract; retain full value-based cache invalidation.
        return (
            backend, widget_ref, width_key, source.type,
            repr(source.props), repr(source.css_computed),
            repr(source.css_stylesheet), repr(source.children),
        )

    def measure(self, backend, widget, node, width, callback):
        key = self.key(backend, widget, node, width)
        if key is None:
            return callback()
        if key in self.pending:
            return self.pending[key]
        if key in self.owner._entries:
            return self.owner._entries[key]
        metrics = callback()
        if isinstance(metrics, IntrinsicSizes):
            self.pending[key] = metrics
        return metrics

    def accept(self, epoch: int):
        if epoch != self.owner.epoch:
            self.pending.clear()
            return
        for key, metrics in self.pending.items():
            self.owner._entries[key] = metrics
            self.owner._entries.move_to_end(key)
        while len(self.owner._entries) > self.owner.limit:
            self.owner._entries.popitem(last=False)
        self.pending.clear()
