"""Strict internal CSS paint and typography value validation.

These values are not yet dispatched to native renderers. Unsupported values
raise clear errors instead of silently changing a widget.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from psx.sfle.lengths import Length, LengthKind, parse_length


@dataclass(frozen=True, slots=True)
class CssColor:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not re.fullmatch(
            r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F])?|#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?", self.value
        ):
            raise ValueError("Expected a #RGB, #RGBA, #RRGGBB or #RRGGBBAA color.")
        object.__setattr__(self, "value", self.value.lower())


VISUAL_EFFECTS = {
    "color": "paint",
    "background-color": "paint",
    "border-color": "paint",
    "border-top-color": "paint",
    "border-right-color": "paint",
    "border-bottom-color": "paint",
    "border-left-color": "paint",
    "font-family": "measurement",
    "font-size": "measurement",
    "font-weight": "measurement",
    "line-height": "measurement",
    "text-align": "paint",
    "border-radius": "paint",
}


def normalize_visual_value(name: str, value: str) -> CssColor | Length | int | str:
    if name not in VISUAL_EFFECTS:
        raise ValueError(f"Unsupported visual CSS property: {name!r}.")
    if name in ("color", "background-color", "border-color", "border-top-color", "border-right-color", "border-bottom-color", "border-left-color"):
        # Common CSS named colors accepted by the portable native paint layer.
        # Normalize before typed hex validation so renderers share one format.
        named = {
            "black": "#000000", "white": "#ffffff", "red": "#ff0000",
            "green": "#008000", "blue": "#0000ff", "yellow": "#ffff00",
            "cyan": "#00ffff", "aqua": "#00ffff", "magenta": "#ff00ff",
            "fuchsia": "#ff00ff", "gray": "#808080", "grey": "#808080",
            "silver": "#c0c0c0", "maroon": "#800000", "olive": "#808000",
            "purple": "#800080", "teal": "#008080", "navy": "#000080",
            "lime": "#00ff00",
        }
        if isinstance(value, str):
            value = named.get(value.strip().lower(), value)
        return value if isinstance(value, CssColor) else CssColor(value)
    if name in ("font-size", "line-height", "border-radius"):
        parsed = parse_length(value)
        if parsed.kind not in (LengthKind.PX, LengthKind.PERCENT) or (
            parsed.value is not None and parsed.value < 0
        ):
            raise ValueError(f"Unsupported CSS size for {name!r}.")
        if name == "border-radius" and parsed.kind == LengthKind.PERCENT:
            return parsed
        return parsed
    if name == "font-weight":
        if type(value) is int and value in range(100, 1000, 100):
            return value
        if value in ("normal", "bold"):
            return 400 if value == "normal" else 700
        if value in {str(x) for x in range(100, 1000, 100)}:
            return int(value)
        raise ValueError("Unsupported font-weight.")
    if name == "font-family":
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise ValueError("Unsupported font-family.")
        # CSS font stacks permit quoted family names and generic fallbacks.
        # Keep the original list so native renderers can choose a supported
        # installed face without treating quotes as part of the family name.
        names = [part.strip() for part in value.split(",")]
        if not names or any(not part for part in names):
            raise ValueError("Unsupported font-family.")
        validated = []
        for part in names:
            if part[0] in ("'", '"'):
                if len(part) < 3 or part[-1] != part[0]:
                    raise ValueError("Unsupported font-family.")
                family = part[1:-1]
            else:
                family = part
            if not re.fullmatch(r"[a-zA-Z0-9 _.-]{1,128}", family) or not family.strip():
                raise ValueError("Unsupported font-family.")
            validated.append(family)
        return ", ".join(validated)
    if name == "text-align":
        if value not in ("left", "right", "center", "start", "end", "justify"):
            raise ValueError("Unsupported text-align.")
        return value
    raise AssertionError("Unreachable CSS validator.")
