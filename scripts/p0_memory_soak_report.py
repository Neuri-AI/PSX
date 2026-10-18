"""Summarize P0 soak JSON measurements without hiding raw evidence.

Usage: python scripts/p0_memory_soak_report.py artifacts/kivy-memory.json
The diagnostic verdict is descriptive, never a universal RSS leak threshold.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    samples = data["samples"]
    if len(samples) < 2:
        raise ValueError("At least two settled samples are needed for trend analysis.")
    first, last = samples[0], samples[-1]
    keys = (
        "rss_bytes", "tracemalloc_current_bytes",
        "retained_instances", "retained_widgets", "active_event_slots",
    )
    deltas = {
        key: (
            None if first[key] is None or last[key] is None
            else int(last[key]) - int(first[key])
        )
        for key in keys
    }
    tail = samples[max(0, len(samples) // 2):]
    tail_deltas = {
        key: (
            None if tail[0][key] is None or tail[-1][key] is None
            else int(tail[-1][key]) - int(tail[0][key])
        )
        for key in keys
    }
    return {
        "backend": data["backend"],
        "python": data["python"],
        "cycles": data["cycles"],
        "sample_count": len(samples),
        "comparison_range": [first["cycles"], last["cycles"]],
        "first_to_last_deltas_bytes_or_counts": deltas,
        "tail_half_deltas_bytes_or_counts": tail_deltas,
        "final_retained_widgets": last["retained_widgets"],
        "final_retained_instances": last["retained_instances"],
        "final_active_event_slots": last["active_event_slots"],
        "probe_status": data["status"],
        "interpretation": (
            "Positive deltas are investigation signals only. "
            "RSS may retain allocator arenas. This does not prove absence "
            "or presence of native memory leaks; inspect raw series."
        ),
    }


def markdown(summary: dict[str, Any]) -> str:
    output = [
        f"### P0 memory soak: {summary['backend']} / Python {summary['python']}",
        f"Cycles: **{summary['cycles']}**; settled samples: **{summary['sample_count']}**.",
        f"Probe result: \`{summary['probe_status']}\`.",
        "",
        "| Metric | First-to-last delta | Last-half delta |",
        "| --- | ---: | ---: |",
    ]
    for key, change in summary["first_to_last_deltas_bytes_or_counts"].items():
        tail = summary["tail_half_deltas_bytes_or_counts"][key]
        output.append(
            f"| \`{key}\` | {change if change is not None else 'N/A'} "
            f"| {tail if tail is not None else 'N/A'} |"
        )
    output.extend(("", summary["interpretation"], ""))
    return "\n".join(output)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("json_file", type=Path)
    p.add_argument("--summary-out", type=Path)
    p.add_argument("--markdown-out", type=Path)
    args = p.parse_args()
    data = json.loads(args.json_file.read_text(encoding="utf-8"))
    summary = summarize(data)
    print(markdown(summary))
    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(markdown(summary), encoding="utf-8")


if __name__ == "__main__":
    main()
