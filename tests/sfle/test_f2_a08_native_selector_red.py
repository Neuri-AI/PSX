"""A08 native selection RED: Rust is primary when extension contract is valid."""
import sys
from types import SimpleNamespace

from psx.sfle.backend import load_layout_engine


def test_A08_native_extension_selected_on_load(monkeypatch):
    fake=SimpleNamespace(
        schema_version=lambda:1,
        compute_json=lambda payload:'{}',
        compute_provisional_json=lambda payload:'{}',
    )
    monkeypatch.setitem(sys.modules,"_sfle_native",fake)
    selected=load_layout_engine()
    assert selected.backend_name=="rust", "Rust must be primary when importable and schema-valid"
