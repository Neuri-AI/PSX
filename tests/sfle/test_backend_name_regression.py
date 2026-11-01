"""RED A08: fallback engine has an explicit diagnostic backend identity."""
from psx.layout.fallback.engine import PythonLayoutEngine
from psx.layout.engine.backend import load_layout_engine


def test_load_time_python_fallback_has_stable_backend_name():
    assert PythonLayoutEngine().backend_name == "python"
    # CI without native wheels selects and identifies Python.
    selected = load_layout_engine()
    assert selected.backend_name in ("python", "rust")
