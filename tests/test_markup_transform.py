from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from psx.core.reconcile import Reconciler
from psx.core.native import NativeWidget
from psx.core.errors import MarkupSyntaxError
from psx.extensions.qt_webengine import WebView
from psx.markup.transform import transform_file, transform_source
from psx.renderers.headless import HeadlessRenderer


def _execute_transformed(source: str) -> dict[str, object]:
    namespace: dict[str, object] = {"__name__": "transformed_fixture"}
    exec(compile(source, "transformed_fixture.py", "exec"), namespace)
    return namespace


def measured_headless():
    from psx.sfle.engine import PythonLayoutEngine
    from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints
    return HeadlessRenderer(
        sfle_constraints=LayoutConstraints(AvailableSize(640, True), AvailableSize(480, True)),
        engine=PythonLayoutEngine(),
        measure_intrinsic=lambda node: IntrinsicSizes(4, 20, 8, 12, 18, 12, 8),
    )


class MarkupM4BTransformTests(unittest.TestCase):
    def test_inline_markup_resolves_state_and_event_callback_lexically(self) -> None:
        result = transform_source(
            """
from psx import Button, Flex, Text, component, psx, use_state

@component
def Counter(prefix):
    count, set_count = use_state(0)
    def increment():
        set_count(lambda previous: previous + 1)
    return psx('<Flex direction="column"><Text value={count} /><Button label="+1" on_click={increment} /></Flex>')
""",
            filename="counter_source.py",
        )
        self.assertEqual(result.transformed_calls, 1)
        self.assertIn("_psx_template_0.render_lexical", result.source)
        self.assertNotIn("return psx(", result.source)
        namespace = _execute_transformed(result.source)
        counter = namespace["Counter"]
        renderer = measured_headless()
        reconciler = Reconciler(renderer)
        root = reconciler.render(counter(prefix="Count"))
        column = root.children[0].handle
        label, button = column.children
        self.assertEqual(label.props["value"], "0")
        button.events["on_click"].invoke()
        renderer.flush()
        self.assertEqual(label.props["value"], "1")

    def test_quoted_numeric_markup_literals_need_no_lexical_scope_entry(self) -> None:
        result = transform_source(
            """
from psx import psx
def view():
    return psx('<Flex direction="column" padding="50" gap="12"><Text value="Ready" /></Flex>')
""",
            filename="numeric_markup.py",
        )
        node = _execute_transformed(result.source)["view"]()
        self.assertEqual(node.props["padding"], 50)
        self.assertEqual(node.props["gap"], 12)

    def test_builtin_textarea_tag_does_not_require_a_python_import(self) -> None:
        result = transform_source(
            """
from psx import psx
note = "draft"
def view():
    return psx('<TextArea value={note} />')
""",
            filename="textarea_builtin.py",
        )
        self.assertNotIn("'TextArea': lambda", result.source)
        node = _execute_transformed(result.source)["view"]()
        self.assertEqual(node.type, "TextArea")
        self.assertEqual(node.props["value"], "draft")

    def test_builtin_webview_tag_does_not_require_a_python_import(self) -> None:
        result = transform_source(
            """
from psx import psx
def view():
    return psx('<WebView url="https://example.test" />')
""",
            filename="webview_builtin.py",
        )
        self.assertNotIn("'WebView': lambda", result.source)

    def test_webview_width_and_height_are_sfle_layout_dimensions(self) -> None:
        declaration = NativeWidget(renderer="pyside6", factory=object)
        with patch("psx.extensions.qt_webengine._declaration", return_value=declaration):
            node = WebView(
                url="https://example.test", width="100%", height="100%", flex_grow=1,
            )
        self.assertIs(node.type, declaration)
        self.assertEqual(node.props["layout_width"], "100%")
        self.assertEqual(node.props["layout_height"], "100%")
        self.assertNotIn("width", node.props)
        self.assertNotIn("height", node.props)
        self.assertEqual(node.props["flex_grow"], 1)

    def test_closure_and_shadowing_follow_normal_python_lexical_rules(self) -> None:
        result = transform_source(
            """
from psx import Text, component, psx
value = "global"

def make(value):
    @component
    def View():
        return psx("<Text value={value} />")
    return View
""",
            filename="closure_source.py",
        )
        namespace = _execute_transformed(result.source)
        view = namespace["make"]("closure")
        renderer = HeadlessRenderer()
        root = Reconciler(renderer).render(view())
        self.assertEqual(root.children[0].handle.props["value"], "closure")

    def test_self_attributes_nested_paths_callbacks_and_rerenders_are_lexical(self) -> None:
        result = transform_source(
            """
from psx import Button, Flex, Text, component, psx, use_state

class Platform:
    def __init__(self, value):
        self.value = value

class WindowModel:
    def __init__(self):
        self.window_title = "Initial title"
        self.platform = Platform("macOS")
        self.is_frozen = False
        self.settings_opened = 0

    def open_settings(self):
        self.settings_opened += 1

    def render(self, refresh):
        return psx('''<Flex direction="column">
        <Text value={self.window_title} />
        <Text value={self.platform.value} />
        <Text value="Frozen" />
        <Button label="Settings" on_click={self.open_settings} />
        <Button label="Refresh" on_click={refresh} />
    </Flex>''')

@component
def View(model):
    revision, set_revision = use_state(0)
    def refresh():
        model.window_title = "Updated title"
        model.platform.value = "Linux"
        model.is_frozen = True
        set_revision(lambda current: current + 1)
    return model.render(refresh)
""",
            filename="window_source.py",
        )
        namespace = _execute_transformed(result.source)
        model = namespace["WindowModel"]()
        renderer = measured_headless()
        root = Reconciler(renderer).render(namespace["View"](model=model))
        column = root.children[0].handle
        title, platform, frozen, settings, refresh = column.children
        self.assertEqual(title.props["value"], "Initial title")
        self.assertEqual(platform.props["value"], "macOS")
        self.assertEqual(frozen.props["value"], "Frozen")
        self.assertEqual(model.settings_opened, 0, "handlers must not run while rendering")
        settings.events["on_click"].invoke()
        self.assertEqual(model.settings_opened, 1)
        refresh.events["on_click"].invoke()
        renderer.flush()
        self.assertEqual(title.props["value"], "Updated title")
        self.assertEqual(platform.props["value"], "Linux")
        self.assertEqual(frozen.props["value"], "Frozen")

    def test_missing_lexical_name_and_attribute_path_have_source_diagnostics(self) -> None:
        missing_name = transform_source(
            """
from psx import Text, component, psx
@component
def View():
    return psx("<Text value={not_in_scope} />")
""",
            filename="missing_name.py",
        )
        with self.assertRaisesRegex(MarkupSyntaxError, "Unknown lexical identifier 'not_in_scope'") as raised:
            Reconciler(HeadlessRenderer()).render(_execute_transformed(missing_name.source)["View"]())
        self.assertEqual(raised.exception.filename, "missing_name.py:5:12")

        missing_attribute = transform_source(
            """
from psx import Text, psx
class Model:
    pass
    def render(self):
        return psx("<Text value={self.platform.value} />")
""",
            filename="missing_attribute.py",
        )
        namespace = _execute_transformed(missing_attribute.source)
        with self.assertRaisesRegex(MarkupSyntaxError, "Invalid lexical attribute path 'self.platform.value'"):
            Reconciler(HeadlessRenderer()).render(namespace["Model"]().render())

    def test_custom_component_tags_are_added_to_lexical_scope(self) -> None:
        result = transform_source(
            """
from psx import Text, component, psx
@component
def Card(title):
    return Text(title)
@component
def Screen():
    return psx("<Card title={title} />")
title = "Ada"
""",
            filename="custom_source.py",
        )
        namespace = _execute_transformed(result.source)
        screen = namespace["Screen"]
        root = Reconciler(HeadlessRenderer()).render(screen())
        child = root.children[0]
        self.assertEqual(child.node.type.name, "Card")
        self.assertEqual(child.node.props["title"], "Ada")

    def test_frozen_module_does_not_inspect_component_source(self) -> None:
        source = """
from __future__ import annotations
from psx import component, psx

@component
def Sidebar():
    return psx("<div><p>Frozen</p></div>")
"""
        generated = transform_source(source, filename="sidebar.py", precompiled=True)
        self.assertEqual(generated.transformed_calls, 1)
        self.assertIn("__psx_build_precompiled__ = True", generated.source)
        self.assertNotIn("return psx(", generated.source)
        # Compile under a virtual filename which does not exist on disk.
        with patch("psx.markup.component_compiler.inspect.getsourcelines",
                   side_effect=AssertionError("source inspection is forbidden")):
            namespace: dict[str, object] = {"__name__": "frozen_sidebar"}
            exec(compile(generated.source, "/missing/sidebar.py", "exec"), namespace)
            root = Reconciler(measured_headless()).render(namespace["Sidebar"]())
            self.assertIsNotNone(root)

    def test_frozen_module_marker_is_after_future_imports(self) -> None:
        generated = transform_source(
            "from __future__ import annotations\nvalue = 42\n",
            precompiled=True,
        )
        namespace: dict[str, object] = {}
        exec(compile(generated.source, "/missing/other.py", "exec"), namespace)
        self.assertTrue(namespace["__psx_build_precompiled__"])
        self.assertEqual(namespace["value"], 42)

    def test_dynamic_and_explicit_scope_calls_are_not_transformed(self) -> None:
        result = transform_source(
            """
from psx import psx
template = "<Text value={value} />"
a = psx(template)
b = psx("<Text value={value} />", scope={"value": "safe"})
""",
            filename="dynamic_source.py",
        )
        self.assertEqual(result.transformed_calls, 0)
        self.assertNotIn("_psx_compile_template", result.source)

    def test_source_map_records_original_python_and_markup_locations(self) -> None:
        result = transform_source(
            """
from psx import psx
def view():
    return psx("<Text value={value} />")
""",
            filename="map_source.py",
        )
        entry = result.source_map.entries[0]
        self.assertEqual(entry.python_line, 4)
        self.assertEqual(entry.python_column, 12)
        self.assertEqual(entry.markup_references, ((1, 14),))

    def test_file_transform_emits_python_and_json_source_map(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output, source_map = root / "view.py", root / "build.py", root / "build.psxmap.json"
            source.write_text("from psx import psx\nnode = psx('<Text value={title} />')\n", encoding="utf-8")
            result = transform_file(source, output, map_path=source_map)
            self.assertEqual(result.transformed_calls, 1)
            self.assertIn("_psx_template_0", output.read_text(encoding="utf-8"))
            self.assertIn("markup_references", source_map.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
