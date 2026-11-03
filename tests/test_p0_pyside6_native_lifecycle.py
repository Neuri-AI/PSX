"""P0 C07: actual PySide6 QObject lifetime after exceptional teardown.

CI: QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_p0_pyside6_native_lifecycle.py
Requires PySide6 and an offscreen-capable runner. Does not measure RSS.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent
from shiboken6 import isValid

from psx import Button, Text, component, use_effect
from psx.core.reconcile import Reconciler
from psx.renderers.qt.pyside import PySide6Renderer


class NativeTeardownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.renderer = PySide6Renderer(argv=["p0-native-lifetime"])

    def setUp(self) -> None:
        self.reconciler = Reconciler(self.renderer)

    def tearDown(self) -> None:
        # If an assertion fails while mounted, do not leak the test widget.
        self.reconciler.unmount()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.renderer.application.processEvents()

    def _drain_deferred_deletes(self) -> None:
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.renderer.application.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_hook_failure_still_deletes_owned_qwidget(self) -> None:
        cleanup_calls: list[str] = []

        @component
        def Screen():
            def effect():
                def cleanup():
                    cleanup_calls.append("effect cleanup")
                    raise RuntimeError("injected effect cleanup")
                return cleanup

            use_effect(effect, [])
            return Button("Close", on_click=lambda: None)

        mounted = self.reconciler.render(Screen())
        button = mounted.children[0].handle.widget
        self.assertTrue(isValid(button))

        with self.assertRaisesRegex(RuntimeError, "injected effect cleanup"):
            self.reconciler.unmount()
        self._drain_deferred_deletes()

        self.assertEqual(cleanup_calls, ["effect cleanup"])
        self.assertIsNone(self.reconciler.root)
        self.assertFalse(isValid(button))

    def test_repeated_mount_unmount_releases_qobjects(self) -> None:
        for index in range(50):
            handle = self.reconciler.render(Text(f"iteration-{index}")).handle
            widget = handle.widget
            self.reconciler.unmount()
            self._drain_deferred_deletes()
            self.assertFalse(isValid(widget), f"iteration {index} retained QWidget")

    def test_event_connection_is_inert_after_unmount(self) -> None:
        callbacks: list[str] = []
        mounted = self.reconciler.render(
            Button("Save", on_click=lambda: callbacks.append("clicked"))
        )
        widget = mounted.handle.widget
        slot = mounted.event_slots["on_click"][0]
        widget.click()
        self.assertEqual(callbacks, ["clicked"])
        self.reconciler.unmount()
        self.assertIsNone(slot.invoke())
        self._drain_deferred_deletes()
        self.assertFalse(isValid(widget))


if __name__ == "__main__":
    unittest.main()
