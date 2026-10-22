"""Lifecycle ownership regressions for VNodes, keyed subtrees and hooks."""
import gc
import weakref

import pytest

from psx import Button, Flex, Text, component, use_effect, use_ref, use_state
from psx.core.reconcile import Reconciler
from benchmarks.resource_baseline import make_renderer


@pytest.mark.parametrize('engine', ('python', 'rust'))
def test_keyed_subtree_removal_releases_previous_node_payload(engine):
    class Payload:
        pass

    payload = Payload()
    reference = weakref.ref(payload)
    renderer = make_renderer(engine)
    reconciler = Reconciler(renderer)
    def create_old_node(held):
        return Flex(Button("first", key="old", on_click=lambda item=held: item), width="640px", height="480px")
    reconciler.render(create_old_node(payload))
    del payload
    gc.collect()
    assert reference() is not None
    reconciler.render(Flex(Button("second", key="new"), width="640px", height="480px"))
    renderer.operations.clear()  # The debug operation log is an explicit external observer.
    gc.collect()
    assert reference() is None
    reconciler.unmount()


@pytest.mark.parametrize('engine', ('python', 'rust'))
def test_ref_cleared_and_effect_cleanup_runs_even_when_it_raises(engine):
    refs = []
    calls = []

    @component
    def Example():
        ref = use_ref()
        refs.append(ref)
        def effect():
            calls.append("setup")
            def cleanup():
                calls.append("cleanup")
                raise RuntimeError("cleanup failed")
            return cleanup
        use_effect(effect, ())
        return Flex(Text("mounted", ref=ref), width="640px", height="480px")

    reconciler = Reconciler(make_renderer(engine))
    reconciler.render(Example())
    assert refs[0].current is not None
    with pytest.raises(RuntimeError, match="cleanup failed"):
        reconciler.unmount()
    assert refs[0].current is None
    assert calls == ["setup", "cleanup"]
    assert reconciler.root is None


@pytest.mark.parametrize('engine', ('python', 'rust'))
def test_effect_cleanup_releases_captured_payload_even_on_exception(engine):
    class Payload:
        pass

    seed = {"value": Payload()}
    reference = weakref.ref(seed["value"])
    cleanups = []

    @component
    def Example():
        def effect():
            value = seed.pop("value")
            def cleanup():
                cleanups.append("called")
                assert value is not None
                raise ValueError("effect cleanup")
            return cleanup
        use_effect(effect, ())
        return Flex(Text("effect"), width="640px", height="480px")

    reconciler = Reconciler(make_renderer(engine))
    reconciler.render(Example())
    with pytest.raises(ValueError, match="effect cleanup"):
        reconciler.unmount()
    gc.collect()
    assert reference() is None
    assert cleanups == ["called"]


@pytest.mark.parametrize("engine", ("python", "rust"))
def test_repeated_keyed_reconciliation_releases_removed_subtree_payloads(engine):
    class Payload:
        pass

    renderer = make_renderer(engine)
    reconciler = Reconciler(renderer)
    weak = []
    for index in range(12):
        payload = Payload()
        weak.append(weakref.ref(payload))
        reconciler.render(Flex(
            Button("click", key=str(index), on_click=lambda item=payload: item),
            width="640px", height="480px"))
        del payload
        renderer.operations.clear()
        gc.collect()
        assert all(ref() is None for ref in weak[:-1])
    reconciler.unmount()
    renderer.operations.clear()
    gc.collect()
    assert all(ref() is None for ref in weak)
