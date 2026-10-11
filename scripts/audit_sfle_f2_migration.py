"""Auditable source inventory for F2.4, never a public component migration.

Run from repository root:
    python scripts/audit_sfle_f2_migration.py
Underlying exact tracked-source query:
    git grep -n -I -E '(^|[^[:alnum:]_])(Row|Column|Scroll)([^[:alnum:]_]|$)' -- psx docs tests examples

Output counts occurrences (not file names only), matching lines, unique files
and per-surface groups. Save artifacts to /tmp/sfle-f2-inventory/.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import json
import re
import subprocess

COMMAND = [
    "git", "grep", "-n", "-I", "-E",
    r"(^|[^[:alnum:]_])(Row|Column|Scroll)([^[:alnum:]_]|$)",
    "--", "psx", "docs", "tests", "examples",
]
REGEX = re.compile(r"(?<![A-Za-z0-9_])(Row|Column|Scroll)(?![A-Za-z0-9_])")
DESTINATION = Path("/tmp/sfle-f2-inventory")

def main() -> None:
    result = subprocess.run(COMMAND, text=True, capture_output=True, check=False)
    if result.returncode not in (0, 1):
        raise SystemExit(f"Inventory grep failed: {result.stderr}")
    lines = result.stdout.splitlines()
    occurrences = Counter()
    matching_lines = Counter()
    files = {word: set() for word in ("Row", "Column", "Scroll")}
    groups = {word: Counter() for word in files}
    for entry in lines:
        path = entry.split(":", 1)[0]
        category = path.split("/", 1)[0]
        source = entry.split(":", 2)[-1]
        words = REGEX.findall(source)
        for word in words:
            occurrences[word] += 1
            files[word].add(path)
            groups[word][category] += 1
        for word in set(words):
            matching_lines[word] += 1
    assert lines or result.returncode == 1
    payload = {
        "command": " ".join(COMMAND),
        "scope": ["psx", "docs", "tests", "examples"],
        "line_hits_total": len(lines),
        "counts": {
            word: {
                "occurrences": occurrences[word],
                "matching_lines": matching_lines[word],
                "distinct_files": len(files[word]),
                "per_scope_occurrences": dict(sorted(groups[word].items())),
            } for word in ("Row", "Column", "Scroll")
        },
        "matching_files": {word: sorted(files[word]) for word in files},
    }
    DESTINATION.mkdir(parents=True, exist_ok=True)
    (DESTINATION / "inventory.json").write_text(json.dumps(payload, indent=2) + "\n")
    (DESTINATION / "git-grep-matches.txt").write_text(result.stdout)
    print("SFLE F2.4 INVENTORY " + json.dumps({k: v for k, v in payload.items()
          if k != "matching_files"}, sort_keys=True), flush=True)

if __name__ == "__main__":
    main()
