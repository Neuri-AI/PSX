"""Black-box certification of native @component lexical PSX execution."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ComponentLexicalRuntimeTests(unittest.TestCase):
    def test_plain_python_entrypoint_state_event_ref_and_effect(self) -> None:
        source = '''
from psx import App, component, psx, use_effect, use_ref, use_state
from psx.renderers.headless import HeadlessRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints

events = []

@component
def Counter():
    count, set_count = use_state(0)
    reference = use_ref()
    def increment_count():
        set_count(lambda previous: previous + 1)
    def effect():
        events.append(f"start:{count}")
        def cleanup():
            events.append(f"stop:{count}")
        return cleanup
    use_effect(effect, [count])
    return psx("""
        <Flex direction="column" gap="12">
            <Text>Counter: {count}</Text>
            <Button ref={reference} on_click={increment_count}>
                Click me! ({count})
            </Button>
        </Flex>
    """)

renderer = HeadlessRenderer(
    sfle_constraints=LayoutConstraints(AvailableSize(640, True), AvailableSize(480, True)),
    engine=PythonLayoutEngine(),
    measure_intrinsic=lambda node: IntrinsicSizes(4, 20, 8, 12, 18, 12, 8),
)
app = App(Counter, renderer=renderer)
app.mount()
column = app.reconciler.root.children[0].handle
label, button = column.children
original_window_handle = app.reconciler.root.native_handle()
original_label = label
original_button = button
assert label.props["value"] == "Counter: 0", label.props
assert button.props["label"] == "Click me! (0)", button.props
button.events["on_click"].invoke()
renderer.flush()
assert app.reconciler.root.native_handle() is original_window_handle
assert app.reconciler.root.children[0].handle is column
assert column.children[0] is original_label
assert column.children[1] is original_button
assert label.props["value"] == "Counter: 1", label.props
assert button.props["label"] == "Click me! (1)", button.props
assert events == ["start:0", "stop:0", "start:1"], events
app.unmount()
assert events[-1] == "stop:1", events
print("LEXICAL_COMPONENT_OK")
'''
        with tempfile.TemporaryDirectory() as tmp:
            entry = Path(tmp) / "main.py"
            entry.write_text(source, encoding="utf-8")
            project_root = Path(__file__).resolve().parents[1]
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(project_root) + os.pathsep + environment.get("PYTHONPATH", "")
            run = subprocess.run(
                [sys.executable, str(entry)],
                capture_output=True,
                text=True,
                cwd=project_root,
                env=environment,
                timeout=30,
                check=False,
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("LEXICAL_COMPONENT_OK", run.stdout)


    def test_external_component_and_approved_ternary_preserve_native_identity(self) -> None:
        source = '''
from psx import App, component, psx, use_state
from psx.renderers.headless import HeadlessRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints

@component
def CustomButton():
    return psx("""
        <Button>Click me!!!!</Button>
    """)

@component
def View():
    count, set_count = use_state(0)
    def increment_count():
        set_count(count + 1)
    is_high = count >= 10
    count_label = f"Count is {count}"
    return psx("""
        <Flex direction="column" gap="12" align_items="center">
            <Text>Hello, Velto!</Text>
            <Button on_click={increment_count}>
                {is_high ? "Count is high!" : count_label}
            </Button>
            <CustomButton />
        </Flex>
    """)

renderer = HeadlessRenderer(
    sfle_constraints=LayoutConstraints(AvailableSize(800, True), AvailableSize(600, True)),
    engine=PythonLayoutEngine(),
    measure_intrinsic=lambda node: IntrinsicSizes(4, 20, 8, 12, 18, 12, 8),
)
app = App(View, renderer=renderer)
root = app.mount()
column = app.reconciler.root.children[0].handle
label, counter_button, custom_button = column.children
assert counter_button.props["label"] == "Count is 0", counter_button.props
assert custom_button.props["label"] == "Click me!!!!", custom_button.props
for count in range(1, 12):
    counter_button.events["on_click"].invoke()
    renderer.flush()
    assert app.reconciler.root.native_handle() is root
    assert app.reconciler.root.children[0].handle is column
    assert column.children[0] is label
    assert column.children[1] is counter_button
    assert column.children[2] is custom_button
    expected = "Count is high!" if count >= 10 else f"Count is {count}"
    assert counter_button.props["label"] == expected, counter_button.props
    assert custom_button.props["label"] == "Click me!!!!"
print("COMPOSITION_TERNARY_OK")
'''
        with tempfile.TemporaryDirectory() as tmp:
            entry = Path(tmp) / "main.py"
            entry.write_text(source, encoding="utf-8")
            project_root = Path(__file__).resolve().parents[1]
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(project_root) + os.pathsep + environment.get("PYTHONPATH", "")
            run = subprocess.run(
                [sys.executable, str(entry)], capture_output=True, text=True,
                cwd=project_root, env=environment, timeout=30, check=False,
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("COMPOSITION_TERNARY_OK", run.stdout)


    def test_plain_python_arrow_map_index_and_component_update(self) -> None:
        source = '''
from psx import App, component, psx, use_state
from psx.renderers.headless import HeadlessRenderer
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, IntrinsicSizes, LayoutConstraints

events = []

@component
def View():
    colors = ["red", "blue"]
    count, set_count = use_state(0)
    def update(index):
        events.append(index)
        set_count(lambda value: value + 1)
    return psx("""
        <Flex direction="column">
            {colors.map((color, index) =>
                <Button key={index} on_click={() => update(index)}>
                    {color}
                </Button>)}
            <Text>{count}</Text>
        </Flex>
    """)

renderer = HeadlessRenderer(
    sfle_constraints=LayoutConstraints(AvailableSize(640, True), AvailableSize(480, True)),
    engine=PythonLayoutEngine(),
    measure_intrinsic=lambda node: IntrinsicSizes(4, 20, 8, 12, 18, 12, 8),
)
app = App(View, renderer=renderer)
app.mount()
column = app.reconciler.root.children[0].handle
a, b, counter = column.children
assert [a.props["label"], b.props["label"]] == ["red", "blue"]
b.events["on_click"].invoke()
renderer.flush()
assert events == [1], events
assert column.children[0] is a and column.children[1] is b
assert counter.props["value"] == "1", counter.props
app.unmount()
print("ARROW_MAP_COMPONENT_OK")
'''
        with tempfile.TemporaryDirectory() as tmp:
            entry = Path(tmp) / "main.py"
            entry.write_text(source, encoding="utf-8")
            project_root = Path(__file__).resolve().parents[1]
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(project_root) + os.pathsep + environment.get("PYTHONPATH", "")
            run = subprocess.run(
                [sys.executable, str(entry)], capture_output=True, text=True,
                cwd=project_root, env=environment, timeout=30, check=False,
            )
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("ARROW_MAP_COMPONENT_OK", run.stdout)


if __name__ == "__main__":
    unittest.main()
