"""Native sizing must use CSS/Cinnamon geometry, not native property writes."""
import unittest

from psx.core.native import Native
from psx.css.markup import compute_markup_styles
from psx.markup.transform import transform_source


class DummyWidget:
    def sizeHint(self):
        return None


class NativeSizingTests(unittest.TestCase):
    def test_explicit_dimensions_are_layout_metadata(self):
        node = Native(DummyWidget, renderer="pyside6", width="80vw", height="100%")
        self.assertEqual(node.props["layout_width"], "80vw")
        self.assertEqual(node.props["layout_height"], "100%")
        self.assertNotIn("width", node.props)
        self.assertNotIn("height", node.props)

    def test_explicit_and_layout_dimensions_conflict(self):
        with self.assertRaisesRegex(TypeError, "both width and layout_width"):
            Native(DummyWidget, renderer="pyside6", width="100%", layout_width="200px")

    def test_cinnamon_receives_native_css_dimensions(self):
        from psx.core.layout_tree import normalize_flex_tree
        from psx.core.vnode import Flex
        from psx.sfle.model import AvailableSize, LayoutConstraints
        from psx.sfle.native_layout_snapshot import prepare_native_layout_snapshot
        from psx.sfle.lengths import LengthKind

        child = Native(DummyWidget, renderer="pyside6")
        from dataclasses import replace
        from psx.css.markup import parse_markup_style
        child = replace(child, css_source=parse_markup_style("native", class_value="browser"))
        root = compute_markup_styles(Flex(child), ".browser { width: 100%; height: 50vh; }")
        limits = LayoutConstraints(AvailableSize(800, True), AvailableSize(600, True))
        prepared = prepare_native_layout_snapshot(normalize_flex_tree(root), limits, generation=1)
        snapshot = prepared.css_geometry_snapshot()
        native_node = next(node for node in snapshot.nodes if node.component == "Native")
        style = dict(native_node.style)
        self.assertEqual(style["layout_width"].kind, LengthKind.PERCENT)
        self.assertEqual(style["layout_width"].value, 1.0)
        self.assertEqual(style["layout_height"].kind, LengthKind.PX)
        self.assertEqual(style["layout_height"].value, 300.0)

    def test_native_class_resolves_css(self):
        source = ("from psx import psx\n"
                  "from psx.core.native import Native\n"
                  "class Browser: pass\n"
                  "def view():\n"
                  "    return psx('<Native widget={Browser} renderer=\"pyside6\" class=\"browser\" />')\n")
        transformed = transform_source(source, filename="native_css.py")
        namespace = {"__name__": "native_css"}
        exec(compile(transformed.source, "native_css.py", "exec"), namespace)
        node = namespace["view"]()
        styled = compute_markup_styles(node, ".browser { width: 100%; height: 50vh; }")
        self.assertEqual(node.css_source.classes, frozenset({"browser"}))
        self.assertIn("width", styled.css_computed.properties)
        self.assertIn("height", styled.css_computed.properties)


if __name__ == "__main__":
    unittest.main()
