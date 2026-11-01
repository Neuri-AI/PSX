"""Mixed inline text and native Tk buttons must preserve HTML-like defaults."""

from psx.core.vnode import Text
from psx.markup.html_aliases import _formatting_host, _inline_text_fragments


def test_spaces_survive_mixed_span_boundaries():
    span = _formatting_host("span", Text("main.py"))
    paragraph = _formatting_host(
        "p", Text("Edit "), span, Text(" and save to test HMR")
    )
    before = [child.props["value"] for child in paragraph.children
              if child.type == "Text"]
    assert before == ["Edit", " ", " ", "and", " ", "save", " ", "to",
                      " ", "test", " ", "HMR"]


def test_inline_fragment_preserves_separating_space():
    fragments = _inline_text_fragments(Text("first second "))
    assert [item.props["value"] for item in fragments] == [
        "first", " ", "second", " "
    ]
