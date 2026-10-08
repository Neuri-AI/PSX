import sys
import tkinter as tk
from qyro import ApplicationContext
from qyro import ApplicationContext
from psx import psx, use_state, use_effect
from psx.integrations.qyro import PSXComponent


class QyroTkinterPsxDemo(tk.Tk, PSXComponent, ApplicationContext):

    def component_will_mount(self):
        self.geometry("640x480")
        self.minsize(640, 480)

    def render(self):
        count, set_count = use_state(0)
        use_effect(lambda: print(f"Count changed to {count}"), [count])

        def increment():
            set_count(lambda value: value + 1)

        def decrement():
            set_count(lambda value: value - 1)

        return psx("""
            <Column padding={32} spacing={10}>
                <Text>Qyro + PSX + Tkinter</Text>
                <Text>App Title: {self.window_title}</Text>
                <Text>Platform: {self.platform.value}</Text>
                <Text>Frozen: {self.is_frozen}</Text>
                <Text>Count: {count}</Text>
                <Button on_click={increment}>Increment</Button>
                <Button on_click={decrement}>Decrement</Button>
            </Column>
        """)



if __name__ == "__main__":
    window = QyroTkinterPsxDemo()
    sys.exit(window.run())

