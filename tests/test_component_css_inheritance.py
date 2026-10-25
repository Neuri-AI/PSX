"""Global stylesheet inheritance across custom PSX component boundaries."""
from dataclasses import replace

from psx.core.instance import MountedInstance
from psx.core.vnode import create_element
from psx.css.inheritance import inherit_component_styles
from psx.css.markup import compute_markup_styles, parse_markup_style
from psx.css.parser import parse_stylesheet


def _host(tag, classes="", *children):
    return replace(
        create_element(tag, *children),
        css_source=parse_markup_style(tag, class_value=classes),
    )


def test_stylesheet_link_scope_reaches_external_component_root():
    sheet = parse_stylesheet(".sidebar { background: #123456; }")
    root = compute_markup_styles(_host("div", "layout"), sheet)
    mounted_root = MountedInstance(root, None)
    boundary = MountedInstance(create_element("div"), mounted_root)
    sidebar = inherit_component_styles(boundary, _host("div", "sidebar"))
    expected = dict(sheet.rules[0].declarations)
    for key, value in expected.items():
        assert sidebar.css_computed.properties[key] == value


def test_parent_child_selectors_and_dynamic_classes():
    sheet = parse_stylesheet(
        ".sidebar-content > button.active { color: #ffffff; }"
    )
    root = compute_markup_styles(_host("div", "layout"), sheet)
    mounted_root = MountedInstance(root, None)
    boundary = MountedInstance(create_element("div"), mounted_root)
    sidebar = _host(
        "div", "sidebar",
        _host("div", "sidebar-content", _host("button", "active")),
    )
    styled = inherit_component_styles(boundary, sidebar)
    button = styled.children[0].children[0]
    expected = dict(sheet.rules[0].declarations)
    for key, value in expected.items():
        assert button.css_computed.properties[key] == value
    inactive = _host(
        "div", "sidebar",
        _host("div", "sidebar-content", _host("button")),
    )
    styled_inactive = inherit_component_styles(boundary, inactive)
    inactive_button = styled_inactive.children[0].children[0]
    assert "color" not in inactive_button.css_computed.specified


def test_reconciler_applies_root_css_to_components_and_updates_active_class():
    from psx.core.component import component
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer

    @component
    def Sidebar(active):
        button = replace(
            create_element("Button", label="Resumen"),
            css_source=parse_markup_style(
                "button", class_value="active" if active else ""
            ),
        )
        return replace(
            create_element("Box", button),
            css_source=parse_markup_style("div", class_value="sidebar"),
        )

    sheet = parse_stylesheet(
        ".sidebar { background-color: #123456; }"
        ".sidebar > button.active { color: #ffffff; }"
    )
    renderer = HeadlessRenderer()
    reconciler = Reconciler(renderer)

    def parent(active):
        return compute_markup_styles(
            create_element("Box", Sidebar(active=active)), sheet
        )

    try:
        first = reconciler.render(parent(True))
        sidebar = first.children[0].children[0]
        button = sidebar.children[0]
        assert "background-color" in sidebar.node.css_computed.specified
        assert "color" in button.node.css_computed.specified
        handle = button.handle

        current = reconciler.render(parent(False))
        changed_button = current.children[0].children[0].children[0]
        assert changed_button.handle is handle
        assert "color" not in changed_button.node.css_computed.specified
    finally:
        reconciler.unmount()
