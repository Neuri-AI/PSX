"""F3-G2 Headless: real mounted rectangles, identity, generations and resize."""
from __future__ import annotations

import pytest

from psx import Button, Flex, Text, component, use_state
from psx.core.errors import RendererCapabilityError
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.errors import DiagnosticCode, SFLEError
from psx.sfle.model import (
    AvailableSize, IntrinsicSizes, LayoutConstraints, LayoutResult,
)


def constraints(width: float = 120, height: float = 60) -> LayoutConstraints:
    return LayoutConstraints(AvailableSize(width, True), AvailableSize(height, True))


def fixed(key: str, width: int = 20) -> object:
    return Flex(key=key, width=width, height=10, flex_basis=width,
                flex_shrink=0)


def new_renderer(**options) -> HeadlessRenderer:
    return HeadlessRenderer(sfle_constraints=constraints(),
                            engine=PythonLayoutEngine(), **options)


def test_opt_in_headless_flex_is_real_sfle_geometry_not_a_dummy_layout() -> None:
    renderer = new_renderer()
    reconciler = Reconciler(renderer)
    root = reconciler.render(
        Flex(fixed("first", 30), fixed("second", 20), direction="row",
             gap=5, width=120, height=60, align_items="flex-start")
    )
    a, b = root.children
    assert root.handle.geometry.width == 120
    assert a.handle.geometry.width == 30
    assert b.handle.geometry.x == a.handle.geometry.x + 35
    assert renderer.sfle_result is not None
    assert renderer.sfle_result.geometry_commit_error == 0.0
    assert renderer.sfle_result.generation == 1
    assert len(renderer.sfle_result.boxes) == 3
    reconciler.unmount()
    assert renderer.sfle_result is None
    assert root.handle.destroyed


def test_keyed_reorder_and_resize_reuse_native_handle_without_remount() -> None:
    renderer = new_renderer()
    reconciler = Reconciler(renderer)
    before = reconciler.render(Flex(fixed("a", 30), fixed("b", 20),
                                    width=120, height=60, gap=5,
                                    align_items="flex-start"))
    ha, hb = (child.handle for child in before.children)
    assert ha.geometry.x < hb.geometry.x

    after = reconciler.render(Flex(fixed("b", 20), fixed("a", 30),
                                   width=120, height=60, gap=10,
                                   align_items="flex-start"))
    assert after.children[0].handle is hb
    assert after.children[1].handle is ha
    assert hb.geometry.x < ha.geometry.x
    assert renderer.sfle_result.generation == 2
    renderer.set_sfle_constraints(constraints(240, 90))
    renderer.commit_layout(after)
    assert renderer.sfle_result.generation == 4
    assert ha.destroyed is False and hb.destroyed is False
    reconciler.unmount()


def test_function_component_renders_without_phantom_box() -> None:
    @component
    def Child():
        return Flex(width=30, height=10, flex_basis=30, flex_shrink=0, key="inner")

    renderer = new_renderer()
    reconciler = Reconciler(renderer)
    root = reconciler.render(Flex(Child(key="child"), width=100, height=40))
    assert len(renderer.sfle_result.boxes) == 2
    assert root.children[0].handle is None
    assert root.children[0].children[0].handle.geometry.width == 30
    reconciler.unmount()


def test_hook_updates_commit_new_geometry_without_remounting_widgets() -> None:
    captured = []

    @component
    def Counter():
        value, set_value = use_state(0)
        captured.append(set_value)
        return Flex(Flex(key="stable", width=20 + value * 5, height=10,
                         flex_basis=20 + value * 5, flex_shrink=0),
                    width=100, height=40)

    renderer = new_renderer()
    reconciler = Reconciler(renderer)
    root = reconciler.render(Counter())
    handle = root.children[0].children[0].handle
    assert handle.geometry.width == 20
    captured[-1](2)
    renderer.flush()
    assert root.children[0].children[0].handle is handle
    assert handle.geometry.width == 30
    assert renderer.sfle_result.generation == 2
    reconciler.unmount()


def test_text_intrinsic_dimensions_must_be_host_supplied() -> None:
    callback_calls = []

    def measure(node):
        callback_calls.append(node.type)
        if node.type == "Text":
            return IntrinsicSizes(15, 15, 10, 10, 15, 10)
        return None

    renderer = new_renderer(measure_intrinsic=measure)
    reconciler = Reconciler(renderer)
    root = reconciler.render(Flex(Text("Hello", key="txt"), width=100, height=40))
    assert "Text" in callback_calls
    assert root.children[0].handle.geometry is not None
    assert renderer.sfle_result is not None
    reconciler.unmount()


def test_bad_engine_generation_does_not_commit_any_rectangles() -> None:
    class WrongGeneration:
        def compute(self, request):
            valid = PythonLayoutEngine().compute(request)
            return LayoutResult(1, request.generation + 1, valid.boxes)

    renderer = HeadlessRenderer(sfle_constraints=constraints(), engine=WrongGeneration())
    reconciler = Reconciler(renderer)
    with pytest.raises(SFLEError) as error:
        reconciler.render(Flex(fixed("a"), width=100, height=40))
    assert error.value.code is DiagnosticCode.INVALID_SNAPSHOT
    assert renderer.sfle_result is None
    assert reconciler.root.handle.geometry is None
    assert reconciler.root.children[0].handle.geometry is None
    reconciler.unmount()


def test_absent_opt_in_is_still_fail_closed_for_g1_clients() -> None:
    renderer = HeadlessRenderer()
    with pytest.raises(RendererCapabilityError, match="F3-G2 SFLE geometry"):
        Reconciler(renderer).render(Flex(width=100, height=40))


def test_opted_in_legacy_rows_still_reject_competing_layout_authority() -> None:
    from psx import Row
    renderer = new_renderer()
    with pytest.raises(RendererCapabilityError, match="Legacy Row/Column"):
        Reconciler(renderer).render(Flex(Row(Text("test")), width=100, height=40))


def test_owner_thread_is_required_for_headless_commit() -> None:
    import threading

    renderer = new_renderer()
    reconciler = Reconciler(renderer)
    root = reconciler.render(Flex(fixed("a"), width=100, height=40))
    errors = []

    def off_thread():
        try:
            renderer.commit_layout(root)
        except SFLEError as error:
            errors.append(error)

    thread = threading.Thread(target=off_thread)
    thread.start()
    thread.join()
    assert len(errors) == 1
    assert errors[0].code is DiagnosticCode.UNSUPPORTED_MEASUREMENT
    assert renderer.sfle_result.generation == 1
    reconciler.unmount()


def test_button_lifecycle_operations_use_real_headless_observations() -> None:
    """Exercise Button operations through the reconciler, not fabricated oracle data."""
    from psx.sfle.f3_g2_oracles import Observation, ORACLES

    calls: list[str] = []

    def first() -> None:
        calls.append("first")

    def second() -> None:
        calls.append("second")

    def observe(handle, *, mounted=True, order=(), callback=None, events=()):
        rect = handle.geometry
        return Observation(
            native_identity=id(handle), mounted=mounted,
            rect=(rect.x, rect.y, rect.width, rect.height) if rect else None,
            state=handle.props.get("label"), order=order,
            events=events, callback_identity=callback,
            disposed=handle.destroyed,
        )

    renderer = new_renderer()
    reconciler = Reconciler(renderer)
    # Explicit dimensions make intrinsic host measurement unnecessary.
    root = reconciler.render(Flex(
        Button("First", key="action", layout_width="40px",
               layout_height="20px", on_click=first),
        Flex(key="peer", width=20, height=20),
        width=120, height=60, gap=5,
    ))
    button = root.children[0].handle
    peer = root.children[1].handle
    created = observe(button)
    ORACLES["create"](None, created)
    assert button in root.handle.children
    assert not button.destroyed

    old_event_slot = button.events["on_click"]
    old_event_slot.invoke()
    assert calls == ["first"]

    updated_root = reconciler.render(Flex(
        Flex(key="peer", width=20, height=20),
        Button("Updated", key="action", layout_width="40px",
               layout_height="20px", on_click=second),
        width=120, height=60, gap=5,
    ))
    assert updated_root is root
    assert root.children[1].handle is button
    assert root.children[0].handle is peer
    assert button.events["on_click"] is old_event_slot

    updated = observe(button)
    ORACLES["update"](created, updated)
    assert button.props["label"] == "Updated"

    reordered = observe(
        button, order=tuple(child.type for child in root.handle.children),
    )
    previous_order = Observation(
        native_identity=created.native_identity, mounted=True,
        rect=created.rect, state=created.state, order=("Button", "Flex"),
    )
    ORACLES["reorder"](previous_order, reordered)
    assert reordered.order == ("Flex", "Button")

    old_event_slot.invoke()
    assert calls == ["first", "second"]
    rebound = observe(button, callback=id(second), events=(id(second),))
    before_rebind = observe(button, callback=id(first))
    ORACLES["event_rebind"](before_rebind, rebound)
    assert len([op for op in renderer.operations
                if op[0] == "bind_event" and op[1] is button]) == 1

    before_unmount = observe(button)
    reconciler.unmount()
    after_unmount = observe(button, mounted=False)
    ORACLES["unmount"](before_unmount, after_unmount)
    assert "on_click" not in button.events
    old_event_slot.invoke()
    assert calls == ["first", "second"]
    assert len([op for op in renderer.operations
                if op[0] == "destroy" and op[1] is button]) == 1


def test_all_supported_headless_components_reconcile_without_remount() -> None:
    """Exercise Flex, Text and Button independently across all lifecycle stages."""
    from psx.sfle.f3_g2_oracles import Observation, ORACLES
    from psx.sfle.f3_g2_matrix import HEADLESS_PORTED

    def measure(node):
        if node.type == "Text":
            return IntrinsicSizes(10, 10, 10, 10, 10, 10)
        return None

    factories = {
        "Flex": lambda width: Flex(
            Text("Child", layout_width="20px", layout_height="10px"),
            width=f"{width}px", height="24px", key="case",
        ),
        "Text": lambda width: Text(
            "Content", key="case", layout_width=f"{width}px",
            layout_height="24px", flex_basis=f"{width}px", flex_shrink=0,
        ),
        "Button": lambda width: Button(
            "Content", key="case", layout_width=f"{width}px",
            layout_height="24px", flex_basis=f"{width}px", flex_shrink=0,
        ),
    }
    assert set(factories) == HEADLESS_PORTED
    for name in sorted(HEADLESS_PORTED):
        renderer = new_renderer(measure_intrinsic=measure)
        reconciler = Reconciler(renderer)
        def view(width, reverse=False):
            child = factories[name](width)
            peer = Flex(key="peer", width="20px", height="24px",
                        flex_basis="20px", flex_shrink=0)
            return Flex(*( (peer, child) if reverse else (child, peer) ),
                        width=160, height=60, gap=8,
                        align_items="flex-start")

        before_root = reconciler.render(view(40))
        old = before_root.children[0]
        handle = old.handle
        def observe(mounted=True, order=()):
            geometry = handle.geometry
            return Observation(
                native_identity=id(handle), mounted=mounted,
                rect=(geometry.x, geometry.y, geometry.width, geometry.height)
                if geometry is not None else None,
                state=geometry.width if geometry is not None else None,
                order=order, disposed=handle.destroyed,
            )
        before = observe()
        ORACLES["create"](None, before)
        assert handle.geometry.width == 40, name
        updated_root = reconciler.render(view(60, reverse=True))
        assert updated_root.children[1] is old
        assert old.handle is handle
        after = observe()
        ORACLES["update"](before, after)
        assert handle.geometry.width == 60, name
        ORACLES["reorder"](
            observe(order=("case", "peer")),
            observe(order=("peer", "case")),
        )
        assert updated_root.handle.children[1] is handle
        # Deliberately bypass constructor validation to test transactional
        # rejection at the reconciliation boundary for every host family.
        from dataclasses import replace
        from types import MappingProxyType
        candidate = view(60, reverse=True)
        original = candidate.children[1]
        corrupted = replace(original, props=MappingProxyType({
            **dict(original.props), "on_invalid": 1,
        }))
        forged = replace(candidate, children=(candidate.children[0], corrupted))
        baseline = observe()
        with pytest.raises(TypeError, match="must be callable"):
            reconciler.render(forged)
        assert updated_root.children[1] is old
        assert old.handle is handle
        assert observe().rect == baseline.rect
        assert observe().state == baseline.state
        ORACLES["rollback"](baseline, replace(observe(), mutation_failed=True))
        prior = observe()
        reconciler.unmount()
        ORACLES["unmount"](prior, observe(mounted=False))
        assert handle.destroyed, name


def test_failed_headless_component_update_keeps_last_committed_node() -> None:
    """A rejected native update must not poison the next reconciliation delta."""
    from dataclasses import replace
    from types import MappingProxyType

    renderer = new_renderer()
    reconciler = Reconciler(renderer)
    root = reconciler.render(Flex(
        Button("Original", key="button", layout_width="70px",
               layout_height="24px", on_click=lambda: None),
        width=120, height=60,
    ))
    child = root.children[0]
    handle = child.handle
    previous = child.node
    previous_rect = handle.geometry
    callback_slot = child.event_slots["on_click"][0]

    invalid = replace(previous, props=MappingProxyType({
        **dict(previous.props), "label": "Mutated", "font_size": -1,
    }))
    with pytest.raises(RendererCapabilityError):
        reconciler.render(Flex(invalid, width=120, height=60))
    assert child.node is previous
    assert handle.props["label"] == "Original"
    assert handle.geometry == previous_rect
    assert child.event_slots["on_click"][0] is callback_slot

    rendered = reconciler.render(Flex(
        Button("Recovered", key="button", layout_width="70px",
               layout_height="24px", on_click=lambda: None),
        width=120, height=60,
    ))
    assert rendered.children[0].handle is handle
    assert handle.props["label"] == "Recovered"
    reconciler.unmount()


@pytest.mark.parametrize("reason", ("content", "font", "theme", "resource", "dpi", "viewport"))
def test_c5_explicit_invalidation_remeasures_without_remount(reason: str) -> None:
    """C5 observable Headless remeasurement, not merely a queued callback."""
    from psx.sfle.f3_g2_oracles import Observation, ORACLES

    calls = []
    measurement = {"width": 20}

    def measure(node):
        if node.type == "Text":
            calls.append(measurement["width"])
            return IntrinsicSizes(
                measurement["width"], measurement["width"], 16, 16,
                measurement["width"], 16,
            )
        return None

    renderer = new_renderer(measure_intrinsic=measure)
    reconciler = Reconciler(renderer)
    root = reconciler.render(Flex(
        Text("Measured", key="content", layout_width="50px", layout_height="16px"),
        width=120, height=60, align_items="flex-start",
    ))
    handle = root.children[0].handle
    original_width = handle.geometry.width
    initial_generation = renderer.sfle_result.generation
    original_calls = len(calls)
    assert original_calls > 0
    measurement["width"] = 38
    renderer.request_sfle_invalidation(reason)
    renderer.request_sfle_invalidation(reason)
    assert renderer._sfle_measurement_invalidations.pending == {reason}
    renderer.flush()
    assert root.children[0].handle is handle
    assert not handle.destroyed
    assert renderer.sfle_result.generation == initial_generation + 1
    assert len(calls) > original_calls
    assert renderer._sfle_measurement_invalidations.pending == set()
    assert renderer._sfle_measurement_invalidations.committed_epoch > 0
    assert handle.geometry.width == original_width  # Fixed CSS width remains authoritative.
    before = Observation(
        id(handle), True, (0, 0, original_width, 16),
        revision=initial_generation, remeasure_count=original_calls,
    )
    after = Observation(
        id(handle), True, (0, 0, handle.geometry.width, 16),
        revision=renderer.sfle_result.generation, remeasure_count=len(calls),
    )
    ORACLES["invalidation"](before, after)
    reconciler.unmount()


def test_c5_stale_remeasurement_is_canceled_after_unmount() -> None:
    calls = []
    def measure(node):
        if node.type == "Text":
            calls.append(node)
            return IntrinsicSizes(15, 15, 16, 16, 15, 16)
        return None
    renderer = new_renderer(measure_intrinsic=measure)
    reconciler = Reconciler(renderer)
    root = reconciler.render(Flex(
        Text("Data", layout_width="50px", layout_height="16px"), width=120, height=60, align_items="flex-start",
    ))
    before = len(calls)
    renderer.request_sfle_invalidation("resource")
    reconciler.unmount()
    renderer.flush()
    assert len(calls) == before
    assert renderer.sfle_result is None
    assert root.handle.destroyed
    assert not renderer._sfle_measurement_invalidations.pending


def test_c5_invalidation_rejects_unrecognized_reasons() -> None:
    renderer = new_renderer()
    with pytest.raises(ValueError, match="Unsupported SFLE measurement invalidation"):
        renderer.request_sfle_invalidation("unknown")
