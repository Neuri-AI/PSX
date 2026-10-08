from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "src")

from PySide6.QtWidgets import QApplication, QMainWindow
from qyro import ApplicationContext, EngineContainer

from pydux import configure_store, create_slice

from psx import App, Button, Column, RendererConfigurationError, Text, component, use_state
from psx.integrations.pydux import use_dispatch, use_selector
from psx.core.reconcile import Reconciler
from psx.integrations.qyro import (
    PSXComponent,
    QyroProvider,
    mount_psx,
    use_container,
    use_qyro_context,
    use_resource,
    use_settings,
)
from psx.renderers.headless import HeadlessRenderer
from psx.renderers.qt.pyside6 import PySide6Renderer


class QyroIntegrationTests(unittest.TestCase):
    def _project_root(self) -> tempfile.TemporaryDirectory[str]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "settings").mkdir()
        (root / "resources" / "images").mkdir(parents=True)
        (root / "settings" / "base.json").write_text(
            json.dumps({"app_name": "PSX Qyro Test", "binding": "PySide6", "version": "1.0.0"}),
            encoding="utf-8",
        )
        (root / "resources" / "images" / "logo.txt").write_text("logo", encoding="utf-8")
        return temporary

    def test_provider_returns_the_same_real_context_and_container_and_uses_qyro_resolvers(self) -> None:
        temporary = self._project_root()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        context = ApplicationContext(framework="headless", custom_root=root, enable_sentry=False)
        expected_container = context.container
        observed: dict[str, object] = {}

        @component
        def Info():
            observed["context"] = use_qyro_context()
            observed["container"] = use_container()
            observed["settings"] = use_settings()
            observed["resource"] = use_resource("images", "logo.txt")
            return Text("ready")

        Reconciler(HeadlessRenderer()).render(QyroProvider(Info(), context=context))
        self.assertIs(observed["context"], context)
        self.assertIs(observed["container"], expected_container)
        self.assertEqual(observed["settings"]["binding"], "PySide6")
        self.assertEqual(Path(observed["resource"]).read_text(encoding="utf-8"), "logo")

    def test_renderer_selection_reads_the_public_qyro_settings_helper(self) -> None:
        with patch("qyro.load_build_settings", return_value={"binding": "PySide6"}):
            app = App(Text("configured"))
        self.assertIsInstance(app.renderer, PySide6Renderer)
        app.unmount()
        with patch("qyro.load_build_settings", return_value={}):
            with self.assertRaises(RendererConfigurationError):
                App(Text("missing"))

    def test_mount_psx_borrows_a_qt_host_and_never_destroys_it(self) -> None:
        renderer = PySide6Renderer(argv=["psx-qyro-test"])
        host = QMainWindow()
        mounted = mount_psx(host, Text("embedded"), renderer=renderer)
        self.assertIs(host.centralWidget(), mounted.widget)
        mounted.unmount()
        self.assertIsNone(host.centralWidget())
        self.assertIsInstance(host, QMainWindow)
        self.assertFalse(host.isHidden() and host.isVisible())

    def test_psx_component_uses_qyro_lifecycle_and_owns_only_its_subtree(self) -> None:
        class DeclarativeWindow(QMainWindow, PSXComponent, ApplicationContext):
            def component_will_mount(self) -> None:
                self.will_mount = True

            def render(self):
                return Column(Text("declarative"), spacing=20)

            def component_did_mount(self) -> None:
                self.did_mount = True

        window = DeclarativeWindow()
        QApplication.instance().processEvents()
        self.assertTrue(window.will_mount)
        self.assertTrue(window.did_mount)
        self.assertIsNotNone(window.centralWidget())
        self.assertIsInstance(window._psx_mount, object)
        window.unmount_psx()
        self.assertIsNone(window.centralWidget())

    def test_psx_component_class_render_supports_hooks(self) -> None:
        class HookWindow(QMainWindow, PSXComponent, ApplicationContext):
            def render(self):
                count, set_count = use_state(0)
                return Column(
                    Text(f"Count: {count}"),
                    Button("Increment", on_click=lambda: set_count(lambda value: value + 1)),
                )

        window = HookWindow()
        QApplication.instance().processEvents()
        layout = window.centralWidget().layout()
        label, button = (layout.itemAt(index).widget() for index in range(2))
        self.assertEqual(label.text(), "Count: 0")
        button.click()
        QApplication.instance().processEvents()
        self.assertEqual(label.text(), "Count: 1")
        window.unmount_psx()

    def test_psx_component_can_provide_pydux_to_a_single_class_render(self) -> None:
        counter = create_slice(
            name="counter",
            initial_state={"count": 0},
            reducers={"increment": lambda state, action: state.update(count=state["count"] + 1)},
        )
        store = configure_store({"counter": counter}, devtools=False)

        class StoreWindow(QMainWindow, PSXComponent, ApplicationContext):
            psx_store = store

            def render(self):
                count = use_selector(lambda state: state["counter"]["count"])
                dispatch = use_dispatch()
                return Column(
                    Text(f"Count: {count}"),
                    Button("Increment", on_click=lambda: dispatch(counter.actions.increment())),
                )

        window = StoreWindow()
        QApplication.instance().processEvents()
        layout = window.centralWidget().layout()
        label, button = (layout.itemAt(index).widget() for index in range(2))
        self.assertEqual(label.text(), "Count: 0")
        button.click()
        QApplication.instance().processEvents()
        self.assertEqual(label.text(), "Count: 1")
        window.unmount_psx()


if __name__ == "__main__":
    unittest.main()
