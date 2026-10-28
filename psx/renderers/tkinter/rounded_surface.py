"""Tk canvas painter for one CSS-owned rounded semantic-host surface.

The host's native children remain real widgets; only background and borders
are painted here. Tk Canvas is opaque, so outside-corner pixels are composited
against the nearest SOLID native/CSS parent surface. This is not general alpha
compositing over images or animated backgrounds.
"""
from __future__ import annotations

import base64
import math
import struct
import zlib
from typing import Mapping

import tkinter as tk


def _png_rgb(width: int, height: int, pixels: bytes) -> str:
    """Encode small antialiased corner patches with the Python standard library."""
    if len(pixels) != width * height * 3:
        raise ValueError("Corner image RGB buffer does not match dimensions.")

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (struct.pack("!I", len(body)) + kind + body
                + struct.pack("!I", zlib.crc32(kind + body) & 0xFFFFFFFF))

    rows = b"".join(
        b"\x00" + pixels[y * width * 3:(y + 1) * width * 3]
        for y in range(height)
    )
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(rows, 6))
           + chunk(b"IEND", b""))
    return base64.b64encode(png).decode("ascii")


def _rgb(widget: tk.Misc, color: str) -> tuple[int, int, int]:
    return tuple(round(channel / 257) for channel in widget.winfo_rgb(color))


def _corner_pixels(
    radius: int,
    corner: str,
    parent: tuple[int, int, int],
    fill: tuple[int, int, int],
    sides: Mapping[str, tuple[float, tuple[int, int, int]]],
) -> bytes:
    """Supersample each boundary pixel from the SAME circular border geometry."""
    # QSS rasterizes its rounded border on a subtly inset subpixel path.
    # Quarter-pixel coverage aligns Tk's bitmap corners with Qt's QSS at
    # small radii without altering the CSS radius or Cinnamon's layout box.
    center = radius + 0.25
    centers = {"tl": (center, center), "tr": (-0.25, center),
               "bl": (center, -0.25), "br": (-0.25, -0.25)}
    if corner not in centers:
        raise ValueError("Unrecognized CSS corner.")
    cx, cy = centers[corner]
    output = bytearray()
    samples = (0.125, 0.375, 0.625, 0.875)
    for y in range(radius):
        for x in range(radius):
            totals = [0, 0, 0]
            for sy in samples:
                for sx in samples:
                    dx, dy = x + sx - cx, y + sy - cy
                    distance = math.hypot(dx, dy)
                    shade = parent
                    if distance <= center:
                        shade = fill
                        # The two adjacent sides split their corner at 45deg.
                        side = ("top" if corner in ("tl", "tr") else "bottom"
                                ) if abs(dy) >= abs(dx) else (
                                    "left" if corner in ("tl", "bl") else "right")
                        ink = sides.get(side)
                        if ink is not None and distance > center - ink[0]:
                            shade = ink[1]
                    for index, channel in enumerate(shade):
                        totals[index] += channel
            output.extend(round(value / 16) for value in totals)
    return bytes(output)


def draw_rounded_surface(
    canvas: tk.Canvas,
    *,
    width: int,
    height: int,
    radius: int,
    parent_color: str,
    fill_color: str | None,
    sides: Mapping[str, tuple[float, str]],
) -> None:
    """Repaint one owned Canvas from the canonical border-box geometry.

    Keep one set of corner images per canvas/paint style. Resizing moves
    existing items; corner rasterization depends on the effective radius and
    colors/strokes, not the full surface dimensions. No global Tk resources.
    """
    items = getattr(canvas, "_psx_css_surface_items", {})
    if width < 1 or height < 1:
        canvas.delete("all")
        canvas._psx_css_surface_items = {}
        canvas._psx_css_corner_images = ()
        canvas._psx_css_corner_revision = None
        return
    r = min(max(0, radius), width // 2, height // 2)
    canvas.configure(background=parent_color, highlightthickness=0, borderwidth=0)
    fill = fill_color or parent_color
    active = set()

    def rectangle(name, bounds, ink, tags):
        active.add(name)
        if name in items:
            canvas.coords(items[name], *bounds)
            canvas.itemconfigure(items[name], fill=ink)
        else:
            items[name] = canvas.create_rectangle(
                *bounds, fill=ink, outline="", tags=tags)

    # The two non-corner rectangles and all strokes share one Canvas.
    if r == 0:
        rectangle("fill-center", (0, 0, width, height), fill,
                  ("psx-css-surface-fill",))
    else:
        rectangle("fill-center", (r, 0, width - r, height), fill,
                  ("psx-css-surface-fill",))
        rectangle("fill-middle", (0, r, width, height - r), fill,
                  ("psx-css-surface-fill",))

    # The straight edge stops exactly where the corner image begins.
    for side, (thickness, ink) in sides.items():
        if thickness <= 0:
            continue
        t = float(thickness)
        edges = {
            "top": (r, 0, width - r, t),
            "right": (width - t, r, width, height - r),
            "bottom": (r, height - t, width - r, height),
            "left": (0, r, t, height - r),
        }
        rectangle(f"side-{side}", edges[side], ink,
                  ("psx-css-surface-side", f"psx-css-{side}"))

    if r == 0:
        canvas._psx_css_corner_images = ()
        canvas._psx_css_corner_revision = None
    else:
        revision = (r, parent_color, fill, tuple(sorted(sides.items())))
        images = getattr(canvas, "_psx_css_corner_images", ())
        if revision != getattr(canvas, "_psx_css_corner_revision", None):
            rgb_parent, rgb_fill = _rgb(canvas, parent_color), _rgb(canvas, fill)
            rgb_sides = {
                side: (thickness, _rgb(canvas, ink))
                for side, (thickness, ink) in sides.items()
            }
            images = tuple(tk.PhotoImage(
                master=canvas, data=_png_rgb(r, r, _corner_pixels(
                    r, corner, rgb_parent, rgb_fill, rgb_sides)), format="png",
            ) for corner in ("tl", "tr", "bl", "br"))
        positions = {"tl": (0, 0), "tr": (width - r, 0),
                     "bl": (0, height - r), "br": (width - r, height - r)}
        for (corner, (x, y)), image in zip(positions.items(), images):
            name = f"corner-{corner}"
            active.add(name)
            if name in items:
                canvas.coords(items[name], x, y)
                canvas.itemconfigure(items[name], image=image)
            else:
                items[name] = canvas.create_image(
                    x, y, anchor="nw", image=image,
                    tags=("psx-css-surface-corner", f"psx-css-{corner}"))
        canvas._psx_css_corner_images = images
        canvas._psx_css_corner_revision = revision

    for name in set(items) - active:
        canvas.delete(items.pop(name))
    # A new fill or stroke can be created above an existing corner during
    # style changes. Keep the same painter ordering as a fresh surface.
    canvas.tag_lower("psx-css-surface-fill")
    canvas.tag_raise("psx-css-surface-corner")
    canvas._psx_css_surface_items = items
