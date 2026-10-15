"""Executable behavior checks for the beginner examples."""
import unittest

from psx import App
from counter import Counter
from hello_world import Hello


class BeginnerExamplesTests(unittest.TestCase):
    def test_hello_world(self):
        app = App(Hello(), renderer="headless")
        try:
            node = app.mount()
            self.assertEqual(node.type, "Flex")
            self.assertEqual(node.children[0].props["value"], "Hello, Velto!")
        finally:
            app.unmount()

    def test_counter_increments_without_replacing_root(self):
        app = App(Counter(), renderer="headless")
        try:
            root = app.mount()
            self.assertEqual(root.children[0].props["value"], "Count: 0")
            root.children[1].props["on_click"]()
            app.renderer.flush()
            self.assertEqual(root.children[0].props["value"], "Count: 1")
        finally:
            app.unmount()


if __name__ == "__main__":
    unittest.main()
