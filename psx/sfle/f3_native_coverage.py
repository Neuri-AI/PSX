"""Explicit F3-G2 native-leaf capability policy (not the G2 closure matrix).

SFLE owns layout for these registered toolkit controls. Qt/Tk supply intrinsic
requested sizes; Kivy's non-textured Widget primitives are admitted only
with *both* explicit pixel layout dimensions, so no default Kivy size/size_hint
is ever fabricated as CSS intrinsic measurement.

Do not add container controls with native child geometry ownership here.
Scroll is G3. Every added cell requires native create/update/event and
readback tests in the corresponding backend's CI job.
"""
from __future__ import annotations

from types import MappingProxyType

from psx.core.errors import RendererCapabilityError
from psx.core.vnode import NodeKind, VNode
from psx.sfle.lengths import LengthKind, parse_length

G2_LEAF_TYPES = MappingProxyType({
    "qt": frozenset({
        "Text", "Button", "Checkbox", "Input", "TextArea",
        "Slider", "Radio", "ProgressBar", "Select", "Image",
        "Link", "Badge", "Divider", "Spacer", "Switch", "SpinBox", "RadioGroup", "Box", "Scroll",
    }),
    "tk": frozenset({
        "Text", "Button", "Checkbox", "TextArea", "Slider", "Radio", "ProgressBar", "Image",
        "Link", "Badge", "Divider", "Spacer", "Switch", "SpinBox", "RadioGroup", "Box", "Select", "Scroll", "ProgressBar",
    }),
    "kivy": frozenset({
        "Text", "Button", "Checkbox", "TextArea", "Slider", "Spacer", "Image",
        "Link", "Badge", "Divider", "Switch", "SpinBox", "Select", "Radio", "RadioGroup", "Box", "Scroll", "Checkbox", "ProgressBar",
    }),
})
KIVY_EXPLICIT_BOUNDS = frozenset({"Checkbox", "Slider", "ProgressBar"})


def g2_native_leaf_needs_measurement(node: VNode, *, backend: str) -> bool:
    """Check one source declaration *before* stripping SFLE item metadata.

    Returns False only for Kivy controls with definite explicit px dimensions
    on both axes. Such controls need NO host intrinsic measurement; any CSS
    intrinsic/auto/% sizes require a future real measurement port.
    """
    if node.kind is not NodeKind.HOST or not isinstance(node.type, str):
        raise RendererCapabilityError(
            f"F3-G2 {backend} native node type is not certified."
        )
    if node.type == "Flex":
        return False
    supported = G2_LEAF_TYPES.get(backend)
    if supported is None:
        raise ValueError(f"Unknown F3-G2 backend {backend!r}.")
    if node.type not in supported:
        raise RendererCapabilityError(
            f"F3-G2 {backend} SFLE geometry not certified for {node.type!r}."
        )
    if node.type == "Scroll":
        if len(node.children) != 1 or (
            node.children[0].kind is not NodeKind.HOST
            or node.children[0].type != "Flex"
        ):
            raise RendererCapabilityError(
                "F3-G2 Scroll requires exactly one explicit Flex content root."
            )
        return False
    if node.type == "Box" and len(node.children) != 1:
        raise RendererCapabilityError(
            "F3-G2 internal Box requires exactly one child."
        )
    if node.type == "RadioGroup" and any(
        child.kind is not NodeKind.HOST or child.type != "Radio"
        for child in node.children
    ):
        raise RendererCapabilityError(
            "F3-G2 RadioGroup children must be Radio nodes."
        )
    if node.type == "Divider" and node.children and (
        len(node.children) != 1
        or node.children[0].kind is not NodeKind.HOST
        or node.children[0].type != "Text"
    ):
        raise RendererCapabilityError(
            "F3-G2 labeled Divider requires exactly one Text child."
        )
    if node.type in ("Box", "RadioGroup") or (
        node.type == "Divider" and node.children
    ):
        # A structural node is measured by SFLE as a container, not as a leaf.
        return False
    if backend == "kivy" and node.type in KIVY_EXPLICIT_BOUNDS:
        for axis in ("layout_width", "layout_height"):
            raw = node.props.get(axis)
            if raw is None:
                raise RendererCapabilityError(
                    f"F3-G2 Kivy {node.type} requires explicit pixel "
                    f"{axis} until a native intrinsic measurement port exists."
                )
            try:
                length = parse_length(raw)
            except (ValueError, TypeError) as exc:
                raise RendererCapabilityError(
                    f"F3-G2 Kivy {node.type}.{axis} must be a definite px length."
                ) from exc
            if length.kind is not LengthKind.PX:
                raise RendererCapabilityError(
                    f"F3-G2 Kivy {node.type}.{axis} must be a definite px length."
                )
        return False
    return True
