"""End-to-end CLI-supervised native app replacement, not isolated renderer mocks."""
from __future__ import annotations

import os
from pathlib import Path
import sys

from velto_cli.adapters.process.development_coordinator import DevelopmentCoordinator


def test_supervised_native_process_restarts_across_real_event_loops(tmp_path):
    backend = os.environ["PSX_GRID_BACKEND"]
    child = Path(__file__).parent / "certification" / "native_supervised_child.py"
    trace = tmp_path / "generations.txt"
    env = dict(os.environ)
    env["KIVY_NO_ARGS"] = "1"
    env["KIVY_NO_CONSOLELOG"] = "1"
    coordinator = DevelopmentCoordinator(tmp_path, debounce=0.05)
    import threading
    import time
    result_holder = []
    error_holder = []
    def supervise():
        try:
            result_holder.append(coordinator.run([sys.executable, str(child), backend, str(trace)], env))
        except BaseException as exc:
            error_holder.append(exc)
    worker = threading.Thread(target=supervise, daemon=True)
    worker.start()
    worker.join(timeout=65)
    if worker.is_alive():
        stage = trace.with_suffix(".stage")
        detail = stage.read_text(encoding="utf-8") if stage.exists() else "no child stage"
        coordinator._stop.set()
        coordinator._restart.set()
        worker.join(timeout=7)
        raise AssertionError(f"Native restart stalled: {backend}, {detail}")
    if error_holder:
        raise error_holder[0]
    result = result_holder[0]
    assert result == 0
    assert trace.read_text(encoding="utf-8").splitlines() == ["0", "1", "2"]
    assert trace.with_suffix(".clean").read_text(encoding="utf-8") == "event_loop_exited"
