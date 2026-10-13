"""Hand-calculated geometry witnesses for the admitted Headless surface."""
from dataclasses import dataclass

from psx.sfle.model import Rect


@dataclass(frozen=True)
class GeometryCase:
    prop: str
    before: object
    after: object
    before_rect: Rect
    after_rect: Rect
    viewport_width: int = 400


BASE = Rect(0, 0, 40, 20)
CASES = [
    GeometryCase("layout_width", 40, 60, BASE, Rect(0, 0, 60, 20)),
    GeometryCase("layout_height", 20, 40, BASE, Rect(0, 0, 40, 40)),
    GeometryCase("layout_min_width", 0, 80, BASE, Rect(0, 0, 80, 20)),
    GeometryCase("layout_min_height", 0, 40, BASE, Rect(0, 0, 40, 40)),
    GeometryCase("layout_max_width", 100, 20, BASE, Rect(0, 0, 20, 20)),
    GeometryCase("layout_max_height", 100, 10, BASE, Rect(0, 0, 40, 10)),
    GeometryCase("flex_basis", 40, 60, BASE, Rect(0, 0, 60, 20)),
    GeometryCase("flex_grow", 0, 1, BASE, Rect(0, 0, 360, 20)),
    GeometryCase("flex_shrink", 0, 1, BASE, Rect(0, 0, 20, 20), 60),
    GeometryCase("align_self", "flex-start", "center", BASE, Rect(0, 50, 40, 20)),
    GeometryCase("order", 0, 2, BASE, Rect(40, 0, 40, 20)),
]
for kind in ("padding", "border"):
    for edge in ("top", "right", "bottom", "left"):
        width, height = (50, 20) if edge in ("left", "right") else (40, 30)
        CASES.append(GeometryCase(f"layout_{kind}_{edge}", 0, 10,
                                  BASE, Rect(0, 0, width, height)))
for edge in ("top", "right", "bottom", "left"):
    rect = Rect(10 if edge == "left" else 0,
                10 if edge == "top" else 0, 40, 20)
    CASES.append(GeometryCase(f"layout_margin_{edge}", 0, 10, BASE, rect))
GEOMETRY_CASES = tuple(CASES)
