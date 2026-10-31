//! Rust/Python parity: projected HTML block width fills its column flex parent.
use sfle_core::compute::{compute, LayoutInput};
use serde_json::{json, Value};

fn snapshot(viewport: u32, fixed: bool) -> LayoutInput {
    let mut paragraph = json!({"direction": "column", "layout_width":"100%"});
    if fixed {
        paragraph["layout_width"] = json!(350);
    }
    let indefinite = json!({
        "width": {"value":null,"definite":false},
        "height": {"value":null,"definite":false},
    });
    let input: Value = json!({
        "schema_version": 1,
        "generation": 1,
        "direction": "ltr",
        "constraints": {
            "width": {"value":viewport,"definite":true},
            "height": {"value":600,"definite":true},
        },
        "nodes": [
            {"node_id":"root","parent_id":null,"component":"Flex",
             "style":{"direction":"column","align_items":"center","row_gap":16}},
            {"node_id":"paragraph","parent_id":"root","component":"Flex",
             "style":paragraph},
            {"node_id":"text","parent_id":"paragraph","component":"Text","style":{}}
        ],
        "measurements": [{
            "node_id":"text",
            "intrinsic": {
                "min_content_width":75,
                "max_content_width":302,
                "preferred_width":302,
                "min_content_height":18,
                "max_content_height":18,
                "preferred_height":18,
                "baseline":null
            },
            "constraints":indefinite,
            "revision":1
        }]
    });
    serde_json::from_value(input).expect("valid immutable Cinnamon snapshot")
}

#[test]
fn html_block_fills_column_container_width() {
    for (viewport, expected) in [(800,800.0),(140,140.0),(60,60.0)] {
        let result = compute(&snapshot(viewport,false)).expect("Rust should solve auto-width flex");
        let paragraph = result.boxes.iter().find(|b| b.node_id=="paragraph").unwrap();
        let text = result.boxes.iter().find(|b| b.node_id=="text").unwrap();
        assert!((paragraph.content.width-expected).abs() <= 1.0/64.0,
                "viewport={viewport} paragraph={:?}", paragraph.content);
        assert!((text.content.width-expected).abs() <= 1.0/64.0,
                "viewport={viewport} text={:?}", text.content);
    }
}

#[test]
fn centered_block_preserves_explicit_width_overflow() {
    let result = compute(&snapshot(140,true)).expect("explicit width");
    let paragraph = result.boxes.iter().find(|b| b.node_id=="paragraph").unwrap();
    assert_eq!(paragraph.content.width,350.0);
}
