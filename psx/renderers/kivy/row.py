"""Built-in Row adapter for the Kivy renderer."""

from kivy.uix.boxlayout import BoxLayout

from psx.core.contracts import ROW_DEFAULTS, validate_row_props
from psx.core.errors import RendererCapabilityError
from psx.core.native import NativeOwnership
from psx.renderers.components.row import child_align, child_expand, normalize_padding, updated_row_props


class KivyRowAdapter:
    def create(self, renderer, node, parent):
        widget = BoxLayout(orientation="horizontal")
        props = {**ROW_DEFAULTS, **node.props}
        validate_row_props(props)
        self._apply_container(widget, props)
        from psx.renderers.kivy.kivy import KivyHandle
        return KivyHandle("Row", widget, props)

    def update(self, renderer, handle, changed, removed):
        props = updated_row_props(handle.props, changed, removed)
        self._apply_container(handle.widget, props)
        handle.props = props
        self._reapply_children(handle)

    def bind_event(self, renderer, handle, event, slot):
        raise RendererCapabilityError(f"Row does not emit events, got {event!r}.")

    def unbind_event(self, renderer, subscription):
        return None

    def destroy(self, renderer, handle):
        if handle.widget.parent is not None:
            handle.widget.parent.remove_widget(handle.widget)

    def insert(self, renderer, parent, child, index):
        if child in parent.children:
            parent.children.remove(child)
        parent.children.insert(index, child)
        renderer._sync_children(parent)
        self._reapply_children(parent)
        return True

    def move(self, renderer, parent, child, index):
        parent.children.remove(child)
        parent.children.insert(index, child)
        renderer._sync_children(parent)
        self._reapply_children(parent)
        return True

    def remove(self, renderer, parent, child):
        if child in parent.children:
            parent.children.remove(child)
        parent.widget.remove_widget(child.widget)
        if (child.native is not None and child.native.ownership is NativeOwnership.BORROWED
                and child.original_parent is not None):
            child.original_parent.add_widget(child.widget)
        self._reapply_children(parent)
        return True

    @staticmethod
    def _apply_container(widget, props):
        left, top, right, bottom = normalize_padding(props["padding"])
        widget.padding = (left, top, right, bottom)
        widget.spacing = int(props["spacing"])
        widget.disabled = not bool(props["enabled"])

    @staticmethod
    def _reapply_children(container):
        for index, child in enumerate(container.children):
            widget = child.widget
            # Un Spacer siempre absorbe el sobrante horizontal del Row,
            # independientemente de la prop `expand` del contenedor.
            is_spacer = child.node_type == "Spacer"
            align = child_align(container.props, index)
            expand = True if is_spacer else child_expand(container.props, index)

            widget.size_hint_x = 1 if expand else None

            # Un BoxLayout anidado con size_hint_x=None mide 100px por defecto
            # y no crece con sus hijos: hay que enlazar minimum_width a width.
            # (Un Spacer es un Widget plano, así que esta rama no le aplica.)
            if not expand and isinstance(widget, BoxLayout):
                if not getattr(widget, "_psx_min_width_bound", False):
                    widget.bind(minimum_width=widget.setter("width"))
                    widget._psx_min_width_bound = True

            if align == "stretch":
                widget.size_hint_y, widget.pos_hint = 1, {}
            else:
                widget.size_hint_y = None
                widget.pos_hint = {"start": {"top": 1}, "center": {"center_y": .5},
                                   "end": {"y": 0}}[align]