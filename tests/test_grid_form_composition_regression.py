"""Regression: HTML forms are valid Cinnamon flows inside GridItem."""

from psx.core.layout_tree import normalize_flex_tree
from psx.core.vnode import Button, Grid, GridItem, Input, create_element
from psx.layout.contracts.model import IntrinsicSizes
from psx.layout.grid import grid_native_measurement as native
from psx.layout.projection.native_layout_snapshot import path_identity
from psx.layout.runtime.native_measurement import NativeMeasurementPort


def test_grid_item_form_is_accepted_as_composite_flow(monkeypatch):
    form = create_element("form", Input(), Button("Go"), display="block")
    grid = normalize_flex_tree(Grid(GridItem(form, span=6)))
    item_id = path_identity(grid.effective_children[0].path)

    class Source:
        def port(self):
            return NativeMeasurementPort(lambda: True, lambda request: None)

        def measure_width(self, node_id, width):
            assert node_id == item_id
            assert width > 0
            return IntrinsicSizes(0, width, 0, 25, width, 25)

    # This test targets the guard ahead of the Grid solver. The composition
    # engine's full placement and native-geometry tests remain separate.
    monkeypatch.setattr(native, "grid_widths", lambda slots, width, gap, engine=None: {item_id: 300.0})
    sentinel = object()
    monkeypatch.setattr(native, "prepare_grid_measurement", lambda *args, **kwargs: sentinel)
    result = native.measure_grid_native(
        grid, content_width=600.0, source=Source(), mounted_ids=(item_id,),
        revisions={item_id: 1}, generation=1, current_generation=1,
        allow_nested=True,
    )
    assert result is sentinel
