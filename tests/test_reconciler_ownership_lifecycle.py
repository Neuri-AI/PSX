"""Lifecycle ownership regressions for VNodes, keyed subtrees and hooks."""
import gc
import weakref

import pytest

from psx import Text, component, use_effect, use_ref, use_state
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
        return Text("first", key="old", on_click=lambda item=held: item)
    reconciler.render(create_old_node(payload))
    del payload
    gc.collect()
    assert reference() is not None
    reconciler.render(Text("second", key="new"))
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
        return Text("mounted", ref=ref)

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
        return Text("effect")

    reconciler = Reconciler(make_renderer(engine))
    reconciler.render(Example())
    with pytest.raises(ValueError, match="effect cleanup"):
        reconciler.unmount()
    gc.collect()
    assert reference() is None
    assert cleanups == ["called"]
