"""Bounded, commit-accepted intrinsic reuse for immutable native Grid text leaves.

This cache never stores native handles or geometry. Entries are published only
after a complete, successful layout commit. Non-text controls remain measured
by the owning toolkit on every commit.
"""
from __future__ import annotations

from collections import OrderedDict
from weakref import ref

from psx.core.vnode import NodeKind
from .model import IntrinsicSizes


class GridIntrinsicReuse:
    def __init__(self, limit: int = 512):
        self._entries: OrderedDict[tuple, IntrinsicSizes] = OrderedDict()
        self.limit = limit
        self.epoch: int | None = None

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
        return (
            backend, widget_ref, float(width), source.type,
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
