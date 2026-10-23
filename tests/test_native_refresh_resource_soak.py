"""Bounded live native refresh resource-soak regression.

The same interpreter, renderer, native event-loop owner and mounted app are reused
throughout the measurement. This is not a proxy based on fresh-process RSS.
"""
from __future__ import annotations

import gc
import os
from pathlib import Path
import tracemalloc
from types import SimpleNamespace

from psx import App, Flex, Text, component, use_state
from psx.devtools import coordinated_refresh as refresh
from tests.test_mounted_grid_native_renderers import make_renderer


def test_native_refresh_memory_remains_bounded(monkeypatch, tmp_path):
    import psutil

    backend = os.environ["PSX_GRID_BACKEND"]
    renderer, close = make_renderer(backend)
    source = tmp_path / "main.py"
    source.write_text("class Demo: pass\n", encoding="utf-8")

    class Demo:
        pass

    context = Demo()
    def first(self):
        value, _ = use_state(29)
        return Flex(Text(f"initial:{value}"))
    slot = [first]
    next_render = [first]
    def root():
        return slot[0](context)
    definition = component(root)
    context._development_render = slot
    context._development_root_definition = definition
    context.app = App(definition, renderer=renderer)
    monkeypatch.setattr(refresh, "_reload_policy", lambda _: object())
    monkeypatch.setattr(refresh, "_project_modules", lambda *_: (frozenset(), {}))
    monkeypatch.setattr(refresh, "_load_updated_class",
                        lambda *_: SimpleNamespace(render=next_render[0]))

    samples = []
    tracemalloc.start()
    try:
        context.app.mount()
        process = psutil.Process()
        for i in range(160):
            def updated(self, index=i):
                value, _ = use_state(29)
                return Flex(Text(f"sample:{index}:{value}"))
            next_render[0] = updated
            assert refresh.refresh_context_source(context, source, ("main.py",))
            if i % 20 == 19:
                if backend == "qt":
                    renderer.application.processEvents()
                elif backend == "tk":
                    renderer.root.update_idletasks()
                gc.collect()
                current, peak = tracemalloc.get_traced_memory()
                samples.append((process.memory_info().rss, current))
        # Disregard the warmup and bounded one-off toolkit caches. Sustained
        # growth beyond these budgets indicates retained objects/resources.
        rss_growth = max(0, samples[-1][0] - samples[1][0])
        python_growth = max(0, samples[-1][1] - samples[1][1])
        assert rss_growth < 32 * 1024 * 1024, samples
        assert python_growth < 8 * 1024 * 1024, samples
    finally:
        context.app.unmount()
        close()
        tracemalloc.stop()
