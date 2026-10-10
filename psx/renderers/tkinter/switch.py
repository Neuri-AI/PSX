"""Animated Tkinter Canvas Switch with explicit callback/timer ownership."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from psx.core.errors import RendererCapabilityError
from psx.renderers.components.switch import SWITCH_SIZES, switch_props, updated_switch_props


def _blend(start: tuple[int, int, int], end: tuple[int, int, int], progress: float) -> str:
    values = [round(a + (b - a) * progress) for a, b in zip(start, end)]
    return "#{:02x}{:02x}{:02x}".format(*values)


class TkSwitchAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.tkinter.tkinter import TkHandle

        props = switch_props(node.props)
        master = parent.widget if parent is not None else renderer.root
        frame = ttk.Frame(master)
        canvas = tk.Canvas(frame, highlightthickness=0, bd=0, takefocus=True)
        canvas.pack(side="left")
        label = ttk.Label(frame)
        label.pack(side="left", padx=(10, 0))
        frame._psx_canvas = canvas
        frame._psx_label = label
        frame._psx_props = props
        frame._psx_progress = float(props["checked"])
        frame._psx_after = None
        frame._psx_event_slot = None
        frame._psx_disposed = False
        frame._psx_draw = lambda: self._draw(frame)
        canvas.bind("<ButtonRelease-1>", lambda e: self._activate(frame))
        canvas.bind("<space>", lambda e: self._activate(frame))
        canvas.bind("<Return>", lambda e: self._activate(frame))
        label.bind("<ButtonRelease-1>", lambda e: self._activate(frame))
        self._apply(frame, props)
        return TkHandle("Switch", frame, props)

    def update(self, renderer, handle, changed, removed):
        props = updated_switch_props(handle.props, changed, removed)
        handle.widget._psx_props = props
        self._apply(handle.widget, props)
        handle.props = props

    def bind_event(self, renderer, handle, event, slot):
        if event != "on_change":
            raise RendererCapabilityError(f"Switch does not emit {event!r}.")
        frame = handle.widget
        frame._psx_event_slot = slot
        return frame, slot

    def unbind_event(self, renderer, subscription):
        frame, slot = subscription
        if frame._psx_event_slot is slot:
            frame._psx_event_slot = None

    def destroy(self, renderer, handle):
        frame = handle.widget
        frame._psx_disposed = True
        self._cancel(frame)
        frame._psx_event_slot = None
        if frame.winfo_exists():
            frame.destroy()

    def _activate(self, frame):
        props = frame._psx_props
        if frame._psx_disposed or not props["enabled"]:
            return "break"
        selected = not props["checked"]
        # This is controlled: the parent must commit the new checked prop.
        # Animate the user's intent without storing it as authoritative state.
        self._animate(frame, selected)
        slot = frame._psx_event_slot
        if slot is not None:
            slot.invoke(selected)
        return "break"

    def _apply(self, frame, props):
        canvas = frame._psx_canvas
        width, height = SWITCH_SIZES[props["size"]]
        canvas.configure(width=width, height=height,
                         cursor="hand2" if props["enabled"] else "arrow")
        frame._psx_label.configure(text=props["label"])
        frame._psx_label.pack_forget()
        if props["label"]:
            frame._psx_label.pack(side="left", padx=(10, 0))
        self._animate(frame, props["checked"])

    def _cancel(self, frame):
        if frame._psx_after is not None:
            try:
                frame.after_cancel(frame._psx_after)
            except tk.TclError:
                pass
            frame._psx_after = None

    def _animate(self, frame, checked):
        self._cancel(frame)
        start = frame._psx_progress
        end = float(checked)
        if start == end:
            self._draw(frame)
            return
        duration_ms = 160
        frames = 10

        def advance(index):
            if frame._psx_disposed or not frame.winfo_exists():
                return
            progress = min(1.0, index / frames)
            eased = 1 - (1 - progress) ** 3
            frame._psx_progress = start + (end - start) * eased
            self._draw(frame)
            if index < frames:
                frame._psx_after = frame.after(duration_ms // frames, advance, index + 1)
            else:
                frame._psx_after = None

        advance(0)

    def _draw(self, frame):
        canvas = frame._psx_canvas
        width, height = SWITCH_SIZES[frame._psx_props["size"]]
        t = frame._psx_progress
        enabled = frame._psx_props["enabled"]
        start = (156, 163, 175) if enabled else (187, 187, 187)
        end = (22, 163, 74) if enabled else (145, 183, 161)
        track = _blend(start, end, t)
        canvas.delete("all")
        radius = height / 2
        # A rounded pill using two circles and a rectangular center.
        canvas.create_oval(0, 0, height, height, fill=track, outline=track)
        canvas.create_oval(width-height, 0, width, height, fill=track, outline=track)
        canvas.create_rectangle(radius, 0, width-radius, height, fill=track, outline=track)
        diameter = height - 6
        x = 3 + (width - height) * t
        canvas.create_oval(x, 3, x + diameter, 3 + diameter, fill="white", outline="white")
        if canvas.focus_get() is canvas:
            canvas.create_rectangle(1, 1, width-1, height-1, outline="#2563EB", width=1)
