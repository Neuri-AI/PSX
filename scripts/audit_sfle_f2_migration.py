"""Reproducible F2.4 inventory of PSX and explicitly supplied external repositories.

Default repository-wide inventory (unchanged):
    python scripts/audit_sfle_f2_migration.py
Complete cross-repository snapshot:
    python scripts/audit_sfle_f2_migration.py \
        --external-root qt=/path/to/qyro-boilerplate-qt \
        --external-root kivy=/path/to/qyro-boilerplate-kivy \
        --external-root tkinter=/path/to/qyro-boilerplate-tkinter

The external roots are clean Git checkouts; each result records its exact HEAD.
Absent, dirty or invalid external roots are fatal rather than silently skipped.
This is F2.4 evidence/inventory, NEVER a Row/Column/Scroll public migration.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess

PATTERN = r"(^|[^[:alnum:]_])(Row|Column|Scroll)([^[:alnum:]_]|$)"
COMMAND = [
    "git", "grep", "-n", "-I", "-E", PATTERN,
    "--", "psx", "docs", "tests", "examples",
]
REGEX = re.compile(r"(?<![A-Za-z0-9_])(Row|Column|Scroll)(?![A-Za-z0-9_])")
DESTINATION = Path("/tmp/sfle-f2-inventory")
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    # Git emits repository text as UTF-8 independently of the Windows console
    # code page. Replacing malformed source bytes keeps the token inventory
    # deterministic and lets the audit report an actual Git failure instead of
    # a locale-dependent decoder crash.
    return subprocess.run(
        command, text=True, encoding="utf-8", errors="replace",
        capture_output=True, check=False,
    )


def _inventory(lines: list[str]) -> dict[str, object]:
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
    return {
        "line_hits_total": len(lines),
        "counts": {
            word: {
                "occurrences": occurrences[word],
                "matching_lines": matching_lines[word],
                "distinct_files": len(files[word]),
                "per_scope_occurrences": dict(sorted(groups[word].items())),
            }
            for word in ("Row", "Column", "Scroll")
        },
        "matching_files": {word: sorted(files[word]) for word in files},
    }


def _external_root(specification: str) -> tuple[str, Path]:
    name, separator, raw_path = specification.partition("=")
    if not separator or not IDENTIFIER.fullmatch(name) or not raw_path:
        raise SystemExit(f"Invalid --external-root; expected identifier=/absolute/checkout: {specification}")
    path = Path(raw_path).resolve()
    if not path.is_dir():
        raise SystemExit(f"Missing external Git checkout for {name}: {path}")
    top = _run(["git", "-C", str(path), "rev-parse", "--show-toplevel"])
    if top.returncode != 0 or Path(top.stdout.strip()).resolve() != path:
        raise SystemExit(f"External root {name} is not a Git repository root: {path}")
    return name, path


def _scan_external(name: str, path: Path) -> tuple[dict[str, object], str]:
    sha = _run(["git", "-C", str(path), "rev-parse", "HEAD"])
    if sha.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", sha.stdout.strip()):
        raise SystemExit(f"External {name} has no valid Git HEAD: {path}")
    dirty = _run(["git", "-C", str(path), "status", "--porcelain", "--untracked-files=no"])
    if dirty.returncode != 0 or dirty.stdout.strip():
        raise SystemExit(f"External {name} contains dirty tracked source; commit it before inventory.")
    command = ["git", "-C", str(path), "grep", "-n", "-I", "-E", PATTERN, "--", "."]
    matches = _run(command)
    if matches.returncode not in (0, 1):
        raise SystemExit(f"External inventory for {name} failed: {matches.stderr}")
    remote = _run(["git", "-C", str(path), "remote", "get-url", "origin"])
    return {
        "commit_sha": sha.stdout.strip(),
        "repository_url": remote.stdout.strip() if remote.returncode == 0 else None,
        "command": " ".join(command),
        **_inventory(matches.stdout.splitlines()),
    }, matches.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description="Auditable F2.4 tracked source inventory")
    parser.add_argument("--external-root", action="append", default=[],
                        metavar="IDENTIFIER=PATH", help="Clean external repository checkout")
    parser.add_argument("--output-dir", type=Path, default=DESTINATION)
    options = parser.parse_args()

    result = _run(COMMAND)
    if result.returncode not in (0, 1):
        raise SystemExit(f"Inventory grep failed: {result.stderr}")
    payload = {
        "command": " ".join(COMMAND),
        "scope": ["psx", "docs", "tests", "examples"],
        **_inventory(result.stdout.splitlines()),
    }
    external = {}
    external_lines = []
    for specification in options.external_root:
        name, path = _external_root(specification)
        if name in external:
            raise SystemExit(f"Duplicate external checkout identifier: {name}")
        report, lines = _scan_external(name, path)
        external[name] = report
        external_lines.append(f"### {name} @ {report['commit_sha']}\n{lines}")
    payload["external_repositories"] = external

    destination = options.output_dir
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "inventory.json").write_text(json.dumps(payload, indent=2) + "\n")
    (destination / "git-grep-matches.txt").write_text(result.stdout)
    (destination / "external-git-grep-matches.txt").write_text("".join(external_lines))
    print("SFLE F2.4 INVENTORY " + json.dumps({
        k: v for k, v in payload.items() if k != "matching_files"
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
