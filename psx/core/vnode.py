"""Immutable UI descriptions and the canonical Python element constructors."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Callable, TypeAlias

from .errors import InvalidChildError, RendererCapabilityError
from .native import NativeWidget
from psx.core.contracts import (
    # Text
    TEXT_PROPS,
    TEXT_DEFAULTS,
    TEXT_CONTRACT,

    # Button
    BUTTON_PROPS,
    BUTTON_DEFAULTS,
    BUTTON_CONTRACT,

    # Slider
    SLIDER_PROPS,
    SLIDER_DEFAULTS,
    SLIDER_CONTRACT,

    # Checkbox
    CHECKBOX_PROPS,
    CHECKBOX_DEFAULTS,
    CHECKBOX_CONTRACT,

    # Input
    INPUT_PROPS,
    INPUT_DEFAULTS,
    INPUT_CONTRACT,

    # TextArea
    TEXTAREA_CONTRACT,
    TEXTAREA_PROPS,
    TEXTAREA_DEFAULTS,

    COLUMN_CONTRACT,
    COLUMN_PROPS,
    COLUMN_DEFAULTS,


    ROW_CONTRACT,
    ROW_PROPS,
    ROW_DEFAULTS,

    # Spacer
    SPACER_PROPS,
    SPACER_DEFAULTS,
    SPACER_CONTRACT,

    # Divider
    DIVIDER_PROPS,
    DIVIDER_DEFAULTS,
    DIVIDER_CONTRACT,

    # Image
    IMAGE_PROPS,
    IMAGE_DEFAULTS,
    IMAGE_CONTRACT,

    # ProgressBar
    PROGRESSBAR_PROPS,
    PROGRESSBAR_DEFAULTS,
    PROGRESSBAR_CONTRACT,

    # Radio
    RADIO_PROPS,
    RADIO_DEFAULTS,
    RADIO_CONTRACT,

    # RadioGroup
    RADIOGROUP_PROPS,
    RADIOGROUP_DEFAULTS,
    RADIOGROUP_CONTRACT,
    SELECT_PROPS,
    SELECT_DEFAULTS,
    SELECT_CONTRACT,
    SWITCH_CONTRACT,
    LINK_CONTRACT,
    BADGE_CONTRACT,
    SPINBOX_CONTRACT,
)

from .validators import (
    validate_text_props,
    validate_slider_props,
    validate_textarea_props,
    validate_column_props,
    validate_row_props,
    validate_checkbox_props,
    validate_input_props,
    validate_button_props,
    validate_divider_props,
    validate_spacer_props,
    validate_progressbar_props,
)

if TYPE_CHECKING:
    from .component import ComponentType


class NodeKind(str, Enum):
    HOST = "host"
    COMPONENT = "component"
    FRAGMENT = "fragment"
    NATIVE = "native"


HostType: TypeAlias = str
# ComponentType is intentionally not imported at module load time to avoid the
# component/vnode import cycle. Runtime validation in create_element is exact.
VNodeType: TypeAlias = object
Key: TypeAlias = str | int


@dataclass(frozen=True, slots=True)
class VNode:
    """A framework-independent, immutable UI description.

    Native widget handles belong to mounted instances, never to this value.
    """

    kind: NodeKind
    type: VNodeType
    key: Key | None
    props: Mapping[str, object]
    children: tuple["VNode", ...]


def _freeze_props(props: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(props))


def _normalize_one(value: object, output: list[VNode]) -> None:
    if value is None or value is False:
        return
    if isinstance(value, VNode):
        output.append(value)
        return
    if isinstance(value, str):
        output.append(Text(value))
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        output.append(Text(str(value)))
        return
    if isinstance(value, (list, tuple)):
        for child in value:
            _normalize_one(child, output)
        return
    if value is True:
        raise InvalidChildError(
            "True is not a valid PSX child; use a conditional expression instead.")
    raise InvalidChildError(f"Unsupported PSX child: {type(value).__name__}")


def normalize_children(values: Iterable[object]) -> tuple[VNode, ...]:
    """Normalize supported declarative child values into immutable VNodes."""
    output: list[VNode] = []
    for value in values:
        _normalize_one(value, output)
    return tuple(output)


def create_element(
    node_type: VNodeType,
    *children: object,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    """Create a VNode; all public builders delegate to this constructor."""
    from .component import ComponentType

    if node_type == "Text":
        validate_text_props(props)
    if key is not None and not isinstance(key, (str, int)):
        raise TypeError("PSX keys must be str, int, or None.")
    if ref is not None:
        props["ref"] = ref
    if isinstance(node_type, ComponentType):
        kind = NodeKind.COMPONENT
    elif node_type is Fragment:
        kind = NodeKind.FRAGMENT
        node_type = "Fragment"
    elif isinstance(node_type, str):
        kind = NodeKind.HOST
    elif isinstance(node_type, NativeWidget):
        kind = NodeKind.NATIVE
        if children:
            raise InvalidChildError(
                "Native widgets cannot have PSX children; compose them in a layout instead.")
    else:
        raise TypeError(
            "PSX element type must be a host name, Fragment, NativeWidget, or @component value.")
    return VNode(kind, node_type, key, _freeze_props(props), normalize_children(children))


class _Fragment:
    def __call__(self, *children: object, key: Key | None = None) -> VNode:
        return create_element(self, *children, key=key)

    def __repr__(self) -> str:
        return "Fragment"


Fragment = _Fragment()


def native_widget(
    widget: NativeWidget, *, key: Key | None = None, ref: object | None = None, **props: object
) -> VNode:
    """Create a VNode for a renderer-specific :class:`NativeWidget` declaration."""
    if not isinstance(widget, NativeWidget):
        raise TypeError("native_widget() requires a NativeWidget declaration.")
    return create_element(widget, key=key, ref=ref, **props)


def _layout(name: str, children: tuple[object, ...], spacing: int, key: Key | None, props: Mapping[str, object]) -> VNode:
    if isinstance(spacing, bool) or not isinstance(spacing, int) or spacing < 0:
        raise ValueError("spacing must be a non-negative integer.")
    return create_element(name, *children, key=key, spacing=spacing, **props)


def Row(
    *children: object, spacing: int = 0,
    padding: int | tuple[int, int] | tuple[int, int, int, int] = 0,
    align: str = "stretch", expand: bool | tuple[bool, ...] = False,
    enabled: bool = True, key: Key | None = None, ref: object | None = None,
    **props: object,
) -> VNode:
    """Horizontal portable container with optional per-child expansion."""
    options = dict(spacing=spacing, padding=padding, align=align,
                   expand=expand, enabled=enabled, **props)
    ROW_CONTRACT.validate_builder(options)
    return create_element("Row", *children, key=key, ref=ref, **options)


def Text(
    value: str | int | float, *, font_size: int | float = 16,
    bold: bool = False, italic: bool = False, color: str | None = None,
    align: str = "left", enabled: bool = True, key: Key | None = None,
    ref: object | None = None, **props: object,
) -> VNode:
    """Portable plain text with a closed, backend-independent contract."""
    options = dict(value=value, font_size=font_size, bold=bold, italic=italic,
                   color=color, align=align, enabled=enabled, **props)
    TEXT_CONTRACT.validate_builder(options)
    if key is not None and (isinstance(key, bool) or not isinstance(key, (str, int))):
        raise RendererCapabilityError("Text.key must be str, int, or None.")
    options["value"] = str(value)
    return create_element("Text", key=key, ref=ref, **options)


def Button(
    label: str | int | float,
    *,
    font_size: int | float = 14,
    on_click: Callable[[], None] | None = None,
    enabled: bool = True,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    """Portable push button with a closed, backend-independent contract."""
    options = dict(label=label, font_size=font_size,
                   on_click=on_click, enabled=enabled, **props)
    BUTTON_CONTRACT.validate_builder(options)
    if key is not None and (isinstance(key, bool) or not isinstance(key, (str, int))):
        raise RendererCapabilityError("Button.key must be str, int, or None.")
    options["label"] = str(label)
    return create_element("Button", key=key, ref=ref, **options)


def Input(
    *,
    value: str = "",
    placeholder: str = "",
    font_size: int | float = 14,
    enabled: bool = True,
    read_only: bool = False,
    password: bool = False,
    on_change: Callable[[str], None] | None = None,
    on_submit: Callable[[], None] | None = None,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    options = dict(
        value=value,
        placeholder=placeholder,
        font_size=font_size,
        enabled=enabled,
        read_only=read_only,
        password=password,
        on_change=on_change,
        on_submit=on_submit,
        **props,
    )
    INPUT_CONTRACT.validate_builder(options)
    return create_element("Input", key=key, ref=ref, **options)


def Checkbox(*, checked: bool = False, enabled: bool = True, on_change: Callable[[bool], None] | None = None,
             key: str | int | None = None, ref: object | None = None, **props: object) -> VNode:
    """Portable boolean checkbox with a boolean ``on_change`` callback."""
    options = dict(checked=checked, enabled=enabled,
                   on_change=on_change, **props)
    CHECKBOX_CONTRACT.validate_builder(options)
    return create_element("Checkbox", key=key, ref=ref, **options)


def TextArea(
    value: str = "",
    *,
    placeholder: str = "",
    font_size: int | float = 14,
    enabled: bool = True,
    read_only: bool = False,
    on_change: Callable[[str], None] | None = None,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    options = dict(
        value=value,
        placeholder=placeholder,
        font_size=font_size,
        enabled=enabled,
        read_only=read_only,
        on_change=on_change,
        **props,
    )
    TEXTAREA_CONTRACT.validate_builder(options)
    return create_element("TextArea", key=key, ref=ref, **options)


def Column(
    *children: object,
    spacing: int = 0,
    padding: int | tuple[int, int] | tuple[int, int, int, int] = 0,
    align: str = "stretch",
    expand: bool | tuple[bool, ...] = False,
    enabled: bool = True,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    """Vertical portable container with optional per-child expansion."""
    options = dict(spacing=spacing, padding=padding, align=align,
                   expand=expand, enabled=enabled, **props)
    COLUMN_CONTRACT.validate_builder(options)
    return create_element("Column", *children, key=key, ref=ref, **options)

def Slider(
    *,
    value: float = 0.0,
    min: float = 0.0,
    max: float = 100.0,
    step: float = 0.0,
    orientation: str = "horizontal",
    enabled: bool = True,
    on_change: Callable[[float], None] | None = None,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    options = dict(
        value=value, min=min, max=max,
        step=step, orientation=orientation, enabled=enabled,
        on_change=on_change, **props,
    )
    SLIDER_CONTRACT.validate_builder(options)
    return create_element("Slider", key=key, ref=ref, **options)

def Spacer(*, key: Key | None = None, ref: object | None = None, **props: object) -> VNode:
    """Absorbe el espacio libre del padre en su eje principal.

    En un ``Column`` expande verticalmente; en un ``Row``, horizontalmente.
    El contenedor decide el eje a partir de su propia orientación.
    """
    SPACER_CONTRACT.validate_builder(props)
    return create_element("Spacer", key=key, ref=ref, **props)

def Divider(
    *children: object,
    orientation: str = "horizontal",
    thickness: int = 1,
    color: str | None = None,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    """Portable separator with an optional single child.

    With no children it renders a plain line. With one child, the child is
    laid out centered on the line (``─── child ───``). ``color=None`` defers
    to the renderer theme; ``thickness`` is the line width in pixels.
    """
    if len(children) > 1:
        raise InvalidChildError("Divider accepts at most one child.")
    options = dict(orientation=orientation, thickness=thickness, color=color, **props)
    DIVIDER_CONTRACT.validate_builder(options)
    return create_element("Divider", *children, key=key, ref=ref, **options)

def Image(
    source: str,
    *,
    fit: str = "contain",
    width: int | None = None,
    height: int | None = None,
    alt: str = "",
    enabled: bool = True,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    """Portable image loaded from a local file path.

    ``source`` is resolved through the application's resource helper, so
    ``get_resource("images", "logo.png")`` is the idiomatic call site.
    The widget takes the image's natural size unless ``width`` or ``height``
    overrides are provided; when only one axis is given, the other is
    computed to preserve the source aspect ratio. ``fit`` decides how the
    image is drawn inside the widget when both axes are set explicitly.
    """
    options = dict(
        source=source, fit=fit, width=width, height=height,
        alt=alt, enabled=enabled, **props,
    )
    IMAGE_CONTRACT.validate_builder(options)
    return create_element("Image", key=key, ref=ref, **options)


def Box(*children: object, key: Key | None = None, ref: object | None = None) -> VNode:
    """Internal passthrough container used by the Qyro integration.

    It exists so the host's top-level widget can stay a stable native type
    even when the user's render root changes between renders (for example,
    ``Row`` becoming ``Column``). Not part of the public portable API; no
    props, no events, no portability guarantees.
    """
    return create_element("Box", *children, key=key, ref=ref)

def ProgressBar(
    *,
    value: float = 0.0,
    min: float = 0.0,
    max: float = 100.0,
    indeterminate: bool = False,
    orientation: str = "horizontal",
    enabled: bool = True,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    """Portable determinate or indeterminate progress bar.

    In determinate mode, ``value`` moves between ``min`` and ``max``. In
    indeterminate mode, the renderer animates the bar to signal that work
    is in progress without a specific completion figure; ``value`` is
    ignored in that mode. Out-of-range ``value`` values are clamped by the
    renderer rather than rejected, so async updates that briefly overshoot
    the range do not raise.
    """
    options = dict(
        value=value, min=min, max=max,
        indeterminate=indeterminate, orientation=orientation,
        enabled=enabled, **props,
    )
    PROGRESSBAR_CONTRACT.validate_builder(options)
    return create_element("ProgressBar", key=key, ref=ref, **options)
def Radio(
    value: str | int,
    *,
    label: str = "",
    enabled: bool = True,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    """Portable radio button.

    ``Radio`` is always expected to be placed inside a ``RadioGroup``, which
    owns the ``value`` of the selected radio and dispatches ``on_change``.
    A ``Radio`` outside a group has no portable selection semantics; the
    renderer may still mount it but its behaviour is backend-specific.
    """
    options = dict(value=value, label=label, enabled=enabled, **props)
    RADIO_CONTRACT.validate_builder(options)
    return create_element("Radio", key=key, ref=ref, **options)


def RadioGroup(
    *children: object,
    value: str | int | None = None,
    on_change: Callable[[str | int], None] | None = None,
    orientation: str = "vertical",
    spacing: int = 0,
    padding: int | tuple[int, int] | tuple[int, int, int, int] = 0,
    enabled: bool = True,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    """Portable mutually exclusive group of ``Radio`` children.

    ``value`` is the currently selected radio's value, or ``None`` for no
    selection. ``on_change`` receives the value of the radio the user just
    selected. Children must be ``Radio`` nodes; any other node raises
    ``RendererCapabilityError`` at mount time.
    """
    options = dict(
        value=value, on_change=on_change, orientation=orientation,
        spacing=spacing, padding=padding, enabled=enabled, **props,
    )
    RADIOGROUP_CONTRACT.validate_builder(options)
    return create_element("RadioGroup", *children, key=key, ref=ref, **options)

def Select(
    *,
    options: tuple[object, ...] | list[object] = (),
    value: str | int | None = None,
    placeholder: str = "",
    enabled: bool = True,
    on_change: Callable[[str | int], None] | None = None,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    """Portable, controlled, single-selection input."""
    config = dict(
        options=options, value=value, placeholder=placeholder,
        enabled=enabled, on_change=on_change, **props,
    )
    SELECT_CONTRACT.validate_builder(config)
    return create_element("Select", key=key, ref=ref, **config)


def Switch(
    *,
    checked: bool = False,
    enabled: bool = True,
    label: str = "",
    size: str = "medium",
    color: str = "#16A34A",
    on_change: Callable[[bool], None] | None = None,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    """Controlled, animated and labeled portable toggle switch."""
    options = dict(
        checked=checked, enabled=enabled,
        label=label, size=size, color=color, on_change=on_change, **props,
    )
    SWITCH_CONTRACT.validate_builder(options)
    return create_element("Switch", key=key, ref=ref, **options)


def Link(
    label: str = "",
    *,
    href: str | None = None,
    on_click: Callable[[], None] | None = None,
    color: str | None = None,
    underline: bool = True,
    enabled: bool = True,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    """Portable clickable text; external href or future-router callback."""
    options = dict(
        label=label, href=href, on_click=on_click,
        color=color, underline=underline, enabled=enabled, **props,
    )
    LINK_CONTRACT.validate_builder(options)
    return create_element("Link", key=key, ref=ref, **options)


def SpinBox(
    *,
    value: int | float = 0,
    min: int | float = 0,
    max: int | float = 100,
    step: int | float = 1,
    decimals: int = 0,
    enabled: bool = True,
    on_change: Callable[[int | float], None] | None = None,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    """Controlled portable numeric input with increment/decrement buttons."""
    config = dict(
        value=value, min=min, max=max, step=step, decimals=decimals,
        enabled=enabled, on_change=on_change, **props,
    )
    SPINBOX_CONTRACT.validate_builder(config)
    return create_element("SpinBox", key=key, ref=ref, **config)


def Badge(
    label: str = "",
    *,
    variant: str = "neutral",
    appearance: str = "filled",
    size: str = "medium",
    shape: str = "rounded",
    enabled: bool = True,
    key: Key | None = None,
    ref: object | None = None,
    **props: object,
) -> VNode:
    """A noninteractive, intrinsically sized semantic status label."""
    options = dict(
        label=label, variant=variant, appearance=appearance,
        size=size, shape=shape, enabled=enabled, **props,
    )
    BADGE_CONTRACT.validate_builder(options)
    return create_element("Badge", key=key, ref=ref, **options)
