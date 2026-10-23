"""End-to-end CLI-supervised native app replacement, not isolated renderer mocks."""
from __future__ import annotations

import multiprocessing
import os
from pathlib import Path
import sys

from velto_cli.adapters.process.development_coordinator import DevelopmentCoordinator


def _supervise(root, command, environment, result):
    coordinator = DevelopmentCoordinator(Path(root), debounce=0.05)
    result.put(coordinator.run(command, environment))


def test_supervised_native_process_restarts_across_real_event_loops(tmp_path):
    import psutil

    backend = os.environ["PSX_GRID_BACKEND"]
    child = Path(__file__).parent / "certification" / "native_supervised_child.py"
    trace = tmp_path / "generations.txt"
    env = dict(os.environ)
    env["KIVY_NO_ARGS"] = "1"
    env["KIVY_NO_CONSOLELOG"] = "1"
    context = multiprocessing.get_context("spawn")
    results = context.Queue()
    supervisor = context.Process(
        target=_supervise,
        args=(str(tmp_path), [sys.executable, str(child), backend, str(trace)], env, results),
    )
    supervisor.start()
    supervisor.join(timeout=75)
    if supervisor.is_alive():
        stage = trace.with_suffix(".stage")
        detail = stage.read_text(encoding="utf-8") if stage.exists() else "no child stage"
        process = psutil.Process(supervisor.pid)
        descendants = process.children(recursive=True)
        for candidate in descendants:
            candidate.terminate()
        psutil.wait_procs(descendants, timeout=4)
        for candidate in descendants:
            if candidate.is_running():
                candidate.kill()
        supervisor.terminate()
        supervisor.join(timeout=5)
        if supervisor.is_alive():
            supervisor.kill()
            supervisor.join(timeout=5)
        raise AssertionError(f"Native restart stalled: {backend}, {detail}")
    assert supervisor.exitcode == 0
    assert results.get(timeout=2) == 0
    assert trace.read_text(encoding="utf-8").splitlines() == ["0", "1", "2"]
    assert trace.with_suffix(".clean").read_text(encoding="utf-8") == "event_loop_exited"
