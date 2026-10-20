"""CSS source graph: local files, optional resource resolvers and relative imports.

Source parsing is independent of Qyro. A resolver may supply bytes from an
encrypted package without creating an intermediate plaintext file.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
import re

from .parser import Rule, Stylesheet, parse_stylesheet

ResourceResolver = Callable[[str], bytes | str]
_IMPORT = re.compile(r'^\s*@import\s+["\']([^"\']+\.css)["\']\s*;\s*', re.I)


@dataclass(frozen=True, slots=True)
class CssSource:
    path: str
    contents: str


class CssSourceManager:
    def __init__(self, resolver: ResourceResolver | None = None, *, root: str | Path = ".") -> None:
        self._resolver = resolver
        self._root = Path(root).resolve()

    def _read(self, name: str) -> str:
        if self._resolver is not None:
            value = self._resolver(name)
        else:
            target = (self._root / name).resolve()
            if not target.is_relative_to(self._root):
                raise ValueError("CSS resource path escapes the project root.")
            value = target.read_bytes()
        if isinstance(value, bytes):
            return value.decode("utf-8-sig")
        if isinstance(value, str):
            return value
        raise TypeError("CSS resource resolver must return bytes or text.")

    def load(self, paths: Iterable[str]) -> Stylesheet:
        rules: list[Rule] = []
        active: set[str] = set()
        def visit(name: str) -> None:
            candidate = Path(name)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise ValueError("Absolute and parent-traversing CSS resource paths are not supported.")
            normalized = candidate.as_posix()
            if normalized in active:
                raise ValueError(f"Circular CSS import: {normalized}")
            active.add(normalized)
            try:
                source = self._read(normalized)
                while True:
                    match = _IMPORT.match(source)
                    if match is None:
                        break
                    dependency = (candidate.parent / match.group(1)).as_posix()
                    visit(dependency)
                    source = source[match.end():]
                if "@import" in source:
                    raise ValueError("CSS @import must be a leading quoted .css path.")
                parsed = parse_stylesheet(source)
                for item in parsed.rules:
                    rules.append(Rule(item.selectors, item.declarations, len(rules)))
            finally:
                active.remove(normalized)
        for path in paths:
            visit(path)
        return Stylesheet(tuple(rules))
