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

renderer = HeadlessRenderer()
app = App(Counter, renderer=renderer)
app.mount()
column = app.reconciler.root.children[0].handle
label, button = column.children
assert label.props["value"] == "Counter: 0", label.props
assert button.props["label"] == "Click me! (0)", button.props
button.events["on_click"].invoke()
renderer.flush()
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


if __name__ == "__main__":
    unittest.main()
