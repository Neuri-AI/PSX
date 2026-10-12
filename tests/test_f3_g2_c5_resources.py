"""C5: external image-source revision detection from real file metadata."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from psx.core.vnode import Image, Flex
from psx.sfle.f3_resource_watch import ImageResourceWatch, file_signature


def test_c5_image_resource_revision_detected_without_vnode_or_handle_change(tmp_path):
    path = tmp_path / "resource.png"
    path.write_bytes(b"original")
    vnode = Image(str(path))
    instance = SimpleNamespace(node=vnode, handle=object(), children=(),
                               disposed=False)
    root = SimpleNamespace(node=Flex(), handle=object(),
                           children=(instance,), disposed=False)
    watcher = ImageResourceWatch()
    assert watcher.sync(root)
    assert watcher.changed() == ()
    first = path.stat().st_mtime_ns
    path.write_bytes(b"new-image-bytes")
    os.utime(path, ns=(first + 1_000_000_000, first + 1_000_000_000))
    assert watcher.changed() == (instance,)
    assert watcher.changed() == ()
    assert watcher.sync(root)
    assert watcher.changed() == ()
    instance.disposed = True
    assert watcher.changed() == ()
    watcher.clear()
    assert not watcher._tracked


def test_c5_unsupported_resources_require_explicit_notification():
    assert file_signature("https://example.com/sample.png") is None
    assert file_signature("qrc:/images/logo.png") is None
    assert file_signature("atlas://widgets/button") is None
