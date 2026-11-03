"""Regression for source indentation in expressive PSX text children."""

from psx.markup.expressive_ast import Literal, Location
from psx.markup.expressive_lower import _literal_child_text
from psx.markup.transform import transform_source


def test_expressive_source_literal_removes_multiline_indentation():
    location = Location(0, 1, 1)
    literal = Literal(
        "\n                         Native, reactive scientific charts\n                    ",
        location,
    )
    assert _literal_child_text(literal).value == "Native, reactive scientific charts"


def test_expressive_source_literal_preserves_inline_boundaries():
    location = Location(0, 1, 1)
    for raw, expected in (
        ("Edit ", "Edit "),
        (" and save", " and save"),
        ("  hello   world  ", " hello world "),
        ("\n          Edit ", "Edit "),
        (" and save\n      ", " and save"),
    ):
        assert _literal_child_text(Literal(raw, location)).value == expected


def _render_expressive(markup: str, *, count: int = 0):
    # Force M4B expressive lowering with arithmetic interpolation without
    # introducing native GUI widgets. This is the same compiler route as a
    # document containing <Native widget={PlotWidget} ... />.
    source = "from psx.markup import psx\n" + (
        "def render(count):\n"
        "    return psx(" + repr(markup) + ")\n"
    )
    transformed = transform_source(source, filename="<whitespace-regression>")
    assert transformed.transformed_calls == 1
    assert "_psx_expr_element" in transformed.source
    namespace = {}
    exec(compile(transformed.source, "<whitespace-regression>", "exec"), namespace)
    return namespace["render"](count)


def test_expressive_multiline_paragraph_is_left_aligned_without_indent():
    root = _render_expressive("""
        <div class="root">
            <p>
                         Native, reactive scientific charts
                    </p>
            <button on_click={() => count + 1}>Count</button>
        </div>
    """)
    para = root.children[0]
    assert para.type == "p"
    assert len(para.children) == 1
    assert para.children[0].props["value"] == "Native, reactive scientific charts"


def test_expressive_paragraph_interpolation_keeps_one_space():
    root = _render_expressive("""
        <div>
            <p>
                Samples: {count} Native, reactive scientific charts
            </p>
            <button on_click={() => count + 1}>Count</button>
        </div>
    """, count=30)
    para = root.children[0]
    assert para.type == "p"
    assert "".join(str(n.props["value"]) for n in para.children) == (
        "Samples: 30 Native, reactive scientific charts"
    )


def test_expressive_inline_span_preserves_spaces_between_words():
    root = _render_expressive("""
        <div>
            <p>Edit <span>main.py</span> and save</p>
            <button on_click={() => count + 1}>Count</button>
        </div>
    """)
    para = root.children[0]
    assert para.type == "p"
    assert para.children[0].props["value"] == "Edit "
    assert para.children[-1].props["value"] == " and save"
