"""Standalone frozen-process F2 A08 probe: Rust wheel or real Python fallback.

Built by PyInstaller on each native OS; no repo checkout at execution.
A missing native extension must be selected at *load-time*, never retried
after a runtime Rust failure.
"""
from __future__ import annotations
import sys
from psx.sfle.backend import load_layout_engine
from psx.sfle.lengths import parse_length
from psx.sfle.model import AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection


def main() -> None:
    assert len(sys.argv) == 2 and sys.argv[1] in ("rust", "python")
    selected = load_layout_engine()
    assert selected.backend_name == sys.argv[1], (
        f"Frozen SFLE backend mismatch: expected {sys.argv[1]}, got {selected.backend_name}"
    )
    root = LayoutNode("root", None, "Flex", (
        ("direction", "row"), ("width", parse_length("100px")),
        ("height", parse_length("60px")), ("align_items", "flex-start"),
    ))
    child = LayoutNode("child", "root", "Box", (
        ("width", parse_length("20px")), ("height", parse_length("20px")),
        ("min_width", parse_length("0px")),
    ))
    request = LayoutInput(1, 17, WritingDirection.LTR, LayoutConstraints(
        AvailableSize(100, True), AvailableSize(60, True)
    ), (root, child), ())
    computed = selected.compute(request)
    boxes = dict(computed.boxes)
    assert list(boxes) == ["root", "child"]
    assert boxes["root"].border.width == 100.0
    assert boxes["child"].border.width == 20.0
    assert boxes["child"].border.x == 0.0
    print(f"SFLE_FROZEN_OK backend={selected.backend_name} schema={computed.schema_version}")


if __name__ == "__main__":
    main()
