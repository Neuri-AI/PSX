"""Qyro Kivy window authored as one declarative PSX component."""

import sys

from kivy.app import App
from kivy.core.window import Window
from qyro import ApplicationContext

from psx import psx, use_state
from psx.integrations.qyro import PSXComponent


class PsxQyroKivyDemo(PSXComponent, App, ApplicationContext):

    def component_will_mount(self) -> None:
        Window.size = (640, 480)
        Window.minimum_width = 640
        Window.minimum_height = 480

    def render(self):
        count, set_count = use_state(0)

        def increment() -> None:
            set_count(lambda value: value + 1)

        return psx("""
            <Column padding={32} spacing={10}>
                <Text>Qyro + PSX + Kivy</Text>
                <Text>App Title: {self.window_title}</Text>
                <Text>Platform: {self.platform.value}</Text>
                <Text>Frozen: {self.is_frozen}</Text>
                <Text>Count: {count}</Text>
                <Button on_click={increment}>Increment</Button>
            </Column>
        """)


if __name__ == "__main__":
    sys.exit(PsxQyroKivyDemo().run())
