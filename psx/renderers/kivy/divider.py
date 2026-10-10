"""Built-in Divider adapter for the Kivy renderer.

Kivy no tiene separador nativo. Se dibuja con Line sobre el canvas de un
Widget. Con hijo, el adapter:

    1. Mide el texto con CoreLabel (el motor de rasterizado de Kivy),
       independiente del estado del widget, para obtener el ancho/alto real.
    2. Dimensiona el Divider a partir de esa medida.
    3. Posiciona el Label dentro del Divider con pos y size explícitos.
    4. Dibuja DOS Line separadas (izquierda y derecha del texto), no una
       polilínea, para que el hueco quede realmente vacío.

En update NO se recrea el canvas: solo se actualizan los atributos de las
instrucciones existentes. Recrear con canvas.clear() interrumpe el repaint
del Label hijo en el frame en que se hace el update.
"""

from __future__ import annotations

from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Line
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from psx.core.contracts import DIVIDER_DEFAULTS
from psx.core.errors import RendererCapabilityError
from psx.renderers.components.divider import (
    divider_props,
    needs_custom_paint,
    updated_divider_props,
)

_MIN_LABEL_GAP = 8
_LABEL_GAP_RATIO = 0.5


def _label_gap(child) -> float:
    font_size = getattr(child, "font_size", None)
    if font_size is None:
        return _MIN_LABEL_GAP
    try:
        return max(_MIN_LABEL_GAP, float(font_size) * _LABEL_GAP_RATIO)
    except (TypeError, ValueError):
        return _MIN_LABEL_GAP


def _measure_label(child) -> tuple[float, float]:
    """Mide el texto con CoreLabel, independiente del estado del widget."""
    if isinstance(child, Label):
        text = getattr(child, "text", "") or ""
        if text:
            font_size = getattr(child, "font_size", 14)
            bold = bool(getattr(child, "bold", False))
            italic = bool(getattr(child, "italic", False))
            try:
                core = CoreLabel(
                    text=text,
                    font_size=font_size,
                    bold=bold,
                    italic=italic,
                )
                core.refresh()
                if core.texture is not None:
                    w, h = core.texture.size
                    if w > 0 and h > 0:
                        return float(w), float(h)
            except Exception:
                pass

    texture = getattr(child, "texture_size", (0, 0))
    if texture[0] > 0 and texture[1] > 0:
        return float(texture[0]), float(texture[1])
    return float(child.width), float(child.height)


class KivyDividerAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.kivy.kivy import KivyHandle
        props = divider_props({**DIVIDER_DEFAULTS, **node.props})

        is_h = props["orientation"] == "horizontal"

        widget = Widget()
        widget._psx_orientation = "horizontal" if is_h else "vertical"
        widget._psx_child = None
        widget._psx_line_before = None
        widget._psx_line_after = None
        widget._psx_color_instruction = None

        self._install_line(widget, props)

        handle = KivyHandle("Divider", widget, props)
        self._apply_size_hint(widget, props)
        return handle

    def update(self, renderer, handle, changed, removed):
        props = updated_divider_props(handle.props, changed, removed)
        handle.props = props
        widget = handle.widget
        widget._psx_orientation = (
            "horizontal" if props["orientation"] == "horizontal" else "vertical"
        )
        # Actualiza las instrucciones sin recrear el canvas.
        self._update_line(widget, props)
        self._apply_size_hint(widget, props)
        self._redraw(widget, props)

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(
            f"Divider does not emit events, got {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        widget = handle.widget
        if widget.parent is not None:
            widget.parent.remove_widget(widget)

    # -- child hooks ------------------------------------------------------

    def insert(self, renderer, parent, child, index):
        widget = parent.widget
        child_widget = child.widget
        self._prepare_child(child_widget)
        widget._psx_child = child_widget
        widget.add_widget(child_widget)

        def _on_child_resize(*_):
            props = getattr(widget, "_psx_props", None)
            if props is not None:
                self._apply_size_hint(widget, props)
                self._redraw(widget, props)

        child_widget.bind(text=_on_child_resize, texture_size=_on_child_resize)

        self._apply_size_hint(widget, parent.props)
        self._redraw(widget, parent.props)
        Clock.schedule_once(
            lambda _dt: self._reflow(widget, parent),
            0,
        )
        return True

    def move(self, renderer, parent, child, index):
        return True

    def remove(self, renderer, parent, child):
        widget = parent.widget
        if widget._psx_child is child.widget:
            widget.remove_widget(child.widget)
            widget._psx_child = None
            self._apply_size_hint(widget, parent.props)
            self._redraw(widget, parent.props)
        return True

    # -- helpers ----------------------------------------------------------

    @staticmethod
    def _prepare_child(widget):
        if isinstance(widget, Label):
            widget.text_size = (None, None)
            widget.size_hint = (None, None)

    def _reflow(self, widget, parent):
        props = getattr(widget, "_psx_props", None) or parent.props
        self._apply_size_hint(widget, props)
        self._redraw(widget, props)

    def _install_line(self, widget, props):
        """Crea las instrucciones de dibujo. Solo se llama en create."""
        p = divider_props(props)
        rgba = _hex_to_rgba(p["color"]) if p["color"] else (0.6, 0.6, 0.6, 0.5)

        widget.canvas.clear()
        with widget.canvas:
            widget._psx_color_instruction = Color(*rgba)
            widget._psx_line_before = Line(width=p["thickness"])
            widget._psx_line_after = Line(width=p["thickness"])

        widget.unbind(pos=self._on_geometry, size=self._on_geometry)
        widget.bind(pos=self._on_geometry, size=self._on_geometry)
        widget._psx_props = props

    def _update_line(self, widget, props):
        """Actualiza atributos de las instrucciones existentes.

        No toca el canvas: recrear con canvas.clear() interrumpe el repaint
        del Label hijo en el frame del update, y el contenido desaparece
        hasta el próximo trigger.
        """
        p = divider_props(props)

        # Si por alguna razón no hay instrucciones (por ejemplo, el widget
        # fue recreado), caemos al install completo.
        if (widget._psx_color_instruction is None
                or widget._psx_line_before is None
                or widget._psx_line_after is None):
            self._install_line(widget, props)
            return

        rgba = _hex_to_rgba(p["color"]) if p["color"] else (0.6, 0.6, 0.6, 0.5)
        widget._psx_color_instruction.rgba = rgba
        widget._psx_line_before.width = p["thickness"]
        widget._psx_line_after.width = p["thickness"]
        widget._psx_props = props

    @staticmethod
    def _on_geometry(instance, _value):
        props = getattr(instance, "_psx_props", None)
        if props is None:
            return
        KivyDividerAdapter._redraw(instance, props)

    @staticmethod
    def _redraw(widget, props):
        p = divider_props(props)
        is_h = p["orientation"] == "horizontal"
        line_before = widget._psx_line_before
        line_after = widget._psx_line_after
        if line_before is None or line_after is None:
            return

        x, y = widget.pos
        w, h = widget.size
        child = widget._psx_child

        if is_h:
            cy = y + h / 2
            if child is not None:
                text_w, text_h = _measure_label(child)
                child.pos = (x + w / 2 - text_w / 2, cy - text_h / 2)
                child.size = (text_w, text_h)
                if text_w > 0:
                    gap = text_w / 2 + _label_gap(child)
                    cx = x + w / 2
                    line_before.points = [x, cy, cx - gap, cy]
                    line_after.points = [cx + gap, cy, x + w, cy]
                    return
            line_before.points = [x, cy, x + w, cy]
            line_after.points = []
        else:
            cx = x + w / 2
            if child is not None:
                text_w, text_h = _measure_label(child)
                child.pos = (cx - text_w / 2, y + h / 2 - text_h / 2)
                child.size = (text_w, text_h)
                if text_h > 0:
                    gap = text_h / 2 + _label_gap(child)
                    cy = y + h / 2
                    line_before.points = [cx, y, cx, cy - gap]
                    line_after.points = [cx, cy + gap, cx, y + h]
                    return
            line_before.points = [cx, y, cx, y + h]
            line_after.points = []

    @staticmethod
    def _apply_size_hint(widget, props):
        is_h = props["orientation"] == "horizontal"

        if is_h:
            widget.size_hint_y = None
            if widget._psx_child is not None:
                _, text_h = _measure_label(widget._psx_child)
                widget.height = max(props["thickness"], text_h)
            else:
                widget.height = props["thickness"]
            widget.size_hint_x = 1
        else:
            widget.size_hint_x = None
            if widget._psx_child is not None:
                text_w, _ = _measure_label(widget._psx_child)
                widget.width = max(props["thickness"], text_w)
            else:
                widget.width = props["thickness"]
            widget.size_hint_y = 1


def _hex_to_rgba(value: str) -> tuple[float, float, float, float]:
    r = int(value[1:3], 16) / 255
    g = int(value[3:5], 16) / 255
    b = int(value[5:7], 16) / 255
    return (r, g, b, 1.0)