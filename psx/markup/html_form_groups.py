"""Lower grouped HTML-like radios into the existing portable RadioGroup host.

This is an immutable VNode composition pass. Native toolkits never receive
HTML name/checked/on_change metadata on individual Radio children.
"""
from __future__ import annotations

from dataclasses import replace

from psx.core.vnode import Radio, RadioGroup, VNode
from .html_aliases import HtmlRadioData, InputChangeEvent, InputEventTarget


def _association(node: VNode) -> tuple[VNode, str] | None:
    """Recognize a row containing one radio and its associated label."""
    if node.type != "div":
        return None
    radio = next((c for c in node.children if c.type == "Radio"
                  and isinstance(c.markup_meta, HtmlRadioData)), None)
    if radio is None:
        return None
    node_id = getattr(radio.css_source, "node_id", None)
    label = next((c for c in node.children if c.type == "label"
                  and c.props.get("for") == node_id and node_id), None)
    if label is None:
        return None
    if any(c is not radio and c is not label for c in node.children):
        return None
    text_parts = [str(c.props["value"]) for c in label.children if c.type == "Text"]
    if len(text_parts) != len(label.children):
        return None
    return radio, "".join(text_parts).strip()


def _attach_checkbox_label(children: tuple[VNode, ...]) -> tuple[VNode, ...]:
    """Associate a label with its adjacent checkbox using the authored id."""
    result = list(children)
    removed: set[int] = set()
    for index, checkbox in enumerate(result):
        if checkbox.type != "Checkbox":
            continue
        node_id = getattr(checkbox.css_source, "node_id", None)
        if not node_id:
            continue
        for target_index, label in enumerate(result):
            if label.type != "label" or label.props.get("for") != node_id:
                continue
            if target_index in removed:
                continue
            if any(c.type != "Text" for c in label.children):
                continue
            caption = "".join(str(c.props["value"]) for c in label.children).strip()
            if not caption:
                continue
            result[index] = replace(
                checkbox, props={**checkbox.props, "label": caption}
            )
            removed.add(target_index)
            break
    return tuple(item for index, item in enumerate(result) if index not in removed)


def compose_html_radio_groups(node: VNode) -> VNode:
    """Build exclusive native groups from sibling HTML radio/label rows."""
    if not node.children:
        return node
    normalized = _attach_checkbox_label(tuple(compose_html_radio_groups(child) for child in node.children))
    grouped: dict[str, list[tuple[int, VNode, str]]] = {}
    for index, child in enumerate(normalized):
        pair = _association(child)
        if pair is None:
            continue
        radio, label = pair
        name = radio.markup_meta.name
        grouped.setdefault(name, []).append((index, radio, label))
    if not grouped:
        return replace(node, children=normalized) if normalized != node.children else node

    first: dict[int, VNode] = {}
    omitted: set[int] = set()
    for name, items in grouped.items():
        seen: set[str | int] = set()
        checked_values: list[str | int] = []
        radios: list[VNode] = []
        handler = None
        for index, radio, label in items:
            value = radio.props["value"]
            if value in seen:
                raise ValueError(f"Duplicate radio value {value!r} for name {name!r}.")
            seen.add(value)
            if radio.markup_meta.checked:
                checked_values.append(value)
            if handler is None:
                handler = radio.markup_meta.on_change
            props = {key: val for key, val in radio.props.items()
                     if key not in ("value", "label")}
            plain = Radio(value, label=label, key=radio.key, **props)
            radios.append(replace(plain, css_source=radio.css_source,
                                  css_computed=radio.css_computed))
            omitted.add(index)
        if len(checked_values) > 1:
            raise ValueError(f"More than one checked radio for name {name!r}.")
        if handler is not None:
            def dispatch(value: str | int, _handler=handler, _name=name) -> object:
                return _handler(InputChangeEvent(InputEventTarget(_name, value, True)))
        else:
            dispatch = None
        group = RadioGroup(*radios, value=checked_values[0] if checked_values else None,
                           on_change=dispatch)
        first[items[0][0]] = group
    out = []
    for index, child in enumerate(normalized):
        if index in first:
            out.append(first[index])
        elif index not in omitted:
            out.append(child)
    return replace(node, children=tuple(out))
