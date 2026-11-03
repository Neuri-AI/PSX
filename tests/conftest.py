"""Local defaults and process isolation for the repository's native audits."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption("--native-backend", choices=("qt", "tk", "kivy"),
                     help="Backend for shared native matrix tests; defaults to installed Qt.")


def pytest_configure(config):
    from tests.native_display import prepare_native_display

    prepare_native_display(config)
    # CI's explicit choices always win. A local full run must not turn every
    # shared native test into a KeyError because it omitted a matrix variable.
    bindings = {"pyside6": "PySide6", "pyqt6": "PyQt6", "pyqt5": "PyQt5", "pyside2": "PySide2"}
    if "PSX_QT_BINDING" not in os.environ:
        installed = next((name for name, package in bindings.items()
                          if importlib.util.find_spec(package) is not None), None)
        if installed is not None:
            os.environ["PSX_QT_BINDING"] = installed
    selected = config.getoption("--native-backend")
    if selected is not None:
        os.environ["PSX_GRID_BACKEND"] = selected
    elif "PSX_GRID_BACKEND" not in os.environ and os.environ.get("PSX_QT_BINDING"):
        os.environ["PSX_GRID_BACKEND"] = "qt"


def pytest_report_header(config):
    if getattr(config, "_psx_private_native_display", False):
        return "Native tests: private Xvfb with scalable system fonts (existing display preserved)"


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    # Collection imports the independent Python oracle for differential tests.
    # Audit actual Rust imports in a fresh interpreter, so those imports cannot
    # contaminate sys.modules or be hidden by deleting entries from it.
    if (Path(pyfuncitem.path).parent.name != "architecture"
            or Path(pyfuncitem.path).name not in (
                "test_rust_only_layout.py", "test_rust_only_native_renderers.py")
            or os.environ.get("_PSX_RUST_AUDIT_CHILD") == "1"):
        return None
    env = dict(os.environ, _PSX_RUST_AUDIT_CHILD="1")
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=short",
                             pyfuncitem.nodeid], cwd=pyfuncitem.config.rootpath,
                            env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    return True
