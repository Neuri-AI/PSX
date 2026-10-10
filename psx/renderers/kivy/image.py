"""Built-in Image adapter for the Kivy renderer.

Uses kivy.uix.image.Image, whose fit_mode property maps almost 1:1 to our
portable contract. The "none" fit maps to Kivy's "scale-down" so the image
is never upscaled beyond its natural size when no explicit size is set.

The image loads asynchronously, so the target size is applied when the
texture becomes available and re-applied on every update.
"""

from __future__ import annotations

from kivy.uix.image import Image as KivyImage

from psx.core.contracts import IMAGE_DEFAULTS
from psx.core.errors import RendererCapabilityError
from psx.renderers.components.image import (
    compute_target_size,
    image_props,
    updated_image_props,
)

_FIT_MODE = {
    "contain": "contain",
    "cover": "cover",
    "fill": "fill",
    "none": "scale-down",
}


class KivyImageAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.kivy.kivy import KivyHandle
        props = image_props({**IMAGE_DEFAULTS, **node.props})

        widget = KivyImage(source=props["source"])
        widget.fit_mode = _FIT_MODE[props["fit"]]
        widget.size_hint = (None, None)
        widget.disabled = not props["enabled"]
        widget._psx_props = props
        widget.bind(texture=KivyImageAdapter._on_texture)

        # If the texture is already cached, apply the target size right away.
        if widget.texture is not None:
            self._on_texture(widget, widget.texture)

        return KivyHandle("Image", widget, props)

    @staticmethod
    def _on_texture(widget, texture):
        if texture is None:
            return
        props = widget._psx_props
        src_w, src_h = texture.size
        target_w, target_h = compute_target_size(
            src_w, src_h, props["width"], props["height"],
        )
        widget.size = (target_w, target_h)
        widget.fit_mode = _FIT_MODE[props["fit"]]

    def update(self, renderer, handle, changed, removed):
        props = updated_image_props(handle.props, changed, removed)
        handle.props = props
        widget = handle.widget
        widget._psx_props = props
        if "source" in changed:
            widget.source = props["source"]
        widget.fit_mode = _FIT_MODE[props["fit"]]
        widget.disabled = not props["enabled"]
        if widget.texture is not None:
            self._on_texture(widget, widget.texture)

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(
            f"Image does not emit events, got {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        widget = handle.widget
        if widget.parent is not None:
            widget.parent.remove_widget(widget)