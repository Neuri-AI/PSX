"""A full mounted native application enters and exits its event loop per generation."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("generation", range(3))
def test_native_process_generation_runs_real_event_loop(tmp_path, generation):
    backend = os.environ["PSX_GRID_BACKEND"]
    script = Path(__file__).parent / "certification" / "native_event_loop_child.py"
    marker = tmp_path / f"generation-{generation}.txt"
    child_env = dict(os.environ)
    child_env["KIVY_NO_ARGS"] = "1"
    child_env["KIVY_NO_CONSOLELOG"] = "1"
    process = subprocess.run(
        [sys.executable, str(script), backend, str(marker)],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=child_env, capture_output=True, text=True, timeout=35,
    )
    assert process.returncode == 0, (
        f"{backend} generation {generation} exit {process.returncode}\n"
        f"stdout: {process.stdout[-3000:]}\nstderr: {process.stderr[-3000:]}"
    )
    assert marker.read_text(encoding="utf-8") == "event_loop_exited"
    assert marker.with_suffix(".clean").read_text(encoding="utf-8") == "unmounted"
