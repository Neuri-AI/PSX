"""CSS resource load ordering, imports, resolver isolation and traversal security."""
import pytest
from psx.css.sources import CssSourceManager
from psx.css.cascade import StyleTarget, resolve_style
from psx.css.visual_values import CssColor


def test_relative_imports_and_cascade_order():
    files = {
        "styles/main.css": '@import "./buttons.css";\n.panel {color: #fff}',
        "styles/buttons.css": ".panel {color: #abc}",
    }
    manager = CssSourceManager(lambda path: files[path])
    sheet = manager.load(("styles/main.css",))
    style = resolve_style(sheet, StyleTarget("div", frozenset({"panel"})))
    assert style.properties["color"] == CssColor("#fff")
    assert [rule.order for rule in sheet.rules] == [0, 1]


def test_cycles_fail_closed():
    files = {"a.css": '@import "b.css";', "b.css": '@import "a.css";'}
    with pytest.raises(ValueError, match="Circular CSS import"):
        CssSourceManager(lambda path: files[path]).load(("a.css",))


def test_filesystem_loader_respects_project_root(tmp_path):
    (tmp_path / "style.css").write_text("div {width: 20px}", encoding="utf-8")
    sheet = CssSourceManager(root=tmp_path).load(("style.css",))
    assert len(sheet.rules) == 1
    with pytest.raises(ValueError):
        CssSourceManager(root=tmp_path).load(("../secret.css",))


def test_resource_resolver_decodes_protected_css_bytes():
    manager = CssSourceManager(lambda _: b"div {color: #fff}")
    assert resolve_style(manager.load(("protected.css",)), StyleTarget("div")).properties["color"] == CssColor("#fff")


def test_unsupported_imports_rejected():
    with pytest.raises(ValueError, match="@import"):
        CssSourceManager(lambda _: 'div { color: #fff } @import "late.css";').load(("main.css",))
