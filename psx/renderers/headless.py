"""Deterministic in-memory renderer for core tests and examples."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from threading import RLock, get_ident

from psx.sfle.model import IntrinsicSizes, LayoutConstraints, LayoutResult, Rect

from psx.core.errors import RendererCapabilityError
from psx.core.events import EventSlot
from psx.core.vnode import NodeKind, VNode
from psx.renderers.adapters import (
    AdapterSubscription,
    DelegatingAdapter,
    RendererAdapterRegistry,
    adapter_key,
    handle_adapter_key,
    run_child_hook,
)
from psx.renderers.components.button import updated_button_props, validate_button_props
from psx.renderers.components.checkbox import updated_checkbox_props, validate_checkbox_props
from psx.renderers.components.input import updated_input_props, validate_input_props
from psx.renderers.components.slider import updated_slider_props, validate_slider_props
from psx.renderers.components.spacer import updated_spacer_props, validate_spacer_props
from psx.renderers.components.text import updated_text_props, validate_text_props
from psx.renderers.components.textarea import updated_textarea_props, validate_textarea_props
from psx.renderers.components.divider import updated_divider_props, validate_divider_props
from psx.renderers.components.image import updated_image_props, validate_image_props
from psx.renderers.components.progressbar import updated_progressbar_props, validate_progressbar_props
from psx.renderers.components.select import updated_select_props
from psx.core.contracts import validate_select_props, validate_switch_props
from psx.renderers.components.switch import updated_switch_props
from psx.renderers.components.link import updated_link_props
from psx.core.contracts import validate_link_props, validate_spinbox_props
from psx.core.contracts import validate_badge_props
from psx.renderers.components.badge import updated_badge_props
from psx.renderers.components.spinbox import updated_spinbox_props
from psx.renderers.components.scroll import updated_scroll_props
from psx.core.contracts import validate_scroll_props
from psx.renderers.components.radio import (
    updated_radio_props,
    updated_radiogroup_props,
    validate_radio_props,
    validate_radiogroup_props,
)

# eq=False: handles compare by identity, so list.remove/in use the fast C
# identity path instead of a recursive field-by-field dataclass comparison.


@dataclass(slots=True, eq=False)
class HeadlessHandle:
    type: object
    props: dict[str, object]
    children: list["HeadlessHandle"] = field(default_factory=list)
    events: dict[str, EventSlot] = field(default_factory=dict)
    destroyed: bool = False
    geometry: Rect | None = None


class HeadlessRenderer:
    """Records native-like operations without importing a UI toolkit."""

    def __init__(
        self,
        *,
        sfle_constraints: LayoutConstraints | None = None,
        measure_intrinsic: Callable[[VNode], IntrinsicSizes | None] | None = None,
        engine: object | None = None,
    ) -> None:
        if sfle_constraints is not None and not isinstance(sfle_constraints, LayoutConstraints):
            raise TypeError("Headless SFLE constraints must be LayoutConstraints.")
        if sfle_constraints is None and (measure_intrinsic is not None or engine is not None):
            raise ValueError("Headless SFLE measurements/engine require viewport constraints.")
        from psx.sfle.backend import load_layout_engine
        self._sfle_constraints = sfle_constraints
        self._sfle_measure = measure_intrinsic
        self._sfle_engine = (engine if engine is not None else load_layout_engine()) if sfle_constraints else None
        self._sfle_generation = 0
        from psx.sfle.native_measurement_invalidation import MeasurementInvalidations
        self._sfle_measurement_invalidations = MeasurementInvalidations()
        self._sfle_invalidation_scheduled = False
        self._sfle_invalidation_lifetime = 0
        self._sfle_mounted_root = None
        self._sfle_in_commit = False
        # Stable native handle identity + immutable prop snapshot index.
        # Published only after a successful geometry transaction.
        self._sfle_intrinsic_cache = {}
        self._sfle_owner_thread = get_ident()
        self.sfle_result: LayoutResult | None = None
        self.operations: list[tuple[object, ...]] = []
        self._pending: list[Callable[[], None]] = []
        self._lock = RLock()
        self.adapters = RendererAdapterRegistry()
        self._default_adapter = DelegatingAdapter()
        for component in (
            "Fragment", "Flex",
            "Text", "Button", "Input", "TextArea", "Checkbox", "Slider",
            "Spacer", "Divider", "Image", "ProgressBar",
            "Radio", "RadioGroup", "Select", "Switch", "Link", "Badge", "SpinBox", "Scroll", "Box", "Native",
        ):
            self.adapters.register(component, self._default_adapter)

    def register_adapter(self, component: str, adapter: object, *, replace: bool = False) -> None:
        self.adapters.register(component, adapter, replace=replace)

    def request_sfle_invalidation(self, reason: str, *, widget_id: int | None = None) -> None:
        """Coalesce semantic measurement changes on the backend owner UI thread.

        The mounted instance is reused; the existing SFLE transaction remains
        the only writer. Teardown invalidates queued work by epoch.
        """
        from psx.sfle.native_measurement_invalidation import MeasurementInvalidations

        if self._sfle_constraints is None:
            raise RendererCapabilityError("SFLE measurement invalidation requires enabled SFLE.")
        state = self._sfle_measurement_invalidations
        state.request(reason, widget_id=widget_id)
        if self._sfle_invalidation_scheduled:
            return
        self._sfle_invalidation_scheduled = True
        scheduled_epoch = self._sfle_invalidation_lifetime

        def flush() -> None:
            if scheduled_epoch != self._sfle_invalidation_lifetime:
                return
            self._sfle_invalidation_scheduled = False
            root = self._sfle_mounted_root
            if root is None or root.disposed or not state.needs_commit():
                return
            epoch = state.epoch
            try:
                self.commit_layout(root)
            except Exception:
                # Preserve all invalidations for explicit retry. A failed
                # native transaction must never acknowledge its epoch.
                self._sfle_last_invalidation_error = True
                raise
            else:
                self._sfle_last_invalidation_error = False
                state.acknowledge(epoch)

        self.schedule_ui(flush)

    def set_sfle_constraints(self, constraints: LayoutConstraints) -> None:
        """Change Headless viewport constraints; caller requests a new commit."""
        if self._sfle_constraints is None:
            raise RendererCapabilityError("SFLE was not enabled for this Headless renderer.")
        if not isinstance(constraints, LayoutConstraints):
            raise TypeError("SFLE constraints must be LayoutConstraints.")
        self._sfle_constraints = constraints
        self._sfle_generation += 1

    def commit_layout(self, root: object) -> None:
        """Commit actual SFLE geometry for the mounted root (if enabled)."""
        if self._sfle_constraints is not None:
            from psx.sfle.headless_layout_bridge import commit_headless_sfle
            commit_headless_sfle(self, root)
            self._sfle_mounted_root = root
            self._sfle_measurement_invalidations.acknowledge(
                self._sfle_measurement_invalidations.epoch)

    def invalidate_layout(self) -> None:
        self._sfle_invalidation_lifetime += 1
        self._sfle_invalidation_scheduled = False
        self._sfle_measurement_invalidations.cancel()
        self._sfle_intrinsic_cache.clear()
        self._sfle_mounted_root = None
        if self._sfle_constraints is not None:
            self._sfle_generation += 1
            self.sfle_result = None

    def create(self, node: VNode, parent: object | None) -> HeadlessHandle:
        adapter = self.adapters.get(adapter_key(node)) or self._default_adapter
        return adapter.create(self, node, parent)  # type: ignore[return-value]

    def _adapter_create(self, node: VNode, parent: object | None) -> HeadlessHandle:
        if self._sfle_constraints is not None:
            if node.kind is NodeKind.NATIVE:
                raise RendererCapabilityError(
                    "Native SFLE native custom widgets require declared geometry and measurement ports."
                )
            if node.kind is NodeKind.HOST:
                from psx.core.registry import builtin_component_registry
                definition = builtin_component_registry().snapshot().get(node.type)
                if definition is None:
                    raise RendererCapabilityError(f"Unknown Headless SFLE host {node.type!r}.")
                if definition.contract is not None:
                    definition.contract.validate(node.props)
            handle = HeadlessHandle(node.type, dict(node.props))
            self.operations.append(("create", handle))
            return handle
        if node.kind is NodeKind.HOST and node.type == "Flex":
            raise RendererCapabilityError(
                "Flex requires the Native SFLE SFLE geometry adapter for Headless; "
                "native fallback layout is forbidden.")
        if node.kind is NodeKind.HOST:
            if node.type == "Text":
                validate_text_props(node.props)
            elif node.type == "Button":
                validate_button_props(node.props)
            elif node.type == "Checkbox":
                validate_checkbox_props(node.props)
            elif node.type == "Input":
                validate_input_props(node.props)
            elif node.type == "TextArea":
                validate_textarea_props(node.props)
            elif node.type == "Slider":
                validate_slider_props(node.props)
            elif node.type == "Spacer":
                validate_spacer_props(node.props)
            elif node.type == "Divider":
                validate_divider_props(node.props)
            elif node.type == "Image":
                validate_image_props(node.props)
            elif node.type == "ProgressBar":
                validate_progressbar_props(node.props)
            elif node.type == "Radio":
                validate_radio_props(node.props)
            elif node.type == "RadioGroup":
                validate_radiogroup_props(node.props)
            elif node.type == "Select":
                validate_select_props(node.props)
            elif node.type == "Switch":
                validate_switch_props(node.props)
            elif node.type == "Link":
                validate_link_props(node.props)
            elif node.type == "Badge":
                validate_badge_props(node.props)
            elif node.type == "SpinBox":
                validate_spinbox_props(node.props)
            elif node.type == "Scroll":
                validate_scroll_props(node.props)
        handle = HeadlessHandle(node.type, dict(node.props))
        self.operations.append(("create", handle))
        return handle

    def update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        adapter = self.adapters.get(
            handle_adapter_key(handle)) or self._default_adapter
        adapter.update(self, handle, changed, removed)

    def _adapter_update(
        self,
        handle: object,
        changed: Mapping[str, object],
        removed: frozenset[str],
    ) -> None:
        target = _handle(handle)
        if self._sfle_constraints is not None:
            from psx.core.registry import builtin_component_registry
            from psx.core.layout_item import validate_flex_item_props
            updated = dict(target.props)
            updated.update(changed)
            for name in removed:
                updated.pop(name, None)
            definition = builtin_component_registry().snapshot().get(target.type)
            if definition is not None and definition.contract is not None:
                definition.contract.validate(updated)
            else:
                validate_flex_item_props(updated, owner=str(target.type))
            target.props = updated
            self.operations.append(("update", target, dict(changed), removed))
            return
        if target.type == "Text":
            updated_text_props(target.props, changed, removed)
        elif target.type == "Input":
            updated_input_props(target.props, changed, removed)
        elif target.type == "TextArea":
            updated_textarea_props(target.props, changed, removed)
        elif target.type == "Slider":
            updated_slider_props(target.props, changed, removed)
        elif target.type == "Button":
            updated_button_props(target.props, changed, removed)
        elif target.type == "Checkbox":
            updated_checkbox_props(target.props, changed, removed)
        elif target.type == "Spacer":
            updated_spacer_props(target.props, changed, removed)
        elif target.type == "Divider":
            updated_divider_props(target.props, changed, removed)
        elif target.type == "Image":
            updated_image_props(target.props, changed, removed)
        elif target.type == "ProgressBar":
            updated_progressbar_props(target.props, changed, removed)
        elif target.type == "Radio":
            updated_radio_props(target.props, changed, removed)
        elif target.type == "RadioGroup":
            updated_radiogroup_props(target.props, changed, removed)
        elif target.type == "Select":
            updated_select_props(target.props, changed, removed)
        elif target.type == "Switch":
            updated_switch_props(target.props, changed, removed)
        elif target.type == "Link":
            updated_link_props(target.props, changed, removed)
        elif target.type == "Badge":
            updated_badge_props(target.props, changed, removed)
        elif target.type == "SpinBox":
            updated_spinbox_props(target.props, changed, removed)
        elif target.type == "Scroll":
            updated_scroll_props(target.props, changed, removed)
        target.props.update(changed)
        for name in removed:
            target.props.pop(name, None)
        self.operations.append(("update", target, dict(changed), removed))

    def insert(self, parent: object, child: object, index: int) -> None:
        adapter = self.adapters.get(
            handle_adapter_key(parent)) or self._default_adapter
        if run_child_hook(adapter, "insert", self, parent, child, index):
            return
        self._default_insert(parent, child, index)

    def _default_insert(self, parent: object, child: object, index: int) -> None:
        container, item = _handle(parent), _handle(child)
        if item in container.children:
            container.children.remove(item)
        container.children.insert(index, item)
        self.operations.append(("insert", container, item, index))

    def move(self, parent: object, child: object, index: int) -> None:
        adapter = self.adapters.get(
            handle_adapter_key(parent)) or self._default_adapter
        if run_child_hook(adapter, "move", self, parent, child, index):
            return
        self._default_move(parent, child, index)

    def _default_move(self, parent: object, child: object, index: int) -> None:
        container, item = _handle(parent), _handle(child)
        container.children.remove(item)
        container.children.insert(index, item)
        self.operations.append(("move", container, item, index))

    def remove(self, parent: object, child: object) -> None:
        adapter = self.adapters.get(
            handle_adapter_key(parent)) or self._default_adapter
        if run_child_hook(adapter, "remove", self, parent, child):
            return
        self._default_remove(parent, child)

    def _default_remove(self, parent: object, child: object) -> None:
        container, item = _handle(parent), _handle(child)
        if item in container.children:
            container.children.remove(item)
        self.operations.append(("remove", container, item))

    def bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        adapter = self.adapters.get(
            handle_adapter_key(handle)) or self._default_adapter
        return AdapterSubscription(adapter, adapter.bind_event(self, handle, event, slot))

    def _adapter_bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        target = _handle(handle)
        target.events[event] = slot
        subscription = (target, event, slot)
        self.operations.append(("bind_event", target, event))
        return subscription

    def unbind_event(self, subscription: object) -> None:
        if isinstance(subscription, AdapterSubscription):
            subscription.adapter.unbind_event(self, subscription.subscription)
            return
        self._adapter_unbind_event(subscription)

    def _adapter_unbind_event(self, subscription: object) -> None:
        target, event, slot = subscription  # type: ignore[misc]
        if target.events.get(event) is slot:
            target.events.pop(event)
        self.operations.append(("unbind_event", target, event))

    def destroy(self, handle: object) -> None:
        adapter = self.adapters.get(
            handle_adapter_key(handle)) or self._default_adapter
        adapter.destroy(self, handle)

    def _adapter_destroy(self, handle: object) -> None:
        target = _handle(handle)
        target.destroyed = True
        self.operations.append(("destroy", target))

    def schedule_ui(self, callback: Callable[[], None]) -> None:
        with self._lock:
            self._pending.append(callback)

    def flush(self) -> None:
        while True:
            with self._lock:
                if not self._pending:
                    return
                callback = self._pending.pop(0)
            callback()

    def run(self) -> int:
        self.flush()
        return 0


def _handle(value: object) -> HeadlessHandle:
    if not isinstance(value, HeadlessHandle):
        raise TypeError("HeadlessRenderer received a foreign handle.")
    return value
