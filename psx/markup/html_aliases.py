"""Explicit portable HTML-like aliases for the PSX markup resolver.

Aliases lower to existing native component VNode types. They must not be
registered as new native host types: doing so would falsify the backend
capability census. Generic flow tags need their own Cinnamon contexts.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
import re

from psx.core.registry import ComponentDefinition
from psx.core.vnode import Image, Text, VNode, create_element
from psx.sfle.display_context import resolve_display

def _html_img(*children: object, src: object = None, **props: object) -> VNode:
    """Lower HTML img src and responsive dimensions to portable Image/Cinnamon.

    The public HTML spelling is `src`; native Image.source remains unchanged.
    Layout owns %/viewport sizes so they are re-evaluated on every resize,
    while the native pixel properties retain legacy intrinsic sizing behavior.
    """
    from pathlib import Path
    from psx.sfle.lengths import LengthKind, parse_length
    from .image_sources import resolve_markup_image_source

    if children:
        raise TypeError("img is a void element and cannot have children.")
    if "source" in props:
        raise ValueError("img uses src, not source.")
    if isinstance(src, Path):
        src = str(src)
    if not isinstance(src, str) or not src:
        raise ValueError("img requires a non-empty src path.")

    for axis in ("width", "height"):
        if axis not in props:
            continue
        raw = props.pop(axis)
        if isinstance(raw, str) and raw.strip().replace(".", "", 1).isdigit():
            raw = float(raw)  # HTML unitless dimensions are CSS pixels.
        try:
            length = parse_length(raw)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"img {axis} must use a positive px, %, vw or vh dimension."
            ) from exc
        if length.kind not in (
            LengthKind.PX, LengthKind.PERCENT, LengthKind.VW, LengthKind.VH,
        ) or length.value is None or length.value <= 0:
            raise ValueError(
                f"img {axis} must use a positive px, %, vw or vh dimension."
            )
        layout_axis = f"layout_{axis}"
        if layout_axis in props:
            raise ValueError(f"img cannot specify both {axis} and {layout_axis}.")
        # Preserve percentages/viewport units for Cinnamon; never collapse
        # them to the initial window geometry.
        if length.kind is LengthKind.PX:
            pixels = float(length.value)
            props[axis] = max(1, round(pixels))
            props[layout_axis] = f"{pixels:g}px"
        else:
            props[layout_axis] = (
                f"{length.value * 100:g}%"
                if length.kind is LengthKind.PERCENT
                else f"{length.value * 100:g}{length.kind.value}"
            )
    return Image(resolve_markup_image_source(src), **props)


@dataclass(frozen=True, slots=True)
class HtmlRadioData:
    name: str
    checked: bool
    on_change: object | None = None


@dataclass(frozen=True, slots=True)
class InputEventTarget:
    name: str
    value: str | bool
    checked: bool | None = None


@dataclass(frozen=True, slots=True)
class InputChangeEvent:
    target: InputEventTarget
    type: str = "change"


def _html_input(*children: object, **props: object) -> VNode:
    """Lower HTML input attributes without changing legacy Input callbacks."""
    from psx.core.vnode import Input
    if children:
        raise TypeError("input is a void element.")
    kind = props.pop("type", "text")
    if kind not in ("text", "password", "checkbox", "radio"):
        raise ValueError("input type must be text, password, checkbox, or radio.")
    name = props.pop("name", None)
    if name is not None and (not isinstance(name, str) or not name):
        raise ValueError("input name must be a nonempty string.")
    if kind == "radio":
        from psx.core.vnode import Radio
        if name is None:
            raise ValueError("input type='radio' requires a group name.")
        value = props.pop("value", None)
        if not isinstance(value, (str, int)) or isinstance(value, bool):
            raise ValueError("input type='radio' requires a string/integer value.")
        checked = props.pop("checked", False)
        if not isinstance(checked, bool):
            raise ValueError("input checked must be a boolean.")
        callback = props.pop("on_change", None)
        if callback is not None and not callable(callback):
            raise ValueError("radio on_change must be callable.")
        return replace(
            Radio(value=value, **props),
            markup_meta=HtmlRadioData(name, checked, callback),
        )
    if kind == "checkbox":
        from psx.core.vnode import Checkbox
        props.pop("value", None)  # checkbox changes carry a boolean checked state
        callback = props.get("on_change")
        if callback is not None:
            def emit(checked: bool) -> object:
                return callback(InputChangeEvent(InputEventTarget(name or "", checked, checked)))
            props["on_change"] = emit
        return Checkbox(**props)
    if kind == "password":
        if "password" in props and props["password"] is not True:
            raise ValueError("input type='password' conflicts with password=False.")
        props["password"] = True
    elif props.get("password") is True:
        raise ValueError("input type='text' conflicts with password=True.")
    callback = props.get("on_change")
    if callback is not None:
        def emit(value: str) -> object:
            return callback(InputChangeEvent(InputEventTarget(name or "", value)))
        props["on_change"] = emit
    return Input(**props)


def _html_select(*children: object, **props: object) -> VNode:
    """Compile HTML option children into the native Select options contract."""
    from psx.core.vnode import Select
    options = []
    for child in children:
        if not isinstance(child, VNode) or child.type != "option":
            raise TypeError("select accepts only option children.")
        options.append({"label": child.props["label"], "value": child.props["value"]})
    if "options" in props and children:
        raise ValueError("select cannot combine options prop with option children.")
    name = props.pop("name", None)
    if name is not None and (not isinstance(name, str) or not name):
        raise ValueError("select name must be a nonempty string.")
    callback = props.get("on_change")
    if callback is not None and name is not None:
        def emit(value: str | int) -> object:
            return callback(InputChangeEvent(InputEventTarget(name, value)))
        props["on_change"] = emit
    if children:
        props["options"] = tuple(options)
    return Select(**props)


def _html_option(*children: object, **props: object) -> VNode:
    """Option is compile-time markup only, never a native host."""
    props.pop("key", None)
    if set(props) != {"value"} or not isinstance(props["value"], (str, int)) or isinstance(props["value"], bool):
        raise ValueError("option requires a string/integer value.")
    if not children or any(not isinstance(c, VNode) or c.type != "Text" for c in children):
        raise TypeError("option requires plain text.")
    label = "".join(str(c.props["value"]) for c in children).strip()
    if not label:
        raise ValueError("option requires nonempty text.")
    return create_element("option", value=props["value"], label=label)


def _html_textarea(*children: object, **props: object) -> VNode:
    """Map named HTML textarea change callbacks to portable event targets."""
    from psx.core.vnode import TextArea
    name = props.pop("name", None)
    if name is not None and (not isinstance(name, str) or not name):
        raise ValueError("textarea name must be a nonempty string.")
    callback = props.get("on_change")
    if callback is not None and name is not None:
        def emit(value: str) -> object:
            return callback(InputChangeEvent(InputEventTarget(name, value)))
        props["on_change"] = emit
    return TextArea(*children, **props)


def _html_checkbox(*children: object, **props: object) -> VNode:
    """Give a lowercase checkbox visible inline text without altering its native contract."""
    from psx.core.vnode import Checkbox
    key = props.pop("key", None)
    checkbox = Checkbox(**props)
    if not children:
        return checkbox
    text = []
    for child in children:
        if not isinstance(child, VNode) or child.type != "Text":
            raise TypeError("checkbox accepts only text label content.")
        text.append(str(child.props["value"]))
    label = " ".join(" ".join(text).split())
    if not label:
        return checkbox
    return create_element("span", checkbox, Text(label), key=key, display="inline")


def _html_button(*children: object, **props: object) -> VNode:
    """Tag HTML submit semantics on its callback, not on native Button props."""
    from psx.core.vnode import Button
    if "type" not in props:
        return Button(*children, **props)
    kind = props.pop("type")
    if kind not in ("submit", "button", "reset"):
        raise ValueError("button type must be submit, button, or reset.")
    if kind == "reset":
        raise ValueError("HTML form reset is not implemented.")
    prior = props.get("on_click")
    def click(*args: object) -> object:
        if prior is not None:
            return prior(*args)
        return None
    click._psx_form_submit_button = kind == "submit"
    props["on_click"] = click
    return Button(*children, **props)


def _html_div(*children: object, display: str = "block", key: str | int | None = None, **props: object) -> VNode:
    """Preserve a true block host in the VNode tree; never alias to Flex."""
    if display not in ("block", "inline"):
        raise ValueError("div display overrides require the native formatting-context port")
    # Creating a VNode is not evidence that a native renderer can mount it.
    allowed = {"layout_width", "layout_height", "ref"}
    unsupported = set(props) - allowed
    if unsupported:
        raise ValueError(f"Unsupported div properties: {sorted(unsupported)}")
    resolve_display("div", display)
    return create_element("div", *children, key=key, display=display, **props)



# Generic HTML-like boxes remain explicit VNode identities rather than
# aliases to existing Flex/Box components. The verified formatting subset
# currently includes block containers and measured inline text fragments.
_BLOCK_TAGS = frozenset({
    "div", "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "section", "main", "header", "footer", "form", "ul", "li",
})
_INLINE_TAGS = frozenset({"span", "label"})
FORMATTING_TAGS = _BLOCK_TAGS | _INLINE_TAGS
_HEADING_FONT_SIZES = {
    "h1": 32, "h2": 28, "h3": 24, "h4": 20, "h5": 18, "h6": 16,
}


def _inline_text_fragments(node: VNode) -> tuple[VNode, ...]:
    """Prepare measured, breakable text words, retaining native font styling."""
    if node.type != "Text":
        return (node,)
    raw = node.props["value"]
    if not isinstance(raw, str):
        raise TypeError("Inline text must have a string value.")
    words = re.findall(r"\S+\s*|\s+", re.sub(r"\s+", " ", raw))
    preserved = {name: value for name, value in node.props.items()
                 if name not in ("value", "ref")}
    return tuple(Text(word, **preserved) for word in words if word.strip())


def _bind_form_submission(node: VNode, on_submit: object) -> VNode:
    """Delegate explicit native submit gestures to existing control adapters.

    Button clicks and Input enter/submit retain their existing handlers. The
    form handler runs afterward; native controls continue owning event binding
    and teardown. Dynamic component internals remain opaque.
    """
    from collections.abc import Callable
    if not isinstance(on_submit, Callable):
        raise TypeError("form on_submit must be callable.")

    if node.kind.value != "host":
        return node
    if node.type == "form":
        return node
    event = ("on_click" if node.type == "Button" and
             getattr(node.props.get("on_click"), "_psx_form_submit_button", True)
             else "on_submit" if node.type == "Input" else None)
    changed = dict(node.props)
    if event is not None:
        prior = changed.get(event)
        def dispatch(*args: object, _prior=prior, **kwargs: object) -> None:
            if _prior is not None:
                _prior(*args, **kwargs)
            on_submit()
        changed[event] = dispatch
    children = tuple(_bind_form_submission(child, on_submit) for child in node.children)
    if event is None and children == node.children:
        return node
    return create_element(node.type, *children, key=node.key, **changed)


def _formatting_host(
    tag: str, *children: object, key: str | int | None = None,
    display: str | None = None, **props: object,
) -> VNode:
    initial = "inline" if tag in _INLINE_TAGS else "block"
    selected = initial if display is None else display
    if selected not in ("inline", "block"):
        raise ValueError(
            f"{tag} display requires an implemented Block/Inline formatting context."
        )
    allowed = {"ref", "layout_width", "layout_height"}
    if tag == "form":
        allowed.add("on_submit")
    if tag == "label":
        allowed.add("for")
    extra = set(props) - allowed
    if extra:
        raise ValueError(f"Unsupported {tag} properties: {sorted(extra)}")
    resolve_display(tag, selected)
    if tag == "li" and not children:
        raise ValueError("li requires content to render a list item.")
    on_submit = props.pop("on_submit", None) if tag == "form" else None
    if on_submit is not None and not callable(on_submit):
        raise TypeError("form on_submit must be callable.")
    normalized = []
    for child in children:
        if tag in ("span", "label", "li") and isinstance(child, VNode) and child.type == "Text":
            normalized.extend(_inline_text_fragments(child))
        elif tag in _HEADING_FONT_SIZES and isinstance(child, VNode) and child.type == "Text":
            options = {
                name: value for name, value in child.props.items()
                if name not in ("value", "font_size", "bold", "ref")
            }
            normalized.append(Text(
                child.props["value"], font_size=_HEADING_FONT_SIZES[tag],
                bold=True, **options,
            ))
        else:
            normalized.append(child)
    if tag == "form" and on_submit is not None:
        normalized = [_bind_form_submission(child, on_submit)
                      if isinstance(child, VNode) else child for child in normalized]
    if tag == "li":
        # Group a bullet and text in the same inline run. Keep nested block
        # children independent rather than inventing a Flex layout.
        inline_fragments = [Text("\u2022 ")]
        while normalized and isinstance(normalized[0], VNode) and normalized[0].type == "Text":
            inline_fragments.append(normalized.pop(0))
        normalized.insert(0, create_element(
            "span", *inline_fragments, display="inline",
        ))
    return create_element(
        tag, *normalized, key=key, display=selected, **props,
    )


def _formatting_constructor(tag: str):
    def construct(*children: object, **props: object) -> VNode:
        return _formatting_host(tag, *children, **props)
    return construct


PORTABLE_HTML_ALIASES: Mapping[str, str] = {
    "button": "Button",
    "input": "Input",
    "textarea": "TextArea",
    "checkbox": "Checkbox",
    "radio": "Radio",
    "radiogroup": "RadioGroup",
    "select": "Select",
    "a": "Link",
    "badge": "Badge",
    "img": "Image",
    "div": "div",
    "span": "span",
    "p": "p",
    "h1": "h1", "h2": "h2", "h3": "h3",
    "h4": "h4", "h5": "h5", "h6": "h6",
    "section": "section", "main": "main",
    "header": "header", "footer": "footer",
    "form": "form", "label": "label", "ul": "ul", "li": "li",
}


def markup_alias_definitions(
    definitions: Mapping[str, ComponentDefinition],
) -> dict[str, ComponentDefinition]:
    """Create scoped aliases without adding phantom native registry entries."""
    result = dict(definitions)
    for alias, native in PORTABLE_HTML_ALIASES.items():
        if native not in definitions or alias in result:
            continue
        source = definitions[native]
        result[alias] = ComponentDefinition(
            alias,
            {"img": _html_img, "input": _html_input, "button": _html_button, "textarea": _html_textarea, "checkbox": _html_checkbox, "select": _html_select, "option": _html_option}.get(alias, source.constructor),
            contract=None if alias in ("checkbox", "select", "option") else source.contract,
            markup_integer_properties=source.markup_integer_properties,
        )
    result.setdefault("option", ComponentDefinition("option", _html_option))
    # Generic formatting boxes are private markup constructors. They must
    # never masquerade as registered legacy/native toolkit primitives.
    for tag in FORMATTING_TAGS:
        if tag not in result:
            constructor = _html_div if tag == "div" else _formatting_constructor(tag)
            result[tag] = ComponentDefinition(tag, constructor)
    return result
