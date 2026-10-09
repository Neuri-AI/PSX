"""Qyro Kivy window authored as one declarative PSX component."""

import sys

from kivy.app import App
from kivy.core.window import Window
from qyro import ApplicationContext

from psx import psx
from psx.integrations.qyro import PSXComponent
from psx.integrations.pydux import use_dispatch, use_selector

from pydux import configure_store, create_slice


counter_slice = create_slice(
    name="counter",
    initial_state={"count": 0},
    reducers={
        "increment": lambda state, action: state.update(
            count=state["count"] + 1
        ),
        "decrement": lambda state, action: state.update(
            count=state["count"] - 1
        ),
    },
)

payload_slice = create_slice(
    name="payload",
    initial_state={"value": 0},
    reducers={
        "set": lambda state, action: state.update(
            value=action.payload
        ),
    },
)

store = configure_store(
    {
        "counter": counter_slice,
        "payload": payload_slice,
    },
    devtools=True,
)


class PsxQyroKivyDemo(PSXComponent, App, ApplicationContext):

    def component_will_mount(self) -> None:
        Window.size = (640, 480)
        Window.minimum_width = 640
        Window.minimum_height = 480

    def render(self):
        count = use_selector(lambda state: state["counter"]["count"])
        payload = use_selector(lambda state: state["payload"]["value"])
        dispatch = use_dispatch()

        def increment() -> None:
            dispatch(counter_slice.actions.increment())

        def decrement() -> None:
            dispatch(counter_slice.actions.decrement())

        def update_payload() -> None:
            dispatch(payload_slice.actions.set(count))

        return psx("""
            <Column padding={50} spacing={12}>
                <Text>Hello, World!</Text>
                <Text>Counter: {count}</Text>
                <Text>Payload: {payload}</Text>
                <Row spacing={12}>
                    <Button on_click={increment}>Increment</Button>
                    <Button on_click={decrement}>Decrement</Button>
                </Row>
                <Button on_click={update_payload}>Copy counter to payload</Button>
            </Column>
        """)


if __name__ == "__main__":
    sys.exit(PsxQyroKivyDemo().run())
