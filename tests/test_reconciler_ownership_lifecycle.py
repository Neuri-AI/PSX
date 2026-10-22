"""Lifecycle ownership regressions for VNodes, keyed subtrees and hooks."""
import gc
import weakref

import pytest

from psx import Text, component, use_effect, use_ref, use_state
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer


def test_keyed_subtree_removal_releases_previous_node_payload():
    class Payload:
        pass

    payload = Payload()
    reference = weakref.ref(payload)
    renderer = HeadlessRenderer()
    reconciler = Reconciler(renderer)
    reconciler.render(Text("first", key="old", on_click=lambda: payload))
    reconciler.render(Text("second", key="new"))
    # The callback above is a closure over the local payload variable.
    # Release the external owner before checking the old mounted tree.
    del payload
    gc.collect()
    assert reference() is None
    reconciler.unmount()


def test_ref_cleared_and_effect_cleanup_runs_even_when_it_raises():
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

    reconciler = Reconciler(HeadlessRenderer())
    reconciler.render(Example())
    assert refs[0].current is not None
    with pytest.raises(RuntimeError, match="cleanup failed"):
        reconciler.unmount()
    assert refs[0].current is None
    assert calls == ["setup", "cleanup"]
    assert reconciler.root is None


def test_effect_cleanup_releases_captured_payload_even_on_exception():
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

    reconciler = Reconciler(HeadlessRenderer())
    reconciler.render(Example())
    with pytest.raises(ValueError, match="effect cleanup"):
        reconciler.unmount()
    gc.collect()
    assert reference() is None
    assert cleanups == ["called"]
