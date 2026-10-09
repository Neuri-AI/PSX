
from psx.core.vnode import Input
from psx.renderers.headless import HeadlessRenderer


def test_input_headless_lifecycle():
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
    handle = renderer.create(node, parent=None)

    assert handle.type == "Input"
    assert handle.props["value"] == "hola"
    assert handle.props["placeholder"] == "Nombre"

    # Evento de usuario simulado
    handle.events["on_change"].invoke("mundo")
    assert received == ["mundo"]

    handle.events["on_submit"].invoke()
    assert submitted == [True]

    # Update programático NO dispara on_change
    renderer.update(handle, {"value": "otro"}, frozenset())
    assert received == ["mundo"]           # sin cambios
    assert handle.props["value"] == "otro"

    # Mismo handle (misma identidad) tras update
    renderer.update(handle, {"placeholder": "X"}, frozenset())
    assert handle.props["placeholder"] == "X"

    # Unmount
    renderer.destroy(handle)
    assert handle.destroyed is True