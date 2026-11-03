"""Safe native attachment virtualization for already-mounted PSX trees.

This is deliberately a renderer-agnostic *attachment* layer.  Cinnamon and
the existing native measurement caches retain authority over geometry; this
module merely removes certified P2 group roots from their native parent and
reattaches them before a P0/P1 commit.  The logical ``MountedInstance`` tree
and its hook cells remain alive throughout.

Keeping handles allocated is an important first safety boundary: arbitrary
toolkit controls, refs and measurements cannot be recreated transparently.
The classifier records those blockers and leaves only that group attached.
"""
from __future__ import annotations

from dataclasses import replace
from collections import Counter

from psx.core.hooks import Ref
from psx.core.vnode import NodeKind


def _walk(instance):
    yield instance
    for child in instance.children:
        yield from _walk(child)


def _bound_instance(index, binding):
    # StructuralBinding is the production handoff. Avoid importing on every
    # lookup (toolkit import hooks are observable and expensive at this scale).
    instance = getattr(binding, "instance", None)
    if instance is not None and getattr(instance, "structural_binding", None) is not None:
        return instance
    return index.get(id(binding))


def _focused(widget: object) -> bool:
    try:
        checker = getattr(widget, "hasFocus", None)
        if callable(checker) and checker():
            return True
        focus_value = getattr(widget, "focus", False)
        if not callable(focus_value) and bool(focus_value):
            return True
        root = getattr(widget, "winfo_toplevel", None)
        if callable(root):
            return root().focus_get() is widget
    except Exception:
        # A toolkit-specific focus probe must never make virtualization unsafe.
        return True
    return False


def _static_pin_reason(instance) -> str | None:
    """Return the narrowest reason an attachment cannot safely be removed."""
    ancestor = instance.parent
    transparent = True
    while ancestor is not None:
        if (isinstance(ancestor.ref, Ref)
                or (ancestor.node.kind is not NodeKind.COMPONENT
                    and ancestor.node.props.get("ref") is not None)):
            return "native-ref"
        if (transparent and ancestor.node.kind is NodeKind.COMPONENT
                and any(type(slot).__name__ == "_EffectSlot" for slot in ancestor.hooks)):
            return "native-effect"
        if ancestor.node.kind is not NodeKind.COMPONENT:
            transparent = False
        ancestor = ancestor.parent
    for current in _walk(instance):
        if current.node.kind is NodeKind.NATIVE:
            return "external-native"
        if (current.node.kind is NodeKind.HOST and current.node.type not in (
            "Grid", "GridItem", "Flex", "Block", "Text", "div", "p",
            "section", "article", "main", "header", "footer", "ul", "li",
            "h1", "h2", "h3", "h4", "h5", "h6",
        )):
            return "native-state"
        if (isinstance(current.ref, Ref)
                or (current.node.kind is not NodeKind.COMPONENT
                    and current.node.props.get("ref") is not None)):
            return "native-ref"
        # Effects may intentionally close over a native object.  Python cannot
        # prove otherwise, so retain this one group rather than broadening the
        # fallback to its Grid/Flex siblings.
        if any(type(slot).__name__ == "_EffectSlot" for slot in current.hooks):
            return "native-effect"
    return None


def _has_focus(instance) -> bool:
    return any(
        _focused(getattr(current.handle, "widget", current.handle))
        for current in _walk(instance) if current.handle is not None
    )


def _host_parent(instance):
    parent = instance.parent
    while parent is not None and parent.handle is None:
        parent = parent.parent
    return parent


def _materialized_count(root) -> int:
    return sum(1 for instance in _walk(root)
               if instance.handle is not None and instance.native_materialized)


def _set_materialized(instance, value: bool) -> None:
    for current in _walk(instance):
        if current.handle is not None:
            current.native_materialized = value


def _dormant_widget_ids(root) -> frozenset[int]:
    return frozenset(
        id(getattr(instance.handle, "widget", instance.handle))
        for instance in _walk(root)
        if instance.handle is not None and not instance.native_materialized
    )


def _child_index(parent, instance) -> int:
    # Component boundaries are transparent to native ordering.  The selected
    # worksets use host sibling groups, but preserving a stable fallback index
    # keeps reattachment correct when a component is an intermediate node.
    try:
        return parent.children.index(instance)
    except ValueError:
        return len(parent.children)


class NativeMaterialization:
    """Per-renderer diagnostics and reversible P2 attachment transitions."""

    def __init__(self) -> None:
        self.materialized = 0
        self.dematerialized = 0
        self.pinned = Counter()
        self._indexed_root = None
        self._by_handle = {}
        self._pin_cache = {}
        self._descendant_widget_ids = {}
        self._live_count = 0
        self._dormant_ids = set()

    def _instances(self, root):
        """Index live handles once per logical tree, not once per resize."""
        if root is self._indexed_root and self._by_handle:
            return self._by_handle
        indexed = {}
        for instance in _walk(root):
            if instance.structural_binding is not None:
                indexed[id(instance.structural_binding)] = instance
            if instance.handle is not None:
                indexed[id(instance.handle)] = instance
                indexed[id(getattr(instance.handle, "widget", instance.handle))] = instance
            elif instance.structural_binding is not None:
                binding = instance.structural_binding
                indexed[id(binding)] = instance
                indexed[id(binding.widget)] = instance
        self._indexed_root = root
        self._by_handle = indexed
        self._live_count = _materialized_count(root)
        self._dormant_ids = set(_dormant_widget_ids(root))
        return indexed

    def invalidate(self) -> None:
        self._indexed_root = None
        self._by_handle = {}
        self._pin_cache = {}
        self._descendant_widget_ids = {}
        self._live_count = 0
        self._dormant_ids = set()

    def _mark(self, instance, value: bool) -> None:
        for current in _walk(instance):
            if current.handle is None or current.native_materialized == value:
                continue
            widget_id = id(getattr(current.handle, "widget", current.handle))
            current.native_materialized = value
            if value:
                self._live_count += 1
                self._dormant_ids.discard(widget_id)
            else:
                self._live_count -= 1
                self._dormant_ids.add(widget_id)

    def _focused_widget(self, renderer):
        """Use the toolkit focus owner once per transaction when available."""
        try:
            application = getattr(renderer, "application", None)
            focus = getattr(application, "focusWidget", None)
            if callable(focus):
                return True, focus()
            root = getattr(renderer, "root", None)
            focus = getattr(root, "focus_get", None)
            if callable(focus):
                return True, focus()
        except Exception:
            # Unknown focus state is handled by the conservative per-group
            # probe below.
            return False, None
        return False, None

    def _pin(self, instance, focused_widget=None, *, focus_known=False):
        marker = id(instance)
        if marker not in self._pin_cache:
            self._pin_cache[marker] = _static_pin_reason(instance)
        static = self._pin_cache[marker]
        if static is not None:
            return static
        if focus_known:
            ids = self._descendant_widget_ids.get(marker)
            if ids is None:
                ids = frozenset(
                    id(getattr(current.handle, "widget", current.handle))
                    for current in _walk(instance) if current.handle is not None
                )
                self._descendant_widget_ids[marker] = ids
            return ("focused" if focused_widget is not None
                    and id(focused_widget) in ids else None)
        return "focused" if _has_focus(instance) else None

    def synchronize(self, renderer, root, bindings, plan):
        """Activate P0/P1 roots and prepare safe P2 detachment, return plan.

        ``bindings`` is the existing Cinnamon node-id -> renderer-handle map.
        No new layout algorithm, handles, or public API is introduced here.
        """
        by_handle = self._instances(root)
        groups = plan.materialization_groups()
        effective = set(plan.deferred_ids)
        focus_known, focused_widget = self._focused_widget(renderer)

        # P0/P1 must be reattached *before* native geometry writes/readback.
        for root_id, node_ids in groups.items():
            instance = _bound_instance(by_handle, bindings[root_id])
            if instance is None:
                effective.difference_update(node_ids)
                self.pinned["missing-instance"] += 1
                continue
            if root_id in effective and instance.native_suspended:
                # Logical dependency/ref/effect auditing already happened at
                # projection. An absent widget cannot acquire native focus.
                continue
            reason = self._pin(instance, focused_widget, focus_known=focus_known)
            deferred = root_id in effective
            if reason is not None:
                effective.difference_update(node_ids)
                self.pinned[reason] += 1
                deferred = False
            if not deferred and not instance.native_materialized:
                if instance.native_suspended:
                    owner = getattr(renderer, "_psx_reconciler", None)
                    if owner is None:
                        raise RuntimeError("Suspended native subtree has no reconciler owner")
                    retired = [current for current in _walk(instance)
                               if current.structural_binding is not None]
                    owner._resume_native(instance)
                    for current in retired:
                        self._dormant_ids.discard(
                            current.structural_binding.identity.accepted_widget_id)
                        if current.handle is not None:
                            self._live_count += 1
                            by_handle[id(current.handle)] = current
                            by_handle[id(getattr(current.handle, "widget", current.handle))] = current
                    # Flattened batches refer to receipt tokens until this
                    # point. Rebind only this activated group's node ids.
                    for node_id in node_ids:
                        current = _bound_instance(by_handle, bindings[node_id])
                        if current is not None and current.handle is not None:
                            widget = getattr(current.handle, "widget", current.handle)
                            from .structural_binding import StructuralBinding
                            if not isinstance(bindings[node_id], StructuralBinding):
                                bindings[node_id] = widget
                            plan.widgets[node_id] = widget
                    self.materialized += 1
                    continue
                parent = _host_parent(instance)
                if parent is None or parent.handle is None:
                    effective.difference_update(node_ids)
                    self.pinned["missing-parent"] += 1
                    continue
                renderer.insert(parent.handle, instance.native_handle(),
                                _child_index(parent, instance))
                instance.attached = True
                instance._placed_handle = instance.native_handle()
                self._mark(instance, True)
                self.materialized += 1

        # Detachment is deliberately a second, post-commit phase.  A failed
        # geometry transaction must leave the last accepted native tree intact.
        # The caller owns the returned transaction plan until acceptance.
        # Keeping another renderer-owned copy would retain the full logical
        # tree and retired toolkit handles beyond the commit/unmount fence.
        renderer._psx_native_materialization = self
        renderer._psx_native_materialized_count = self._live_count
        renderer._psx_native_dematerialized_count = self.dematerialized
        renderer._psx_native_materialization_pins = dict(self.pinned)
        renderer._psx_native_dormant_widget_ids = frozenset(self._dormant_ids)
        return replace(plan, deferred_ids=frozenset(effective))

    def finalize(self, renderer, root, bindings, plan):
        """Detach P2 roots only after their surrounding commit was accepted."""
        by_handle = self._instances(root)
        groups = plan.materialization_groups()
        effective = set(plan.deferred_ids)
        # Detaching a QWidget/Kivy/Tk subtree is not a free bookkeeping
        # operation (Qt's setParent may synchronously invalidate styles and
        # descendants).  Bound it on the interactive resize path: P2 is
        # already excluded from geometry, measurement and paint work, and a
        # still-attached stale subtree remains safely clipped below viewport
        # until the next bounded retirement opportunity.
        budget = (64 if getattr(renderer, "_psx_in_native_viewport_resize", False)
                  else None)
        retired = 0
        for root_id, node_ids in groups.items():
            if root_id not in effective:
                continue
            if budget is not None and retired >= budget:
                continue
            instance = _bound_instance(by_handle, bindings[root_id])
            if instance is None or not instance.native_materialized:
                continue
            parent = _host_parent(instance)
            if parent is None or parent.handle is None:
                effective.difference_update(node_ids)
                self.pinned["missing-parent"] += 1
                continue
            try:
                owner = getattr(renderer, "_psx_reconciler", None)
                if plan.release_native and owner is not None:
                    # Preserve bindings before releasing resources, then
                    # replace toolkit references with structural identities.
                    members = list(_walk(instance))
                    # Resolve native identities before destroy(). Python may
                    # recycle a freed handle id for a new receipt immediately;
                    # looking up old ids after allocation can bind another
                    # card's node to this group's receipt.
                    node_instances = {
                        node_id: _bound_instance(by_handle, bindings[node_id])
                        for node_id in node_ids
                    }
                    self._mark(instance, False)
                    owner._suspend_native(instance)
                    for current in members:
                        binding = current.structural_binding
                        if binding is not None:
                            by_handle[id(binding)] = current
                            by_handle[id(binding.widget)] = current
                    for node_id in node_ids:
                        current = node_instances[node_id]
                        if current is not None and current.structural_binding is not None:
                            token = current.structural_binding.widget
                            from .structural_binding import StructuralBinding
                            if not isinstance(bindings[node_id], StructuralBinding):
                                bindings[node_id] = token
                            plan.widgets[node_id] = token
                else:
                    renderer.remove(parent.handle, instance.native_handle())
            except Exception:
                # Detachment is an optimization after an accepted layout, not
                # a condition for publishing that layout.  Keep this single
                # group active and report why rather than risking a partial
                # native lifecycle transition.
                effective.difference_update(node_ids)
                self.pinned["detach-failed"] += 1
                continue
            instance.attached = False
            instance._placed_handle = None
            self._mark(instance, False)
            self.dematerialized += 1
            retired += 1
        renderer._psx_native_materialization = self
        renderer._psx_native_materialized_count = self._live_count
        renderer._psx_native_dematerialized_count = self.dematerialized
        renderer._psx_native_materialization_pins = dict(self.pinned)
        renderer._psx_native_dormant_widget_ids = frozenset(self._dormant_ids)
        # Native object ids can be recycled after a real resource release.
        # Rebuild the identity index at the next transaction boundary.
        if plan.release_native and retired:
            self._indexed_root = None
        return replace(plan, deferred_ids=frozenset(effective))


def synchronize_native_materialization(renderer, root, bindings, plan):
    manager = getattr(renderer, "_psx_native_materialization", None)
    if not isinstance(manager, NativeMaterialization):
        manager = NativeMaterialization()
    return manager.synchronize(renderer, root, bindings, plan)


def finalize_native_materialization(renderer, root, bindings, plan):
    manager = getattr(renderer, "_psx_native_materialization", None)
    if not isinstance(manager, NativeMaterialization):
        return plan
    return manager.finalize(renderer, root, bindings, plan)
