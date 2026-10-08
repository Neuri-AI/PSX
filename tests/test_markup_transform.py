from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "src")

from psx.core.reconcile import Reconciler
from psx.core.errors import MarkupSyntaxError
from psx.markup.transform import transform_file, transform_source
from psx.renderers.headless import HeadlessRenderer


def _execute_transformed(source: str) -> dict[str, object]:
    namespace: dict[str, object] = {"__name__": "transformed_fixture"}
    exec(compile(source, "transformed_fixture.py", "exec"), namespace)
    return namespace


class MarkupM4BTransformTests(unittest.TestCase):
    def test_inline_markup_resolves_state_and_event_callback_lexically(self) -> None:
        result = transform_source(
            """
from psx import Button, Column, Text, component, psx, use_state

@component
def Counter(prefix):
    count, set_count = use_state(0)
    def increment():
        set_count(lambda previous: previous + 1)
    return psx("<Column><Text>{prefix}: {count}</Text><Button on_click={increment}>+1</Button></Column>")
""",
            filename="counter_source.py",
        )
        self.assertEqual(result.transformed_calls, 1)
        self.assertIn("_psx_template_0.render_lexical", result.source)
        self.assertNotIn("return psx(", result.source)
        namespace = _execute_transformed(result.source)
        counter = namespace["Counter"]
        renderer = HeadlessRenderer()
        reconciler = Reconciler(renderer)
        root = reconciler.render(counter(prefix="Count"))
        column = root.children[0].handle
        label, button = column.children
        self.assertEqual(label.props["value"], "Count: 0")
        button.events["on_click"].invoke()
        renderer.flush()
        self.assertEqual(label.props["value"], "Count: 1")

    def test_static_numeric_markup_literals_need_no_lexical_scope_entry(self) -> None:
        result = transform_source(
            """
from psx import psx
def view():
    return psx("<Column padding={50} spacing={12}><Text>Ready</Text></Column>")
""",
            filename="numeric_markup.py",
        )
        node = _execute_transformed(result.source)["view"]()
        self.assertEqual(node.props["padding"], 50)
        self.assertEqual(node.props["spacing"], 12)

    def test_closure_and_shadowing_follow_normal_python_lexical_rules(self) -> None:
        result = transform_source(
            """
from psx import Text, component, psx
value = "global"

def make(value):
    @component
    def View():
        return psx("<Text>{value}</Text>")
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
from psx import Button, Column, Text, component, psx, use_state

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
        return psx('''<Column>
        <Text>App Title: {self.window_title}</Text>
        <Text>Platform: {self.platform.value}</Text>
        <Text>Frozen: {self.is_frozen}</Text>
        <Button on_click={self.open_settings}>Settings</Button>
        <Button on_click={refresh}>Refresh</Button>
    </Column>''')

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
        renderer = HeadlessRenderer()
        root = Reconciler(renderer).render(namespace["View"](model=model))
        column = root.children[0].handle
        title, platform, frozen, settings, refresh = column.children
        self.assertEqual(title.props["value"], "App Title: Initial title")
        self.assertEqual(platform.props["value"], "Platform: macOS")
        self.assertEqual(frozen.props["value"], "Frozen: False")
        self.assertEqual(model.settings_opened, 0, "handlers must not run while rendering")
        settings.events["on_click"].invoke()
        self.assertEqual(model.settings_opened, 1)
        refresh.events["on_click"].invoke()
        renderer.flush()
        self.assertEqual(title.props["value"], "App Title: Updated title")
        self.assertEqual(platform.props["value"], "Platform: Linux")
        self.assertEqual(frozen.props["value"], "Frozen: True")

    def test_missing_lexical_name_and_attribute_path_have_source_diagnostics(self) -> None:
        missing_name = transform_source(
            """
from psx import Text, component, psx
@component
def View():
    return psx("<Text>{not_in_scope}</Text>")
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
        return psx("<Text>{self.platform.value}</Text>")
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

    def test_dynamic_and_explicit_scope_calls_are_not_transformed(self) -> None:
        result = transform_source(
            """
from psx import psx
template = "<Text>{value}</Text>"
a = psx(template)
b = psx("<Text>{value}</Text>", scope={"value": "safe"})
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
    return psx("<Text>{value}</Text>")
""",
            filename="map_source.py",
        )
        entry = result.source_map.entries[0]
        self.assertEqual(entry.python_line, 4)
        self.assertEqual(entry.python_column, 12)
        self.assertEqual(entry.markup_references, ((1, 7),))

    def test_file_transform_emits_python_and_json_source_map(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output, source_map = root / "view.py", root / "build.py", root / "build.psxmap.json"
            source.write_text("from psx import psx\nnode = psx('<Text>{title}</Text>')\n", encoding="utf-8")
            result = transform_file(source, output, map_path=source_map)
            self.assertEqual(result.transformed_calls, 1)
            self.assertIn("_psx_template_0", output.read_text(encoding="utf-8"))
            self.assertIn("markup_references", source_map.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
