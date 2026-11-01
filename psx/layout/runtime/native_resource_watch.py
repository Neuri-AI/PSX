"""C5 local-image resource change tracking for mounted SFLE widgets.

Polling signatures is deliberately backend-neutral: Qt/Tk/Kivy schedule the
poll on their own UI thread, so image reload and SFLE measurement stay native.
Only local regular files are watched; URLs and virtual resources require
explicit invalidation or a native toolkit signal.
"""
from __future__ import annotations

from pathlib import Path

from psx.core.vnode import NodeKind


def file_signature(source: object) -> tuple[int, int] | None:
    if not isinstance(source, (str, Path)):
        return None
    name = str(source)
    if not name or "://" in name or name.startswith(("qrc:", "atlas:")):
        return None
    path = Path(name)
    try:
        if not path.is_file():
            return None
        stat = path.stat()
    except (OSError, ValueError):
        return None
    return stat.st_mtime_ns, stat.st_size


class ImageResourceWatch:
    def __init__(self) -> None:
        self._tracked: dict[int, tuple[object, object, tuple[int, int] | None]] = {}

    def clear(self) -> None:
        self._tracked.clear()

    def sync(self, root: object) -> bool:
        """Retain existing baselines, include new Image handles, discard old."""
        tracked = {}
        def walk(instance: object) -> None:
            if (instance.node.kind is NodeKind.HOST
                    and instance.node.type == "Image"
                    and instance.handle is not None
                    and not instance.disposed):
                source = instance.node.props.get("source")
                if (isinstance(source, (str, Path)) and str(source)
                        and "://" not in str(source)
                        and not str(source).startswith(("qrc:", "atlas:"))):
                    identity = id(instance.handle)
                    prior = self._tracked.get(identity)
                    previous = (
                        prior[2] if prior is not None and prior[1] == source
                        else file_signature(source)
                    )
                    tracked[identity] = (instance, source, previous)
            for child in instance.children:
                walk(child)
        walk(root)
        self._tracked = tracked
        return bool(tracked)

    def changed(self) -> tuple[object, ...]:
        modified = []
        for identity, (instance, source, previous) in tuple(self._tracked.items()):
            if instance.disposed:
                self._tracked.pop(identity, None)
                continue
            current = file_signature(source)
            if current != previous:
                # Do not consume the revision until the native reload succeeds.
                # A failed decode, missing resource or transient toolkit error
                # must be retried on the next owner-thread poll.
                modified.append(instance)
        return tuple(modified)

    def acknowledge(self, instance: object) -> None:
        """Commit a resource revision only after native reload and invalidation."""
        handle = getattr(instance, "handle", None)
        if handle is None or getattr(instance, "disposed", False):
            return
        identity = id(handle)
        prior = self._tracked.get(identity)
        if prior is None or prior[0] is not instance:
            return
        self._tracked[identity] = (instance, prior[1], file_signature(prior[1]))
