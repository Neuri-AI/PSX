"""Native SFLE certification census, derived from the actual built-in registry.

A *declared* native port is not a certification for all lifecycle operations.
Keep explicit unknown/pending outcomes rather than treating the leaf allowlist
as proof of create/update/reorder/unmount/borrowed/rollback support.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from psx.core.registry import builtin_component_registry
from psx.sfle.native_component_capabilities import NATIVE_LEAF_TYPES
from .native_operation_evidence import COMPONENT_OPERATION_TESTS

BACKENDS = ("qt", "tk", "kivy", "headless")
OPERATIONS = (
    "create", "update", "reorder", "unmount", "event_rebind",
    "borrowed_ownership", "rollback", "invalidation",
)

# Explicit exceptions to the host-native leaf policy. Not permitted as
# silent unsupported additions: all new registry entries must be classified.
TRANSPARENT = frozenset({"Fragment"})
STRUCTURAL = frozenset({"Flex"})
LEGACY = frozenset({"Row", "Column"})
EXTERNAL = frozenset({"Native"})
# Complete G2 backlog for built-ins not yet admitted. A new registry entry
# MUST be classified, otherwise CI fails rather than silently turning it red
# or accidentally green when it is not part of the reviewed scope.
UNPORTED_BY_BACKEND = MappingProxyType({
    "qt": frozenset(),
    "tk": frozenset(),
    "kivy": frozenset(),
    "headless": frozenset({
        "Checkbox", "Input", "TextArea", "Slider", "Spacer", "Divider",
        "Image", "ProgressBar", "Radio", "RadioGroup", "Select", "Switch",
        "Link", "Badge", "SpinBox", "Scroll", "Box",
    }),
})

HEADLESS_PORTED = frozenset({"Flex", "Text", "Button"})
# Full operation evidence must exist as tests (not only adapter method names).
# Each entry names one test that actually exercises that operation on a real
# backend, and is verified to exist in the repository by the test suite.
EVIDENCE = MappingProxyType({
    "qt": MappingProxyType({
        "create": "test_binding_and_native_geometry_owner",
        "update": "test_state_update_recommits_without_widget_remount",
        "reorder": "test_keyed_reconciliation_and_button_event_rebind",
        "unmount": "test_queued_resize_is_ignored_after_unmount",
        "event_rebind": "test_keyed_reconciliation_and_button_event_rebind",
        "rollback": "test_stale_layout_generation_fails_before_native_write",
        "invalidation": "test_native_root_resize_automatically_recomputes_sfle",
    }),
    "tk": MappingProxyType({
        "create": "test_real_ttk_widgets_use_sfle_place_not_pack_or_grid",
        "update": "test_hooks_events_and_scheduler_commit_without_remounting",
        "reorder": "test_keyed_reordering_retains_native_handles_and_updates_sfle_positions",
        "unmount": "test_tk_configure_does_not_commit_after_unmount",
        "event_rebind": "test_textarea_explicit_height_and_callback_rebind",
        "rollback": "test_engine_generation_mismatch_rejects_without_native_mutation",
        "invalidation": "test_real_tk_host_configure_automatically_reflows_sfle",
    }),
    "kivy": MappingProxyType({
        "create": "test_real_kivy_native_bottom_left_geometry_and_reconciliation",
        "update": "test_real_kivy_native_bottom_left_geometry_and_reconciliation",
        "unmount": "test_scroll_basic_sfle_viewport_and_explicit_content_root",
        "event_rebind": "test_switch_spinbox_select_native_interaction_and_sfle_geometry",
        "invalidation": "test_native_root_and_sdl2_window_resize_automatically_reflow_sfle",
    }),
    "headless": MappingProxyType({
        "create": "test_opt_in_headless_flex_is_real_sfle_geometry_not_a_dummy_layout",
        "update": "test_hook_updates_commit_new_geometry_without_remounting_widgets",
        "reorder": "test_keyed_reorder_and_resize_reuse_native_handle_without_remount",
        "unmount": "test_bad_engine_generation_does_not_commit_any_rectangles",
        "rollback": "test_bad_engine_generation_does_not_commit_any_rectangles",
    }),
})


@dataclass(frozen=True, slots=True)
class G2Cell:
    component: str
    backend: str
    status: str
    operations_with_evidence: tuple[str, ...]
    pending_operations: tuple[str, ...]

    @property
    def fully_certified(self) -> bool:
        return self.status == "native" and not self.pending_operations


def native_certification_matrix() -> tuple[G2Cell, ...]:
    """Enumerate every registry × backend cell with no implicit green status."""
    names = tuple(sorted(builtin_component_registry().snapshot()))
    for backend, component, operation in COMPONENT_OPERATION_TESTS:
        if backend not in BACKENDS or operation not in OPERATIONS:
            raise ValueError(f"Invalid component evidence key: {backend}, {component}, {operation}")
        if component not in names:
            raise ValueError(f"Evidence references absent registry component {component!r}.")
    for backend in BACKENDS:
        classified = (
            set(NATIVE_LEAF_TYPES.get(backend, HEADLESS_PORTED))
            | STRUCTURAL | TRANSPARENT | LEGACY | EXTERNAL
            | set(UNPORTED_BY_BACKEND[backend])
        )
        unknown = set(names) - classified
        stale = classified - set(names)
        if unknown or stale:
            raise ValueError(
                f"G2 {backend} registry classification out of sync: "
                f"unclassified={sorted(unknown)}, absent={sorted(stale)}."
            )
    result: list[G2Cell] = []
    for backend in BACKENDS:
        allowed = NATIVE_LEAF_TYPES.get(backend, HEADLESS_PORTED)
        for name in names:
            if name in TRANSPARENT:
                status = "transparent"
            elif name in LEGACY:
                status = "legacy_deferred"
            elif name in STRUCTURAL:
                status = "native"
            elif name in EXTERNAL:
                status = "external_port_required"
            elif name in allowed:
                status = "native"
            else:
                status = "unported"
            # Only references reviewed for this exact backend/component
            # certify an operation. Generic backend tests do not propagate.
            if status != "native" and any(
                key[0] == backend and key[1] == name
                for key in COMPONENT_OPERATION_TESTS
            ):
                raise ValueError(f"Evidence on non-native G2 cell {backend}/{name}.")
            evidence = (
                tuple(op for op in OPERATIONS
                      if (backend, name, op) in COMPONENT_OPERATION_TESTS)
                if status == "native" else ()
            )
            pending = tuple(op for op in OPERATIONS if op not in evidence)
            result.append(G2Cell(name, backend, status, evidence, pending))
    return tuple(result)


def native_matrix_summary() -> dict[str, dict[str, int]]:
    summary = {}
    for backend in BACKENDS:
        subset = [cell for cell in native_certification_matrix() if cell.backend == backend]
        summary[backend] = {
            key: sum(cell.status == key for cell in subset)
            for key in ("native", "unported", "legacy_deferred",
                        "transparent", "external_port_required")
        }
    return summary


def native_operation_coverage_summary() -> dict[str, dict[str, dict[str, int]]]:
    """Machine-readable C2 evidence counts, by backend and operation.

    Only native cells contribute: unported/legacy/external cells are recorded
    in native_matrix_summary() and never accidentally counted as passes here.
    A pending operation is an explicit gap for C3–C6, not a C2 failure.
    """
    cells = native_certification_matrix()
    return {
        backend: {
            operation: {
                "evidenced": sum(
                    c.status == "native" and operation in c.operations_with_evidence
                    for c in cells if c.backend == backend
                ),
                "pending": sum(
                    c.status == "native" and operation in c.pending_operations
                    for c in cells if c.backend == backend
                ),
            }
            for operation in OPERATIONS
        }
        for backend in BACKENDS
    }
