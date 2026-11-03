"""Compare dependency metadata from pinned local ecosystem checkouts.

Requires packaging, and tomli on Python 3.10. This is a static checker,
not a substitute for building and installing wheels.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


@dataclass(frozen=True)
class Distribution:
    name: str
    version: str
    dependencies: tuple[str, ...]
    extras: dict[str, tuple[str, ...]]


def metadata(path: Path) -> Distribution:
    with path.open("rb") as handle:
        raw: dict[str, Any] = tomllib.load(handle)
    if "project" in raw:
        project = raw["project"]
        return Distribution(
            project["name"], project["version"],
            tuple(project.get("dependencies", ())),
            {key: tuple(values) for key, values in project.get("optional-dependencies", {}).items()},
        )
    poetry = raw["tool"]["poetry"]
    return Distribution(poetry["name"], poetry["version"], (), {})


def audit(providers: dict[str, Distribution]) -> list[str]:
    errors: list[str] = []
    for consumer in providers.values():
        all_deps = [("base", dep) for dep in consumer.dependencies]
        for extra, requirements in consumer.extras.items():
            all_deps.extend((f"extra:{extra}", dep) for dep in requirements)
        for source, dependency in all_deps:
            req = Requirement(dependency)
            name = canonicalize_name(req.name)
            other = providers.get(name)
            if other is None:
                # Other third-party dependencies are outside this local graph.
                if name in {"psx", "velto", "velto-core", "pydux", "qyro-engine", "qyro-cli"}:
                    errors.append(f"{consumer.name} ({source}): {req} has no local provider")
                continue
            if not req.specifier.contains(other.version, prereleases=True):
                errors.append(
                    f"{consumer.name} ({source}): {req} excludes "
                    f"{other.name}=={other.version}"
                )
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", type=Path, nargs="+", help="paths to ecosystem pyproject.toml files")
    args = parser.parse_args()
    distributions = [metadata(path) for path in args.manifests]
    providers = {canonicalize_name(dist.name): dist for dist in distributions}
    if len(providers) != len(distributions):
        parser.error("duplicate distribution names in manifests")
    problems = audit(providers)
    for problem in problems:
        print("CONFLICT:", problem)
    print(f"Checked {len(providers)} local distributions; {len(problems)} compatibility conflicts")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
