from psx.css.cascade import StyleTarget, resolve_style
from psx.css.effects import StyleEffect, classify_style_change
from psx.css.parser import parse_stylesheet


def computed(css: str):
    return resolve_style(parse_stylesheet(css), StyleTarget("div"))


def test_color_change_does_not_require_layout():
    before = computed("div { color: #000; background-color: #fff }")
    after = computed("div { color: #f00; background-color: #fff }")
    assert classify_style_change(before, after) == StyleEffect.PAINT


def test_font_changes_require_new_measurement_and_geometry():
    before = computed("div { font-size: 16px }")
    after = computed("div { font-size: 22px }")
    effect = classify_style_change(before, after)
    assert effect & StyleEffect.MEASUREMENT
    assert effect & StyleEffect.GEOMETRY


def test_width_changes_require_geometry():
    assert classify_style_change(computed("div { width: 10px }"), computed("div { width: 20px }")) == StyleEffect.GEOMETRY


def test_identical_computed_styles_are_noop():
    before = computed("div { color: #fff }")
    after = computed("div { color: #fff }")
    assert classify_style_change(before, after) == StyleEffect.NONE


def test_paint_only_marked_tree_preserves_cinnamon_geometry_without_commit():
    """Paint-only changes reuse existing layout but still update mounted CSS."""
    from psx.core.reconcile import Reconciler
    from psx.renderers.headless import HeadlessRenderer
    from psx.sfle.model import AvailableSize, LayoutConstraints, IntrinsicSizes

    renderer = HeadlessRenderer(
        sfle_constraints=LayoutConstraints(
            AvailableSize(240, True), AvailableSize(120, True)),
        measure_intrinsic=lambda _: IntrinsicSizes(40, 40, 12, 12, 40, 12),
    )
    commits = []
    original = renderer.commit_layout

    def counted(root):
        commits.append(root)
        return original(root)

    renderer.commit_layout = counted
    tree = Reconciler(renderer)

    def page(css):
        return __import__("psx").psx(
            f'<div style="width: 120px; {css}">'
            '<button key="save" style="color: #123456">Save</button></div>'
        )

    try:
        first = tree.render(page("color: #111111"))
        assert len(commits) == 1
        handle = first.children[0].handle
        geometry = handle.geometry
        second = tree.render(page("color: #222222"))
        assert second.children[0].handle is handle
        assert handle.geometry == geometry
        assert len(commits) == 1
        assert second.node.css_computed.properties["color"].value == "#222222"

        tree.render(page("width: 140px; color: #222222"))
        assert len(commits) == 2
        tree.render(page("width: 140px; color: #222222; font-size: 22px"))
        assert len(commits) == 3
    finally:
        tree.unmount()
