"""Verify that the public beginner guide's exact files start a native Qt app."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/public/getting-started/first-app.mdx"
EXAMPLE = ROOT / "examples/documented_hello"


def _code_block(text: str, language: str, preceding: str) -> str:
    marker = text.index(preceding)
    expression = r"```" + language + r"\n(.*?)\n```"
    match = re.search(expression, text[marker:], re.S)
    assert match is not None, (language, preceding)
    return match.group(1).rstrip() + "\n"


def test_documented_files_are_exact_copy() -> None:
    text = DOC.read_text(encoding="utf-8")
    snippets = {
        "settings/base.json": _code_block(text, "json", "Create `settings/base.json`"),
        "main.py": _code_block(text, "python", "Create `main.py`"),
        "pyproject.toml": _code_block(text, "toml", "Create `pyproject.toml`"),
    }
    for relative, snippet in snippets.items():
        expected = (EXAMPLE / relative).read_text(encoding="utf-8")
        assert snippet == expected, f"Guide and example differ: {relative}"
    assert json.loads(snippets["settings/base.json"])["framework"] == "pyside6"
    assert "HelloApp().run()" in snippets["main.py"]


def test_extracted_application_mounts_and_runs() -> None:
    text = DOC.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="velto-beginner-") as directory:
        root = Path(directory)
        (root / "settings").mkdir()
        (root / "main.py").write_text(
            _code_block(text, "python", "Create `main.py`"), encoding="utf-8"
        )
        (root / "settings/base.json").write_text(
            _code_block(text, "json", "Create `settings/base.json`"), encoding="utf-8"
        )
        (root / "pyproject.toml").write_text(
            _code_block(text, "toml", "Create `pyproject.toml`"), encoding="utf-8"
        )
        environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
        # The complete copied application remains unchanged. Only the test
        # harness instantiates it, checks the real native widget, and exits.
        harness = """
from main import HelloApp
from PySide6.QtWidgets import QApplication, QLabel
app = HelloApp(enable_sentry=False)
try:
    handle = app.mount()
    assert handle is app.handle and handle is not None
    qt = QApplication.instance()
    assert qt is not None
    assert any(isinstance(w, QLabel) and 'Hello, Velto!' in w.text()
               for w in qt.allWidgets()), 'Expected native Qt label'
    assert app.renderer.sfle_result is not None
    assert app.renderer.sfle_result.geometry_commit_error == 0.0
    print('DOCUMENTED_HELLO_NATIVE_MOUNT_OK', flush=True)
finally:
    app.unmount()
assert app.handle is None
"""
        result = subprocess.run(
            [sys.executable, "-c", harness],
            cwd=root, env=environment, text=True, capture_output=True,
            timeout=90, check=False,
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert "DOCUMENTED_HELLO_NATIVE_MOUNT_OK" in result.stdout
        # Run the public main.py entrypoint itself. The harness only arranges
        # a bounded Qt event-loop exit so CI does not need a human to close it.
        entrypoint_harness = """
import runpy
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
qt = QApplication.instance() or QApplication([])
QTimer.singleShot(1200, qt.quit)
runpy.run_path('main.py', run_name='__main__')
print('DOCUMENTED_HELLO_ENTRYPOINT_OK', flush=True)
"""
        execution = subprocess.run(
            [sys.executable, "-c", entrypoint_harness], cwd=root,
            env=environment, text=True, capture_output=True,
            timeout=90, check=False,
        )
        assert execution.returncode == 0, (execution.stdout, execution.stderr)
        assert "DOCUMENTED_HELLO_ENTRYPOINT_OK" in execution.stdout


if __name__ == "__main__":
    test_documented_files_are_exact_copy()
    test_extracted_application_mounts_and_runs()
    print("DOCUMENTED_HELLO_REPRODUCED", flush=True)
