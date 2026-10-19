"""Native SFLE Headless: real mounted rectangles, identity, generations and resize."""
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


def test_mounted_headless_flex_consumes_canonical_item_lengths(monkeypatch) -> None:
    from psx.sfle.lengths import Length
    from psx.sfle.native_layout_snapshot import PreparedNativeLayoutSnapshot

    observed = []
    original = PreparedNativeLayoutSnapshot.canonical_snapshot

    def record(prepared):
        snapshot = original(prepared)
        observed.append(snapshot)
        return snapshot

    monkeypatch.setattr(PreparedNativeLayoutSnapshot, "canonical_snapshot", record)
    renderer = new_renderer()
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(Flex(
            Button("Left", key="left", layout_width="40px",
                   layout_height="20px", flex_basis="40px", flex_shrink=0),
            Button("Right", key="right", layout_width="30px",
                   layout_height="20px", flex_basis="30px", flex_shrink=0),
            direction="row", gap=8, width=120, height=60,
            align_items="flex-start",
        ))
        assert observed, "Mounted Headless must consume canonical item lengths"
        style = dict(observed[-1].nodes[1].style)
        assert style["layout_width"] == Length.px(40)
        assert style["layout_height"] == Length.px(20)
        assert root.children[0].handle.geometry.width == 40
        assert root.children[0].handle.geometry.height == 20
        assert root.children[1].handle.geometry.x == 48
        assert root.children[1].handle.geometry.width == 30
        assert renderer.sfle_result.geometry_commit_error == 0.0
    finally:
        reconciler.unmount()


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


def test_canonical_width_change_reflows_sibling_without_remeasuring_unchanged_leaf() -> None:
    measured = []

    def measure(node):
        if node.type != "Text":
            return None
        measured.append(node.props["value"])
        return IntrinsicSizes(20, 20, 16, 16, 20, 16)

    renderer = new_renderer(measure_intrinsic=measure)
    renderer.set_sfle_constraints(constraints(400, 90))
    reconciler = Reconciler(renderer)

    def view(width):
        return Flex(
            Text("Alpha", key="a", layout_width=f"{width}px",
                 layout_height="20px", flex_shrink=0),
            Text("Beta", key="b", layout_width="40px",
                 layout_height="20px", flex_shrink=0),
            direction="row", width="400px", height="90px",
            gap=8, align_items="flex-start",
        )

    try:
        root = reconciler.render(view(150))
        first, second = (child.handle for child in root.children)
        assert measured == ["Alpha", "Beta"]
        assert (first.geometry.width, second.geometry.x) == (150, 158)
        generation = renderer.sfle_result.generation
        updated = reconciler.render(view(200))
        assert updated.children[0].handle is first
        assert updated.children[1].handle is second
        assert (first.geometry.width, second.geometry.x) == (200, 208)
        assert measured == ["Alpha", "Beta", "Alpha"], measured
        assert renderer.sfle_result.generation > generation
        renderer.commit_layout(updated)
        assert measured == ["Alpha", "Beta", "Alpha"]
        assert (first.geometry.width, second.geometry.x) == (200, 208)
    finally:
        reconciler.unmount()
    assert not renderer._sfle_intrinsic_cache


def test_text_color_only_skips_cinnamon_measurement_and_geometry_writes(monkeypatch) -> None:
    from psx.renderers.headless import HeadlessHandle

    class CountingEngine:
        def __init__(self):
            self.delegate = PythonLayoutEngine()
            self.calls = 0

        def compute(self, request):
            self.calls += 1
            return self.delegate.compute(request)

    engine = CountingEngine()
    measured = []
    writes = []
    original_setattr = HeadlessHandle.__setattr__

    def record(handle, name, value):
        if name == "geometry":
            writes.append((id(handle), value))
        return original_setattr(handle, name, value)

    monkeypatch.setattr(HeadlessHandle, "__setattr__", record)

    def measure(node):
        if node.type != "Text":
            return None
        measured.append(node.props["value"])
        return IntrinsicSizes(20, 20, 16, 16, 20, 16)

    renderer = HeadlessRenderer(sfle_constraints=constraints(), engine=engine,
                                measure_intrinsic=measure)
    reconciler = Reconciler(renderer)

    def view(color, width="40px"):
        return Flex(
            Text("Stable text", key="text", color=color, layout_width=width,
                 layout_height="20px"),
            direction="row", width=120, height=60, align_items="flex-start",
        )

    try:
        root = reconciler.render(view("#111111"))
        handle = root.children[0].handle
        initial_geometry = handle.geometry
        assert engine.calls == 1
        assert measured == ["Stable text"]
        writes.clear()

        updated = reconciler.render(view("#222222"))
        assert updated.children[0].handle is handle
        assert handle.props["color"] == "#222222"
        assert handle.geometry == initial_geometry
        assert engine.calls == 1, "Paint-only updates must bypass Cinnamon"
        assert measured == ["Stable text"], "Paint-only updates must not remeasure"
        assert writes == [], "Paint-only updates must not rewrite geometry"

        reconciler.render(view("#222222", width="55px"))
        assert engine.calls == 2, "Geometry changes must still run Cinnamon"
        assert handle.geometry.width == 55
        assert measured == ["Stable text", "Stable text"]

        renderer.request_sfle_invalidation("font")
        renderer.flush()
        assert engine.calls == 3, "Semantic invalidation must override paint reuse"
        assert len(measured) == 3
    finally:
        reconciler.unmount()
    assert renderer._sfle_committed_signatures is None


def test_equal_geometry_commit_does_not_write_or_trigger_resize_feedback(monkeypatch) -> None:
    from psx.renderers.headless import HeadlessHandle

    renderer = new_renderer()
    reconciler = Reconciler(renderer)
    root = reconciler.render(Flex(
        Flex(key="first", width=30, height=20),
        Flex(key="second", width=20, height=20),
        direction="row", gap=5, width=120, height=60,
    ))
    handles = tuple(child.handle for child in root.children)
    initial = tuple(handle.geometry for handle in handles)
    writes = []
    original_setattr = HeadlessHandle.__setattr__

    def record_setattr(handle, name, value):
        if name == "geometry":
            writes.append((handle, value))
        return original_setattr(handle, name, value)

    monkeypatch.setattr(HeadlessHandle, "__setattr__", record_setattr)
    try:
        renderer.commit_layout(root)
        renderer.commit_layout(root)
        assert writes == [], "Equal committed rectangles must not be rewritten"
        assert tuple(handle.geometry for handle in handles) == initial
        assert tuple(child.handle for child in root.children) == handles
        assert renderer.sfle_result.geometry_commit_error == 0.0
    finally:
        reconciler.unmount()


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


def test_absent_opt_in_is_still_fail_closed_for_flex_clients() -> None:
    renderer = HeadlessRenderer()
    with pytest.raises(RendererCapabilityError, match="Native SFLE SFLE geometry"):
        Reconciler(renderer).render(Flex(width=100, height=40))


def test_opted_in_legacy_rows_still_reject_competing_layout_authority() -> None:
    from psx.core.errors import UnknownComponentError
    from psx.core.registry import builtin_component_registry
    registry = builtin_component_registry()
    with pytest.raises(UnknownComponentError):
        registry.resolve("Row")


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
    from psx.sfle.native_operation_oracles import Observation, ORACLES

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
    from psx.sfle.native_operation_oracles import Observation, ORACLES
    from psx.sfle.native_component_matrix import HEADLESS_PORTED

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
        for reason in ("content", "font", "theme", "resource", "dpi", "viewport"):
            original_generation = renderer.sfle_result.generation
            renderer.request_sfle_invalidation(reason)
            renderer.flush()
            assert old.handle is handle, (name, reason)
            assert renderer.sfle_result.generation == original_generation + 1, (name, reason)
            assert not handle.destroyed, (name, reason)
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
def test_native_invalidation_explicit_invalidation_remeasures_without_remount(reason: str) -> None:
    """C5 observable Headless remeasurement, not merely a queued callback."""
    from psx.sfle.native_operation_oracles import Observation, ORACLES

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


def test_native_invalidation_stale_remeasurement_is_canceled_after_unmount() -> None:
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


def test_native_invalidation_invalidation_rejects_unrecognized_reasons() -> None:
    renderer = new_renderer()
    with pytest.raises(ValueError, match="Unsupported SFLE measurement invalidation"):
        renderer.request_sfle_invalidation("unknown")


def test_native_invalidation_headless_intrinsic_cache_skips_unaffected_siblings() -> None:
    measured = []

    def measure(node):
        if node.type == "Text":
            measured.append(node.props.get("text"))
            return IntrinsicSizes(20, 20, 14, 14, 20, 14)
        return None

    renderer = new_renderer(measure_intrinsic=measure)
    reconciler = Reconciler(renderer)

    def view(first="Alpha"):
        return Flex(
            Text(first, key="a", layout_width="40px", layout_height="18px"),
            Text("Beta", key="b", layout_width="40px", layout_height="18px"),
            width=120, height=60, align_items="flex-start",
        )

    root = reconciler.render(view())
    assert len(measured) == 2
    original_handles = [child.handle for child in root.children]

    renderer.commit_layout(root)
    assert len(measured) == 2, "Unchanged measurements must be reused"
    new_root = reconciler.render(view("Changed"))
    assert new_root is root
    assert len(measured) == 3, measured
    assert [child.handle for child in root.children] == original_handles

    renderer.request_sfle_invalidation("font")
    renderer.flush()
    assert len(measured) == 5, measured
    assert all(not handle.destroyed for handle in original_handles)
    reconciler.unmount()
    assert not renderer._sfle_intrinsic_cache


def test_native_invalidation_invalidated_during_measurement_rejects_stale_geometry_and_recovers() -> None:
    """A semantic event raised by a host measurement cannot commit old boxes."""
    from psx.sfle.errors import SFLEError

    source = {"width": 20, "mutate": False}
    renderer_holder = {}

    def measure(node):
        if node.type == "Text":
            if source["mutate"]:
                source["mutate"] = False
                renderer_holder["renderer"].request_sfle_invalidation("resource")
            return IntrinsicSizes(source["width"], source["width"], 14, 14,
                                  source["width"], 14)
        return None

    renderer = new_renderer(measure_intrinsic=measure)
    renderer_holder["renderer"] = renderer
    reconciler = Reconciler(renderer)
    root = reconciler.render(Flex(
        Text("Measured", layout_width="40px", layout_height="20px"),
        width=120, height=60,
    ))
    widget = root.children[0].handle
    previous = widget.geometry
    previous_generation = renderer.sfle_result.generation
    source["width"] = 35
    source["mutate"] = True
    renderer._sfle_measurement_invalidations.request("content")
    with pytest.raises(SFLEError, match="Stale semantic invalidation"):
        renderer.commit_layout(root)
    assert widget.geometry == previous
    assert renderer.sfle_result.generation == previous_generation
    assert renderer._sfle_measurement_invalidations.needs_commit()

    renderer.commit_layout(root)
    assert renderer.sfle_result.generation > previous_generation
    assert not renderer._sfle_measurement_invalidations.needs_commit()
    assert root.children[0].handle is widget
    reconciler.unmount()


def test_native_invalidation_failed_queued_measurement_retains_request_until_successful_retry() -> None:
    from psx.sfle.errors import SFLEError

    fail = {"active": False}
    def measure(node):
        if node.type == "Text":
            if fail["active"]:
                raise RuntimeError("transient native resource failure")
            return IntrinsicSizes(12, 12, 14, 14, 12, 14)
        return None

    renderer = new_renderer(measure_intrinsic=measure)
    reconciler = Reconciler(renderer)
    root = reconciler.render(Flex(
        Text("Retry", layout_width="40px", layout_height="20px"),
        width=120, height=60,
    ))
    native = root.children[0].handle
    initial = native.geometry
    fail["active"] = True
    renderer.request_sfle_invalidation("resource")
    with pytest.raises(RuntimeError, match="transient native resource failure"):
        renderer.flush()
    assert renderer._sfle_measurement_invalidations.needs_commit()
    assert native.geometry == initial
    assert renderer._sfle_last_invalidation_error
    fail["active"] = False
    renderer.request_sfle_invalidation("resource")
    renderer.flush()
    assert not renderer._sfle_measurement_invalidations.needs_commit()
    assert not renderer._sfle_last_invalidation_error
    assert root.children[0].handle is native
    reconciler.unmount()


def test_native_invalidation_targeted_invalidations_remeasure_only_dirty_native_handles() -> None:
    """Resource events should not remeasure independent mounted siblings."""
    calls: list[str] = []
    widths = {"Alpha": 20, "Beta": 25, "Gamma": 30}

    def measure(node):
        if node.type != "Text":
            return None
        label = node.props["value"]
        calls.append(label)
        width = widths[label]
        return IntrinsicSizes(width, width, 14, 14, width, 14)

    renderer = new_renderer(measure_intrinsic=measure)
    reconciler = Reconciler(renderer)
    root = reconciler.render(Flex(
        Text("Alpha", key="a", layout_width="40px", layout_height="18px"),
        Text("Beta", key="b", layout_width="40px", layout_height="18px"),
        Text("Gamma", key="c", layout_width="40px", layout_height="18px"),
        width=120, height=60, align_items="flex-start",
    ))
    handles = tuple(child.handle for child in root.children)
    assert calls == ["Alpha", "Beta", "Gamma"]
    baseline = tuple(handle.geometry for handle in handles)
    calls.clear()

    renderer.request_sfle_invalidation("resource", widget_id=id(handles[1]))
    renderer.request_sfle_invalidation("content", widget_id=id(handles[1]))
    renderer.flush()
    assert calls == ["Beta"], calls
    assert tuple(child.handle for child in root.children) == handles
    assert tuple(handle.geometry for handle in handles) == baseline
    assert not renderer._sfle_measurement_invalidations.needs_commit()

    calls.clear()
    renderer.request_sfle_invalidation("dpi")
    renderer.flush()
    assert calls == ["Alpha", "Beta", "Gamma"]
    reconciler.unmount()


def test_native_invalidation_multi_trigger_invalidation_during_measurement_preserves_cache_and_retries() -> None:
    """An invalidation racing a provisional measure cannot publish its cache."""
    calls: list[str] = []
    race = {"enabled": False, "fail": False}
    holder: dict[str, HeadlessRenderer] = {}

    def measure(node):
        if node.type != "Text":
            return None
        label = node.props["value"]
        calls.append(label)
        if label == "Beta" and race["enabled"]:
            race["enabled"] = False
            state = holder["renderer"]._sfle_measurement_invalidations
            state.request("font", widget_id=id(handles[0]))
            state.request("dpi")
        if label == "Beta" and race["fail"]:
            raise RuntimeError("native measurement temporarily unavailable")
        return IntrinsicSizes(22, 22, 14, 14, 22, 14)

    renderer = new_renderer(measure_intrinsic=measure)
    holder["renderer"] = renderer
    reconciler = Reconciler(renderer)
    root = reconciler.render(Flex(
        Text("Alpha", key="a", layout_width="40px", layout_height="18px"),
        Text("Beta", key="b", layout_width="40px", layout_height="18px"),
        width=120, height=60, align_items="flex-start",
    ))
    handles = tuple(child.handle for child in root.children)
    baseline = tuple(handle.geometry for handle in handles)
    previous_cache = dict(renderer._sfle_intrinsic_cache)
    previous_result = renderer.sfle_result
    calls.clear()

    race["enabled"] = True
    renderer._sfle_measurement_invalidations.request(
        "resource", widget_id=id(handles[1]),
    )
    with pytest.raises(SFLEError, match="Stale semantic invalidation"):
        renderer.commit_layout(root)
    assert calls == ["Beta"]
    assert renderer._sfle_intrinsic_cache == previous_cache
    assert renderer.sfle_result is previous_result
    assert tuple(handle.geometry for handle in handles) == baseline
    assert renderer._sfle_measurement_invalidations.pending == {
        "resource", "font", "dpi",
    }

    race["fail"] = True
    with pytest.raises(RuntimeError, match="temporarily unavailable"):
        renderer.commit_layout(root)
    assert renderer._sfle_intrinsic_cache == previous_cache
    assert renderer.sfle_result is previous_result
    assert renderer._sfle_measurement_invalidations.needs_commit()

    race["fail"] = False
    calls.clear()
    renderer.commit_layout(root)
    assert calls == ["Alpha", "Beta"]
    assert not renderer._sfle_measurement_invalidations.needs_commit()
    assert renderer.sfle_result.generation > previous_result.generation
    assert tuple(child.handle for child in root.children) == handles
    assert tuple(handle.geometry for handle in handles) == baseline
    reconciler.unmount()


def test_native_invalidation_invalidation_during_native_readback_rolls_back_and_recovers(monkeypatch) -> None:
    """A resource event during readback must not publish stale geometry."""
    import psx.sfle.headless_layout_bridge as bridge

    renderer = new_renderer()
    reconciler = Reconciler(renderer)
    root = reconciler.render(Flex(
        Flex(key="first", width=30, height=20),
        Flex(key="second", width=20, height=20),
        width=120, height=60, gap=5,
    ))
    widgets = tuple(child.handle for child in root.children)
    before = tuple(widget.geometry for widget in widgets)
    published = renderer.sfle_result
    cache = dict(renderer._sfle_intrinsic_cache)
    original_ports = bridge.SFLEAdapterPorts
    injected = {"pending": True}

    def race_ports(**kwargs):
        original_read = kwargs["read_rectangles"]

        def read():
            data = original_read()
            if injected["pending"]:
                injected["pending"] = False
                renderer._sfle_measurement_invalidations.request("resource")
            return data

        kwargs["read_rectangles"] = read
        return original_ports(**kwargs)

    monkeypatch.setattr(bridge, "SFLEAdapterPorts", race_ports)
    with pytest.raises(SFLEError, match="Stale semantic invalidation during native readback"):
        renderer.commit_layout(root)
    assert tuple(widget.geometry for widget in widgets) == before
    assert renderer.sfle_result is published
    assert renderer._sfle_intrinsic_cache == cache
    assert renderer._sfle_measurement_invalidations.pending == {"resource"}
    assert tuple(child.handle for child in root.children) == widgets
    renderer.commit_layout(root)
    assert not renderer._sfle_measurement_invalidations.pending
    assert renderer.sfle_result.generation > published.generation
    assert tuple(child.handle for child in root.children) == widgets
    reconciler.unmount()


def test_native_invalidation_solver_invalidation_rejects_provisional_result_and_recovers() -> None:
    """A synchronous resource event during SFLE compute must fence native writes."""
    renderer = new_renderer()
    reconciler = Reconciler(renderer)
    root = reconciler.render(Flex(
        fixed("a", 30), fixed("b", 20), width=120, height=60, gap=5,
    ))
    widgets = tuple(child.handle for child in root.children)
    geometry_before = tuple(widget.geometry for widget in widgets)
    previous = renderer.sfle_result
    engine = renderer._sfle_engine

    class InjectDuringCompute:
        def compute(self, request):
            result = engine.compute(request)
            renderer._sfle_measurement_invalidations.request("resource")
            return result

    renderer._sfle_engine = InjectDuringCompute()
    with pytest.raises(SFLEError, match="Stale semantic invalidation before geometry"):
        renderer.commit_layout(root)
    assert tuple(widget.geometry for widget in widgets) == geometry_before
    assert renderer.sfle_result is previous
    assert renderer._sfle_measurement_invalidations.needs_commit()

    renderer._sfle_engine = engine
    renderer.commit_layout(root)
    assert not renderer._sfle_measurement_invalidations.needs_commit()
    assert renderer.sfle_result.generation > previous.generation
    assert tuple(child.handle for child in root.children) == widgets
    reconciler.unmount()


def test_unchanged_headless_commit_reuses_cinnamon_but_resize_recomputes():
    class CountingEngine:
        def __init__(self):
            self.calls = 0
            self.delegate = PythonLayoutEngine()

        def compute(self, snapshot):
            self.calls += 1
            return self.delegate.compute(snapshot)

    engine = CountingEngine()
    renderer = HeadlessRenderer(sfle_constraints=constraints(), engine=engine)
    reconciler = Reconciler(renderer)
    try:
        root = reconciler.render(Flex(
            fixed("left", 30), fixed("right", 20),
            width=120, height=60, direction="row", gap=5,
        ))
        assert engine.calls == 1
        geometry = tuple(child.handle.geometry for child in root.children)
        renderer.commit_layout(root)
        assert engine.calls == 1
        assert tuple(child.handle.geometry for child in root.children) == geometry
        assert renderer.sfle_result.generation == 2
        renderer.set_sfle_constraints(constraints(200, 60))
        renderer.commit_layout(root)
        assert engine.calls == 2
    finally:
        reconciler.unmount()
    assert renderer._sfle_prior_solver_input is None
    assert renderer._sfle_prior_solver_result is None


def test_mounted_headless_uses_incremental_sizing_for_unchanged_flex_sibling():
    class TrackingEngine(PythonLayoutEngine):
        def __init__(self):
            self.reused = []
            self.incremental_calls = 0

        def compute_incremental(self, request, **kwargs):
            self.incremental_calls += 1
            kwargs["reused_contexts"] = self.reused
            return super().compute_incremental(request, **kwargs)

    engine = TrackingEngine()
    renderer = HeadlessRenderer(sfle_constraints=constraints(300, 100), engine=engine)
    reconciler = Reconciler(renderer)

    def view(width):
        return Flex(
            Flex(fixed("nested-left", 20), key="left", width=width,
                 height=25, flex_shrink=0),
            Flex(fixed("nested-right", 20), key="right", width=50,
                 height=25, flex_shrink=0),
            direction="row", width=300, height=100, key="root",
        )

    try:
        root = reconciler.render(view(40))
        right = root.children[1].handle
        before = right.geometry
        updated = reconciler.render(view(60))
        assert engine.incremental_calls >= 1
        assert engine.reused, "Unchanged, definitely-sized Flex should reuse sizing"
        assert updated.children[1].handle is right
        assert right.geometry.x == 60
        assert right.geometry.width == before.width
    finally:
        reconciler.unmount()
