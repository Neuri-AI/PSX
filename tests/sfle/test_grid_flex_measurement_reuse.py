"""Native Grid Flex measurement reuse must remain transaction-scoped."""
from psx import Flex, Text
from psx.core.layout_tree import normalize_flex_tree
from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.grid_flex_composition import prepare_composed_flex
from psx.sfle.model import IntrinsicSizes


def test_equal_leaf_widths_measure_once_per_composition_without_stale_reuse():
    calls = []

    def measure_leaf(identifier, node, width):
        calls.append((identifier, width))
        return IntrinsicSizes(30, 30, 12, 12, 30, 12)

    def compose(label):
        node = normalize_flex_tree(Flex(Text(label), direction="column"))
        return prepare_composed_flex(
            node,
            content_width=180,
            generation=1,
            current_generation=1,
            measure_leaf=measure_leaf,
            measure_grid=lambda _node, _width: None,
            is_ui_thread=lambda: True,
            engine=PythonLayoutEngine(),
        )

    first = compose("first")
    first_calls = list(calls)
    assert first.content_height >= 0
    # A provisional remeasurement at an unchanged width must reuse the
    # intrinsic metric captured earlier in this same composition.
    assert len({(identifier, width) for identifier, width in first_calls}) == len(first_calls)
    calls.clear()
    second = compose("updated")
    assert second.content_height >= 0
    # A new composition must measure again, even for the same node and width.
    assert calls


def test_explicit_height_flex_leaf_does_not_repeat_width_sensitive_measurements():
    """Fixed-height leaves need one intrinsic read, not provisional remeasurement."""
    calls = []

    def measure_leaf(identifier, node, width):
        calls.append((identifier, width))
        return IntrinsicSizes(30, 30, 12, 12, 30, 12)

    node = normalize_flex_tree(Flex(
        Text("fixed height", layout_height="24px"),
        direction="column",
    ))
    result = prepare_composed_flex(
        node, content_width=180, generation=1, current_generation=1,
        measure_leaf=measure_leaf,
        measure_grid=lambda _node, _width: None,
        is_ui_thread=lambda: True,
        engine=PythonLayoutEngine(),
    )
    assert result.content_height >= 24
    assert len(calls) == 1
