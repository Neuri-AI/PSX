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
