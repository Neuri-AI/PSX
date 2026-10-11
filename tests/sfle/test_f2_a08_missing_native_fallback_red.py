"""A08 fallback occurs only on extension loading failure."""
import importlib
from psx.sfle.backend import load_layout_engine
from psx.sfle.engine import PythonLayoutEngine

def test_A08_load_time_import_error_selects_python(monkeypatch):
    original=importlib.import_module
    def blocked(name,*args,**kwargs):
        if name=="_sfle_native":
            raise ImportError("Native wheel absent on this platform")
        return original(name,*args,**kwargs)
    monkeypatch.setattr(importlib,"import_module",blocked)
    selected=load_layout_engine()
    assert isinstance(selected,PythonLayoutEngine)
