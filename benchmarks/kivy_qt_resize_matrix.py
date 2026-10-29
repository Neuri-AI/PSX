"""Repeat the real Qt/Kivy mixed resize suite in isolated native processes.

No compositor frame claims: repeat summaries are native event-to-Cinnamon commits.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from benchmarks.kivy_qt_mixed_resize import compare


CELLS = (("qt", "python"), ("kivy", "rust"),
         ("qt", "rust"), ("kivy", "python"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("benchmark-results/mixed-1000"))
    parser.add_argument("--warmup", type=int, default=32)
    parser.add_argument("--cycles", type=int, default=240)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--tolerance", type=float, default=1.0)
    args = parser.parse_args()
    if args.repeats < 1 or args.cycles < 100 or args.warmup < 0:
        parser.error("repeats>=1, cycles>=100, warmup>=0 are required")
    args.output.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).with_name("kivy_qt_mixed_resize.py")
    rows = []
    failures = []
    for repeat in range(args.repeats):
        sequence = CELLS if repeat % 2 == 0 else tuple(reversed(CELLS))
        for adapter, engine in sequence:
            name = f"{adapter}-{engine}-repeat-{repeat}"
            dest = args.output / name
            dest.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, str(script), "--adapter", adapter,
                   "--engine", engine, "--warmup", str(args.warmup),
                   "--cycles", str(args.cycles), "--output", str(dest),
                   "--tolerance", str(args.tolerance)]
            result = subprocess.run(cmd, capture_output=True, text=True)
            log = dest / "run.log"
            log.write_text(
                "$ " + " ".join(cmd) + "\n" + result.stdout + "\n" + result.stderr,
                encoding="utf-8")
            if result.returncode:
                failures.append(dict(cell=name, returncode=result.returncode, log=str(log)))
                print(f"FAILED {name}: {log}", file=sys.stderr, flush=True)
                print("\n".join(log.read_text(encoding="utf-8").splitlines()[-35:]),
                      file=sys.stderr, flush=True)
                continue
            data = json.loads((dest / f"{adapter}-{engine}.json").read_text(encoding="utf-8"))
            rows.append(dict(repeat=repeat, **data))
            print(f"OK {name}: p50={data['summary']['p50_ms']:.2f} "
                  f"p95={data['summary']['p95_ms']:.2f} "
                  f"p99={data['summary']['p99_ms']:.2f} ms", flush=True)
    parity = []
    for repeat in range(args.repeats):
        observed = [r for r in rows if r["repeat"] == repeat]
        if len(observed) == 4:
            parity.append(dict(repeat=repeat, **compare(observed, args.tolerance)))
    report = {
        "repeats": args.repeats, "warmup": args.warmup, "cycles": args.cycles,
        "budget_ms": 1000 / 60, "failures": failures,
        "cells": [{k: v for k, v in row.items() if k not in ("samples", "rectangles")}
                  for row in rows],
        "geometry_parity": parity,
        "presentation_fps": None, "presentation_frames_dropped": None,
        "note": "Native resize→commit budget only; compositor frames are not measured.",
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if failures or len(rows) != 4 * args.repeats or any(not p["passed"] for p in parity):
        raise SystemExit("Mixed benchmark incomplete or geometry parity failed; see report.json")


if __name__ == "__main__":
    main()
