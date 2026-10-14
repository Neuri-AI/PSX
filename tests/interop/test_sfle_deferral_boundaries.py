"""F2 point 5: approved deferral boundaries remain explicitly fail-closed.

Do not reject the previously certified definite-size aspect-ratio and fixed-wrap
subsets. These two deferred dependency classes must instead be rejected by
both engines with the same code and source node ID, never silently guessed.
"""
from dataclasses import replace

import pytest

from psx.sfle.model import (
    AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, WritingDirection,
)
from test_sfle_differential import (
    _python_compute, _rects, _rust_compute, rust_binary,
)


def _request(generation, nodes, *, width=None, height=None):
    return LayoutInput(
        1, generation, WritingDirection.LTR,
        LayoutConstraints(
            AvailableSize(width, width is not None),
            AvailableSize(height, height is not None),
        ),
        tuple(LayoutNode(name, parent, component, tuple(styles.items()))
              for name, parent, component, styles in nodes),
        (),
    )


@pytest.mark.parametrize("seed", (81, 98))
@pytest.mark.parametrize("component,explicit_replaced", (
    ("Image", None), ("Box", True),
))
def test_deferred_replaced_ratio_without_intrinsic_metrics_fails_closed(
    seed, component, explicit_replaced, rust_binary,
):
    root_id, child_id = f"root_{seed}", f"media_{seed}"
    media_style = {"aspect_ratio": 2.0, "width": "auto", "height": "auto"}
    if explicit_replaced is not None:
        media_style["replaced"] = explicit_replaced
    snapshot = _request(seed, (
        (root_id, None, "Flex", {
            "width": "150px", "height": "auto", "align_items": "flex-start",
        }),
        (child_id, root_id, component, media_style),
    ))
    for backend, outcome in (
        ("python", _python_compute(snapshot)),
        ("rust", _rust_compute(rust_binary, snapshot)),
    ):
        assert not outcome["ok"], (backend, seed, outcome)
        assert outcome["error"]["code"] == "SFLE_UNSUPPORTED_FEATURE", (backend, outcome)
        assert outcome["error"]["node_id"] == child_id, (backend, outcome)


@pytest.mark.parametrize("direction,wrap", (
    ("row", "wrap"), ("row-reverse", "wrap-reverse"),
    ("column", "wrap"), ("column-reverse", "wrap-reverse"),
))
def test_deferred_intrinsically_auto_sized_wrap_without_definite_main_axis_fails_closed(
    direction, wrap, rust_binary,
):
    nodes = [
        ("root", None, "Flex", {
            "direction": direction, "wrap": wrap,
            "width": "auto", "height": "auto",
            "align_items": "flex-start",
        }),
        ("a", "root", "Box", {
            "width": "30px", "height": "18px", "flex_basis": "30px",
            "min_width": "0px", "flex_shrink": 0,
        }),
        ("b", "root", "Box", {
            "width": "30px", "height": "18px", "flex_basis": "30px",
            "min_width": "0px", "flex_shrink": 0,
        }),
    ]
    snapshot = _request(611, nodes)
    for backend, outcome in (
        ("python", _python_compute(snapshot)),
        ("rust", _rust_compute(rust_binary, snapshot)),
    ):
        assert not outcome["ok"], (backend, direction, wrap, outcome)
        assert outcome["error"]["code"] == "SFLE_UNSUPPORTED_FEATURE", (backend, outcome)
        assert outcome["error"]["node_id"] == "root", (backend, outcome)


@pytest.mark.parametrize("mode", ("definite-ratio", "fixed-wrap"))
def test_deferred_features_do_not_reject_previously_supported_subsets(
    mode, rust_binary,
):
    if mode == "definite-ratio":
        nodes = (
            ("root", None, "Flex", {
                "width": "200px", "height": "80px", "align_items": "flex-start",
            }),
            ("image", "root", "Image", {
                "width": "40px", "height": "auto", "aspect_ratio": 2.0,
                "flex_basis": "40px", "min_width": "0px",
            }),
        )
    else:
        nodes = (
            ("root", None, "Flex", {
                "width": "80px", "height": "90px", "wrap": "wrap",
                "align_items": "flex-start",
            }),
            ("a", "root", "Box", {"width": "50px", "height": "20px",
                                   "flex_basis": "50px", "min_width": "0px"}),
            ("b", "root", "Box", {"width": "50px", "height": "20px",
                                   "flex_basis": "50px", "min_width": "0px"}),
        )
    snapshot = _request(910, nodes)
    python, rust = _python_compute(snapshot), _rust_compute(rust_binary, snapshot)
    assert python["ok"] and rust["ok"], (mode, python.get("error"), rust.get("error"))
    assert _rects(python["result"]) == _rects(rust["result"]), mode


def test_certified_intrinsic_auto_wrap_with_definite_max_width_remains_supported(
    rust_binary,
):
    # The pre-existing recursive sizing fixture proves that a definite max
    # constraint can bound wrapped lines despite width:auto.
    from pathlib import Path
    import json

    fixtures = json.loads((
        Path(__file__).resolve().parents[1] /
        "sfle" / "fixtures" / "f2_recursive_sizing.json"
    ).read_text())
    case = next(c for c in fixtures if c["id"] == "auto-parent-max-width-wrap")
    from test_recursive_sizing_regression import make_snapshot
    snapshot = make_snapshot(case)
    python, rust = _python_compute(snapshot), _rust_compute(rust_binary, snapshot)
    assert python["ok"] and rust["ok"], (python.get("error"), rust.get("error"))
    assert _rects(python["result"]) == _rects(rust["result"])
