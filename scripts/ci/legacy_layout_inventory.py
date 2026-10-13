"""Inventory active legacy layout references before retiring their public API.

Use --check at the final removal gate; without it, report migration targets.
Documentation and historical architecture records are intentionally excluded.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


LEGACY_LAYOUTS = frozenset({"Row", "Column"})
LEGACY_PRIVATE = re.compile(
    r"^(?:ROW|COLUMN)_(?:CONTRACT|PROPS|DEFAULTS)$"
    r"|^(?:Qt|Tk|Kivy)(?:Row|Column)Adapter$"
    r"|^validate_(?:row|column)_props$"
)


@dataclass(frozen=True, slots=True)
class LegacyReference:
    path: str
    line: int
    symbol: str
    usage: str


def references(path: str, source: str) -> tuple[LegacyReference, ...]:
    """Classify executable identifiers and component-name literals."""
    tree = ast.parse(source, filename=path)
    found: set[LegacyReference] = set()

    class Inspector(ast.NodeVisitor):
        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            for imported in node.names:
                if imported.name in LEGACY_LAYOUTS or LEGACY_PRIVATE.fullmatch(imported.name):
                    found.add(LegacyReference(path, node.lineno, imported.name, "import"))
            self.generic_visit(node)

        def visit_Import(self, node: ast.Import) -> None:
            for imported in node.names:
                symbol = imported.name.rsplit(".", 1)[-1]
                if symbol in LEGACY_LAYOUTS or LEGACY_PRIVATE.fullmatch(symbol):
                    found.add(LegacyReference(path, node.lineno, symbol, "import"))
            self.generic_visit(node)

        def visit_Name(self, node: ast.Name) -> None:
            if node.id in LEGACY_LAYOUTS:
                found.add(LegacyReference(path, node.lineno, node.id, "identifier"))
            elif LEGACY_PRIVATE.fullmatch(node.id):
                found.add(LegacyReference(path, node.lineno, node.id, "legacy_adapter_or_contract"))
            self.generic_visit(node)

        def visit_Attribute(self, node: ast.Attribute) -> None:
            if node.attr in LEGACY_LAYOUTS:
                found.add(LegacyReference(path, node.lineno, node.attr, "attribute"))
            elif LEGACY_PRIVATE.fullmatch(node.attr):
                found.add(LegacyReference(path, node.lineno, node.attr, "legacy_adapter_or_contract"))
            self.generic_visit(node)

        def visit_Constant(self, node: ast.Constant) -> None:
            if isinstance(node.value, str):
                for symbol in LEGACY_LAYOUTS:
                    if node.value == symbol:
                        found.add(LegacyReference(path, node.lineno, symbol, "component_name"))
                    elif f"<{symbol}" in node.value or f"</{symbol}" in node.value:
                        found.add(LegacyReference(path, node.lineno, symbol, "markup"))
            self.generic_visit(node)

    Inspector().visit(tree)
    return tuple(sorted(found, key=lambda item: (item.line, item.symbol, item.usage)))


def tracked_python_files(root: Path) -> tuple[Path, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.py"], cwd=root,
        capture_output=True, check=True,
    )
    return tuple(
        root / name.decode("utf-8")
        for name in result.stdout.split(b"\x00")
        if name and (root / name.decode("utf-8")).is_file()
    )


def inventory(root: Path) -> tuple[LegacyReference, ...]:
    found: list[LegacyReference] = []
    for file in tracked_python_files(root):
        relative = file.relative_to(root).as_posix()
        if relative.startswith(("docs/", "archive/")):
            continue
        found.extend(references(relative, file.read_text(encoding="utf-8")))
    return tuple(sorted(found, key=lambda item: (item.path, item.line, item.symbol)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    found = inventory(args.root)
    payload = {
        "count": len(found),
        "files": len({item.path for item in found}),
        "references": [asdict(item) for item in found],
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if args.check and found:
        raise SystemExit(f"Legacy portable layout references remain: {len(found)}")


if __name__ == "__main__":
    main()
