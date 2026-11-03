
from psx.core.vnode import Input
from psx.renderers.headless import HeadlessRenderer


from psx.core.reconcile import Reconciler
from psx.core.vnode import Input
from psx.renderers.headless import HeadlessRenderer


def test_input_headless_lifecycle() -> None:
    received: list[str] = []
    submitted: list[bool] = []

    node = Input(
        value="hola",
        placeholder="Nombre",
        on_change=received.append,
        on_submit=lambda: submitted.append(True),
        key="inp",
    )
    renderer = HeadlessRenderer()
    reconciler = Reconciler(renderer)

    # Mount through the reconciler to register declarative events.
    mounted = reconciler.render(node)
    handle = mounted.native_handle()

    assert handle.type == "Input"
    assert handle.props["value"] == "hola"
    assert handle.props["placeholder"] == "Nombre"

    # Simulate user interaction.
    handle.events["on_change"].invoke("mundo")
    assert received == ["mundo"]

    handle.events["on_submit"].invoke()
    assert submitted == [True]

    # Programmatic updates must not trigger on_change.
    updated = Input(
        value="otro",
        placeholder="Nombre",
        on_change=received.append,
        on_submit=lambda: submitted.append(True),
        key="inp",
    )

    updated_mount = reconciler.render(updated)

    assert updated_mount.native_handle() is handle
    assert handle.props["value"] == "otro"
    assert received == ["mundo"]

    # Updating another property preserves native handle identity.
    updated_again = Input(
        value="otro",
        placeholder="X",
        on_change=received.append,
        on_submit=lambda: submitted.append(True),
        key="inp",
    )

    final_mount = reconciler.render(updated_again)

    assert final_mount.native_handle() is handle
    assert handle.props["placeholder"] == "X"

    # Unmount must destroy the handle and unregister its events.
    reconciler.unmount()

    assert handle.destroyed is True
    assert handle.events == {}