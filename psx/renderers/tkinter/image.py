"""Built-in Image adapter for the Tkinter renderer.

Uses Pillow (PIL) to load and resize images, and tkinter.PhotoImage through
ImageTk.PhotoImage for display. Tk's native PhotoImage supports only integer
zoom/subsample and no arbitrary float scaling, so Pillow is effectively
required for anything beyond showing the source at its natural size.

If Pillow is not installed, the adapter falls back to tk.PhotoImage at
native size, ignoring width, height, and fit. In that mode a JPEG or SVG
source will raise a capability error because Tk cannot load those formats.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from psx.core.contracts import IMAGE_DEFAULTS
from psx.core.errors import RendererCapabilityError
from psx.renderers.components.image import (
    compute_fit_rect,
    compute_target_size,
    image_props,
    updated_image_props,
)

try:
    from PIL import Image as PILImage, ImageTk
    _HAS_PIL = True
except ImportError:  # pragma: no cover - depends on optional Pillow
    _HAS_PIL = False


class TkImageAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.tkinter.tkinter import TkHandle
        props = image_props({**IMAGE_DEFAULTS, **node.props})

        master = parent.widget if parent is not None else renderer.root
        widget = ttk.Label(master)
        widget._psx_source = None
        widget._psx_image_cache = None
        widget._psx_photo = None  # keep the PhotoImage alive
        widget._psx_props = props
        widget._psx_sfle_image = renderer._sfle_constraints is not None

        self._load_and_apply(widget, props)
        return TkHandle("Image", widget, props)

    def update(self, renderer, handle, changed, removed):
        props = updated_image_props(handle.props, changed, removed)
        handle.props = props
        widget = handle.widget
        widget._psx_props = props
        self._load_and_apply(widget, props)

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(
            f"Image does not emit events, got {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        widget = handle.widget
        if widget.winfo_exists():
            widget.configure(image="")
            widget.destroy()
        # Tcl image objects and Pillow buffers may outlive widget destruction
        # while external observers still hold a Python handle.
        widget._psx_photo = None
        widget._psx_image_cache = None
        widget._psx_source = None
        widget._psx_props = None
        handle.props = {}

    @staticmethod
    def _load_and_apply(widget, props):
        source = props["source"]

        if not _HAS_PIL:
            # Fallback: native PhotoImage at natural size only.
            if widget._psx_source != source:
                try:
                    widget._psx_image_cache = tk.PhotoImage(file=source)
                except tk.TclError as error:
                    raise RendererCapabilityError(
                        f"Tkinter could not load {source!r}. Install Pillow "
                        f"for JPEG, arbitrary scaling, and width/height support."
                    ) from error
                widget._psx_source = source
            widget._psx_photo = widget._psx_image_cache
            widget.configure(image=widget._psx_photo, text="")
            return

        # Full path with Pillow.
        if widget._psx_source != source:
            try:
                with PILImage.open(source) as decoded:
                    widget._psx_image_cache = decoded.convert("RGBA")
            except (OSError, PILImage.UnidentifiedImageError):
                widget._psx_image_cache = None
            widget._psx_source = source

        pil = widget._psx_image_cache
        if pil is None:
            widget.configure(image="", text=props["alt"])
            widget._psx_photo = None
            return

        src_w, src_h = pil.size
        target_w, target_h = compute_target_size(
            src_w, src_h, props["width"], props["height"],
        )
        if target_w <= 0 or target_h <= 0:
            widget.configure(image="", text=props["alt"])
            widget._psx_photo = None
            return

        x, y, w, h = compute_fit_rect(
            src_w, src_h, target_w, target_h, props["fit"],
        )
        scaled = pil.resize(
            (max(1, int(round(w))), max(1, int(round(h)))),
            PILImage.LANCZOS,
        )
        canvas = PILImage.new(
            "RGBA", (int(target_w), int(target_h)), (0, 0, 0, 0),
        )
        canvas.paste(scaled, (int(round(x)), int(round(y))), scaled)
        photo = ImageTk.PhotoImage(canvas)
        widget._psx_photo = photo
        widget.configure(image=photo, text="")
    @staticmethod
    def paint_sfle(widget, width: int, height: int) -> None:
        """Recompose a loaded image inside the final SFLE native place rectangle."""
        source = widget._psx_image_cache
        if source is None:
            raise RendererCapabilityError("Tk Image has no decoded source for SFLE painting.")
        props = widget._psx_props
        if width <= 0 or height <= 0:
            widget.configure(image="", text="")
            return
        if not _HAS_PIL:
            # Tk's built-in PhotoImage has no arbitrary fractional resize.
            # A source without Pillow is still usable at native dimensions,
            # otherwise fail explicitly rather than paint a wrong fit.
            if (width, height) != (source.width(), source.height()) or props["fit"] not in ("none", "contain"):
                raise RendererCapabilityError(
                    "Tk SFLE Image requires Pillow for scaling/cropping; "
                    "install Pillow or use the source's intrinsic dimensions."
                )
            widget._psx_photo = source
            widget.configure(image=source, text="")
            return
        sw, sh = source.size
        x, y, w, h = compute_fit_rect(sw, sh, width, height, props["fit"])
        painted = source.resize(
            (max(1, round(w)), max(1, round(h))), PILImage.LANCZOS,
        )
        canvas = PILImage.new("RGBA", (width, height), (0, 0, 0, 0))
        canvas.paste(painted, (round(x), round(y)), painted)
        photo = ImageTk.PhotoImage(canvas)
        widget._psx_photo = photo
        widget.configure(image=photo, text="")
