"""Tkinter renderer for PSX's small portable primitive subset.

Tkinter is imported only by this adapter.  Layout nodes are represented by
``ttk.Frame`` instances and PSX exclusively manages their ``pack`` children.

Adding a new host tag
---------------------
Call :func:`register_primitive` once (module import time is fine); every
``TkinterRenderer`` picks it up, including renderers created before the call::

    register_primitive(
        "Slider",
        factory=ttk.Scale,                      # called as factory(master)
        validate=validate_slider_props,
        apply=apply_tk_slider,                  # apply(widget, props)
        updated_props=updated_slider_props,
        events={"on_change": ("command", emit_call)},
    )

Container tags are registered with :func:`register_layout`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from queue import Empty, SimpleQueue
from threading import get_ident
import sys
import tkinter as tk
from tkinter import ttk
from psx.core.errors import RendererCapabilityError
from psx.markup.html_aliases import FORMATTING_TAGS
from psx.core.events import EventSlot
from psx.core.native import NativeOwnership, NativeWidget, _clear_native_snapshot
from psx.core.vnode import NodeKind, VNode
from psx.core.props import FLEX_ITEM_PROPS
from psx.sfle.native_component_capabilities import native_leaf_needs_measurement
from psx.sfle.external_native_geometry_ports import external_port_for
from psx.sfle.model import LayoutConstraints, LayoutResult
from psx.renderers.adapters import (
    AdapterSubscription,
    DelegatingAdapter,
    RendererAdapterRegistry,
    adapter_key,
    handle_adapter_key,
    run_child_hook,
)
from psx.renderers.components.text import apply_tk_text, updated_text_props
from psx.renderers.components.button import apply_tk_button, updated_button_props
from psx.renderers.components.checkbox import apply_tk_checkbox, updated_checkbox_props
from psx.renderers.components.input import apply_tk_input, updated_input_props
from psx.renderers.components.textarea import apply_tk_textarea, updated_textarea_props
from psx.renderers.components.slider import apply_tk_slider, updated_slider_props
from psx.renderers.components.spacer import apply_tk_spacer, updated_spacer_props
from psx.renderers.components.progressbar import apply_tk_progressbar, updated_progressbar_props
from psx.renderers.components.radio import updated_radio_props

from psx.core.contracts import (
    validate_textarea_props,
    validate_input_props,
    validate_button_props,
    validate_checkbox_props,
    validate_text_props,
    validate_slider_props,
    validate_spacer_props,
    validate_progressbar_props,
    validate_radio_props,
)

def _tk_css_scalable_font(widget: tk.Misc, family: str) -> bool:
    """Check actual X11/Tk glyph metrics, not the configured font options.

    With bitmap-only aliases such as X11 'fixed', Tcl accepts a 30px bold
    request while continuing to draw the same 10pt normal bitmap.
    """
    from tkinter import font as tkfont

    root = widget.winfo_toplevel()
    cached = getattr(root, "_psx_css_scalable_font_support", None)
    if cached is None:
        cached = {}
        root._psx_css_scalable_font_support = cached
    key = family.casefold()
    if key not in cached:
        small = tkfont.Font(root=widget, family=family, size=-12)
        large = tkfont.Font(root=widget, family=family, size=-30, weight="bold")
        cached[key] = (large.metrics("linespace") > small.metrics("linespace")
                       and large.actual("weight") == "bold")
    return cached[key]


def _tk_css_system_font(widget: tk.Misc, generic: str) -> str | None:
    """Resolve CSS generics from the platform's font inventory, not X11 aliases."""
    from tkinter import font as tkfont

    if sys.platform.startswith("linux"):
        # Fontconfig is the desktop authority for generic family matching on
        # Linux. Tcl/Tk's X11 alias lookup can resolve sans-serif to 'fixed'.
        # Probe both installation and actual Tk rasterization before accepting.
        import subprocess

        try:
            match = subprocess.run(
                ("fc-match", "-f", "%{family}\\n", generic),
                capture_output=True, check=True, text=True, timeout=2,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
        else:
            families = match.stdout.splitlines()
            if families:
                for family in families[0].split(","):
                    candidate = family.strip()
                    if candidate and _tk_css_scalable_font(widget, candidate):
                        return candidate

    # On other platforms, and without fontconfig, use actual native font
    # metrics. A nominally resolved family is not proof of scalable glyphs.
    candidate = str(tkfont.Font(root=widget, family=generic,
                                size=-30, weight="bold").actual("family"))
    if _tk_css_scalable_font(widget, candidate):
        return candidate
    return None


def _resolve_css_tk_font_family(widget: tk.Misc, family_stack: str) -> str:
    """Resolve CSS fallbacks to an actually scalable native font family.

    Keep resolved candidates scoped to the Tk root. Do not substitute a
    hardcoded platform font or silently accept a bitmap-only X11 alias.
    """
    from tkinter import font as tkfont

    if not isinstance(family_stack, str) or not family_stack.strip():
        raise ValueError("CSS font-family requires a nonempty family stack.")
    root = widget.winfo_toplevel()
    inventory = getattr(root, "_psx_css_font_inventory", None)
    if inventory is None:
        inventory = {
            family.casefold(): family for family in tkfont.families(root=widget)
        }
        root._psx_css_font_inventory = inventory
    resolved = getattr(root, "_psx_css_font_fallbacks", None)
    if resolved is None:
        resolved = {}
        root._psx_css_font_fallbacks = resolved
    generics = frozenset({
        "sans-serif", "serif", "monospace", "cursive", "fantasy", "system-ui",
    })
    for part in family_stack.split(","):
        family = part.strip().strip("\\\"'")
        if not family:
            continue
        key = family.casefold()
        if key in generics:
            generic = "sans-serif" if key == "system-ui" else key
            if generic not in resolved:
                resolved[generic] = _tk_css_system_font(widget, generic)
            candidate = resolved[generic]
            if candidate is not None:
                return candidate
            continue
        installed = inventory.get(key)
        if installed is not None and _tk_css_scalable_font(widget, installed):
            return installed

    default = str(tkfont.nametofont("TkDefaultFont", root=widget).actual("family"))
    if _tk_css_scalable_font(widget, default):
        return default
    raise ValueError(
        "Tk CSS font-family cannot find a scalable native face for "
        f"{family_stack!r}; check Tk/Xft and system fontconfig availability."
    )


_LAYOUT_PROPS = frozenset({"spacing", "padding"})
_LAYOUT_UPDATABLE = frozenset({"spacing", "padding"})

# (widget option that holds the callback, factory building the Python callback)
EventDef = tuple[str, Callable[[tk.Misc, EventSlot], Callable[[], object | None]]]

# Makers
def _make_radio(master):
    return ttk.Radiobutton(master)

# Appliers
def apply_tk_radio(widget, props):
    widget.configure(text=str(props["label"]))
    widget.state(("!disabled",) if props["enabled"] else ("disabled",))
    widget._psx_radio_value = props["value"]

# factories for creating event callbacks for Tkinter widgets
def _tk_input_factory(master):
    var = tk.StringVar()
    entry = ttk.Entry(master, textvariable=var)
    entry.var = var
    return entry

def _tk_textarea_factory(master):
    return tk.Text(master, wrap="word")

@dataclass(slots=True, eq=False)
class TkHandle:
    node_type: object
    widget: tk.Misc
    props: dict[str, object]
    children: list["TkHandle"] = field(default_factory=list)
    native: NativeWidget | None = None


@dataclass(slots=True)
class TkEventSubscription:
    widget: tk.Misc
    event: str
    callback: Callable[[], object | None]
    option: str = "command"
    binding_id: str | None = None


@dataclass(slots=True)
class TkNativeEventSubscription:
    dispose: Callable[[], None]


# -- event callback factories (reusable when registering new primitives) ---

def emit_call(widget: tk.Misc, slot: EventSlot) -> Callable[[], object | None]:
    """Invoke the slot with no arguments."""
    return lambda: slot.invoke()


def emit_checked(widget: tk.Misc, slot: EventSlot) -> Callable[[], object | None]:
    """Invoke the slot with the checkbox's current boolean state."""
    return lambda: slot.invoke(bool(widget._psx_variable.get()))

def emit_tk_input(widget, slot):
    def _trace(*_):
        if getattr(widget, "_psx_updating", False):
            return
        slot.invoke(widget.var.get())
    return _trace

def emit_tk_submit(widget, slot):
    def submit(event):
        # Widget-level key bindings execute even when ttk's class binding is
        # disabled. Guard the public callback against that native behavior.
        if not widget.instate(("disabled",)):
            return slot.invoke()
        return None
    return submit

def emit_tk_textarea(widget, slot):
    def _on_modified(event):
        if getattr(widget, "_psx_updating", False):
            return
        if widget.edit_modified():
            widget.edit_modified(False)
            slot.invoke(widget.get("1.0", "end-1c"))
    return _on_modified

def emit_tk_slider(widget, slot):
    def _on_command(value_str):
        if getattr(widget, "_psx_updating", False):
            return
        slot.invoke(float(value_str))
    return _on_command


# -- registries -------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PrimitiveSpec:
    """Everything the renderer needs to know about one leaf host primitive."""

    factory: Callable[[tk.Misc], tk.Misc]
    validate: Callable[[Mapping[str, object]], None]
    apply: Callable[[tk.Misc, Mapping[str, object]], None]
    updated_props: Callable[
        [Mapping[str, object], Mapping[str, object], frozenset[str]], dict[str, object]
    ]
    events: Mapping[str, EventDef] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LayoutSpec:
    horizontal: bool
    props: frozenset[str] = _LAYOUT_PROPS


_PRIMITIVES: dict[str, PrimitiveSpec] = {}
_LAYOUTS: dict[str, LayoutSpec] = {}
_FRAGMENT_LAYOUT = LayoutSpec(horizontal=False, props=frozenset({"spacing"}))
_STRUCTURAL = frozenset({"Fragment", "Native"})


def register_primitive(
    name: str,
    *,
    factory: Callable[[tk.Misc], tk.Misc],
    validate: Callable[[Mapping[str, object]], None],
    apply: Callable[[tk.Misc, Mapping[str, object]], None],
    updated_props: Callable[..., dict[str, object]],
    events: Mapping[str, EventDef] | None = None,
    replace: bool = False,
) -> PrimitiveSpec:
    """Register a leaf host tag."""
    if name in _STRUCTURAL or name in _LAYOUTS or (name in _PRIMITIVES and not replace):
        raise ValueError(f"Primitive {name!r} is already registered.")
    spec = PrimitiveSpec(factory, validate, apply, updated_props, dict(events or {}))
    _PRIMITIVES[name] = spec
    return spec


def register_layout(
    name: str, *, horizontal: bool, props: frozenset[str] = _LAYOUT_PROPS, replace: bool = False
) -> None:
    """Register a container tag backed by a ``ttk.Frame`` managed with ``pack``."""
    if name in _STRUCTURAL or name in _PRIMITIVES or (name in _LAYOUTS and not replace):
        raise ValueError(f"Layout {name!r} is already registered.")
    _LAYOUTS[name] = LayoutSpec(horizontal, props)


# -- built-in tags ----------------------------------------------------------

def _make_checkbox(master: tk.Misc) -> ttk.Checkbutton:
    variable = tk.BooleanVar(master=master)
    widget = ttk.Checkbutton(master, variable=variable)
    widget._psx_variable = variable
    return widget


def _apply_checkbox(widget: tk.Misc, props: Mapping[str, object]) -> None:
    apply_tk_checkbox(widget, props, widget._psx_variable)


register_primitive(
    "Text", factory=lambda master: (tk.Label(master, borderwidth=0, highlightthickness=0, padx=0, pady=0) if sys.platform == "darwin" else ttk.Label(master)),
    validate=validate_text_props, apply=apply_tk_text, updated_props=updated_text_props,
)
register_primitive(
    "Button", factory=ttk.Button,
    validate=validate_button_props, apply=apply_tk_button, updated_props=updated_button_props,
    events={"on_click": ("command", emit_call)},
)
register_primitive(
    "Checkbox", factory=_make_checkbox,
    validate=validate_checkbox_props, apply=_apply_checkbox, updated_props=updated_checkbox_props,
    events={"on_change": ("command", emit_checked)},
)

register_primitive(
    "Input",
    factory=_tk_input_factory,
    validate=validate_input_props,
    apply=apply_tk_input,
    updated_props=updated_input_props,
    events={
        "on_change": ("<<Modified>>", emit_tk_input),  # realmente se usa trace, ver nota
        "on_submit": ("<Return>", emit_tk_submit),
        "on_click": ("<Button-1>", lambda w, s: (lambda event: s.invoke() if not w.instate(("disabled",)) else None)),
    },
)
register_primitive(
    "TextArea",
    factory=_tk_textarea_factory,
    validate=validate_textarea_props,
    apply=apply_tk_textarea,
    updated_props=updated_textarea_props,
    events={"on_change": ("<<Modified>>", emit_tk_textarea)},
)
register_primitive(
    "Slider",
    factory=ttk.Scale,
    validate=validate_slider_props,
    apply=apply_tk_slider,
    updated_props=updated_slider_props,
    events={"on_change": ("command", emit_tk_slider)},
)
register_primitive(
    "Spacer", factory=ttk.Frame,
    validate=validate_spacer_props, apply=apply_tk_spacer,
    updated_props=updated_spacer_props,
)
register_primitive(
    "ProgressBar", factory=lambda master: ttk.Progressbar(master),
    validate=validate_progressbar_props,
    apply=apply_tk_progressbar,
    updated_props=updated_progressbar_props,
)

register_primitive(
    "Radio", factory=_make_radio,
    validate=validate_radio_props,
    apply=apply_tk_radio,
    updated_props=updated_radio_props,
)
# -- renderer ---------------------------------------------------------------

class TkinterRenderer:
    """Map PSX primitives to ttk widgets and use Tk's existing event loop."""

    def __init__(
        self, root: tk.Tk | None = None, *, poll_interval_ms: int = 10,
        sfle_constraints: LayoutConstraints | None = None,
        engine: object | None = None,
    ) -> None:
        if sfle_constraints is not None and not isinstance(sfle_constraints, LayoutConstraints):
            raise TypeError("Tk SFLE viewport must be LayoutConstraints.")
        if sfle_constraints is None and engine is not None:
            raise ValueError("Tk SFLE engine requires explicit viewport constraints.")
        if sfle_constraints is not None and (
            not sfle_constraints.width.definite or not sfle_constraints.height.definite
        ):
            raise RendererCapabilityError("Tk SFLE viewport requires definite axes.")
        from psx.sfle.backend import load_layout_engine
        self._sfle_constraints = sfle_constraints
        self._sfle_engine = (engine if engine is not None else load_layout_engine()) if sfle_constraints else None
        self._sfle_backend = "tk"
        self._sfle_generation = 0
        self._sfle_theme_bind_id = None
        from psx.sfle.native_measurement_invalidation import MeasurementInvalidations
        self._sfle_measurement_invalidations = MeasurementInvalidations()
        from psx.sfle.native_intrinsic_cache import NativeIntrinsicCache
        self._sfle_native_intrinsic_cache = NativeIntrinsicCache()
        self._sfle_prior_solver_input = None
        self._sfle_prior_solver_result = None
        self._sfle_prior_solver_engine = None
        from psx.sfle.native_resource_watch import ImageResourceWatch
        self._sfle_image_resource_watch = ImageResourceWatch()
        self._sfle_resource_poll_scheduled = False
        self._sfle_resource_error: Exception | None = None
        self._sfle_invalidation_scheduled = False
        self._sfle_invalidation_lifetime = 0
        self._sfle_mounted_root = None
        self._sfle_in_commit = False
        self._sfle_owner_thread = get_ident()
        self._sfle_mounted_root = None
        self._sfle_resize_baseline = None
        self._sfle_resize_pending = None
        self._sfle_resize_after_id = None
        self._sfle_resize_bind_id = None
        self._sfle_resize_bind_tag = None
        self._sfle_resize_epoch = 0
        self._sfle_resize_error: Exception | None = None
        self._sfle_textarea_epoch = 0
        self._sfle_textarea_after_id: str | None = None
        self._sfle_textarea_error: Exception | None = None
        self._sfle_root_widget: tk.Misc | None = None
        self.sfle_result: LayoutResult | None = None
        self._sfle_physical_commit_error: float | None = None
        self.root = root if root is not None else tk.Tk()
        self._owns_root = root is None
        self._pending: SimpleQueue[Callable[[], None]] = SimpleQueue()
        self._poll_interval_ms = poll_interval_ms
        self._closed = False
        self._after_id: str | None = None
        self.adapters = RendererAdapterRegistry()
        self._default_adapter = DelegatingAdapter()
        # "Input" stays reserved (unsupported in Tk) so custom adapters still need replace=True.
        for component in dict.fromkeys((*_LAYOUTS, *_PRIMITIVES, "Fragment", "Flex", "Input", "Native")):
            self.adapters.register(component, self._default_adapter)
        from .divider import TkDividerAdapter
        from .image import TkImageAdapter
        from .box import TkBoxAdapter
        from .radiogroup import TkRadioGroupAdapter
        from .select import TkSelectAdapter
        from .switch import TkSwitchAdapter
        from .link import TkLinkAdapter
        from .badge import TkBadgeAdapter
        from .spinbox import TkSpinBoxAdapter
        from .scroll import TkScrollAdapter
        self.adapters.register("Divider", TkDividerAdapter())
        self.adapters.register("Image", TkImageAdapter())
        self.adapters.register("Box", TkBoxAdapter())
        self.adapters.register("RadioGroup", TkRadioGroupAdapter())
        self.adapters.register("Select", TkSelectAdapter())
        self.adapters.register("Switch", TkSwitchAdapter())
        self.adapters.register("Link", TkLinkAdapter())
        self.adapters.register("Badge", TkBadgeAdapter())
        self.adapters.register("SpinBox", TkSpinBoxAdapter())
        self.adapters.register("Scroll", TkScrollAdapter())
        if sfle_constraints is not None:
            from .flex import TkSFLEFlexAdapter
            self.adapters.register("Flex", TkSFLEFlexAdapter(), replace=True)
        self._schedule_drain()

    def register_adapter(self, component: str, adapter: object, *, replace: bool = False) -> None:
        self.adapters.register(component, adapter, replace=replace)

    def _sfle_poll_image_resources(self, lifetime: int) -> None:
        if lifetime != self._sfle_invalidation_lifetime:
            return
        self._sfle_resource_poll_scheduled = False
        root = self._sfle_mounted_root
        if root is None or root.disposed:
            return
        for instance in self._sfle_image_resource_watch.changed():
            if instance.disposed:
                continue
            widget = instance.handle.widget
            # Image adapters cache decoded content by source string; a
            # revision at that same path must bypass the old decoded image.
            widget._psx_source = None
            widget._psx_pixmap_cache = None
            widget._psx_image_cache = None
            source = instance.node.props["source"]
            try:
                self.update(instance.handle, {"source": source}, frozenset())
                reload_image = getattr(widget, "reload", None)
                if callable(reload_image):
                    reload_image()
                self._sfle_resource_error = None
                self.request_sfle_invalidation("resource", widget_id=id(widget))
                self._sfle_image_resource_watch.acknowledge(instance)
            except Exception as error:
                # Preserve the last committed geometry and keep watching;
                # recreating a missing/invalid file can recover in place.
                self._sfle_resource_error = error
        self._sfle_schedule_image_poll()

    def _sfle_schedule_image_poll(self) -> None:
        if self._sfle_resource_poll_scheduled:
            return
        root = self._sfle_mounted_root
        if (root is None or root.disposed
                or not self._sfle_image_resource_watch.sync(root)):
            return
        self._sfle_resource_poll_scheduled = True
        epoch = self._sfle_invalidation_lifetime
        self.root.after(
            600, lambda: self._sfle_poll_image_resources(epoch))

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
        """Explicit Tk host viewport change; caller re-commits the mounted tree."""
        if self._sfle_constraints is None:
            raise RendererCapabilityError("Tk SFLE was not enabled for this renderer.")
        if not isinstance(constraints, LayoutConstraints):
            raise TypeError("Tk SFLE viewport must be LayoutConstraints.")
        if not constraints.width.definite or not constraints.height.definite:
            raise RendererCapabilityError("Tk SFLE viewport axes must be definite.")
        self._sfle_constraints = constraints
        self._sfle_generation += 1
        if self._sfle_root_widget is not None and self._sfle_root_widget.winfo_exists():
            from psx.sfle.native_grid_bridge import is_mounted_native_grid_root
            # A Grid root is projected together with its children by the
            # atomic commit. Placing it here exposes the new parent width
            # while the child rectangles still belong to the previous frame.
            mounted = self._sfle_mounted_root
            if mounted is None:
                self._sfle_root_widget.place_configure(
                    width=round(constraints.width.value),
                    height=round(constraints.height.value),
                )

    def _sfle_on_theme_changed(self, event) -> None:
        if (not self._closed and event.widget is self.root
                and self._sfle_mounted_root is not None):
            self.request_sfle_invalidation("theme")

    def _sfle_on_configure(self, event) -> None:
        if (self._closed or event.widget is not self.root
                or self._sfle_mounted_root is None):
            return
        width, height = event.width, event.height
        # Aqua can dispatch obsolete 1x1 Configure events during window
        # mapping, after the real viewport has already been established.
        # Never replace Cinnamon's definite window constraints with that
        # transient geometry or an event no longer matching the Tk host.
        if width <= 1 or height <= 1:
            return
        if (width, height) != (self.root.winfo_width(), self.root.winfo_height()):
            return
        if self._sfle_resize_baseline == (width, height):
            return
        self._sfle_resize_baseline = (width, height)
        constraints = self._sfle_constraints
        if constraints is None:
            return
        target = (
            width if self._sfle_root_axis_tracks_viewport("width") else constraints.width.value,
            height if self._sfle_root_axis_tracks_viewport("height") else constraints.height.value,
        )
        if (constraints.width.value, constraints.height.value) == target:
            return
        self._sfle_resize_pending = target
        # Cocoa's live-resize tracking loop may defer Tcl after(0) callbacks
        # until the mouse is released. Consume the native Configure event
        # directly on Aqua so the mounted tree follows each delivered size.
        # Do not recurse while a layout transaction is already running.
        if sys.platform == "darwin" and not self._sfle_in_commit:
            if self._sfle_resize_after_id is not None:
                self.root.after_cancel(self._sfle_resize_after_id)
                self._sfle_resize_after_id = None
            self._sfle_flush_viewport_resize(self._sfle_resize_epoch)
            return
        if self._sfle_resize_after_id is None:
            epoch = self._sfle_resize_epoch
            # Run the coalesced commit before Tk's idle redraw. An idle
            # callback can run after Tk paints old child rectangles against
            # the new window bounds, causing the visible snap-back effect.
            self._sfle_resize_after_id = self.root.after(
                0, lambda: self._sfle_flush_viewport_resize(epoch),
            )

    def _sfle_root_axis_tracks_viewport(self, axis: str) -> bool:
        """Whether the mounted SFLE root resolves this axis from the host."""
        from psx.core.vnode import NodeKind
        from psx.sfle.lengths import LengthKind, parse_length

        instance = self._sfle_mounted_root
        while instance is not None and instance.node.kind is NodeKind.COMPONENT:
            if len(instance.children) != 1:
                return False
            instance = instance.children[0]
        if instance is None:
            return False
        if instance.node.type in FORMATTING_TAGS:
            # Semantic roots use viewport constraints even when their own
            # content box is intrinsically or explicitly sized. Descendants
            # may still depend on vw/vh and need a fresh Cinnamon commit.
            return True
        if instance.node.type == "Grid":
            # A mounted Grid root also follows the native viewport. Without
            # this branch Tk ignored interactive window resizing while the
            # explicit set_sfle_constraints() benchmark still passed.
            return True
        if instance.node.type != "Flex":
            return False
        value = instance.node.props.get(axis, "auto")
        return parse_length(value).kind in {LengthKind.AUTO, LengthKind.PERCENT,
                                            LengthKind.VW, LengthKind.VH,
                                            LengthKind.VMIN, LengthKind.VMAX}

    def _sfle_flush_viewport_resize(self, epoch: int) -> None:
        self._sfle_resize_after_id = None
        if (self._closed or epoch != self._sfle_resize_epoch
                or self._sfle_mounted_root is None):
            return
        size = self._sfle_resize_pending
        self._sfle_resize_pending = None
        if size is None:
            return
        root = self._sfle_mounted_root
        if root.disposed:
            return
        from psx.sfle.model import AvailableSize
        try:
            self.set_sfle_constraints(LayoutConstraints(
                AvailableSize(size[0], True), AvailableSize(size[1], True),
            ))
            self.commit_layout(root)
            self._sfle_resize_error = None
        except Exception as exc:
            self._sfle_resize_error = exc
            import logging
            logging.getLogger(__name__).exception("Tk SFLE viewport resize failed")

    def _sfle_on_textarea_modified(self, event) -> None:
        widget = event.widget
        if (self._closed or self._sfle_constraints is None
                or self._sfle_mounted_root is None or self._sfle_in_commit
                or getattr(widget, "_psx_updating", False)
                or not widget.edit_modified()):
            return
        if self._sfle_textarea_after_id is None:
            epoch = self._sfle_textarea_epoch
            self._sfle_textarea_after_id = self.root.after_idle(
                lambda: self._sfle_flush_textarea_modified(epoch),
            )

    def _sfle_flush_textarea_modified(self, epoch: int) -> None:
        self._sfle_textarea_after_id = None
        if (self._closed or epoch != self._sfle_textarea_epoch
                or self._sfle_mounted_root is None):
            return
        root = self._sfle_mounted_root
        if root.disposed:
            return
        try:
            self._sfle_measurement_invalidations.request("content")
            self.commit_layout(root)
            self._sfle_textarea_error = None
        except Exception as exc:
            self._sfle_textarea_error = exc
            import logging
            logging.getLogger(__name__).exception("Tk TextArea SFLE remeasurement failed")

    def commit_layout(self, root: object) -> None:
        if self._sfle_constraints is None:
            return
        from psx.sfle.native_grid_bridge import is_mounted_native_grid_root, commit_native_grid
        from psx.sfle.grid_native_commit import GridCommitBackend
        from psx.sfle.tkinter_layout_bridge import commit_tk_sfle
        # Native style/texture signals can arrive while measuring. Retry a
        # bounded number of times using the latest semantic epoch; never
        # publish a transaction rejected for stale measurements.
        from psx.sfle.errors import SFLEError
        prior_signatures = getattr(self, "_sfle_committed_signatures", None)
        semantic_dirty = self._sfle_measurement_invalidations.needs_commit()
        grid_root = is_mounted_native_grid_root(root)
        for attempt in range(3):
            try:
                if grid_root:
                    commit_native_grid(self, root, backend=GridCommitBackend.TK)
                else:
                    commit_tk_sfle(self, root)
                break
            except SFLEError as error:
                if ("Stale semantic invalidation" not in str(error)
                        or attempt == 2):
                    raise
        # An Aqua background reconciliation walks every descendant and
        # crosses the Tcl bridge for each one. Pure viewport changes cannot
        # change CSS backgrounds when the mounted identities, declarative
        # dependencies and paint properties are unchanged. Keep the full
        # walk for first mount, semantic invalidations, unsafe properties,
        # replacements and style changes.
        current_signatures = getattr(self, "_sfle_committed_signatures", None)
        same_paint_tree = (
            not grid_root
            and prior_signatures is not None
            and current_signatures is not None
            and prior_signatures[0][1] == current_signatures[0][1]
            and prior_signatures[1] == current_signatures[1]
        )
        if semantic_dirty or not same_paint_tree:
            self._sync_aqua_layout_surfaces()
        self._sfle_measurement_invalidations.acknowledge(
            self._sfle_measurement_invalidations.epoch)

        self._sfle_textarea_epoch += 1
        if self._sfle_textarea_after_id is not None:
            self.root.after_cancel(self._sfle_textarea_after_id)
            self._sfle_textarea_after_id = None
        if self._sfle_resize_bind_id is None:
            # Subscribe after the first successful commit: ignore native
            # initialization and changes of unrelated child Frames.
            self._sfle_resize_baseline = (
                self.root.winfo_width(), self.root.winfo_height(),
            )
            # Toplevel widget binding tags are inherited by descendants.
            # A normal root.bind('<Configure>') dispatches a full Python
            # Event object for every child placement, even though our handler
            # discards those events. Use a root-only tag instead.
            tag = f"PSXResizeRoot_{id(self)}"
            self.root.bindtags((tag, *self.root.bindtags()))
            self._sfle_resize_bind_tag = tag
            self._sfle_resize_bind_id = self.root.bind_class(
                tag, "<Configure>", self._sfle_on_configure, add="+",
            )
        if self._sfle_theme_bind_id is None:
            self._sfle_theme_bind_id = self.root.bind(
                "<<ThemeChanged>>", self._sfle_on_theme_changed, add="+",
            )
        self._sfle_mounted_root = root
        self._sfle_schedule_image_poll()

    def _sync_aqua_layout_surfaces(self) -> None:
        """Project CSS backgrounds onto structural Aqua Grid track hosts.

        Classic Frames have no theme-painted border, so an empty Grid and
        spaces between GridItems expose the ancestor's background exactly.
        Cinnamon alone controls their native rectangles.
        """
        if sys.platform != "darwin":
            return

        def walk(widget):
            if getattr(widget, "_psx_css_layout_surface", False):
                ancestor = widget.master
                fill = None
                while ancestor is not None:
                    fill = getattr(ancestor, "_psx_css_background", None)
                    if fill is not None:
                        break
                    ancestor = getattr(ancestor, "master", None)
                resolved = (fill if fill is not None
                            else widget._psx_css_layout_default_background)
                if str(widget.cget("background")) != resolved:
                    widget.configure(background=resolved)
            for child in widget.winfo_children():
                if child is not getattr(widget, "_psx_css_fill_canvas", None):
                    walk(child)

        walk(self.root)

    def invalidate_layout(self) -> None:
        self._sfle_invalidation_lifetime += 1
        self._sfle_invalidation_scheduled = False
        self._sfle_measurement_invalidations.cancel()
        self._sfle_native_intrinsic_cache.clear()
        # A full unmount/remount must drop cached VNode blueprints and old
        # native intrinsic identities; a later tree always starts fresh.
        for cache_name in (
            "_psx_grid_intrinsic_reuse", "_psx_grid_flow_blueprints",
            "_sfle_structural_snapshot_reuse",
        ):
            cache = getattr(self, cache_name, None)
            if cache is not None:
                cache.clear()
        self._sfle_prior_solver_input = None
        self._sfle_prior_solver_result = None
        self._sfle_prior_solver_engine = None
        self._sfle_image_resource_watch.clear()
        self._sfle_resource_poll_scheduled = False
        self._sfle_mounted_root = None
        if self._sfle_theme_bind_id is not None:
            try:
                self.root.unbind("<<ThemeChanged>>", self._sfle_theme_bind_id)
            except tk.TclError:
                pass
            self._sfle_theme_bind_id = None
        if self._sfle_constraints is not None:
            self._sfle_generation += 1
            self._sfle_resize_epoch += 1
            self._sfle_textarea_epoch += 1
            if self._sfle_textarea_after_id is not None:
                try:
                    self.root.after_cancel(self._sfle_textarea_after_id)
                except tk.TclError:
                    pass
                self._sfle_textarea_after_id = None
            self._sfle_textarea_error = None
            self._sfle_mounted_root = None
            self._sfle_resize_baseline = None
            self._sfle_resize_pending = None
            if self._sfle_resize_after_id is not None:
                try:
                    self.root.after_cancel(self._sfle_resize_after_id)
                except tk.TclError:
                    pass
                self._sfle_resize_after_id = None
            if self._sfle_resize_bind_tag is not None:
                tag = self._sfle_resize_bind_tag
                try:
                    self.root.unbind_class(tag, "<Configure>")
                    self.root.bindtags(tuple(
                        existing for existing in self.root.bindtags()
                        if existing != tag
                    ))
                    if self._sfle_resize_bind_id is not None:
                        self.root.deletecommand(self._sfle_resize_bind_id)
                except tk.TclError:
                    pass
                self._sfle_resize_bind_tag = None
                self._sfle_resize_bind_id = None
            self.sfle_result = None
            self._sfle_physical_commit_error = None
            self._sfle_root_widget = None

    def _adapter_for(self, key: object):
        return self.adapters.get(key) or self._default_adapter

    # -- create -----------------------------------------------------------

    def create(self, node: VNode, parent: object | None) -> TkHandle:
        if self._sfle_constraints is not None:
            # G2 incremental native coverage: no silent native pack/grid
            # fallback for builtins or custom declarations not ported yet.
            if node.kind not in (NodeKind.HOST, NodeKind.NATIVE):
                raise RendererCapabilityError("Native SFLE requires a host or Native layout participant.")
            # An unregistered custom host or a Native declaration without a
            # strict SFLE port must fail *before* its factory mutates the GUI.
            port = external_port_for(node, self)
            if port is None and node.type not in ("Flex", "Grid", "GridItem") and node.type not in FORMATTING_TAGS:
                native_leaf_needs_measurement(node, backend="tk")
            if node.type not in ("Flex", "Grid", "GridItem"):
                node = VNode(node.kind, node.type, node.key,
                             {name: value for name, value in node.props.items()
                              if name not in FLEX_ITEM_PROPS}, node.children)
        # Scroll owns an inner content frame. New Tk widgets must be constructed
        # with that frame as their real native master; pack(in_=...) alone
        # cannot reparent a widget into a descendant of its original master.
        native_parent = parent
        if parent is not None and getattr(parent, "node_type", None) == "Scroll":
            # DelegatingAdapter._adapter_create expects an actual TkHandle.
            # A SimpleNamespace breaks _as_handle() and nested layouts.
            native_parent = TkHandle(
                "ScrollContent", parent.widget._psx_content, {}
            )
        handle = self._adapter_for(adapter_key(node)).create(self, node, native_parent)
        self._bind_scroll_wheel(handle.widget)
        return handle

    @staticmethod
    def _bind_scroll_wheel(widget: tk.Misc) -> None:
        # Each mounted widget registers only on itself; no global bind_all().
        def on_wheel(event):
            current = widget
            while current is not None:
                if hasattr(current, "_psx_canvas"):
                    consumed = current._wheel(event)
                    if consumed == "break":
                        return consumed
                current = getattr(current, "master", None)
            return None
        current = widget
        in_scroll = False
        while current is not None:
            if hasattr(current, "_psx_canvas"):
                in_scroll = True
                break
            current = getattr(current, "master", None)
        if not in_scroll:
            return
        widget.bind("<MouseWheel>", on_wheel, add="+")
        widget.bind("<Shift-MouseWheel>", on_wheel, add="+")
        widget.bind("<Button-4>", on_wheel, add="+")
        widget.bind("<Button-5>", on_wheel, add="+")

    def _adapter_create(self, node: VNode, parent: object | None) -> TkHandle:
        if node.kind is NodeKind.HOST and node.type in FORMATTING_TAGS:
            if self._sfle_constraints is None or node.props.get("display") not in ("block", "inline"):
                raise RendererCapabilityError(
                    "Tkinter div requires an enabled Cinnamon Block viewport.")
            master = _as_handle(parent).widget if parent is not None else self.root
            frame = ttk.Frame(master)
            if parent is None:
                constraints = self._sfle_constraints
                if (not constraints.width.definite or not constraints.height.definite
                        or constraints.width.value is None or constraints.height.value is None):
                    frame.destroy()
                    raise RendererCapabilityError(
                        "Tk Block root requires a definite viewport.")
                frame.place(
                    x=0, y=0, width=round(constraints.width.value),
                    height=round(constraints.height.value),
                )
                self._sfle_root_widget = frame
            if node.type == "label":
                # Implicit label association is scoped to a nested native Entry.
                # The widget owns this binding and destroys it on teardown.
                def focus_nested_input(_event):
                    pending = list(frame.winfo_children())
                    while pending:
                        candidate = pending.pop(0)
                        if isinstance(candidate, (tk.Entry, ttk.Entry)):
                            if str(candidate.cget("state")) != "disabled":
                                candidate.focus_force()
                            return
                        pending.extend(candidate.winfo_children())

                frame.bind("<Button-1>", focus_nested_input, add="+")
            return TkHandle(node.type, frame, dict(node.props))
        if node.kind is NodeKind.HOST and node.type in ("Grid", "GridItem"):
            if self._sfle_constraints is None:
                raise RendererCapabilityError(
                    f"Native SFLE {self._sfle_backend} SFLE geometry not certified for {node.type!r}.")
            if node.type == "GridItem" and (parent is None or _as_handle(parent).node_type != "Grid"):
                raise RendererCapabilityError("GridItem must be a direct child of a mounted Grid.")
            if node.type == "Grid" and parent is not None and _as_handle(parent).node_type not in ("GridItem", "Flex", "div", "main", "section", "article", "header", "footer"):
                raise RendererCapabilityError("Grid must be inside a supported Cinnamon layout container.")
            master = _as_handle(parent).widget if parent is not None else self.root
            # Unlike Aqua TFrame, classic Frame has an instance-owned
            # background and no theme-drawn border. These hosts are purely
            # structural; Cinnamon continues to own all native geometry.
            frame = (tk.Frame(master, borderwidth=0, highlightthickness=0)
                     if sys.platform == "darwin" else ttk.Frame(master))
            frame._psx_css_layout_surface = True
            if sys.platform == "darwin":
                frame._psx_css_layout_default_background = str(frame.cget("background"))
            return TkHandle(node.type, frame, dict(node.props))
        if node.kind is NodeKind.HOST and node.type == "Flex":
            raise RendererCapabilityError(
                "Flex requires the Native SFLE SFLE geometry adapter for Tkinter; "
                "native fallback layout is forbidden.")
        _validate_props(node)
        master = _as_handle(parent).widget if parent is not None else self.root
        if node.kind is NodeKind.NATIVE:
            return self._native(node, master)
        if _layout_of(node) is not None:
            padding = int(node.props.get("padding", 0))
            return TkHandle(node.type, ttk.Frame(master, padding=padding), dict(node.props))
        if node.kind is not NodeKind.HOST:
            raise RendererCapabilityError(f"Tkinter cannot create node kind {node.kind.value!r}.")
        spec = _PRIMITIVES.get(node.type)
        if spec is None:
            raise RendererCapabilityError(f"Tkinter does not support host primitive {node.type!r}.")
        if node.type == "Button" and sys.platform == "darwin":
            # Aqua's ttk Button theme ignores instance CSS colors.
            widget = tk.Button(master, relief="flat", borderwidth=0, highlightthickness=0)
        else:
            widget = spec.factory(master)
        spec.apply(widget, node.props)
        if self._sfle_constraints is not None and node.type == "TextArea":
            # Preserve the native editor's selection/cursor; only observe
            # real <<Modified>> notifications, never reset the flag here.
            widget.bind("<<Modified>>", self._sfle_on_textarea_modified, add="+")
        return TkHandle(node.type, widget, dict(node.props))

    @staticmethod
    def _css_corner_parent_surface(widget: tk.Misc) -> str:
        """Read the currently painted ancestor, not a cached corner color."""
        ancestor = widget.master
        while ancestor is not None:
            authored = getattr(ancestor, "_psx_css_background", None)
            if authored is not None:
                return authored
            ancestor = getattr(ancestor, "master", None)

        # No CSS background was authored. Use the actual native surface,
        # rather than introducing a palette color into the CSS adapter.
        parent = widget.master
        if parent is not None:
            try:
                native = str(parent.cget("background"))
                if native:
                    return native
            except tk.TclError:
                pass
        themed = str(ttk.Style(widget).lookup("TFrame", "background") or "")
        if themed:
            return themed
        return str(widget.winfo_toplevel().cget("background"))

    def _refresh_css_corner_surfaces(self, widget: tk.Misc) -> None:
        """Update opaque Tk corner masks after an ancestor CSS-only change.

        Reconciliation may not call apply_css on an unchanged card when only
        its parent's computed background changes. Canvas masks are opaque:
        their background must track the effective parent paint on every such
        change, without remounting any native widget.
        """
        fill_corners = getattr(widget, "_psx_css_background_corners", ())
        stroke_corners = getattr(widget, "_psx_css_border_corners", ())
        button_canvas = getattr(widget, "_psx_css_button_surface", None)
        if (button_canvas is not None
                and getattr(widget, "_psx_css_button_authored_background", None) is None):
            surrounding = self._css_corner_parent_surface(widget)
            old = widget._psx_css_button_paint_values
            if old[0] != surrounding:
                widget._psx_css_button_paint_values = (surrounding, *old[1:])
                self._redraw_css_ttk_button(widget)
            if str(button_canvas.cget("background")) != surrounding:
                button_canvas.configure(background=surrounding)
        # The unified surface must also follow ancestor-only CSS changes.
        if getattr(widget, "_psx_css_unified_surface", None) is not None:
            self._redraw_css_unified_surface(widget)
        if not fill_corners and not stroke_corners:
            return
        surrounding = self._css_corner_parent_surface(widget)
        for corner in fill_corners:
            if str(corner.cget("background")) != surrounding:
                corner.configure(background=surrounding)
        own = getattr(widget, "_psx_css_background", None)
        for corner in stroke_corners:
            paint = own if own is not None else surrounding
            if str(corner.cget("background")) != paint:
                corner.configure(background=paint)

    @staticmethod
    def _redraw_css_ttk_button(widget: ttk.Button) -> None:
        """Repaint the CSS-owned button surface, never a theme palette."""
        canvas = getattr(widget, "_psx_css_button_surface", None)
        if canvas is None or not canvas.winfo_exists():
            return
        fill, ink, radius, label, align, font, left, right = widget._psx_css_button_paint_values
        width, height = max(1, canvas.winfo_width()), max(1, canvas.winfo_height())
        radius = min(radius, width // 2, height // 2)
        canvas.delete("all")
        if radius:
            canvas.create_rectangle(radius, 0, width - radius, height,
                                    fill=fill, outline="", tags=("psx-css-button-fill",))
            canvas.create_rectangle(0, radius, width, height - radius,
                                    fill=fill, outline="", tags=("psx-css-button-fill",))
            for x in (0, width - 2 * radius):
                for y in (0, height - 2 * radius):
                    canvas.create_oval(x, y, x + 2 * radius, y + 2 * radius,
                                      fill=fill, outline="", tags=("psx-css-button-fill",))
        else:
            canvas.create_rectangle(0, 0, width, height, fill=fill, outline="",
                                    tags=("psx-css-button-fill",))
        anchors = {
            "left": ("w", max(0, left)),
            "center": ("center", width // 2),
            "right": ("e", max(0, width - right)),
        }
        anchor, x = anchors[align]
        canvas.create_text(x, height // 2, text=label, font=font, fill=ink,
                           anchor=anchor, tags=("psx-css-button-text",))

    def _paint_css_ttk_button(self, widget: ttk.Button, computed: object,
                             styles: dict[str, object], font: object) -> None:
        """Own CSS Button paint when ttk themes disregard authored colors.

        The actual ttk.Button keeps focus, keyboard invocation, event slots,
        layout/measurement identity and native accessibility.  A placed Canvas
        is paint only and never participates in Cinnamon geometry.
        """
        from psx.css.native_paint import background_hex, native_border_radius
        from psx.sfle.lengths import LengthKind

        painted = getattr(widget, "_psx_css_button_surface", None)
        paint_keys = (
            "background-color", "border-width", "border-color",
            "border-top-width", "border-bottom-width", "border-left-width",
            "border-right-width", "border-radius",
        )
        needs_paint = computed is not None and any(
            name in computed.specified for name in paint_keys
        )
        if not needs_paint:
            if painted is not None:
                painted.destroy()
                del widget._psx_css_button_surface
                del widget._psx_css_button_paint_values
                del widget._psx_css_button_authored_background
            return

        radius = native_border_radius(computed)
        if radius != int(radius):
            raise ValueError("Tk CSS Button surface needs integer px border-radius.")
        background = background_hex(computed)
        foreground = styles.get("color")
        if foreground is None:
            name = str(widget.cget("style"))
            foreground = (ttk.Style(widget).lookup(name, "foreground")
                          or ttk.Style(widget).lookup("TButton", "foreground"))
        if not foreground:
            raise ValueError("Tk CSS Button requires a resolvable native foreground.")
        padding = []
        for side in ("left", "right"):
            value = computed.properties[f"padding-{side}"]
            if value.kind is not LengthKind.PX:
                raise ValueError("Tk CSS Button padding requires pixel units.")
            padding.append(round(value.value))
        parent_fill = self._css_corner_parent_surface(widget)
        fill = background if background is not None else parent_fill

        if painted is None:
            painted = tk.Canvas(widget, borderwidth=0, highlightthickness=0,
                                takefocus=0)
            widget._psx_css_button_surface = painted
            widget._psx_css_button_pressed = False

            def on_press(event):
                if widget.instate(("disabled",)):
                    return
                widget._psx_css_button_pressed = True
                widget.focus_set()

            def on_release(event):
                pressed = widget._psx_css_button_pressed
                widget._psx_css_button_pressed = False
                if (pressed and not widget.instate(("disabled",))
                        and 0 <= event.x < painted.winfo_width()
                        and 0 <= event.y < painted.winfo_height()):
                    widget.invoke()

            painted.bind("<ButtonPress-1>", on_press)
            painted.bind("<ButtonRelease-1>", on_release)
            painted.bind("<Leave>", lambda _event: setattr(
                widget, "_psx_css_button_pressed", False))
            # Internal Canvas Configure handlers never consume Event fields.
            # A zero-argument Tcl binding avoids constructing a full Python
            # Tk Event for every intermediate child resize.
            painted.tk.call(
                "bind", str(painted), "<Configure>",
                painted.register(lambda: self._redraw_css_ttk_button(widget)),
            )
        widget._psx_css_button_authored_background = background
        widget._psx_css_button_paint_values = (
            fill, str(foreground), int(radius), str(widget.cget("text")),
            styles.get("text-align", "center"), font, *padding,
        )
        painted.configure(background=parent_fill, cursor=str(widget.cget("cursor")))
        painted.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.tkraise(painted)
        # The generic native border overlays are created earlier in apply_css.
        # Keep them visible over the newly painted control surface.
        for decoration in (
            *getattr(widget, "_psx_css_border_edges", ()),
            *getattr(widget, "_psx_css_border_corners", ()),
        ):
            tk.Misc.tkraise(decoration)
        self._redraw_css_ttk_button(widget)

    def _redraw_css_unified_surface(self, widget: tk.Misc) -> None:
        """Refresh one Canvas for CSS fill, border and antialiased corners."""
        canvas = getattr(widget, "_psx_css_unified_surface", None)
        if canvas is None or not canvas.winfo_exists():
            return
        radius, fill, sides = widget._psx_css_unified_values
        parent = self._css_corner_parent_surface(widget)
        width, height = canvas.winfo_width(), canvas.winfo_height()
        revision = (width, height, radius, parent, fill, tuple(sorted(sides.items())))
        if revision == getattr(canvas, "_psx_css_paint_revision", None):
            return
        from psx.renderers.tkinter.rounded_surface import draw_rounded_surface

        draw_rounded_surface(
            canvas, width=width, height=height, radius=radius,
            parent_color=parent, fill_color=fill, sides=sides,
        )
        canvas._psx_css_paint_revision = revision

    def _schedule_css_unified_surface_redraw(self, widget: tk.Misc) -> None:
        """Coalesce child Configure storms before Tk's next idle paint."""
        canvas = getattr(widget, "_psx_css_unified_surface", None)
        if canvas is None or not canvas.winfo_exists():
            return
        if getattr(canvas, "_psx_css_redraw_after_id", None) is not None:
            return

        def flush():
            canvas._psx_css_redraw_after_id = None
            if canvas.winfo_exists():
                self._redraw_css_unified_surface(widget)

        # Register on the renderer root, not the child Canvas: destroying a
        # canvas must not invalidate a still-pending Tcl callback command.
        canvas._psx_css_redraw_after_id = self.root.after_idle(flush)

    def _paint_css_unified_surface(
        self, widget: tk.Misc, computed: object, fill: str | None,
    ) -> None:
        """Paint rounded semantic CSS in one instance-owned layer.

        Opaque compositing against a solid real ancestor is deliberate:
        Canvas has no native per-pixel backdrop transparency over sibling
        images or animations. Do not silently claim such alpha support.
        """
        from psx.css.native_paint import (
            native_border_paint, native_border_radius, native_side_border_paint,
        )

        canvas = getattr(widget, "_psx_css_unified_surface", None)
        if computed is None:
            if canvas is not None:
                canvas.destroy()
                del widget._psx_css_unified_surface
                del widget._psx_css_unified_values
            return
        radius = native_border_radius(computed)
        full_stroke = native_border_paint(computed)
        individual = native_side_border_paint(computed)
        if not radius or not (fill is not None or full_stroke or individual):
            if canvas is not None:
                canvas.destroy()
                del widget._psx_css_unified_surface
                del widget._psx_css_unified_values
            return
        if radius != int(radius) or radius < 1:
            raise ValueError("Tk unified rounded CSS surfaces require integer pixel radius.")
        sides = {}
        if full_stroke is not None:
            thickness, ink = full_stroke
            if thickness != int(thickness) or thickness < 1:
                raise ValueError("Tk unified CSS border requires positive integer pixel width.")
            sides.update({name: (thickness, ink)
                          for name in ("top", "right", "bottom", "left")})
        for name, thickness, rgba in individual:
            if thickness != int(thickness) or thickness < 1:
                raise ValueError("Tk unified CSS side requires positive integer pixel width.")
            if rgba[3] != 1:
                raise ValueError("Tk unified CSS side requires opaque color.")
            ink = "#%02x%02x%02x" % tuple(round(v * 255) for v in rgba[:3])
            sides[name] = (thickness, ink)
        if canvas is None:
            canvas = tk.Canvas(widget, borderwidth=0, highlightthickness=0, takefocus=0)
            widget._psx_css_unified_surface = canvas
            canvas.tk.call(
                "bind", str(canvas), "<Configure>",
                canvas.register(lambda: self._schedule_css_unified_surface_redraw(widget)),
            )
        widget._psx_css_unified_values = (int(radius), fill, sides)
        canvas.place(x=0, y=0, relwidth=1, relheight=1)
        # A ttk theme may paint over a lowered child canvas (Aqua). Keep
        # the CSS layer above the theme, but beneath all native content.
        tk.Misc.tkraise(canvas)
        for child in widget.winfo_children():
            if child is not canvas:
                tk.Misc.tkraise(child)
        self._redraw_css_unified_surface(widget)

    def apply_css(self, handle: object, computed: object) -> None:
        """Apply CSS backgrounds through an instance-scoped ttk Frame style."""
        from psx.css.native_paint import background_hex
        from psx.css.cursor import TK_CURSOR_SHAPES
        target = _as_handle(handle)
        widget = target.widget
        # Tk cursors belong to the actual widget, not ttk's global theme.
        # Resolve CSS even for bare div/p and Text, not just buttons.
        authored_cursor = (
            computed.properties["cursor"] if computed is not None
            and "cursor" in computed.specified else "auto"
        )
        if authored_cursor != "auto":
            if not hasattr(widget, "_psx_css_original_cursor"):
                widget._psx_css_original_cursor = str(widget.cget("cursor"))
            native_cursor = TK_CURSOR_SHAPES[authored_cursor]
            try:
                widget.configure(cursor=native_cursor)
            except tk.TclError:
                # Tk does not expose every CSS cursor on every OS provider.
                # Preserve the application instead of aborting source refresh.
                widget.configure(cursor="arrow")
        elif hasattr(widget, "_psx_css_original_cursor"):
            widget.configure(cursor=widget._psx_css_original_cursor)
            del widget._psx_css_original_cursor
        from psx.css.native_paint import native_border_radius, native_border_paint, native_side_border_paint
        unified = (
            target.node_type in FORMATTING_TAGS
            and native_border_radius(computed) > 0
            and (
                background_hex(computed) is not None
                or native_border_paint(computed) is not None
                or bool(native_side_border_paint(computed))
            )
        )
        # Tk/ttk themes do not expose reliable bordercolor painting. Keep an
        # instance-local four-edge overlay instead of changing global ttk styles.
        if target.node_type in ("Button", "Input", "TextArea", "Checkbox", "Radio", "Select", "Link", "Text", "Badge") or target.node_type in FORMATTING_TAGS:
            from psx.css.native_paint import native_border_paint, native_border_radius
            stroke = None if unified else native_border_paint(computed)
            radius = native_border_radius(computed)
            widget = target.widget
            edges = getattr(widget, "_psx_css_border_edges", None)
            corners = getattr(widget, "_psx_css_border_corners", None)
            if stroke is None:
                if edges is not None:
                    for edge in edges:
                        edge.destroy()
                    del widget._psx_css_border_edges
                if corners is not None:
                    for corner in corners:
                        corner.destroy()
                    del widget._psx_css_border_corners
            else:
                thickness, color = stroke
                if int(thickness) != thickness or thickness < 1:
                    raise ValueError("Tk border painting requires positive integer device pixels.")
                if edges is None:
                    edges = tuple(tk.Frame(widget, borderwidth=0, highlightthickness=0, takefocus=0) for _ in range(4))
                    widget._psx_css_border_edges = edges
                n = int(thickness)
                if radius and (int(radius) != radius or radius < n):
                    raise ValueError("Tk rounded borders require integer px radius >= border-width.")
                r = int(radius)
                placements = (
                    dict(x=r, y=0, relwidth=1, width=-2*r, height=n),
                    dict(x=r, rely=1, y=-n, relwidth=1, width=-2*r, height=n),
                    dict(x=0, y=r, width=n, relheight=1, height=-2*r),
                    dict(relx=1, x=-n, y=r, width=n, relheight=1, height=-2*r),
                ) if r else (
                    dict(x=0, y=0, relwidth=1, height=n),
                    dict(x=0, rely=1, y=-n, relwidth=1, height=n),
                    dict(x=0, y=0, width=n, relheight=1),
                    dict(relx=1, x=-n, y=0, width=n, relheight=1),
                )
                for edge, place in zip(edges, placements):
                    edge.configure(background=color)
                    edge.place(**place)
                    edge.lift()
                if not r or (target.node_type in FORMATTING_TAGS
                             and background_hex(computed) is not None):
                    # Formatting hosts paint the rounded stroke together
                    # with their fill. A second opaque Canvas would replace
                    # the real parent color around the clipped corner.
                    if corners is not None:
                        for corner in corners:
                            corner.destroy()
                        del widget._psx_css_border_corners
                else:
                    if corners is None or int(corners[0].cget("width")) != r:
                        if corners is not None:
                            for corner in corners:
                                corner.destroy()
                        corners = tuple(
                            tk.Canvas(widget, width=r, height=r, borderwidth=0,
                                      highlightthickness=0, takefocus=0)
                            for _ in range(4)
                        )
                        widget._psx_css_border_corners = corners
                    # Corner masks sample the actual CSS ancestor surface.
                    # CSS-only changes to the parent refresh them in place.
                    surface = (getattr(widget, "_psx_css_background", None)
                               or self._css_corner_parent_surface(widget))
                    positions = (
                        (dict(x=0, y=0), (0, 0, 2*r, 2*r), 90),
                        (dict(relx=1, x=-r, y=0), (-r, 0, r, 2*r), 0),
                        (dict(x=0, rely=1, y=-r), (0, -r, 2*r, r), 180),
                        (dict(relx=1, rely=1, x=-r, y=-r), (-r, -r, r, r), 270),
                    )
                    for corner, (place, bounds, start) in zip(corners, positions):
                        corner.configure(background=surface)
                        corner.delete("all")
                        corner.create_arc(*bounds, start=start, extent=90,
                                          style="arc", outline=color, width=n)
                        corner.place(**place)
                        tk.Misc.tkraise(corner)
        # Qt projects individual border sides through QSS. ttk has no
        # equivalent per-widget side stroke: paint just the authored sides
        # without adding borders to the other three edges.
        if target.node_type in FORMATTING_TAGS:
            from psx.css.visual_values import CssColor
            from psx.sfle.lengths import Length, LengthKind
            side_edges = getattr(target.widget, "_psx_css_side_borders", None)
            active_sides = set()
            active_paint = {}
            side_radius = native_border_radius(computed)
            if computed is not None and not unified:
                for side in ("top", "right", "bottom", "left"):
                    width_key, color_key = f"border-{side}-width", f"border-{side}-color"
                    if width_key not in computed.specified and color_key not in computed.specified:
                        continue
                    width = computed.properties[width_key] if width_key in computed.specified else computed.properties["border-width"]
                    shade = computed.properties[color_key] if color_key in computed.specified else computed.properties["border-color"]
                    if not isinstance(width, Length) or width.kind is not LengthKind.PX or width.value < 0:
                        raise ValueError("Tk CSS side borders require nonnegative pixel widths.")
                    if width.value == 0:
                        continue
                    if int(width.value) != width.value:
                        raise ValueError("Tk side borders require integer pixel widths.")
                    if not isinstance(shade, CssColor):
                        raise TypeError("Tk CSS side border needs a validated color.")
                    hex_color = shade.value
                    if len(hex_color) not in (4, 7):
                        raise ValueError("Tk side border painting requires opaque RGB colors.")
                    if side_edges is None:
                        side_edges = {}
                        target.widget._psx_css_side_borders = side_edges
                    if side not in side_edges:
                        side_edges[side] = tk.Frame(target.widget, bd=0, highlightthickness=0, takefocus=0)
                    edge = side_edges[side]
                    edge.configure(background=hex_color)
                    n = int(width.value)
                    if side_radius:
                        if side_radius != int(side_radius) or side_radius < n / 2:
                            raise ValueError(
                                "Tk rounded side borders require integer radius >= half stroke width."
                            )
                        if background_hex(computed) is None:
                            raise ValueError(
                                "Tk rounded side borders require an authored opaque background."
                            )
                    r = int(side_radius)
                    places = {
                        "top": dict(x=r, y=0, relwidth=1, width=-2*r, height=n),
                        "right": dict(relx=1, x=-n, y=r, width=n, relheight=1, height=-2*r),
                        "bottom": dict(x=r, rely=1, y=-n, relwidth=1, width=-2*r, height=n),
                        "left": dict(x=0, y=r, width=n, relheight=1, height=-2*r),
                    }
                    edge.place(**places[side])
                    edge.lift()
                    active_sides.add(side)
                    active_paint[side] = (n, hex_color)
            target.widget._psx_css_side_corner_styles = active_paint
            if side_edges:
                for side in tuple(side_edges):
                    if side not in active_sides:
                        side_edges.pop(side).destroy()
        if target.node_type == "Badge":
            from psx.css.native_paint import foreground_hex
            widget = target.widget
            widget._psx_css_foreground = foreground_hex(computed)
            text_items = widget.find_withtag("all")
            for item in text_items:
                if widget.type(item) == "text":
                    if widget._psx_css_foreground is not None:
                        widget.itemconfigure(item, fill=widget._psx_css_foreground)
                    else:
                        from psx.renderers.components.badge import badge_style
                        widget.itemconfigure(item, fill=badge_style(target.props)[0])
            return
        if target.node_type == "Text":
            from psx.css.native_paint import native_text_typography
            from psx.renderers.components.text import apply_tk_text
            apply_tk_text(target.widget, target.props)
            styles = native_text_typography(computed, line_height=True)
            if "font-family" in styles:
                styles["font-family"] = _resolve_css_tk_font_family(
                    target.widget, computed.properties["font-family"]
                )
            if self._sfle_constraints is not None:
                revision = (target.props.get("value"), tuple((name, styles.get(name)) for name in ("font-family", "font-size", "font-weight", "line-height")))
                if getattr(target.widget, "_psx_css_font_revision", None) != revision:
                    target.widget._psx_css_font_revision = revision
                    self.request_sfle_invalidation("font", widget_id=id(target.widget))
            if "font-family" in styles:
                target.widget._psx_text_font.configure(family=styles["font-family"])
            if "font-size" in styles:
                target.widget._psx_text_font.configure(size=-round(styles["font-size"]))
            if "font-weight" in styles:
                target.widget._psx_text_font.configure(weight="bold" if styles["font-weight"] >= 600 else "normal")
            if "text-align" in styles:
                align = styles["text-align"]
                target.widget.configure(justify=align, anchor={"left": "w", "center": "center", "right": "e"}[align])
            if "color" in styles:
                target.widget.configure(foreground=styles["color"])
            # ttk.Label paints its own theme surface, unlike Qt's QLabel.
            # Match the nearest explicitly CSS-painted ancestor rather than
            # exposing the theme's default grey rectangle behind text.
            ancestor = target.widget.master
            inherited_fill = None
            while ancestor is not None:
                inherited_fill = getattr(ancestor, "_psx_css_background", None)
                if inherited_fill is not None:
                    break
                ancestor = ancestor.master
            label_style = f"PsxCssText{id(target.widget)}.TLabel"
            ttk_style = ttk.Style(target.widget)
            if isinstance(target.widget, tk.Label):
                if not hasattr(target.widget, "_psx_css_original_background"):
                    target.widget._psx_css_original_background = target.widget.cget("background")
                target.widget.configure(
                    background=inherited_fill if inherited_fill is not None
                    else target.widget._psx_css_original_background
                )
            elif inherited_fill is None:
                if hasattr(target.widget, "_psx_css_background_style"):
                    del target.widget._psx_css_background_style
                target.widget.configure(style="TLabel")
            else:
                # Several ttk themes prioritize their TLabel style font when
                # painting a custom CSS background. Project the exact named
                # Tk font into this *instance-owned* style as well as the
                # widget option, so a theme cannot restore its default face.
                label_config = {
                    "background": inherited_fill,
                    "font": target.widget._psx_text_font,
                }
                # Foreground stays on the native Label option; leaving
                # the style foreground untouched also preserves theme state.
                ttk_style.configure(label_style, **label_config)
                target.widget._psx_css_background_style = label_style
                target.widget.configure(style=label_style,
                                        font=target.widget._psx_text_font)
            # Explicitly opt-in diagnostic for host-specific font failures.
            # Report the computed CSS and the actual Tcl/Tk font separately:
            # a theme, stylesheet source or layout may otherwise look like
            # the same font-size issue in a screenshot.
            import os
            if os.environ.get("PSX_TK_CSS_TRACE") == "1":
                native_font = target.widget._psx_text_font
                specified = frozenset() if computed is None else computed.specified
                trace = {
                    "text": target.props.get("value"),
                    "specified_typography": {
                        key: str(computed.properties[key])
                        for key in ("font-family", "font-size", "font-weight", "line-height")
                        if key in specified
                    },
                    "projected_typography": {
                        key: styles[key]
                        for key in ("font-family", "font-size", "font-weight", "line-height")
                        if key in styles
                    },
                    "native_font": {
                        key: native_font.actual(key)
                        for key in ("family", "size", "weight")
                    },
                    "configured_font": {
                        key: native_font.cget(key)
                        for key in ("family", "size", "weight")
                    },
                    "font_option": str(target.widget.cget("font")),
                    "style": str(target.widget.cget("style"))
                        if isinstance(target.widget, ttk.Label) else None,
                    "style_font": ttk_style.lookup(
                        str(target.widget.cget("style")), "font"
                    ) if isinstance(target.widget, ttk.Label) else None,
                    "line_pixels": native_font.metrics("linespace"),
                    "requested_height": target.widget.winfo_reqheight(),
                    "tk_scaling": target.widget.tk.call("tk", "scaling"),
                }
                print("[PSX-TK-CSS] " + repr(trace), file=sys.stderr, flush=True)
            layer = getattr(target.widget, "_psx_css_text_layer", None)
            leading = styles.get("line-height")
            target.widget._psx_css_line_height = leading
            if leading is None:
                if layer is not None:
                    layer.destroy()
                    del target.widget._psx_css_text_layer
                return
            metrics = target.widget._psx_text_font.metrics("linespace")
            # Tk's spacing2/spacing3 only add interline spacing. Negative
            # leading would alter glyph rasterization rather than line boxes.
            if float(leading) != round(leading):
                raise ValueError("Tk exact line-height requires integer device pixels.")
            if leading < metrics:
                raise ValueError("Tk exact line-height cannot be shorter than native glyph linespace.")
            if layer is None:
                layer = tk.Text(
                    target.widget, wrap="word", borderwidth=0,
                    highlightthickness=0, padx=0, pady=0,
                    takefocus=0, cursor="arrow", relief="flat",
                )
                target.widget._psx_css_text_layer = layer
                layer.place(x=0, y=0, relwidth=1, relheight=1)
            layer.configure(state="normal")
            layer.delete("1.0", "end")
            layer.insert("1.0", str(target.props.get("value", "")))
            layer.tag_configure("_psx_css_alignment", justify=str(target.widget.cget("justify")))
            layer.tag_add("_psx_css_alignment", "1.0", "end")
            extra = round(leading - metrics)
            layer.configure(
                font=target.widget._psx_text_font,
                fg=str(target.widget.cget("foreground")) if styles.get("color") else "black",
                spacing2=extra, spacing3=extra,
                state="disabled",
            )
            return
        if target.node_type == "TextArea":
            from psx.css.native_paint import native_text_typography
            from tkinter import font as tkfont
            styles = native_text_typography(computed)
            widget = target.widget
            if "font-family" in styles:
                styles["font-family"] = _resolve_css_tk_font_family(
                    widget, computed.properties["font-family"]
                )
            if not hasattr(widget, "_psx_css_area_base_font"):
                widget._psx_css_area_base_font = widget.cget("font")
                widget._psx_css_area_font = tkfont.Font(
                    root=widget, font=widget._psx_css_area_base_font
                )
                widget._psx_css_area_base_config = widget._psx_css_area_font.actual()
                widget._psx_css_area_base_foreground = widget.cget("foreground")
            font = widget._psx_css_area_font
            font.configure(**widget._psx_css_area_base_config)
            if "font-family" in styles:
                font.configure(family=styles["font-family"])
            if "font-size" in styles:
                font.configure(size=-round(styles["font-size"]))
            if "font-weight" in styles:
                font.configure(weight="bold" if styles["font-weight"] >= 600 else "normal")
            widget.configure(font=font if styles else widget._psx_css_area_base_font)
            widget.configure(foreground=styles.get("color", widget._psx_css_area_base_foreground))
            tag = "_psx_css_text_align"
            if "text-align" in styles:
                widget.tag_configure(tag, justify=styles["text-align"])
                widget.tag_add(tag, "1.0", "end")
            else:
                widget.tag_delete(tag)
            if self._sfle_constraints is not None:
                revision = tuple(
                    (name, styles.get(name)) for name in
                    ("font-family", "font-size", "font-weight")
                )
                if getattr(widget, "_psx_css_font_revision", None) != revision:
                    widget._psx_css_font_revision = revision
                    self.request_sfle_invalidation("font", widget_id=id(widget))
            return
        if target.node_type == "Link":
            from psx.css.native_paint import native_text_typography
            from tkinter import font as tkfont
            styles = native_text_typography(computed)
            widget = target.widget
            if "font-family" in styles:
                styles["font-family"] = _resolve_css_tk_font_family(
                    widget, computed.properties["font-family"]
                )
            if not styles:
                if hasattr(widget, "_psx_css_link_font"):
                    widget.configure(
                        font=widget._psx_css_link_original_font,
                        anchor=widget._psx_css_link_original_anchor,
                        foreground=widget._psx_css_link_original_foreground,
                    )
                if self._sfle_constraints is not None and hasattr(widget, "_psx_css_font_revision"):
                    revision = tuple((key, None) for key in ("font-family", "font-size", "font-weight"))
                    if widget._psx_css_font_revision != revision:
                        widget._psx_css_font_revision = revision
                        self.request_sfle_invalidation("font", widget_id=id(widget))
                return
            if not hasattr(widget, "_psx_css_link_font"):
                widget._psx_css_link_original_font = widget.cget("font")
                widget._psx_css_link_original_anchor = widget.cget("anchor")
                widget._psx_css_link_original_foreground = widget.cget("foreground")
                widget._psx_css_link_font = tkfont.Font(
                    root=widget, font=widget._psx_css_link_original_font
                )
                widget._psx_css_link_font_base = widget._psx_css_link_font.actual()
            font = widget._psx_css_link_font
            font.configure(**widget._psx_css_link_font_base)
            if "font-family" in styles:
                font.configure(family=styles["font-family"])
            if "font-size" in styles:
                font.configure(size=-round(styles["font-size"]))
            if "font-weight" in styles:
                font.configure(weight="bold" if styles["font-weight"] >= 600 else "normal")
            widget.configure(font=font)
            widget.configure(foreground=styles.get("color", widget._psx_css_link_original_foreground))
            if "text-align" in styles:
                widget.configure(anchor={"left": "w", "center": "center", "right": "e"}[styles["text-align"]])
            if self._sfle_constraints is not None:
                revision = tuple((key, styles.get(key)) for key in
                                 ("font-family", "font-size", "font-weight"))
                if getattr(widget, "_psx_css_font_revision", None) != revision:
                    widget._psx_css_font_revision = revision
                    self.request_sfle_invalidation("font", widget_id=id(widget))
            return
        if target.node_type in ("Button", "Checkbox", "Input", "Radio", "Select"):
            from psx.css.native_paint import native_text_typography
            from tkinter import font as tkfont
            styles = native_text_typography(computed, line_height=target.node_type == "Button")
            widget = target.widget
            if "font-family" in styles:
                styles["font-family"] = _resolve_css_tk_font_family(
                    widget, computed.properties["font-family"]
                )
            button_paint = (
                target.node_type == "Button"
                and computed is not None
                and (
                    background_hex(computed) is not None
                    or any(key in computed.specified for key in (
                        "padding", "padding-left", "padding-right",
                        "padding-top", "padding-bottom", "text-align",
                        "cursor", "border-width", "border-color",
                        "border-radius",
                    ))
                )
            )
            if isinstance(widget, tk.Button):
                if not hasattr(widget, "_psx_css_default_background"):
                    widget._psx_css_default_background = str(widget.cget("background"))
                    widget._psx_css_default_foreground = str(widget.cget("foreground"))
                    widget._psx_css_default_font = str(widget.cget("font"))
                ancestor = widget.master
                ancestor_bg = None
                while ancestor is not None:
                    ancestor_bg = getattr(ancestor, "_psx_css_background", None)
                    if ancestor_bg is not None:
                        break
                    ancestor = ancestor.master
                background = (background_hex(computed) or ancestor_bg
                              or widget._psx_css_default_background)
                foreground = styles.get("color", widget._psx_css_default_foreground)
                if not hasattr(widget, "_psx_css_classic_font"):
                    widget._psx_css_classic_font = tkfont.Font(
                        root=widget, font=widget._psx_css_default_font)
                    widget._psx_css_classic_font_defaults = widget._psx_css_classic_font.actual()
                font = widget._psx_css_classic_font
                font.configure(**widget._psx_css_classic_font_defaults)
                if "font-family" in styles:
                    font.configure(family=styles["font-family"])
                if "font-size" in styles:
                    font.configure(size=-round(styles["font-size"]))
                if "font-weight" in styles:
                    font.configure(weight="bold" if styles["font-weight"] >= 600 else "normal")
                props = computed.properties if computed is not None else {}
                from psx.sfle.lengths import LengthKind
                padding = []
                for side in ("left", "top", "right", "bottom"):
                    value = props.get(f"padding-{side}")
                    if value is not None and value.kind is not LengthKind.PX:
                        raise ValueError("Tk CSS button padding requires pixel units.")
                    padding.append(round(value.value) if value is not None else 0)
                left, top, right, bottom = padding
                widget.configure(
                    font=font, background=background, activebackground=background,
                    foreground=foreground, activeforeground=foreground,
                    relief="flat", borderwidth=0, highlightthickness=0,
                    padx=max(left, right), pady=max(top, bottom),
                    anchor={"left": "w", "center": "center", "right": "e"}[
                        styles.get("text-align", "center")],
                )
                # Aqua paints its native button surface even if Tk's bg
                # options are set. Own the pixel surface with a single Canvas
                # above the button, preserving the button's handle and invoke().
                radius = native_border_radius(computed)
                if radius != int(radius) or radius < 0:
                    raise ValueError("Tk CSS button radius requires nonnegative integer px.")
                paint = getattr(widget, "_psx_css_button_paint", None)
                if paint is None:
                    paint = tk.Canvas(widget, borderwidth=0,
                                      highlightthickness=0, takefocus=0)
                    widget._psx_css_button_paint = paint
                    paint.bind("<Button-1>", lambda _event: widget.focus_set(), add="+")
                    paint.bind("<ButtonRelease-1>", lambda _event: (
                        widget.invoke() if str(widget.cget("state")) != "disabled"
                        else None), add="+")
                paint.configure(background=ancestor_bg or background,
                                cursor=str(widget.cget("cursor")))
                paint.place(x=0, y=0, relwidth=1, relheight=1)
                tk.Misc.tkraise(paint)
                widget._psx_css_button_paint_values = (
                    background, foreground, int(radius), str(widget.cget("text")),
                    str(styles.get("text-align", "center")), font,
                )
                def repaint(event=None):
                    if not paint.winfo_exists():
                        return
                    width = max(1, paint.winfo_width())
                    height = max(1, paint.winfo_height())
                    fill, ink, corner, label, align, face = widget._psx_css_button_paint_values
                    corner = min(corner, width // 2, height // 2)
                    paint.delete("all")
                    if corner:
                        paint.create_rectangle(corner, 0, width-corner, height,
                                               fill=fill, outline="")
                        paint.create_rectangle(0, corner, width, height-corner,
                                               fill=fill, outline="")
                        for x in (0, width-2*corner):
                            for y in (0, height-2*corner):
                                paint.create_oval(x, y, x+2*corner, y+2*corner,
                                                  fill=fill, outline="")
                    else:
                        paint.create_rectangle(0, 0, width, height,
                                               fill=fill, outline="")
                    anchors = {"left": ("w", max(0, left)),
                               "center": ("center", width//2),
                               "right": ("e", max(0, width-right))}
                    anchor, text_x = anchors[align]
                    paint.create_text(text_x, height//2, text=label,
                                      font=face, fill=ink, anchor=anchor)
                if not hasattr(paint, "_psx_css_resize_bound"):
                    paint.bind("<Configure>", repaint, add="+")
                    paint._psx_css_resize_bound = True
                repaint()
                return
            if not styles and not button_paint:
                if target.node_type == "Button" and isinstance(widget, ttk.Button):
                    self._paint_css_ttk_button(widget, None, {}, None)
                if hasattr(widget, "_psx_css_native_font"):
                    widget._psx_css_native_font.configure(
                        **widget._psx_css_native_original_font_config
                    )
                    if target.node_type not in ("Input", "Select"):
                        widget.configure(style=widget._psx_css_native_original_style)
                    else:
                        widget.configure(font=widget._psx_css_native_original_font)
                        if target.node_type == "Select" and hasattr(widget, "_psx_css_native_original_combobox_style"):
                            widget.configure(style=widget._psx_css_native_original_combobox_style)
                        if target.node_type == "Input":
                            widget.configure(foreground=widget._psx_css_native_original_foreground)
                    if self._sfle_constraints is not None and hasattr(widget, "_psx_css_font_revision"):
                        cleared = tuple((key, None) for key in ("font-family", "font-size", "font-weight", "line-height"))
                        if widget._psx_css_font_revision != cleared:
                            widget._psx_css_font_revision = cleared
                            self.request_sfle_invalidation("font", widget_id=id(widget))
                return
            if not hasattr(widget, "_psx_css_native_font"):
                widget._psx_css_native_original_font = (
                    widget.cget("font") if target.node_type in ("Input", "Select") else None
                )
                if target.node_type == "Select":
                    widget._psx_css_native_original_combobox_style = str(widget.cget("style"))
                widget._psx_css_native_original_foreground = (
                    str(widget.cget("foreground")) if target.node_type == "Input" else None
                )
                widget._psx_css_native_original_style = (
                    str(widget.cget("style")) if target.node_type not in ("Input", "Select") else None
                )
            if not hasattr(widget, "_psx_css_native_base_font"):
                # Start with the actual component style, not the generic ttk
                # class: PSX Button styles specify pixel-sized fonts there.
                if target.node_type in ("Input", "Select"):
                    original = widget.cget("font")
                else:
                    theme = ttk.Style(widget)
                    style_name = str(widget.cget("style")) or widget.winfo_class()
                    original = (theme.lookup(style_name, "font")
                                or theme.lookup(widget.winfo_class(), "font"))
                widget._psx_css_native_base_font = original or "TkDefaultFont"
            if not hasattr(widget, "_psx_css_native_font"):
                widget._psx_css_native_font = tkfont.Font(
                    root=widget, font=widget._psx_css_native_base_font)
            font = widget._psx_css_native_font
            if not hasattr(widget, "_psx_css_native_original_font_config"):
                widget._psx_css_native_original_font_config = font.actual()
            native_font = widget._psx_css_native_original_font_config
            # A Tk named Font uses positive *points* by default. Preserve
            # the portable Button/Input component size in negative device
            # pixels when CSS only specifies paint, padding or alignment.
            base_size = native_font["size"]
            if target.node_type in ("Button", "Input"):
                from psx.core.contracts import BUTTON_DEFAULTS, INPUT_DEFAULTS
                defaults = BUTTON_DEFAULTS if target.node_type == "Button" else INPUT_DEFAULTS
                base_size = -max(1, round(target.props.get(
                    "font_size", defaults["font_size"]
                )))
            font.configure(**native_font)
            font.configure(
                family=styles.get("font-family", native_font["family"]),
                size=-round(styles["font-size"]) if "font-size" in styles else base_size,
                weight=("bold" if styles["font-weight"] >= 600 else "normal")
                if "font-weight" in styles else native_font["weight"],
            )
            if target.node_type in ("Input", "Select"):
                widget.configure(font=font)
                if target.node_type == "Select" and "color" not in styles and hasattr(widget, "_psx_css_native_original_combobox_style"):
                    widget.configure(style=widget._psx_css_native_original_combobox_style)
                if "color" in styles:
                    if target.node_type == "Input":
                        widget.configure(foreground=styles["color"])
                    else:
                        name = f"PsxCssColor{id(widget)}.TCombobox"
                        theme = ttk.Style(widget)
                        theme.configure(name, foreground=styles["color"])
                        widget.configure(style=name)
                if "text-align" in styles:
                    widget.configure(justify=styles["text-align"])
                else:
                    widget.configure(justify="left")
            else:
                style_name = f"PsxCssType{id(widget)}.{widget.winfo_class()}"
                style = ttk.Style(widget)
                config = {"font": font}
                if "color" in styles:
                    config["foreground"] = styles["color"]
                if target.node_type == "Button":
                    # ttk buttons need instance-scoped theme styles; geometry
                    # alone cannot project the authored CSS background/edges.
                    color = background_hex(computed)
                    if color is not None:
                        config["background"] = color
                    leading = styles.get("line-height")
                    if leading is not None and (
                        "\n" in str(widget.cget("text"))
                        or leading < font.metrics("linespace")
                        or float(leading) != round(leading)
                    ):
                        raise ValueError("Tk Button line-height requires single-line text and integer pixels above native linespace.")
                    extra = max(0, round(leading - font.metrics("linespace"))) if leading is not None else 0
                    base = style.lookup(widget.winfo_class(), "padding") or (0,)
                    if isinstance(base, (tuple, list)):
                        parts = [int(value) for value in base]
                    else:
                        parts = [int(value) for value in str(base).replace("(", "").replace(")", "").replace(",", " ").split()]
                    if len(parts) == 1:
                        l = t = r = b = parts[0]
                    elif len(parts) == 2:
                        l = r = parts[0]
                        t = b = parts[1]
                    elif len(parts) == 4:
                        l, t, r, b = parts
                    else:
                        raise ValueError("Unsupported native Tk button padding format.")
                    if computed is not None and (
                        "padding" in computed.specified or any(
                            f"padding-{side}" in computed.specified
                            for side in ("top", "right", "bottom", "left")
                        )
                    ):
                        from psx.sfle.lengths import LengthKind
                        dimensions = []
                        for side in ("left", "top", "right", "bottom"):
                            length = computed.properties[f"padding-{side}"]
                            if length.kind is not LengthKind.PX:
                                raise ValueError("Tk native Button padding requires pixel lengths.")
                            dimensions.append(round(length.value))
                        l, t, r, b = dimensions
                    config["padding"] = (
                        l, t + extra // 2, r, b + extra - extra // 2
                    )
                if target.node_type == "Button":
                    config["anchor"] = {
                        "left": "w", "center": "center", "right": "e",
                    }[styles.get("text-align", "center")]
                elif "text-align" in styles:
                    raise ValueError(f"Tk {target.node_type} does not support exact text-align.")
                style.configure(style_name, **config)
                if target.node_type == "Button":
                    # Theme maps can override the configured ordinary-state
                    # color and obscure authored active/selected class rules.
                    if "background" in config:
                        style.map(style_name, background=[
                            ("disabled", config["background"]),
                            ("active", config["background"]),
                            ("!disabled", config["background"]),
                        ])
                    else:
                        style.map(style_name, background=[])
                    if "foreground" in config:
                        style.map(style_name, foreground=[
                            ("disabled", config["foreground"]),
                            ("active", config["foreground"]),
                            ("!disabled", config["foreground"]),
                        ])
                    else:
                        style.map(style_name, foreground=[])
                widget.configure(style=style_name)
                if target.node_type == "Button" and isinstance(widget, ttk.Button):
                    self._paint_css_ttk_button(widget, computed, styles, font)
            if self._sfle_constraints is not None:
                keys = ("font-family", "font-size", "font-weight", "line-height")
                if any(key in styles for key in keys) or hasattr(widget, "_psx_css_font_revision"):
                    revision = tuple((key, styles.get(key)) for key in keys)
                    if getattr(widget, "_psx_css_font_revision", None) != revision:
                        widget._psx_css_font_revision = revision
                        self.request_sfle_invalidation("font", widget_id=id(widget))
            return
        if target.node_type not in FORMATTING_TAGS:
            return
        color = background_hex(computed)
        widget = target.widget
        previous_background = getattr(widget, "_psx_css_background", None)
        widget._psx_css_background = color
        from psx.css.native_paint import native_border_radius
        radius = native_border_radius(computed)
        if color is None:
            widget.configure(style="TFrame")
        else:
            style_name = f"PsxCss{id(widget)}.TFrame"
            ttk.Style(widget).configure(style_name, background=color)
            widget.configure(style=style_name)

        # A parent-only CSS refresh does not reapply unchanged child styles.
        # Text labels must nevertheless repaint against their new CSS surface.
        if previous_background != color:
            def refresh_descendant_labels(parent):
                for child in parent.winfo_children():
                    if ((isinstance(child, ttk.Label) and hasattr(child, "_psx_css_background_style"))
                            or isinstance(child, tk.Label)):
                        background = color
                        ancestor = child.master
                        while ancestor is not None:
                            candidate = getattr(ancestor, "_psx_css_background", None)
                            if candidate is not None:
                                background = candidate
                                break
                            ancestor = ancestor.master
                        if isinstance(child, tk.Label):
                            if not hasattr(child, "_psx_css_original_background"):
                                child._psx_css_original_background = child.cget("background")
                            child.configure(background=(
                                background if background is not None
                                else child._psx_css_original_background
                            ))
                        elif background is None:
                            child.configure(style="TLabel")
                        else:
                            name = child._psx_css_background_style
                            ttk.Style(child).configure(name, background=background)
                            child.configure(style=name)
                    refresh_descendant_labels(child)
            refresh_descendant_labels(widget)
            # Child CSS is unchanged, but opaque rounded masks would still
            # expose the previous parent's color without this repaint.
            def refresh_descendant_corners(parent):
                for child in parent.winfo_children():
                    self._refresh_css_corner_surfaces(child)
                    if child is not getattr(parent, "_psx_css_fill_canvas", None):
                        refresh_descendant_corners(child)
            refresh_descendant_corners(widget)

        if unified:
            # The previous multi-widget corner and edge paint is replaced
            # with a single owned surface; avoid simultaneous decorations.
            old_fill = getattr(widget, "_psx_css_fill_canvas", None)
            if old_fill is not None:
                old_fill.destroy()
                del widget._psx_css_fill_canvas
            old_corners = getattr(widget, "_psx_css_background_corners", None)
            if old_corners is not None:
                for old_corner in old_corners:
                    old_corner.destroy()
                del widget._psx_css_background_corners
            self._paint_css_unified_surface(widget, computed, color)
            return

        # Drop the unified paint when the authored style is reset or
        # no longer contains a painted rounded border/surface.
        self._paint_css_unified_surface(widget, None, None)

        # Several native ttk themes (notably macOS Aqua) ignore custom
        # TFrame background styles. Paint the CSS fill in a child canvas
        # lowered behind the existing native children, without changing
        # geometry ownership or introducing a global theme override.
        surface = getattr(widget, "_psx_css_fill_canvas", None)
        if color is None:
            if surface is not None:
                surface.destroy()
                del widget._psx_css_fill_canvas
        else:
            if surface is None:
                surface = tk.Canvas(
                    widget, borderwidth=0, highlightthickness=0,
                    takefocus=0, background=color,
                )
                widget._psx_css_fill_canvas = surface
            else:
                surface.configure(background=color)
            surface.place(x=0, y=0, relwidth=1, relheight=1)
            # Aqua draws themed TFrame surfaces *over* a lowered child
            # canvas. Keep the CSS fill above the theme, but below every
            # real content child and any border/corner painting overlays.
            tk.Misc.tkraise(surface)
            for child in widget.winfo_children():
                if child is not surface:
                    tk.Misc.tkraise(child)

        if sys.platform == "darwin":
            # CSS backgrounds do not inherit, but ttk.Frame is opaque under
            # Aqua. A formatting host with no authored background must
            # *visually* expose its nearest painted ancestor instead of
            # covering it with the system dark theme. Reproject descendants
            # when a parent changes without relying on CSS reconciliation to
            # revisit unchanged child nodes.
            def repaint_formatting_surfaces(host):
                for child in host.winfo_children():
                    if hasattr(child, "_psx_css_background"):
                        explicit = child._psx_css_background
                        inherited = None
                        ancestor = child.master
                        while ancestor is not None:
                            inherited = getattr(ancestor, "_psx_css_background", None)
                            if inherited is not None:
                                break
                            ancestor = ancestor.master
                        fill = explicit if explicit is not None else inherited
                        painted = getattr(child, "_psx_css_fill_canvas", None)
                        if fill is None:
                            if painted is not None:
                                painted.destroy()
                                del child._psx_css_fill_canvas
                        else:
                            if painted is None:
                                painted = tk.Canvas(
                                    child, borderwidth=0, highlightthickness=0,
                                    takefocus=0, background=fill)
                                child._psx_css_fill_canvas = painted
                            else:
                                painted.configure(background=fill)
                            painted.place(x=0, y=0, relwidth=1, relheight=1)
                            tk.Misc.tkraise(painted)
                            for sibling in child.winfo_children():
                                if sibling is not painted:
                                    tk.Misc.tkraise(sibling)
                    self._refresh_css_corner_surfaces(child)
                    # Only recurse into native content widgets. Paint
                    # canvases are owned decorations, never CSS boxes.
                    if child is not getattr(host, "_psx_css_fill_canvas", None):
                        repaint_formatting_surfaces(child)

            if color is None:
                inherited = None
                ancestor = widget.master
                while ancestor is not None:
                    inherited = getattr(ancestor, "_psx_css_background", None)
                    if inherited is not None:
                        break
                    ancestor = ancestor.master
                if inherited is not None:
                    fill_canvas = getattr(widget, "_psx_css_fill_canvas", None)
                    if fill_canvas is None:
                        fill_canvas = tk.Canvas(
                            widget, borderwidth=0, highlightthickness=0,
                            takefocus=0, background=inherited)
                        widget._psx_css_fill_canvas = fill_canvas
                    else:
                        fill_canvas.configure(background=inherited)
                    fill_canvas.place(x=0, y=0, relwidth=1, relheight=1)
                    tk.Misc.tkraise(fill_canvas)
                    for child in widget.winfo_children():
                        if child is not fill_canvas:
                            tk.Misc.tkraise(child)
            repaint_formatting_surfaces(widget)
            self._sync_aqua_layout_surfaces()

        # ttk.Frame has a rectangular background. Four small, instance-owned
        # canvases mask its corners against the surrounding native surface and
        # paint a filled quarter-circle. This is a paint overlay, not a new
        # container, so children and event dispatch remain unchanged.
        corners = getattr(widget, "_psx_css_background_corners", None)
        if color is None or radius == 0:
            if corners is not None:
                for corner in corners:
                    corner.destroy()
                del widget._psx_css_background_corners
            return
        if radius != int(radius) or radius < 1:
            raise ValueError("Tk rounded CSS backgrounds require integer px radius.")
        r = int(radius)
        surface = self._css_corner_parent_surface(widget)
        if corners is None or int(corners[0].cget("width")) != r:
            if corners is not None:
                for corner in corners:
                    corner.destroy()
            corners = tuple(tk.Canvas(widget, width=r, height=r, borderwidth=0,
                                      highlightthickness=0, takefocus=0) for _ in range(4))
            widget._psx_css_background_corners = corners
        placements = (
            (dict(x=0, y=0), (0, 0, 2*r, 2*r), 90),
            (dict(relx=1, x=-r, y=0), (-r, 0, r, 2*r), 0),
            (dict(x=0, rely=1, y=-r), (0, -r, 2*r, r), 180),
            (dict(relx=1, rely=1, x=-r, y=-r), (-r, -r, r, r), 270),
        )
        from psx.css.native_paint import native_border_paint
        stroke = native_border_paint(computed)
        for corner, (place, bounds, start) in zip(corners, placements):
            corner.configure(background=surface)
            corner.delete("all")
            if stroke is None:
                corner.create_arc(*bounds, start=start, extent=90,
                                  style="pieslice", fill=color,
                                  outline=color, width=0)
            else:
                thickness, ink = stroke
                n = int(thickness)
                corner.create_arc(*bounds, start=start, extent=90,
                                  style="pieslice", fill=ink,
                                  outline=ink, width=0)
                inner = (bounds[0] + n, bounds[1] + n,
                         bounds[2] - n, bounds[3] - n)
                if inner[2] > inner[0] and inner[3] > inner[1]:
                    corner.create_arc(*inner, start=start, extent=90,
                                      style="pieslice", fill=color,
                                      outline=color, width=0)
            corner.place(**place)
            tk.Misc.tkraise(corner)
        # Add each authored side's half-corner arc above the matching
        # rounded surface mask. Unstyled sides never gain a phantom stroke.
        side_corner_styles = getattr(widget, "_psx_css_side_corner_styles", {})
        if side_corner_styles:
            corner_sides = (
                (("top", 90), ("left", 135)),
                (("top", 45), ("right", 0)),
                (("bottom", 225), ("left", 180)),
                (("bottom", 270), ("right", 315)),
            )
            for canvas, (_, bounds, _), arcs in zip(corners, placements, corner_sides):
                for side, start in arcs:
                    if side not in side_corner_styles:
                        continue
                    n, ink = side_corner_styles[side]
                    half = n / 2
                    inset = (bounds[0] + half, bounds[1] + half,
                             bounds[2] - half, bounds[3] - half)
                    canvas.create_arc(
                        *inset, start=start, extent=45, style="arc",
                        outline=ink, width=n, tags=("psx-css-side-arc",),
                    )
        self._refresh_css_corner_surfaces(widget)

    # -- update -----------------------------------------------------------

    def update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        if self._sfle_constraints is not None and _as_handle(handle).node_type != "Flex":
            changed = {name: value for name, value in changed.items()
                       if name not in FLEX_ITEM_PROPS}
            removed = frozenset(name for name in removed if name not in FLEX_ITEM_PROPS)
            if not changed and not removed:
                return
        self._adapter_for(handle_adapter_key(handle)).update(self, handle, changed, removed)

    def _adapter_update(self, handle: object, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        target = _as_handle(handle)
        if target.node_type in FORMATTING_TAGS:
            updated = dict(target.props)
            updated.update(changed)
            for name in removed:
                updated.pop(name, None)
            if updated.get("display") not in ("block", "inline"):
                raise RendererCapabilityError(
                    "div currently supports only the Cinnamon Block context.")
            target.props = updated
            return
        if target.node_type in ("Grid", "GridItem"):
            target.props.update(changed)
            for name in removed:
                target.props.pop(name, None)
            return
        if target.native is not None:
            _update_native(target, changed, removed)
            return
        spec = _PRIMITIVES.get(target.node_type)
        if spec is not None:
            props = spec.updated_props(target.props, changed, removed)
            spec.apply(target.widget, props)
            target.props = props
            return
        self._update_layout(target, changed, removed)

    def _update_layout(self, target: TkHandle, changed: Mapping[str, object], removed: frozenset[str]) -> None:
        if not (removed <= _LAYOUT_UPDATABLE and changed.keys() <= _LAYOUT_UPDATABLE):
            unsupported = (set(changed) | set(removed)) - _LAYOUT_UPDATABLE
            raise RendererCapabilityError(
                f"Unsupported Tkinter props for {target.node_type!r}: {', '.join(sorted(unsupported))}"
            )
        target.props.update(changed)
        for name in removed:
            target.props.pop(name, None)
        if "padding" in changed or "padding" in removed:
            _as_frame(target).configure(padding=int(target.props.get("padding", 0)))
        if "spacing" in changed or "spacing" in removed:
            self._repack(target)

    # -- tree operations --------------------------------------------------

    def insert(self, parent: object, child: object, index: int) -> None:
        adapter = self._adapter_for(handle_adapter_key(parent))
        if run_child_hook(adapter, "insert", self, parent, child, index):
            return
        self._default_insert(parent, child, index)

    def _default_insert(self, parent: object, child: object, index: int) -> None:
        if _as_handle(parent).node_type in ("Grid", "GridItem") or _as_handle(parent).node_type in FORMATTING_TAGS:
            container, item = _as_handle(parent), _as_handle(child)
            if item not in container.children:
                container.children.insert(index, item)
            return
        self._place(_as_handle(parent), _as_handle(child), index, require_existing=False)

    def move(self, parent: object, child: object, index: int) -> None:
        adapter = self._adapter_for(handle_adapter_key(parent))
        if run_child_hook(adapter, "move", self, parent, child, index):
            return
        self._default_move(parent, child, index)

    def _default_move(self, parent: object, child: object, index: int) -> None:
        if _as_handle(parent).node_type in ("Grid", "GridItem") or _as_handle(parent).node_type in FORMATTING_TAGS:
            container, item = _as_handle(parent), _as_handle(child)
            if item in container.children:
                container.children.remove(item)
                container.children.insert(index, item)
            return
        self._place(_as_handle(parent), _as_handle(child), index, require_existing=True)

    def remove(self, parent: object, child: object) -> None:
        adapter = self._adapter_for(handle_adapter_key(parent))
        if run_child_hook(adapter, "remove", self, parent, child):
            return
        self._default_remove(parent, child)

    def _default_remove(self, parent: object, child: object) -> None:
        container, item = _as_handle(parent), _as_handle(child)
        if item in container.children:
            container.children.remove(item)
        if container.node_type in ("Grid", "GridItem"):
            item.widget.place_forget()
            return
        item.widget.pack_forget()

    def _place(self, container: TkHandle, item: TkHandle, index: int, *, require_existing: bool) -> None:
        """Put ``item`` at ``index`` and re-pack only the children that can have changed position."""
        children = container.children
        try:
            old = children.index(item)
        except ValueError:
            if require_existing:
                raise
            old = None
        else:
            del children[old]
        children.insert(index, item)
        new = children.index(item)
        self._repack(container, new if old is None else min(old, new))

    def _repack(self, parent: TkHandle, start: int = 0) -> None:
        frame = _as_frame(parent)
        options = _pack_options(parent)
        for child in parent.children[start:]:
            child.widget.pack_forget()
            child.widget.pack(in_=frame, **options)

    def destroy(self, handle: object) -> None:
        self._adapter_for(handle_adapter_key(handle)).destroy(self, handle)

    def _adapter_destroy(self, handle: object) -> None:
        target = _as_handle(handle)
        if target.native is not None:
            _clear_native_snapshot(target.widget)
        if target.native is not None and target.native.ownership is NativeOwnership.BORROWED:
            return
        if target.widget.winfo_exists():
            target.widget.destroy()

    # -- events -----------------------------------------------------------

    def bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        adapter = self._adapter_for(handle_adapter_key(handle))
        return AdapterSubscription(adapter, adapter.bind_event(self, handle, event, slot))

    def _adapter_bind_event(self, handle: object, event: str, slot: EventSlot) -> object:
        handle = _as_handle(handle)
        if handle.native is not None:
            if handle.native.bind_event is None:
                raise RendererCapabilityError(
                    f"Native widget {handle.native.name!r} has no event adapter for {event!r}."
                )
            disposer = handle.native.bind_event(handle.widget, event, slot)
            if not callable(disposer):
                raise TypeError("NativeWidget.bind_event must return a callable disposer.")
            return TkNativeEventSubscription(disposer)

        spec = _PRIMITIVES.get(handle.node_type)
        definition = spec.events.get(event) if spec is not None else None
        if definition is None:
            raise RendererCapabilityError(f"{event} is not supported by {handle.node_type} in Tkinter.")
        option, make_callback = definition
        callback = make_callback(handle.widget, slot)  # only the requested event's closure is built
        if handle.node_type == "Input" and event == "on_change":
            variable = handle.widget.var
            token = variable.trace_add("write", callback)
            def unsubscribe() -> None:
                try:
                    variable.trace_remove("write", token)
                except tk.TclError:
                    pass
            return TkNativeEventSubscription(unsubscribe)
        if option.startswith("<"):
            # Tk virtual and keyboard events must use bind, not configure.
            binding_id = handle.widget.bind(option, callback, add="+")
            return TkEventSubscription(handle.widget, event, callback, option, binding_id)
        handle.widget.configure(**{option: callback})
        return TkEventSubscription(handle.widget, event, callback, option)

    def unbind_event(self, subscription: object) -> None:
        if isinstance(subscription, AdapterSubscription):
            subscription.adapter.unbind_event(self, subscription.subscription)
            return
        self._adapter_unbind_event(subscription)

    def _adapter_unbind_event(self, subscription: object) -> None:
        if isinstance(subscription, TkNativeEventSubscription):
            try:
                subscription.dispose()
            except tk.TclError:
                pass
            return
        target = _as_subscription(subscription)
        if target.binding_id is not None:
            target.widget.unbind(target.option, target.binding_id)
        else:
            target.widget.configure(**{target.option: ""})

    # -- scheduling / lifecycle ------------------------------------------

    def schedule_ui(self, callback: Callable[[], None]) -> None:
        """Queue work safely; Tk's ``after`` polling drains it on the UI thread."""
        self._pending.put(callback)

    def flush(self) -> None:
        """Drain queued work now; intended for deterministic tests on the Tk thread."""
        self._drain_pending()

    def restore_root(self, previous) -> None:
        """Keep Tk's last committed native root after a failed replacement."""
        self._sfle_root_widget = _as_handle(previous).widget

    def run(self) -> int:
        self.root.mainloop()
        return 0

    def close(self) -> None:
        if self._sfle_constraints is not None:
            self.invalidate_layout()
        self._closed = True
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        if self._owns_root and self.root.winfo_exists():
            self.root.destroy()

    def _drain_scheduled(self) -> None:
        if self._closed or not self.root.winfo_exists():
            return
        self._after_id = None
        self._drain_pending()
        self._schedule_drain()

    def _schedule_drain(self) -> None:
        if self._closed:
            return
        try:
            self._after_id = self.root.after(self._poll_interval_ms, self._drain_scheduled)
        except tk.TclError:
            # The borrowed Qyro host may already be in teardown.
            self._closed = True

    def _drain_pending(self) -> None:
        while True:
            try:
                self._pending.get_nowait()()
            except Empty:
                return

    # -- factories --------------------------------------------------------

    @staticmethod
    def _native(node: VNode, master: tk.Misc) -> TkHandle:
        declaration = node.type
        if not isinstance(declaration, NativeWidget) or declaration.renderer != "tkinter":
            renderer = declaration.renderer if isinstance(declaration, NativeWidget) else "unknown"
            raise RendererCapabilityError(
                f"Native widget is declared for renderer {renderer!r}, not 'tkinter'."
            )
        initial_props = {k: v for k, v in node.props.items() if not k.startswith("on_")}
        if initial_props and declaration.update is None:
            raise RendererCapabilityError(
                f"Native widget {declaration.name!r} received props but has no update adapter."
            )
        # Tk widget masters are immutable. Even a widget already parented to
        # the PSX Flex would be destroyed together with that Flex; therefore
        # borrowed ownership cannot be guaranteed. Fail closed BEFORE writes.
        if declaration.ownership is NativeOwnership.BORROWED:
            raise RendererCapabilityError(
                "Borrowed Tk widgets are unsupported: Tkinter cannot "
                "reparent them or preserve their lifetime on PSX teardown."
            )
        widget = _build_native_widget(declaration, master)
        if not isinstance(widget, tk.Misc):
            raise RendererCapabilityError(
                f"Native widget {declaration.name!r} must create a tkinter widget, got {type(widget).__name__}."
            )
        try:
            if declaration.update is not None:
                declaration.update(widget, initial_props, frozenset())
        except Exception:
            if declaration.ownership is NativeOwnership.OWNED and widget.winfo_exists():
                widget.destroy()
            raise
        return TkHandle(declaration, widget, dict(initial_props), native=declaration)


# -- module helpers ---------------------------------------------------------

def _layout_spec(node_type: object) -> LayoutSpec | None:
    return _LAYOUTS.get(node_type) if isinstance(node_type, str) else None


def _layout_of(node: VNode) -> LayoutSpec | None:
    return _FRAGMENT_LAYOUT if node.kind is NodeKind.FRAGMENT else _layout_spec(node.type)


def _pack_options(parent: TkHandle) -> dict[str, object]:
    spacing = int(parent.props.get("spacing", 0))
    layout = _layout_spec(parent.node_type)
    if layout is not None and layout.horizontal:
        return {"side": tk.LEFT, "fill": tk.NONE, "expand": False, "padx": spacing, "pady": 0}
    return {"side": tk.TOP, "fill": tk.X, "expand": True, "padx": 0, "pady": spacing}


def _update_native(target: TkHandle, changed: Mapping[str, object], removed: frozenset[str]) -> None:
    update = target.native.update
    if (changed or removed) and update is None:
        raise RendererCapabilityError(
            f"Native widget {target.native.name!r} received prop changes but has no update adapter."
        )
    if update is not None:
        update(target.widget, changed, removed)


def _build_native_widget(declaration: NativeWidget, master: tk.Misc) -> object:
    if declaration.factory is None:
        return declaration.widget
    return declaration.factory(master) if declaration.takes_parent else declaration.factory()


def _as_handle(value: object) -> TkHandle:
    if not isinstance(value, TkHandle):
        raise TypeError("TkinterRenderer received a foreign handle.")
    return value


def _as_frame(handle: TkHandle) -> ttk.Frame:
    if not isinstance(handle.widget, ttk.Frame):
        raise RendererCapabilityError(f"{handle.node_type!r} cannot contain PSX children in Tkinter.")
    return handle.widget


def _as_subscription(value: object) -> TkEventSubscription:
    if not isinstance(value, TkEventSubscription):
        raise TypeError("TkinterRenderer received a foreign event subscription.")
    return value


def _validate_props(node: VNode) -> None:
    if node.kind is NodeKind.NATIVE:
        return
    if node.kind is NodeKind.HOST:
        spec = _PRIMITIVES.get(node.type)
        if spec is not None:
            spec.validate(node.props)
            return
    layout = _layout_of(node)
    if layout is None or node.props.keys() <= layout.props:
        return
    unsupported = set(node.props) - layout.props
    raise RendererCapabilityError(
        f"Unsupported Tkinter props for {node.type!r}: {', '.join(sorted(unsupported))}"
    )
