"""Resolve literal HTML img sources using the same application resource roots as CSS.

The application resource facade is optional: PSX remains usable without Qyro.
The markup layer resolves a source once per render; native image adapters
continue receiving filesystem paths via their established Image.source prop.
"""

from __future__ import annotations

from pathlib import Path


def resolve_markup_image_source(value: str) -> str:
    """Prefer a packaged Qyro resource; keep ordinary filesystem paths valid."""
    if not isinstance(value, str) or not value:
        raise ValueError("img src must be a non-empty path string.")
    if "://" in value or value.startswith(("qrc:", "atlas:")):
        return value
    original = Path(value)
    if original.is_absolute():
        return value

    try:
        from qyro import get_resource
    except ImportError:
        get_resource = None
    if get_resource is not None:
        # required=False avoids treating normal filesystem fallbacks as errors.
        candidate = Path(get_resource(value, required=False))
        if candidate.is_file():
            return str(candidate)

    from psx.css.context import current_css_context
    context = current_css_context()
    if context is not None:
        candidate = (context.root / value).resolve()
        if candidate.is_relative_to(context.root.resolve()) and candidate.is_file():
            return str(candidate)

    return value
