"""Functional behavior and cleanup tests for the real task-board example."""
import unittest

from app import create_app


class TaskBoardTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.root = self.app.mount()

    def tearDown(self):
        self.app.unmount()

    def test_initial_state(self):
        self.assertEqual(self.root.children[1].props["value"], "Remaining: 3")
        self.assertEqual(len(self.root.children), 6)

    def test_toggle_updates_summary_and_row(self):
        self.root.children[2].children[1].props["on_click"]()
        self.app.renderer.flush()
        self.assertEqual(self.root.children[1].props["value"], "Remaining: 2")
        self.assertTrue(self.root.children[2].children[0].props["value"].startswith("[x]"))

    def test_clear_removes_completed_row(self):
        self.root.children[2].children[1].props["on_click"]()
        self.app.renderer.flush()
        self.root.children[-1].props["on_click"]()
        self.app.renderer.flush()
        self.assertEqual(len(self.root.children), 5)
        self.assertEqual(self.root.children[1].props["value"], "Remaining: 2")
        self.assertIn("Run the behavior tests", self.root.children[2].children[0].props["value"])


if __name__ == "__main__":
    unittest.main()
