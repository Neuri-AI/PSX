"""Built-in ProgressBar adapter for the Kivy renderer.

Kivy's ProgressBar has no orientation property, so vertical bars are
rejected. In indeterminate mode, the adapter runs an Animation that cycles
the bar's value between zero and its maximum; the animation is stopped on
every switch back to determinate and on destroy.
"""

from __future__ import annotations

from kivy.animation import Animation
from kivy.uix.progressbar import ProgressBar as KivyProgressBar

from psx.core.contracts import PROGRESSBAR_DEFAULTS
from psx.core.errors import RendererCapabilityError
from psx.renderers.components.progressbar import (
    progressbar_props,
    relative_max,
    relative_value,
    updated_progressbar_props,
)


class KivyProgressBarAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.kivy.kivy import KivyHandle
        props = progressbar_props({**PROGRESSBAR_DEFAULTS, **node.props})
        if props["orientation"] == "vertical":
            raise RendererCapabilityError(
                "Kivy ProgressBar does not support vertical orientation."
            )
        widget = KivyProgressBar()
        widget._psx_indeterminate_anim = None
        self._apply(widget, props)
        return KivyHandle("ProgressBar", widget, props)

    def update(self, renderer, handle, changed, removed):
        props = updated_progressbar_props(handle.props, changed, removed)
        handle.props = props
        if props["orientation"] == "vertical":
            raise RendererCapabilityError(
                "Kivy ProgressBar does not support vertical orientation."
            )
        self._apply(handle.widget, props)

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(
            f"ProgressBar does not emit events, got {event!r}."
        )

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        widget = handle.widget
        _stop_indeterminate(widget)
        if widget.parent is not None:
            widget.parent.remove_widget(widget)

    @staticmethod
    def _apply(widget, props):
        widget.disabled = not props["enabled"]
        widget.max = relative_max(props)

        if props["indeterminate"]:
            if widget._psx_indeterminate_anim is None:
                _start_indeterminate(widget, widget.max)
            return

        _stop_indeterminate(widget)
        widget.value = relative_value(props)


def _start_indeterminate(widget, rel_max: float) -> None:
    _stop_indeterminate(widget)
    anim = (
        Animation(value=0.0, duration=1.0, t="in_out_quad")
        + Animation(value=rel_max, duration=1.0, t="in_out_quad")
    )
    anim.repeat = True
    anim.start(widget)
    widget._psx_indeterminate_anim = anim


def _stop_indeterminate(widget) -> None:
    if getattr(widget, "_psx_indeterminate_anim", None) is None:
        return
    Animation.cancel_all(widget)
    widget._psx_indeterminate_anim = None