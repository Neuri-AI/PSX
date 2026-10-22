"""State payload lifetime checks for component teardown."""
import gc
import weakref
from psx import Text, component, use_state
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer


def test_retained_setter_does_not_hold_disposed_state_payload():
    class Payload:
        pass

    value = Payload()
    reference = weakref.ref(value)
    captured = {}

    @component
    def Item():
        current, set_current = use_state(value)
        captured["setter"] = set_current
        return Text("item")

    reconciler = Reconciler(HeadlessRenderer())
    reconciler.render(Item())
    del value
    assert reference() is not None
    reconciler.unmount()
    gc.collect()
    assert reference() is None
    captured["setter"](Payload())
    assert reconciler.root is None
