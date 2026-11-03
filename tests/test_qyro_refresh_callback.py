"""Regression for PSX callback contract: Qyro owns state coordination."""
from pathlib import Path
from types import SimpleNamespace

from psx.devtools.coordinated_refresh import refresh_context_source


def test_unmounted_refresh_does_not_prepare_state(tmp_path: Path):
    called = []
    context = SimpleNamespace(app=None)
    source = tmp_path / "main.py"
    source.write_text("pass\n")
    result = refresh_context_source(
        context, source, ("main.py",),
        prepare_state=lambda candidate: called.append(candidate),
    )
    assert result is False
    assert called == []
