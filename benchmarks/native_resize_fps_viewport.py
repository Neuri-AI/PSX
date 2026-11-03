"""Compare viewport + early Cinnamon geometry optimization against full work.

Uses the identical Qt/Tk/Kivy native resize workload and number of cycles
for both subprocess-isolated runs. Each per-adapter/count cell is itself a
separate process, as in native_resize_fps.py. These figures are layout
transaction throughput, never compositor-presented frames per second.

Example:
  python benchmarks/native_resize_fps_viewport.py --adapters qt kivy tk \\
    --engine rust --scenario cards --counts 6 12 24 48 100 250 500 \\
    --cycles 40 --warmup 5 --timeout 10 \\
    --output benchmark-results/viewport-optimization
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("--output", type=Path, default=Path(
        "benchmark-results/viewport-optimization",
    ))
    args, passthrough = parser.parse_known_args()
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    benchmark = Path(__file__).with_name("native_resize_fps.py")
    results = {}
    for name, flags in (
        ("before", ["--disable-early-geometry-reuse", "--disable-viewport-defer"]),
        ("after", []),
    ):
        destination = root / name
        # Run controls through the same benchmark implementation to avoid
        # comparing unrelated engines, event loops or benchmark procedures.
        command = [sys.executable, str(benchmark), *passthrough, *flags,
                   "--output", str(destination)]
        proc = subprocess.run(command, check=False)
        if not (destination / "summary.json").exists():
            raise SystemExit(f"{name} did not produce its summary (exit {proc.returncode})")
        rows = json.loads((destination / "summary.json").read_text(encoding="utf-8"))
        results[name] = {(r["adapter"], r["engine"], r["scenario"],
                          r["logical_items"]): r for r in rows
                         if "error" not in r}
        if proc.returncode:
            raise SystemExit(f"{name} returned {proc.returncode}; inspect {destination}")
    output = []
    for key in sorted(results["after"], key=lambda k:(k[3], k[0], k[1], k[2])):
        optimized = results["after"][key]
        control = results["before"].get(key)
        if control is None:
            raise SystemExit(f"Missing baseline for {key}")
        before = control["event_to_commit"]
        after = optimized["event_to_commit"]
        row = {
            "adapter": key[0], "engine": key[1], "scenario": key[2],
            "count": key[3], "native_widgets": optimized["native_widgets"],
            "p95_before_ms": before["p95_ms"],
            "p95_after_ms": after["p95_ms"],
            "mean_before_ms": before["mean_ms"],
            "mean_after_ms": after["mean_ms"],
            "full_idle_p95_before_ms": control["request_to_full_settlement"]["p95_ms"],
            "full_idle_p95_after_ms": optimized["request_to_full_settlement"]["p95_ms"],
            "full_solver_calls_before": control["full_solver_calls"],
            "full_solver_calls_after": optimized["full_solver_calls"],
            "idle_commits_before": control["idle_reconciliation_commits"],
            "idle_commits_after": optimized["idle_reconciliation_commits"],
            "p95_reduction_pct": (
                100 * (1 - after["p95_ms"] / before["p95_ms"])
                if before["p95_ms"] else None
            ),
            "solver_calls_before": control["solver_calls"],
            "solver_calls_after": optimized["solver_calls"],
            "early_cache_hits_after": optimized.get("accepted_grid_geometry_hits", 0),
            "layout_hz_before": control["layout_hz"],
            "layout_hz_after": optimized["layout_hz"],
        }
        output.append(row)
        print(f"{key[0]}/{key[1]} n={key[3]} "
              f"p95 {before['p95_ms']:.2f} -> {after['p95_ms']:.2f} ms; "
              f"solver calls {row['solver_calls_before']} -> "
              f"{row['solver_calls_after']}; "
              f"cache hits {row['early_cache_hits_after']}; "
              f"full idle p95 {row['full_idle_p95_before_ms']:.2f} -> "
              f"{row['full_idle_p95_after_ms']:.2f} ms", flush=True)
    (root / "comparison.json").write_text(json.dumps(output, indent=2),
                                           encoding="utf-8")
    with (root / "comparison.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=output[0].keys())
        writer.writeheader()
        writer.writerows(output)


if __name__ == "__main__":
    main()
