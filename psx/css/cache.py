"""Bounded, instance-owned CSS parse and computed-style cache.

Cache entries hold only immutable stylesheet and style fingerprints, never
mounted VNodes, native handles, callbacks or renderer instances.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from .cascade import ComputedStyle, StyleTarget, resolve_style
from .parser import Stylesheet, parse_stylesheet
from .properties import CssDeclaration


@dataclass(frozen=True, slots=True)
class StyleCacheStats:
    parses: int
    computations: int
    hits: int
    evictions: int
    entries: int


class StyleResolver:
    def __init__(self, *, max_entries: int = 256) -> None:
        if type(max_entries) is not int or max_entries < 1:
            raise ValueError("max_entries must be a positive integer.")
        self.max_entries = max_entries
        self._sheets: OrderedDict[str, Stylesheet] = OrderedDict()
        self._styles: OrderedDict[tuple[object, ...], ComputedStyle] = OrderedDict()
        self._parses = 0
        self._computations = 0
        self._hits = 0
        self._evictions = 0

    def _remember(self, cache: OrderedDict, key: object, value: object) -> None:
        cache[key] = value
        cache.move_to_end(key)
        if len(cache) > self.max_entries:
            cache.popitem(last=False)
            self._evictions += 1

    def resolve(
        self,
        source: str,
        target: StyleTarget,
        *,
        inline: tuple[CssDeclaration, ...] = (),
        inherited: ComputedStyle | None = None,
    ) -> ComputedStyle:
        sheet = self._sheets.get(source)
        if sheet is None:
            sheet = parse_stylesheet(source)
            self._parses += 1
            self._remember(self._sheets, source, sheet)
        else:
            self._sheets.move_to_end(source)
        inherited_key = tuple(sorted(inherited.properties.items())) if inherited is not None else ()
        # Hashing the key rejects mutable/untrusted payloads rather than retaining them.
        key = (source, target, inline, inherited_key)
        try:
            hash(key)
        except TypeError as error:
            raise ValueError("CSS cache keys must contain immutable values.") from error
        existing = self._styles.get(key)
        if existing is not None:
            self._styles.move_to_end(key)
            self._hits += 1
            return existing
        computed = resolve_style(sheet, target, inline=inline, inherited=inherited)
        self._computations += 1
        self._remember(self._styles, key, computed)
        return computed

    def clear(self) -> None:
        self._sheets.clear()
        self._styles.clear()

    @property
    def stats(self) -> StyleCacheStats:
        return StyleCacheStats(
            self._parses, self._computations, self._hits, self._evictions,
            len(self._sheets) + len(self._styles),
        )
