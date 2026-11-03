"""Layout identity for a logical host that currently owns no native widget.

These receipts intentionally expose no toolkit geometry or measurement API.
Cinnamon may retain a receipt for P2; any native measurement must first
materialize its owning logical subtree through the reconciler.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(eq=False)
class DormantWidgetIdentity:
    accepted_widget_id: int
    never_materialized: bool = False


@dataclass(eq=False, slots=True)
class StructuralBinding:
    instance: object
    accepted_handle_id: int
    identity: DormantWidgetIdentity

    @property
    def widget(self):
        handle = self.instance.handle
        if handle is not None:
            return getattr(handle, "widget", handle)
        current = self.instance.structural_binding
        return current.identity if current is not None else self.identity

    @property
    def node_type(self):
        return self.instance.node.type

    def __getattr__(self, name):
        handle = self.instance.handle
        if handle is None:
            raise AttributeError(name)
        return getattr(handle, name)


def widget_identity(widget):
    """Retain accepted native identity across retirement, never across remount."""
    if isinstance(widget, DormantWidgetIdentity):
        return widget.accepted_widget_id
    return id(widget)


def layout_binding(instance):
    if instance.structural_binding is None and instance.handle is not None:
        retain_binding(instance)
    return instance.structural_binding


def retain_binding(instance):
    handle = instance.handle
    if handle is not None:
        instance.structural_binding = StructuralBinding(
            instance, id(handle),
            DormantWidgetIdentity(id(getattr(handle, "widget", handle))),
        )


def initialize_structural_binding(instance):
    """Give an unmaterialized host a logical identity, with no native handle."""
    instance.structural_binding = StructuralBinding(
        instance, 0, DormantWidgetIdentity(id(instance), True),
    )


def can_defer_initial_grid_item(node, renderer, parent):
    """Initial certificate for GridItems and repeated normal-flow cards."""
    if parent is None:
        return False
    owner = parent
    while owner is not None and owner.node.kind.name == "COMPONENT":
        owner = owner.parent
    if owner is None:
        return False
    grid_item = node.type == "GridItem" and owner.node.type == "Grid"
    flow_card = (node.type in ("Flex", "div", "p") and bool(node.children)
                 and owner.node.type in ("Flex", "div", "section", "main", "article")
                 and len(owner.node.children) >= 12)
    if (node.kind.name != "HOST" or not (grid_item or flow_card)
            or getattr(renderer, "_sfle_constraints", None) is None
            or renderer.__class__.__module__.split(".")[:3] not in (
                ["psx", "renderers", "qt"], ["psx", "renderers", "tkinter"],
                ["psx", "renderers", "kivy"],
            )):
        return False
    from types import SimpleNamespace
    from psx.layout.adapters.grid_viewport_workset import subtree_is_safe_for_root_culling
    current = parent
    scroll_owners = 0
    while current is not None:
        if current.node.kind.name != "COMPONENT" and current.node.props.get("ref") is not None:
            return False
        # Nested Grid composition is owned by its outer GridItem batch; an
        # inner initial suspension must not bypass that owner's fallback.
        if current.node.type == "GridItem":
            return False
        if not grid_item and current.node.type == "Grid":
            return False
        if current.node.type == "Scroll":
            scroll_owners += 1
            if scroll_owners > 1:
                return False
        else:
            proxy = SimpleNamespace(kind=current.node.kind, type=current.node.type,
                                    source=current.node, effective_children=())
            if current.node.kind.name == "HOST" and not subtree_is_safe_for_root_culling(proxy):
                return False
        if any(type(slot).__name__ == "_EffectSlot" for slot in current.hooks):
            return False
        current = current.parent

    def safe(source):
        # Evaluate components logically first. The resulting host tree, refs
        # and effect slots are available to the viewport/fallback classifier
        # before any native rectangle is committed or an effect runs.
        if source.kind.name == "COMPONENT":
            return True
        if (source.kind.name != "HOST"
                or source.type not in ("GridItem", "Flex", "div", "p", "Text")
                or source.props.get("ref") is not None
                or any(str(key).startswith("on_") or callable(value)
                       for key, value in source.props.items())):
            return False
        if flow_card and len(source.children) >= 12:
            # Only one repeated sibling tier is virtualized in this simple
            # initial certificate; deeper candidates retain the full path.
            return False
        proxy = SimpleNamespace(kind=source.kind, type=source.type,
                                source=source, effective_children=())
        return (subtree_is_safe_for_root_culling(proxy)
                and all(safe(child) for child in source.children))
    return safe(node)


def materialize_for_measurement(renderer, node, handles):
    """Promote only the suspended subtree whose current metrics are required."""
    binding = handles[id(node.source)]
    if isinstance(binding, StructuralBinding) and binding.instance.native_suspended:
        instance = binding.instance
        while instance.parent is not None and instance.parent.native_suspended:
            instance = instance.parent
        renderer._psx_reconciler._resume_native(instance)
    return binding.widget


def promote_required_native_subtrees(renderer, root):
    """Resolve component-discovered native dependencies before native preflight.

    A component can render controls, refs or positioned content which were
    unknown when its GridItem/Flow parent was first evaluated logically.
    Promote that owning group alone; safe sibling groups remain handleless.
    """
    from types import SimpleNamespace
    from .native_materialization import _static_pin_reason
    from psx.layout.adapters.grid_viewport_workset import subtree_is_safe_for_root_culling
    owner = renderer._psx_reconciler

    def safe(instance):
        node = instance.node
        if node.kind.name == "HOST":
            proxy = SimpleNamespace(kind=node.kind, type=node.type, source=node,
                                    effective_children=())
            if not subtree_is_safe_for_root_culling(proxy):
                return False
        return all(safe(child) for child in instance.children)

    def visit(instance):
        if instance.native_suspended:
            if _static_pin_reason(instance) is not None or not safe(instance):
                owner._resume_native(instance)
            return
        for child in instance.children:
            visit(child)

    visit(root)
