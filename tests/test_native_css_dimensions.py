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
