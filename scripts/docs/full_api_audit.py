"""G1 exhaustive *declared surface* inventory (not a native execution certificate).

The program audits root and package __all__, actual signatures, the builtin
registry, contracts, and test references. Generated snapshots fail on drift.
"""
from __future__ import annotations

import argparse
import ast
import importlib
import inspect
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _describe(obj: object) -> dict[str, object]:
    try:
        signature = str(inspect.signature(obj))
    except (TypeError, ValueError):
        signature = None
    try:
        source_object = type(obj) if callable(obj) and not (inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismethod(obj)) else obj
        file = inspect.getsourcefile(source_object) or inspect.getfile(source_object)
        source = str(Path(file).resolve().relative_to(ROOT))
        _, line = inspect.getsourcelines(source_object)
    except (TypeError, OSError, ValueError):
        source, line = None, None
    return {
        "kind": "class" if inspect.isclass(obj) else "callable" if callable(obj) else "constant",
        "signature": signature,
        "implementation": source,
        "line": line,
        "docstring": (inspect.getdoc(obj) or "").splitlines()[0:1],
    }


def collect() -> dict[str, object]:
    import psx
    import psx.markup
    import psx.renderers
    from psx.core.registry import builtin_component_registry

    modules = [psx, psx.markup, psx.renderers]
    additional = (
        "psx.plugins", "psx.core.errors", "psx.core.hooks",
        "psx.core.registry", "psx.core.native", "psx.core.vnode",
        "psx.integrations.qyro",
    )
    test_files = sorted((ROOT / "tests").rglob("test_*.py"))
    test_sources = {str(p.relative_to(ROOT)): p.read_text(encoding="utf-8")
                    for p in test_files}
    public: dict[str, dict[str, object]] = {}
    for module in modules:
        names = getattr(module, "__all__", None)
        if not isinstance(names, list) or len(names) != len(set(names)):
            raise ValueError(f"{module.__name__} requires unique explicit __all__")
        for name in names:
            obj = getattr(module, name)
            record = _describe(obj)
            # Candidate references are NOT equivalent to executed behavioral evidence.
            record["candidate_test_files"] = [path for path, body in test_sources.items()
                                               if name in body]
            public[f"{module.__name__}.{name}"] = record
    supplemental: dict[str, list[str]] = {}
    for module_name in additional:
        module = importlib.import_module(module_name)
        file = Path(module.__file__)
        tree = ast.parse(file.read_text(encoding="utf-8"))
        declared = sorted({
            node.name for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        })
        supplemental[module_name] = declared
        for name in declared:
            record = _describe(getattr(module, name))
            record["candidate_test_files"] = [path for path, body in test_sources.items()
                                               if name in body]
            public[f"{module_name}.{name}"] = record

    components: dict[str, dict[str, object]] = {}
    registry = builtin_component_registry()
    for name, definition in sorted(registry.snapshot().items()):
        contract = definition.contract
        components[name] = {
            "public_root_export": name in psx.__all__,
            "registry_constructor": _describe(definition.constructor),
            "contract": None if contract is None else {
                "properties": sorted(contract.properties),
                "defaults": {k: repr(v) for k, v in sorted(contract.defaults.items())},
                "events": sorted(contract.events),
                "child_policy": contract.child_policy,
                "content_property": contract.content_property,
            },
        }

    return {
        "schema_version": 1,
        "scope": "declared psx, psx.markup, psx.renderers __all__ plus builtin registry",
        "modules": {m.__name__: list(m.__all__) for m in modules},
        "symbols": dict(sorted(public.items())),
        "registered_components": components,
        "additional_declared_modules": supplemental,
        "test_reference_policy": "candidate string references only; not executable test proof",
        "limitations": [
            "Supplemental submodule declarations need a normative public/private API boundary",
            "Signatures are runtime introspection; no behavioral verification inferred",
            "Registry presence does not prove native renderer support",
            "Optional Qyro/Pydux integrations are not certified by this inventory",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args()
    if bool(args.write) == bool(args.check):
        parser.error("Choose exactly one of --write or --check")
    output = json.dumps(collect(), indent=2, ensure_ascii=False) + "\n"
    target = args.write or args.check
    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding="utf-8")
    elif target.read_text(encoding="utf-8") != output:
        raise SystemExit("G1 declared API census drift; regenerate and review source changes")
    print("G1 declared API snapshot validated")


if __name__ == "__main__":
    main()
