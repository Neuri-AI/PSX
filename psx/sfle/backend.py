"""F2 native backend selection contract; implementation pending RED tests."""
from __future__ import annotations
from .engine import PythonLayoutEngine


def load_layout_engine():
    """Choose one engine at load time; no mid-transaction fallback."""
    return PythonLayoutEngine()
