"""C6 family audit: new Modal-type nodes need dedicated certification."""
from __future__ import annotations

import pytest
from tests.certification.f3_g2_families import (
    FAMILY_POLICY, classify_component_family, family_inventory,
)

def test_c6_family_manifest_exactly_covers_live_registry():
    items = family_inventory()
    assert items
    assert len(items) == len(FAMILY_POLICY)
    assert {i.component for i in items} == set(FAMILY_POLICY)
    assert classify_component_family("Flex").driver_type == "layout_specific"
    assert classify_component_family("Button").driver_type == "native_leaf"
    assert classify_component_family("Scroll").driver_type == "container_specific"
    assert classify_component_family("Native").driver_type == "explicit_special_case"

def test_c6_new_component_never_inherits_existing_leaf_proof():
    with pytest.raises(ValueError, match="Unclassified"):
        classify_component_family("Modal")
    proposed = dict(FAMILY_POLICY, Modal="overlay_portal")
    modal = classify_component_family("Modal", policy=proposed)
    assert modal.driver_type == "overlay_portal_specific"
    assert modal.requires_child_policy
    assert modal.requires_portal_lifecycle
    assert modal.driver_type != classify_component_family("Button").driver_type
    with pytest.raises(ValueError, match="Unclassified"):
        classify_component_family("Modal", policy={"Modal": "unknown"})

def test_c6_no_existing_registered_overlay_can_bypass_dedicated_driver():
    assert all(x.family != "overlay_portal" for x in family_inventory())
