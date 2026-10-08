"""Backward-compatible entry point for :mod:`psx_benchmark`."""

from psx_benchmark import main


if __name__ == "__main__":
    raise SystemExit(main())
