"""Deterministic, dependency-free PSX benchmark suite.

The suite measures the core/headless path only. Native GUI timings are not
comparable across window servers and belong in renderer-specific smoke runs.
Use a baseline captured on the same machine and Python version:

    PYTHONPATH=src python benchmarks/psx_benchmark.py --write-baseline .bench.json
    PYTHONPATH=src python benchmarks/psx_benchmark.py --baseline .bench.json
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
import gc
import json
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter
import tracemalloc
from typing import Any

from psx import Button, Column, Row, Text, builtin_component_registry, component, psx, use_state
from psx.core.reconcile import Reconciler
from psx.renderers.headless import HeadlessRenderer


Result = dict[str, Any]

class _OpsOnlyRenderer(HeadlessRenderer):
    """Registra move/insert/remove sin mutar listas de hijos.

    Aísla el coste del reconciliador del coste de list.remove/insert del
    HeadlessRenderer. El reconciliador no lee `handle.children`, así que la
    secuencia de operaciones emitida es la misma.
    """

    def move(self, parent: object, child: object, index: int) -> None:
        self.operations.append(("move", parent, child, index))

    def insert(self, parent: object, child: object, index: int) -> None:
        self.operations.append(("insert", parent, child, index))

    def remove(self, parent: object, child: object) -> None:
        self.operations.append(("remove", parent, child))

def _tree(size: int, value: int = 0, *, single_update: bool = False):
    return Column(
        *(
            Text(f"{value}:{index}" if not single_update or index == 0 else f"0:{index}", key=index)
            for index in range(size)
        )
    )


def _measure(
    name: str,
    setup: Callable[[], tuple[Callable[[], None], Callable[[], int]]],
    *,
    iterations: int,
    repeats: int,
) -> Result:
    """Measure an operation, including operation count but excluding setup."""
    samples: list[float] = []
    operation_counts: list[float] = []
    peak_bytes = 0
    retained_bytes = 0
    for _ in range(repeats):
        action, operations = setup()
        units: list[int] = []
        for _ in range(iterations):
            start = perf_counter()
            action()
            samples.append(perf_counter() - start)
            units.append(operations())

        # Allocation tracing materially changes timing. Run an equivalent
        # second pass for memory so latency remains a useful regression signal.
        memory_action, _memory_operations = setup()
        tracemalloc.start()
        for _ in range(iterations):
            memory_action()
        gc.collect()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        operation_counts.append(statistics.mean(units))
        peak_bytes = max(peak_bytes, peak)
        retained_bytes = max(retained_bytes, current)
    average = statistics.mean(samples)
    ordered = sorted(samples)
    p95 = ordered[max(0, -(-len(ordered) * 95 // 100) - 1)]
    return {
        "name": name,
        "iterations": iterations,
        "repeats": repeats,
        "mean_ms": round(average * 1000, 4),
        "median_ms": round(statistics.median(samples) * 1000, 4),
        "p95_ms": round(p95 * 1000, 4),
        "work_units_per_iteration": round(statistics.mean(operation_counts), 2),
        "peak_python_bytes": peak_bytes,
        "retained_python_bytes": retained_bytes,
        "ops_per_second": round(1 / average, 2) if average else 0,
    }


def _mount_tree(size: int) -> tuple[Callable[[], None], Callable[[], int]]:
    renderer = HeadlessRenderer()
    reconciler = Reconciler(renderer)

    def action() -> None:
        renderer.operations.clear()
        reconciler.render(_tree(size))
        reconciler.unmount()

    return action, lambda: len(renderer.operations)


def _vnode_build(size: int, *, single_update: bool = False, noop: bool = False) -> tuple[Callable[[], None], Callable[[], int]]:
    tick = 0

    def action() -> None:
        nonlocal tick
        tick += 0 if noop else 1
        _tree(size, tick, single_update=single_update)

    return action, lambda: size + 1


def _update_tree(size: int, *, single_update: bool = False, noop: bool = False) -> tuple[Callable[[], None], Callable[[], int]]:
    renderer = HeadlessRenderer()
    reconciler = Reconciler(renderer)
    reconciler.render(_tree(size, single_update=single_update))
    renderer.operations.clear()
    tick = 0

    def action() -> None:
        nonlocal tick
        renderer.operations.clear()
        tick += 0 if noop else 1
        reconciler.render(_tree(size, tick, single_update=single_update))

    return action, lambda: len(renderer.operations)


def _reconcile_prebuilt(
    size: int, *, single_update: bool = False, noop: bool = False, iterations: int
) -> tuple[Callable[[], None], Callable[[], int]]:
    """Measure reconciliation only; VNodes are deliberately built before timing."""
    renderer = HeadlessRenderer()
    reconciler = Reconciler(renderer)
    # No-op reconciliation still receives an equivalent *new* VNode tree.
    values = [0 for _ in range(iterations + 1)] if noop else list(range(iterations + 1))
    nodes = [_tree(size, value, single_update=single_update) for value in values]
    reconciler.render(nodes[0])
    renderer.operations.clear()
    index = 0

    def action() -> None:
        nonlocal index
        renderer.operations.clear()
        index = (index + 1) % len(nodes)
        reconciler.render(nodes[index])

    return action, lambda: len(renderer.operations)


def _keyed_reorder(
    size: int, renderer_factory: Callable[[], HeadlessRenderer] = HeadlessRenderer
) -> tuple[Callable[[], None], Callable[[], int]]:
    renderer = renderer_factory()
    reconciler = Reconciler(renderer)
    values = list(range(size))
    reconciler.render(Row(*(Text(str(index), key=index) for index in values)))
    renderer.operations.clear()

    def action() -> None:
        renderer.operations.clear()
        values.reverse()
        reconciler.render(Row(*(Text(str(index), key=index) for index in values)))

    return action, lambda: len(renderer.operations)


def _event_replacement() -> tuple[Callable[[], None], Callable[[], int]]:
    renderer = HeadlessRenderer()
    reconciler = Reconciler(renderer)
    reconciler.render(Button("Save", on_click=lambda: None))
    renderer.operations.clear()
    tick = 0

    def action() -> None:
        nonlocal tick
        renderer.operations.clear()
        tick += 1
        reconciler.render(Button("Save", on_click=lambda: None))
        reconciler.root.handle.events["on_click"].invoke()  # type: ignore[union-attr]

    return action, lambda: len(renderer.operations)


def _event_mount_unmount() -> tuple[Callable[[], None], Callable[[], int]]:
    renderer = HeadlessRenderer()
    reconciler = Reconciler(renderer)

    def action() -> None:
        renderer.operations.clear()
        reconciler.render(Button("Save", on_click=lambda: None))
        reconciler.unmount()

    return action, lambda: len(renderer.operations)


def _batched_state() -> tuple[Callable[[], None], Callable[[], int]]:
    renderer = HeadlessRenderer()
    reconciler = Reconciler(renderer)
    captured: dict[str, object] = {}

    @component
    def Counter():
        value, set_value = use_state(0)
        captured["set"] = set_value
        return Text(value)

    reconciler.render(Counter())
    renderer.operations.clear()

    def action() -> None:
        renderer.operations.clear()
        setter = captured["set"]
        setter(lambda value: value + 1)  # type: ignore[operator]
        setter(lambda value: value + 1)  # type: ignore[operator]
        setter(lambda value: value + 1)  # type: ignore[operator]
        renderer.flush()

    return action, lambda: len(renderer.operations)


def _markup_render(size: int) -> tuple[Callable[[], None], Callable[[], int]]:
    source = "<Column>" + "".join(f"<Text value={{item{index}}} />" for index in range(size)) + "</Column>"
    values = {f"item{index}": str(index) for index in range(size)}
    # Compile once so this measures safe template rendering, not parser setup.
    from psx.markup import compile_template

    template = compile_template(source, filename="<benchmark>")
    def action() -> None:
        template.render(values)

    return action, lambda: 1


def _markup_compile(size: int) -> tuple[Callable[[], None], Callable[[], int]]:
    source = "<Column>" + "".join(f"<Text value={{item{index}}} />" for index in range(size)) + "</Column>"
    from psx.markup import clear_template_cache, compile_template

    counter = 0

    def action() -> None:
        nonlocal counter
        counter += 1
        # A distinct filename intentionally bypasses the template cache.
        compile_template(source, filename=f"<benchmark-{counter}>")
        clear_template_cache()

    return action, lambda: 1


def _m4b_transform() -> tuple[Callable[[], None], Callable[[], int]]:
    from psx.markup.transform import transform_source

    source = "from psx import psx\n\ndef view(title):\n    return psx('<Text>{title}</Text>')\n"

    def action() -> None:
        transform_source(source, filename="benchmark_view.py")

    return action, lambda: 1


def _component_resolution() -> tuple[Callable[[], None], Callable[[], int]]:
    """Measure isolated registry lookups without a compiler/cache side effect."""
    registry = builtin_component_registry()
    names = ("Column", "Row", "Text", "Button", "Input", "Checkbox", "Fragment", "Native")

    def action() -> None:
        for name in names:
            registry.resolve(name)

    return action, lambda: len(names)


def run_suite(*, size: int = 200, iterations: int = 100, repeats: int = 5) -> dict[str, object]:
    """Return JSON-safe measurements for major PSX reconciliation paths."""
    scenarios = (
        ("mount_unmount", lambda: _mount_tree(size)),
        ("vnode_build_full", lambda: _vnode_build(size)),
        ("vnode_build_single", lambda: _vnode_build(size, single_update=True)),
        ("vnode_build_noop", lambda: _vnode_build(size, noop=True)),
        ("full_update_combined", lambda: _update_tree(size)),
        ("full_update_reconcile_only", lambda: _reconcile_prebuilt(size, iterations=iterations)),
        ("single_update_combined", lambda: _update_tree(size, single_update=True)),
        ("single_update_reconcile_only", lambda: _reconcile_prebuilt(size, single_update=True, iterations=iterations)),
        ("noop_update_combined", lambda: _update_tree(size, noop=True)),
        ("noop_update_reconcile_only", lambda: _reconcile_prebuilt(size, noop=True, iterations=iterations)),
        ("keyed_reorder", lambda: _keyed_reorder(size)),
        ("keyed_reorder_reconcile_only", lambda: _keyed_reorder(size, _OpsOnlyRenderer)),
        ("event_callback_replacement", _event_replacement),
        ("event_mount_unmount_cleanup", _event_mount_unmount),
        ("batched_state_scheduler", _batched_state),
        ("markup_render", lambda: _markup_render(size)),
        ("markup_compile", lambda: _markup_compile(size)),
        ("m4b_transform", _m4b_transform),
        ("component_registry_resolution", _component_resolution),
    )
    return {
        "schema": 1,
        "runtime": {"python": sys.version.split()[0], "platform": platform.platform()},
        "parameters": {"tree_size": size, "iterations": iterations, "repeats": repeats},
        "scenarios": [_measure(name, setup, iterations=iterations, repeats=repeats) for name, setup in scenarios],
    }


def compare(current: dict[str, object], baseline: dict[str, object]) -> list[dict[str, object]]:
    """Compare mean timings; positive percentage means a regression."""
    old = {item["name"]: item for item in baseline.get("scenarios", [])}  # type: ignore[union-attr]
    results: list[dict[str, object]] = []
    for item in current["scenarios"]:  # type: ignore[index]
        previous = old.get(item["name"])
        if previous is None or not previous["mean_ms"]:
            continue
        delta = ((item["mean_ms"] - previous["mean_ms"]) / previous["mean_ms"]) * 100
        results.append({"name": item["name"], "mean_ms_delta_percent": round(delta, 2)})
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic PSX core benchmarks.")
    parser.add_argument("--size", type=int, default=200, help="nodes in tree workloads")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--baseline", type=Path, help="JSON baseline captured on this machine")
    parser.add_argument("--write-baseline", type=Path, help="write this result as a JSON baseline")
    parser.add_argument("--max-regression", type=float, default=None, help="fail if timing regression exceeds percent")
    args = parser.parse_args(argv)
    if args.size < 1 or args.iterations < 1 or args.repeats < 1:
        parser.error("size, iterations, and repeats must be positive")
    result = run_suite(size=args.size, iterations=args.iterations, repeats=args.repeats)
    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        result["comparison"] = compare(result, baseline)
    if args.write_baseline:
        args.write_baseline.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    if args.max_regression is not None:
        changes = result.get("comparison", [])
        if any(change["mean_ms_delta_percent"] > args.max_regression for change in changes):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
