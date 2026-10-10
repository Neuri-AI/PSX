use serde_json::Value;
use sfle_core::compute::{AvailableSize, LayoutConstraints, LayoutInput, LayoutNode, MeasuredBox, IntrinsicSizes};
use std::path::PathBuf;

pub fn fixture(id: &str) -> (Value, LayoutInput) {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../tests/sfle/fixtures/f2_alpha_acceptance.json");
    let data: Value = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
    let case = data["cases"].as_array().unwrap().iter()
        .find(|c| c["id"] == id).unwrap().clone();
    let axis = |value: &Value| AvailableSize {
        value: value.as_f64(), definite: value.as_f64().is_some(),
    };
    let nodes = case["nodes"].as_array().unwrap().iter().map(|n| LayoutNode {
        node_id: n["node_id"].as_str().unwrap().to_string(),
        parent_id: n["parent_id"].as_str().map(str::to_owned),
        component: n["component"].as_str().unwrap().to_string(),
        style: n["style"].as_object().unwrap().clone(),
    }).collect();
    let constraints = LayoutConstraints {
        width: axis(&case["viewport"]["width"]),
        height: axis(&case["viewport"]["height"]),
    };
    let measurements = case["measurements"].as_array().unwrap().iter().map(|m| {
        let intrinsic = IntrinsicSizes {
            min_content_width: 20.0,
            max_content_width: m["at_width"].as_f64().unwrap_or(100.0),
            min_content_height: 20.0,
            max_content_height: m["height"].as_f64().unwrap_or(60.0),
            preferred_width: m["at_width"].as_f64().unwrap_or(100.0),
            preferred_height: m["height"].as_f64().unwrap_or(60.0),
            baseline: None,
        };
        MeasuredBox {
            node_id: m["node"].as_str().unwrap().to_string(),
            intrinsic, constraints: LayoutConstraints {
                width: axis(&m["at_width"]), height: axis(&m["height"]),
            }, revision: 0,
        }
    }).collect();
    let snapshot = LayoutInput {
        schema_version: 1, generation: 17,
        direction: case["writing_direction"].as_str().unwrap().to_string(),
        constraints, nodes, measurements,
    };
    (case,snapshot)
}
