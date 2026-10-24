"""HTML option elements normalize into the portable Select contract."""
import pytest
from psx.markup.compile import psx
from psx.markup.html_aliases import InputChangeEvent


def test_html_select_option_children_and_named_event():
    events = []
    node = psx('<select name="language" on_change={changed}>'
               '<option value="py">Python</option>'
               '<option value="js">JavaScript</option></select>',
               scope={"changed": events.append})
    assert node.type == "Select"
    assert node.props["options"] == (
        {"label": "Python", "value": "py"},
        {"label": "JavaScript", "value": "js"},
    )
    node.props["on_change"]("js")
    assert events == [InputChangeEvent(events[0].target)]
    assert events[0].target.name == "language"
    assert events[0].target.value == "js"


def test_select_rejects_non_option_children():
    with pytest.raises(TypeError, match="option"):
        psx('<select><div>Invalid</div></select>')
