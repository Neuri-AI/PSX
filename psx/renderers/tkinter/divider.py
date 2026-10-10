"""Built-in Divider adapter for the Tkinter renderer.

Usa un ``tk.Canvas`` como widget raíz. La línea se dibuja con ``create_line``
en dos segmentos (izquierda y derecha del texto). El hijo (Text), si existe,
se incrusta en el canvas con ``create_window``, conservando su propia fuente
y color, y se posiciona centrado.

El ttk.Label del hijo no hereda el fondo del canvas, así que le aplicamos un
estilo con background idéntico al del canvas al insertarlo y en cada redraw.

El estado del adapter vive en el propio canvas (no en ``TkHandle``, que usa
``slots=True``).

Nota: solo se soporta ``Text`` como hijo del ``Divider`` en Tk.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from psx.core.contracts import DIVIDER_DEFAULTS, validate_divider_props
from psx.core.errors import RendererCapabilityError
from psx.renderers.components.divider import (
    divider_props,
    updated_divider_props,
)

_MIN_LABEL_GAP = 8
_LABEL_GAP_RATIO = 0.5


def _label_gap_from_text_width(text_width: int) -> int:
    """Hueco proporcional (basado en el ancho del texto como proxy)."""
    return max(_MIN_LABEL_GAP, int(text_width * 0.05) + _MIN_LABEL_GAP)


class TkDividerAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.tkinter.tkinter import TkHandle
        props = divider_props({**DIVIDER_DEFAULTS, **node.props})
        validate_divider_props(props)

        master = parent.widget if parent is not None else renderer.root
        is_h = props["orientation"] == "horizontal"

        if is_h:
            canvas = tk.Canvas(master, height=max(props["thickness"], 1),
                               highlightthickness=0, bd=0,
                               bg=_parent_bg(master))
        else:
            canvas = tk.Canvas(master, width=max(props["thickness"], 1),
                               highlightthickness=0, bd=0,
                               bg=_parent_bg(master))

        canvas._psx_props = props
        canvas._psx_child_widget = None
        canvas._psx_child_window_id = None

        canvas.bind("<Configure>", lambda _e: self._redraw(canvas, canvas._psx_props))

        handle = TkHandle("Divider", canvas, props)
        self._redraw(canvas, props)
        return handle

    def update(self, renderer, handle, changed, removed):
        props = updated_divider_props(handle.props, changed, removed)
        handle.props = props
        canvas = handle.widget
        canvas._psx_props = props

        is_h = props["orientation"] == "horizontal"
        if is_h:
            canvas.configure(height=max(props["thickness"], 1))
        else:
            canvas.configure(width=max(props["thickness"], 1))
        self._redraw(canvas, props)

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(
            f"Divider does not emit events, got {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        if handle.widget.winfo_exists():
            handle.widget.destroy()

    # -- child hooks ------------------------------------------------------

    def insert(self, renderer, parent, child, index):
        canvas = parent.widget
        child_widget = child.widget

        if not isinstance(child_widget, ttk.Label):
            raise RendererCapabilityError(
                f"Tkinter Divider only supports Text as its child, "
                f"got {type(child_widget).__name__}."
            )

        try:
            child_widget.pack_forget()
        except tk.TclError:
            pass

        # El ttk.Label hereda del tema, no del padre. Le aplicamos un estilo
        # con el mismo fondo que el canvas para que no muestre una caja.
        _sync_label_style(canvas, child_widget)

        canvas._psx_child_widget = child_widget
        self._redraw(canvas, parent.props)
        return True

    def move(self, renderer, parent, child, index):
        return True

    def remove(self, renderer, parent, child):
        canvas = parent.widget
        if canvas._psx_child_widget is child.widget:
            if canvas._psx_child_window_id is not None:
                canvas.delete(canvas._psx_child_window_id)
                canvas._psx_child_window_id = None
            canvas._psx_child_widget = None
            self._redraw(canvas, parent.props)
        return True

    # -- helpers ----------------------------------------------------------

    def _redraw(self, canvas, props):
        p = divider_props(props)
        is_h = p["orientation"] == "horizontal"
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w <= 1 or h <= 1:
            return

        color = p["color"] if p["color"] is not None else _theme_separator_color(canvas)
        thickness = p["thickness"]
        child_widget = canvas._psx_child_widget

        # Re-sincroniza el estilo del hijo con el fondo actual del canvas
        # (por si el tema o el propio canvas cambiaron de color).
        if child_widget is not None and child_widget.winfo_exists():
            _sync_label_style(canvas, child_widget)

        canvas.delete("psx_line")

        if is_h:
            cy = h // 2
            if child_widget is not None and child_widget.winfo_exists():
                child_widget.update_idletasks()
                child_w = child_widget.winfo_reqwidth()
                child_h = child_widget.winfo_reqheight()
                if canvas._psx_child_window_id is None:
                    canvas._psx_child_window_id = canvas.create_window(
                        w // 2, cy, window=child_widget, anchor="center",
                        tags=("psx_child",),
                    )
                else:
                    canvas.coords(canvas._psx_child_window_id, w // 2, cy)
                    canvas.itemconfigure(canvas._psx_child_window_id,
                                         window=child_widget)
                if child_h + 4 > h:
                    canvas.configure(height=child_h + 4)

                gap = child_w // 2 + _label_gap_from_text_width(child_w)
                cx = w // 2
                canvas.create_line(0, cy, cx - gap, cy,
                                   fill=color, width=thickness, tags=("psx_line",))
                canvas.create_line(cx + gap, cy, w, cy,
                                   fill=color, width=thickness, tags=("psx_line",))
            else:
                canvas.create_line(0, cy, w, cy,
                                   fill=color, width=thickness, tags=("psx_line",))
        else:
            cx = w // 2
            if child_widget is not None and child_widget.winfo_exists():
                child_widget.update_idletasks()
                child_w = child_widget.winfo_reqwidth()
                child_h = child_widget.winfo_reqheight()
                if canvas._psx_child_window_id is None:
                    canvas._psx_child_window_id = canvas.create_window(
                        cx, h // 2, window=child_widget, anchor="center",
                        tags=("psx_child",),
                    )
                else:
                    canvas.coords(canvas._psx_child_window_id, cx, h // 2)
                    canvas.itemconfigure(canvas._psx_child_window_id,
                                         window=child_widget)
                if child_w + 4 > w:
                    canvas.configure(width=child_w + 4)

                gap = child_h // 2 + _label_gap_from_text_width(child_h)
                cy = h // 2
                canvas.create_line(cx, 0, cx, cy - gap,
                                   fill=color, width=thickness, tags=("psx_line",))
                canvas.create_line(cx, cy + gap, cx, h,
                                   fill=color, width=thickness, tags=("psx_line",))
            else:
                canvas.create_line(cx, 0, cx, h,
                                   fill=color, width=thickness, tags=("psx_line",))


def _sync_label_style(canvas, child_widget):
    """Aplica al ttk.Label hijo el mismo fondo que el canvas.

    ttk.Label usa un estilo del tema (TLabel) cuyo background NO hereda del
    padre. Sin esto, el texto del Divider se ve dentro de una caja gris.
    """
    try:
        bg = canvas.cget("background")
        style = ttk.Style(canvas)
        style_name = "PSX.Divider.Label.TLabel"
        style.configure(style_name, background=bg)
        child_widget.configure(style=style_name)
    except tk.TclError:
        pass


def _parent_bg(master):
    """Color de fondo efectivo del padre.

    Los ``ttk.Frame`` no exponen ``background`` en ``cget``; su fondo vive en
    el estilo del tema. Los ``tk.Frame`` (y ``tk.Tk``) sí lo exponen.
    Probamos primero ``cget``, y si falla, leemos el estilo ttk. Como último
    recurso, subimos al toplevel.
    """
    try:
        bg = master.cget("background")
        if bg:
            return bg
    except tk.TclError:
        pass


    try:
        style_name = str(master.cget("style")) or "TFrame"
    except tk.TclError:
        style_name = "TFrame"
    try:
        bg = str(master.tk.call("ttk::style", "lookup", style_name, "-background"))
        if bg:
            return bg
    except tk.TclError:
        pass

    try:
        return master.winfo_toplevel().cget("background")
    except tk.TclError:
        return "white"


def _theme_separator_color(canvas):
    try:
        color = str(canvas.tk.call("ttk::style", "lookup", "TSeparator", "-background"))
        if color:
            return color
    except tk.TclError:
        pass
    return "#a0a0a0"