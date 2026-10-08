"""Run a PSX application under the development supervisor."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import HotReloadConfig
from .supervisor import DevelopmentSupervisor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a PSX application with supervised hot reload.")
    parser.add_argument("entry", type=Path, help="Python entry-point file")
    parser.add_argument("--root", type=Path, help="Project root (defaults to the entry parent)")
    parser.add_argument("--debounce", type=float, default=0.25)
    args = parser.parse_args(argv)
    entry = args.entry.resolve()
    root = (args.root or entry.parent).resolve()
    config = HotReloadConfig(enabled=True, development=True, root=root, debounce_seconds=args.debounce)
    return DevelopmentSupervisor([sys.executable, str(entry)], root=root, config=config).run()


if __name__ == "__main__":
    raise SystemExit(main())
