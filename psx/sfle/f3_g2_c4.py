"""C4 external widget ownership and resource evidence, kept separate from builtins.

Required receipts are backend-specific. Unsupported ownership is a negative
contract, not an implicit success or borrowed-widget destruction certificate.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class C4Case:
    backend: str
    variant: str
    expectation: str
    test_name: str


# Exactly one executable test for each external host ownership/resource
# scenario, including supported rejection instead of fictional Tk reparenting.
C4_CASES = (
    C4Case("qt", "native_owned", "disposed", "test_external_native_owned_borrowed_and_custom_resources"),
    C4Case("qt", "native_borrowed", "retained_and_reparented", "test_external_native_owned_borrowed_and_custom_resources"),
    C4Case("qt", "custom_adapter", "destroy_once", "test_external_native_owned_borrowed_and_custom_resources"),
    C4Case("tk", "native_owned", "disposed", "test_owned_native_and_custom_tk_resources_are_released_once"),
    C4Case("tk", "native_borrowed", "rejected_without_mutation", "test_borrowed_tk_widget_with_foreign_parent_fails_without_disposal"),
    C4Case("tk", "custom_adapter", "destroy_once", "test_owned_native_and_custom_tk_resources_are_released_once"),
    C4Case("kivy", "native_owned", "detached", "test_c4_owned_native_and_custom_adapter_cleanup"),
    C4Case("kivy", "native_borrowed", "retained_and_reparented", "test_borrowed_native_widget_restores_parent_and_disposes_only_own_bindings"),
    C4Case("kivy", "custom_adapter", "destroy_once", "test_c4_owned_native_and_custom_adapter_cleanup"),
)

C4_BY_BACKEND = MappingProxyType({
    backend: tuple(case for case in C4_CASES if case.backend == backend)
    for backend in ("qt", "tk", "kivy")
})
