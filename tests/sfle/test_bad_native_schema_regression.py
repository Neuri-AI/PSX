"""A08 imported but incompatible native ABI must fail closed."""
import sys
from types import SimpleNamespace
import pytest
from psx.layout.engine.backend import load_layout_engine
from psx.layout.contracts.errors import SFLEError,DiagnosticCode

def test_A08_loaded_incompatible_extension_is_not_silently_fallback(monkeypatch):
    monkeypatch.setitem(sys.modules,"_sfle_native",SimpleNamespace(schema_version=lambda:2))
    with pytest.raises(SFLEError) as exc:
        load_layout_engine()
    assert exc.value.code==DiagnosticCode.BACKEND_MISMATCH
