"""Regressions for HTML-like multiline and checkbox contents."""
from psx.markup.compile import psx
from psx.markup.html_aliases import InputChangeEvent


def test_named_textarea_emits_portable_change_event():
    values = []
    node = psx('<textarea name="manifest" value="First" on_change={changed}></textarea>',
               scope={"changed":values.append})
    assert node.type == "TextArea"
    assert node.props["value"] == "First"
    node.props["on_change"]("Second")
    assert values == [InputChangeEvent(target=values[0].target)]
    assert values[0].target.name == "manifest"
    assert values[0].target.value == "Second"


def test_lowercase_checkbox_child_text_is_visible():
    node = psx("<checkbox>hhehe</checkbox>")
    assert node.type == "span"
    assert node.children[0].type == "Checkbox"
    assert node.children[1].type == "Text"
    assert node.children[1].props["value"] == "hhehe"


def test_empty_checkbox_stays_a_native_checkbox():
    assert psx("<checkbox />").type == "Checkbox"
