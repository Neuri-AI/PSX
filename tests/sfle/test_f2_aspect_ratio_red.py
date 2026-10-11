"""RED cases for aspect-ratio transfer in the normalized F2 snapshot path."""
import pytest

from psx.sfle.engine import PythonLayoutEngine
from psx.sfle.model import AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection


def snapshot(nodes):
    unknown = AvailableSize(None, False)
    return LayoutInput(1, 31, WritingDirection.LTR, LayoutConstraints(unknown, unknown),
                       tuple(LayoutNode(*node) for node in nodes), ())


@pytest.mark.parametrize(("nodes", "expected"), [
    (
        (("root", None, "Flex", (("width", 200), ("height", 50))),
         ("image", "root", "Image", (("aspect_ratio", 2.0),))),
        (100.0, 50.0),
    ),
    (
        (("root", None, "Flex", (("width", 80), ("height", 200), ("direction", "column"))),
         ("image", "root", "Image", (("aspect_ratio", 2.0),))),
        (80.0, 40.0),
    ),
    (
        (("root", None, "Flex", (("width", 200), ("height", 100), ("align_items", "flex-start"))),
         ("image", "root", "Image", (("width", 30), ("aspect_ratio", 2.0)))),
        (30.0, 15.0),
    ),
])
def test_aspect_ratio_transfers_definite_cross_size(nodes, expected):
    result = PythonLayoutEngine().compute(snapshot(nodes))
    image = dict(result.boxes)["image"].content
    assert (image.width, image.height) == expected


@pytest.mark.parametrize("ratio", (0, -1, float("inf")))
def test_aspect_ratio_requires_a_positive_finite_number(ratio):
    with pytest.raises(ValueError):
        request = snapshot((("root", None, "Flex", (("width", 10),)),
                            ("image", "root", "Image", (("aspect_ratio", ratio),))))
        PythonLayoutEngine().compute(request)
