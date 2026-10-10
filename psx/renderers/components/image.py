"""Portable Image prop normalization and shared geometry helpers.

Backends only need to load the source file, apply the target size to the
widget, and draw the loaded image inside the fit rectangle. All cross-backend
geometry lives here so the four adapters stay small and consistent.
"""

from __future__ import annotations

from collections.abc import Mapping

from psx.core.contracts import IMAGE_DEFAULTS, IMAGE_PROPS, validate_image_props
from psx.core.errors import RendererCapabilityError


def image_props(props: Mapping[str, object]) -> dict[str, object]:
    validate_image_props(props)
    return {**IMAGE_DEFAULTS, **props}


def updated_image_props(
    current: Mapping[str, object],
    changed: Mapping[str, object],
    removed: frozenset[str],
) -> dict[str, object]:
    unknown = (set(changed) | set(removed)) - IMAGE_PROPS
    if unknown:
        raise RendererCapabilityError(
            f"Unsupported Image props: {', '.join(sorted(unknown))}"
        )
    result = {name: value for name, value in current.items() if name not in removed}
    result.update(changed)
    return image_props(result)


def compute_target_size(
    src_w: int,
    src_h: int,
    width: int | None,
    height: int | None,
) -> tuple[int, int]:
    """Compute the widget size given the source dimensions and overrides.

    Both axes set: use them as given.
    Only one axis set: derive the other from the source aspect ratio.
    Neither set: use the source's natural size.
    """
    if width is not None and height is not None:
        return int(width), int(height)
    if width is not None:
        if src_w <= 0:
            return int(width), int(height) if height is not None else 0
        return int(width), max(1, int(round(width * src_h / src_w)))
    if height is not None:
        if src_h <= 0:
            return (int(width) if width is not None else 0), int(height)
        return max(1, int(round(height * src_w / src_h))), int(height)
    return max(0, int(src_w)), max(0, int(src_h))


def compute_fit_rect(
    src_w: int,
    src_h: int,
    dst_w: int,
    dst_h: int,
    fit: str,
) -> tuple[float, float, float, float]:
    """Return ``(x, y, w, h)`` where the source is drawn inside the destination.

    The destination is the widget's own rectangle. ``x`` and ``y`` are offsets
    relative to the widget's top-left, and ``w``/``h`` are the drawn size.
    Callers that cannot draw outside the widget (Qt's ``QLabel``, Tk's
    ``PhotoImage``) will clip the negative offsets automatically.
    """
    if src_w <= 0 or src_h <= 0 or dst_w <= 0 or dst_h <= 0:
        return (0.0, 0.0, float(max(0, dst_w)), float(max(0, dst_h)))

    if fit == "fill":
        return (0.0, 0.0, float(dst_w), float(dst_h))

    if fit == "none":
        x = (dst_w - src_w) / 2
        y = (dst_h - src_h) / 2
        return (float(x), float(y), float(src_w), float(src_h))

    if fit == "contain":
        scale = min(dst_w / src_w, dst_h / src_h)
    elif fit == "cover":
        scale = max(dst_w / src_w, dst_h / src_h)
    else:
        raise ValueError(f"Unknown Image.fit value: {fit!r}")

    new_w = src_w * scale
    new_h = src_h * scale
    x = (dst_w - new_w) / 2
    y = (dst_h - new_h) / 2
    return (float(x), float(y), float(new_w), float(new_h))