"""C5: external image-source revision detection from real file metadata."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from psx.core.vnode import Image, Flex
from psx.sfle.native_resource_watch import ImageResourceWatch, file_signature


def test_native_invalidation_image_resource_revision_detected_without_vnode_or_handle_change(tmp_path):
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
    assert watcher.changed() == (instance,), "Unacknowledged failed reload must retry"
    watcher.acknowledge(instance)
    assert watcher.changed() == ()
    assert watcher.sync(root)
    assert watcher.changed() == ()
    instance.disposed = True
    assert watcher.changed() == ()
    watcher.clear()
    assert not watcher._tracked


def test_native_invalidation_unsupported_resources_require_explicit_notification():
    assert file_signature("https://example.com/sample.png") is None
    assert file_signature("qrc:/images/logo.png") is None
    assert file_signature("atlas://widgets/button") is None


def test_native_invalidation_deleted_image_is_detected_and_recreation_retries(tmp_path):
    path = tmp_path / "resource.png"
    path.write_bytes(b"first")
    instance = SimpleNamespace(node=Image(str(path)), handle=object(),
                               children=(), disposed=False)
    root = SimpleNamespace(node=Flex(), handle=object(),
                           children=(instance,), disposed=False)
    watcher = ImageResourceWatch()
    assert watcher.sync(root)
    path.unlink()
    assert watcher.changed() == (instance,)
    watcher.acknowledge(instance)
    assert watcher.sync(root), "Keep watching a temporarily absent file"
    assert watcher.changed() == ()
    path.write_bytes(b"restored")
    assert watcher.changed() == (instance,)
    watcher.acknowledge(instance)
    assert watcher.changed() == ()


def test_native_invalidation_failed_image_decode_is_retried_without_another_file_change(tmp_path):
    path = tmp_path / "decode.png"
    path.write_bytes(b"version-1")
    instance = SimpleNamespace(node=Image(str(path)), handle=object(),
                               children=(), disposed=False)
    root = SimpleNamespace(node=Flex(), handle=object(),
                           children=(instance,), disposed=False)
    watch = ImageResourceWatch()
    assert watch.sync(root)
    path.write_bytes(b"version-2-longer")
    assert watch.changed() == (instance,)
    # Simulate an exception from a toolkit's native image decoding path.
    assert watch.sync(root)
    assert watch.changed() == (instance,)
    watch.acknowledge(instance)
    assert watch.changed() == ()
