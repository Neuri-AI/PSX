"""Public-behaviour characterization guard for the refactoring milestones.

These assertions intentionally use only public PSX entry points and the
dependency-free renderer.  GUI and optional-integration coverage remains in
the existing renderer/integration suites.
"""

from __future__ import annotations

from psx import Button, Flex, Ref, Text, component, psx, use_ref, use_state
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer


def test_public_python_and_markup_paths_preserve_identity_events_keys_and_refs() -> None:
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints
    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(AvailableSize(640, True), AvailableSize(480, True)),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda node: IntrinsicSizes(4, 20, 8, 12, 18, 12, 8),
    )
    reconciler = Reconciler(renderer)
    observed: list[str] = []

    @component
    def Counter():
        count, set_count = use_state(0)
        button_ref = use_ref()
        return psx(
            "<Flex direction='column' gap={gap}><Text key=\"label\">Count: {count}</Text>"
            "<Button key=\"increment\" ref={button_ref} on_click={increment}>+1</Button></Flex>",
            scope={
                "gap": 8,
                "count": count,
                "button_ref": button_ref,
                "increment": lambda: (observed.append(str(count)), set_count(count + 1)),
            },
        )

    root = reconciler.render(Counter())
    column = root.children[0].handle
    label, button = column.children
    assert isinstance(root.children[0].children[1].ref, Ref)
    assert root.children[0].children[1].ref.current is button
    button.events["on_click"].invoke()
    renderer.flush()
    assert observed == ["0"]
    assert column.children == [label, button]
    assert label.props["value"] == "Count: 1"
    assert button.events["on_click"] is root.children[0].children[1].event_slots["on_click"][0]


def test_public_builders_keep_normalization_and_default_props() -> None:
    tree = Flex("label", Button("Save"), Text("ready"), direction="column")
    assert [child.type for child in tree.children] == ["Text", "Button", "Text"]
    assert tree.children[0].props["value"] == "label"
    assert tree.children[1].props == {"label": "Save", "font_size": 14, "on_click": None, "enabled": True}
    assert tree.children[2].props["font_size"] == 16
