from __future__ import annotations

from psx import Checkbox, psx
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer


def test_checkbox_python_markup_identity_events_and_cleanup() -> None:
    renderer = HeadlessRenderer()
    reconciler = Reconciler(renderer)
    calls: list[tuple[str, bool]] = []
    root = reconciler.render(Checkbox(on_change=lambda value: calls.append(("old", value)), key="accept"))
    handle = root.handle
    handle.events["on_change"].invoke(True)
    reconciler.render(Checkbox(checked=True, on_change=lambda value: calls.append(("new", value)), key="accept"))
    assert reconciler.root.handle is handle
    assert handle.props["checked"] is True
    handle.events["on_change"].invoke(False)
    assert calls == [("old", True), ("new", False)]
    reconciler.unmount()
    assert handle.destroyed and not handle.events


def test_checkbox_is_a_transparent_builtin_markup_tag() -> None:
    node = psx('<Checkbox checked={checked} enabled={enabled} on_change={changed} />', scope={
        "checked": True, "enabled": False, "changed": lambda value: value,
    })
    assert node.type == "Checkbox"
    assert dict(node.props) == {"checked": True, "enabled": False, "on_change": node.props["on_change"]}
