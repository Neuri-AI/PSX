"""F3-G2 Tk Flex host: native ownership only; SFLE distributes all space.

Unlike legacy Row/Column this adapter never invokes pack()/grid(). Tkinter
receives already-computed border rectangles through place() in the SFLE
geometry commit, with no second geometry authority.
"""
from __future__ import annotations

from tkinter import ttk

from psx.core.contracts import FLEX_CONTRACT
from psx.core.errors import RendererCapabilityError


class TkSFLEFlexAdapter:
    def create(self, renderer, node, parent):
        from psx.renderers.tkinter.tkinter import TkHandle
        FLEX_CONTRACT.validate(node.props)
        master = parent.widget if parent is not None else renderer.root
        widget = ttk.Frame(master)
        if parent is None:
            constraints = renderer._sfle_constraints
            if not (constraints.width.definite and constraints.height.definite):
                raise RendererCapabilityError(
                    "Tk SFLE root requires a definite viewport on both axes."
                )
            widget.place(
                x=0, y=0,
                width=round(constraints.width.value),
                height=round(constraints.height.value),
            )
            renderer._sfle_root_widget = widget
        return TkHandle("Flex", widget, dict(node.props))

    def update(self, renderer, handle, changed, removed):
        props = dict(handle.props)
        props.update(changed)
        for name in removed:
            props.pop(name, None)
        FLEX_CONTRACT.validate(props)
        handle.props = props

    def insert(self, renderer, parent, child, index):
        # Tk widget masters are immutable; children are already instantiated
        # with the real SFLE parent by TkinterRenderer.create().
        if child.widget.master is not parent.widget:
            raise RendererCapabilityError("Tk SFLE child has an incorrect native master.")
        if child in parent.children:
            parent.children.remove(child)
        parent.children.insert(index, child)
        return True

    def move(self, renderer, parent, child, index):
        if child.widget.master is not parent.widget:
            raise RendererCapabilityError("Tk SFLE moved child has an incorrect native master.")
        parent.children.remove(child)
        parent.children.insert(index, child)
        return True

    def remove(self, renderer, parent, child):
        if child in parent.children:
            parent.children.remove(child)
        child.widget.place_forget()
        return True

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(f"Flex does not emit {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        if renderer._sfle_root_widget is handle.widget:
            renderer._sfle_root_widget = None
        if handle.widget.winfo_exists():
            handle.widget.destroy()
