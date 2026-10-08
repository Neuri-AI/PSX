"""Generated with ``qyro init --binding Tkinter`` and adapted for PSX M7."""

import sys
import tkinter as tk
from qyro import ApplicationContext
from psx import psx
from psx.integrations.qyro import PSXComponent
from psx.integrations.pydux import use_dispatch, use_selector
from store import store, counter_slice, payload_slice



class PsxQyroTkinterDemo(tk.Tk, PSXComponent, ApplicationContext):
    def component_will_mount(self) -> None:
        self.geometry("640x480")
        self.minsize(640, 480)

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
    window = PsxQyroTkinterDemo()
    sys.exit(window.run())
