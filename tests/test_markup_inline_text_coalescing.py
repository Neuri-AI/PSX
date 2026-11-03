"""Mixed paragraph text and expression results use one native text run."""
from psx.markup.expressive_runtime import element


def render_count(count):
    return element("p", {}, ("Total colors ", count),
                   "inline-count.py", 1, 1)


def test_adjacent_literal_and_numeric_expression_share_one_text_host():
    paragraph = render_count(4)
    assert paragraph.type == "p"
    assert len(paragraph.children) == 1
    assert paragraph.children[0].type == "Text"
    assert paragraph.children[0].props["value"] == "Total colors 4"


def test_zero_count_is_visible_in_paragraph():
    paragraph = render_count(0)
    assert len(paragraph.children) == 1
    assert paragraph.children[0].props["value"] == "Total colors 0"


def test_different_text_styles_are_not_coalesced():
    from psx.core.vnode import Text
    paragraph = element("p", {}, (Text("One", bold=True), Text("Two")),
                        "inline-count.py", 1, 1)
    assert len(paragraph.children) == 2


def test_heading_expression_is_one_text_host():
    heading = element("h2", {}, ("Count ", 4), "inline-count.py", 1, 1)
    assert len(heading.children) == 1
    assert heading.children[0].props["value"] == "Count 4"


def test_div_adjacent_text_fragments_render_as_one_native_text_host():
    from psx.core.vnode import Text
    sidebar = element("div", {}, (
        element("div", {}, ("Mi", " ", "panel"), "sidebar.py", 1, 1),
    ), "sidebar.py", 1, 1)
    logo = sidebar.children[0]
    assert len(logo.children) == 1
    assert logo.children[0].type == "Text"
    assert logo.children[0].props["value"] == "Mi panel"


def test_distinct_styled_text_nodes_in_div_remain_separate():
    from psx.core.vnode import Text
    logo = element("div", {}, (
        Text("Mi", bold=True), Text(" panel"),
    ), "sidebar.py", 1, 1)
    assert len(logo.children) == 2
