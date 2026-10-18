"""Reviewed family policy for future builtins, including overlays/portals.

Registry census is intentionally fail-closed. A new component cannot inherit
leaf or Flex certification merely because it was registered. This is a
certification *policy*, not a new Modal implementation or runtime API.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from psx.core.registry import builtin_component_registry
from psx.sfle.native_component_capabilities import NATIVE_LEAF_TYPES

FAMILIES = frozenset({
    "leaf", "layout_container", "structural_container",
    "native_viewport", "transparent", "external_port", "legacy",
    "overlay_portal",
})
_SPECIAL = {
    "Flex": "layout_container",
    "Grid": "layout_container",
    "GridItem": "structural_container",
    "Box": "structural_container",
    "RadioGroup": "structural_container",
    "Divider": "structural_container",
    "Scroll": "native_viewport",
    "Fragment": "transparent",
    "Native": "external_port",
    "WebView": "external_port",
}
_LEAVES = frozenset.union(*(frozenset(types) for types in NATIVE_LEAF_TYPES.values())) - set(_SPECIAL)
FAMILY_POLICY = MappingProxyType({
    **{name: "leaf" for name in _LEAVES},
    **_SPECIAL,
})

@dataclass(frozen=True, slots=True)
class FamilyRequirement:
    component: str
    family: str
    driver_type: str
    requires_child_policy: bool
    requires_portal_lifecycle: bool

def classify_component_family(name: str, *, policy=FAMILY_POLICY) -> FamilyRequirement:
    family = policy.get(name)
    if family not in FAMILIES:
        raise ValueError(f"Unclassified or invalid G2 component family: {name!r}")
    if family == "overlay_portal":
        driver = "overlay_portal_specific"
    elif family in ("structural_container", "native_viewport"):
        driver = "container_specific"
    elif family == "layout_container":
        driver = "layout_specific"
    elif family == "leaf":
        driver = "native_leaf"
    else:
        driver = "explicit_special_case"
    return FamilyRequirement(
        name, family, driver,
        family in {"layout_container", "structural_container", "native_viewport", "overlay_portal"},
        family == "overlay_portal",
    )

def family_inventory() -> tuple[FamilyRequirement, ...]:
    names = set(builtin_component_registry().snapshot())
    if names != set(FAMILY_POLICY):
        raise ValueError(
            f"G2 family policy differs from registry: "
            f"unclassified={sorted(names - set(FAMILY_POLICY))}; "
            f"stale={sorted(set(FAMILY_POLICY) - names)}"
        )
    return tuple(classify_component_family(name) for name in sorted(names))
