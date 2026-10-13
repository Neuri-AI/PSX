"""F3-G2 external leaf geometry ports for Native and registered custom hosts.

A port measures one *actual* toolkit leaf on its UI thread, applies one
native-parent-relative rectangle computed by SFLE/F2, and reads it back.
It must not compute sibling layout, mutate the SFLE snapshot, or manage
PSX children. Toolkit adapters remain responsible for native ownership.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from psx.core.errors import RendererCapabilityError
from psx.core.native import NativeWidget
from psx.core.vnode import NodeKind, VNode
from .errors import DiagnosticCode, SFLEError
from .model import IntrinsicSizes, LayoutConstraints, MeasuredBox, Rect


@dataclass(frozen=True, slots=True)
class SFLEExternalPort:
    """Required explicit geometry authority for one external native leaf.

    measure(widget, constraints) -> IntrinsicSizes: *content* metrics.
    apply(widget, projected_rect) -> None: native parent-relative coordinates.
    read(widget) -> Rect: the same native parent-relative coordinate frame.

    The runtime invokes these only on the renderer's owner UI thread and
    validates complete measurements, generations and <=1px native readback.
    """

    measure: Callable[[object, LayoutConstraints], IntrinsicSizes]
    apply: Callable[[object, Rect], None]
    read: Callable[[object], Rect]

    def __post_init__(self) -> None:
        for name in ("measure", "apply", "read"):
            if not callable(getattr(self, name)):
                raise TypeError(f"SFLEExternalPort.{name} must be callable.")


def external_port_for(node: VNode, renderer: object) -> SFLEExternalPort | None:
    """Return a certified explicit port; reject external leaves without one.

    Built-in primitives return None and use the existing native measurement
    and geometry committer. A registered custom host needs a non-default
    adapter carrying sfle_port; a Native declaration carries its own port.
    """
    if node.kind is NodeKind.NATIVE:
        declaration = node.type
        port = declaration.sfle_port if isinstance(declaration, NativeWidget) else None
        if not isinstance(port, SFLEExternalPort):
            raise RendererCapabilityError(
                "F3-G2 Native requires SFLEExternalPort(measure, apply, read)."
            )
        return port
    if node.kind is not NodeKind.HOST:
        raise RendererCapabilityError("F3-G2 external leaf requires a HOST or Native node.")
    from .f3_native_coverage import NATIVE_LEAF_TYPES
    kind = getattr(renderer, "_sfle_backend", None)
    if node.type == "Flex" or node.type in NATIVE_LEAF_TYPES.get(kind, ()):
        return None
    adapter = renderer.adapters.get(str(node.type))
    from psx.renderers.adapters import DelegatingAdapter
    if adapter is None or isinstance(adapter, DelegatingAdapter):
        raise RendererCapabilityError(
            f"F3-G2 {kind} SFLE geometry not certified for {node.type!r}."
        )
    port = getattr(adapter, "sfle_port", None)
    if not isinstance(port, SFLEExternalPort):
        # Existing portable builtin adapters are not user custom adapters.
        # Keep their existing explicit "not certified" failure contract.
        from psx.core.registry import builtin_component_registry
        if node.type in builtin_component_registry().snapshot():
            raise RendererCapabilityError(
                f"F3-G2 {kind} SFLE geometry not certified for {node.type!r}."
            )
        raise RendererCapabilityError(
            f"F3-G2 custom adapter {node.type!r} requires "
            "sfle_port=SFLEExternalPort(measure, apply, read)."
        )
    if node.children:
        raise RendererCapabilityError(
            f"F3-G2 custom host {node.type!r} must be a leaf; "
            "external adapters cannot own PSX child geometry."
        )
    return port


def measure_external(
    port: SFLEExternalPort, widget: object,
    constraints: LayoutConstraints, node_id: str, generation: int,
) -> MeasuredBox:
    metrics = port.measure(widget, constraints)
    if not isinstance(metrics, IntrinsicSizes):
        raise SFLEError(
            DiagnosticCode.UNSUPPORTED_MEASUREMENT,
            "External SFLE measure() must return IntrinsicSizes.", node_id,
        )
    return MeasuredBox(node_id, metrics, constraints, generation)


def read_external(port: SFLEExternalPort, widget: object, node_id: str) -> Rect:
    rect = port.read(widget)
    if not isinstance(rect, Rect):
        raise SFLEError(
            DiagnosticCode.INVALID_SNAPSHOT,
            "External SFLE read() must return a native-parent-relative Rect.", node_id,
        )
    return rect
